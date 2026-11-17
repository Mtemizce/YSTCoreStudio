#!/usr/bin/env python3
"""Seslendirme metnini düzenle ve yalnızca DEĞİŞEN satırların sesini yeniden üret (Kurgu bu metni katmanda tutmadığı için bu araç var).

  python sistem/araclar/ses_duzenle.py goster <proje> [--format ana]                    plan.json'daki satır ve parçaları listeler
  python sistem/araclar/ses_duzenle.py uygula <proje> --duzenleme degisiklik.json [--format ana]
      degisiklik.json: {"<satir_id>": ["parça 1 yeni metin", "parça 2 yeni metin", …]}  (parça sayısı aynı olmalı)

Ne yapar: plan.json'u günceller (özgün plan .yedek'e), yalnızca değişen satırları voice_studio ile üretir (aynı motor/ayar), yeni .wav dosyalarını
ses/ klasörüne yazar ve rapor.json'u birleştirir. Süre değiştiyse söyler: sahne süreleri/altyazı zamanları ses parça başlangıçlarına bağlıysa
yönetmen (orkestratör) bunları yeniden hizalamalı. Kurgu'da aç → sayfayı yenile; ses katmanı aynı dosya adını kullandığı için yeni ses gelir.
Ücretli motorda (ElevenLabs) yeniden üretim faturalanır ve bulut iznine tabidir (voice_studio aynı denetimleri yapar).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / ".claude" / "skills" / "kurgu-video-studio" / "scripts" / "voice_studio.py"
VENV_PY = ROOT / "sistem" / "ortam" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not VENV_PY.exists():  # kurulumsuz çalışma (geliştirme/CI): çalıştıran yorumlayıcı
    VENV_PY = Path(sys.executable)


def plan_yolu(proje: str, fmt: str) -> Path:
    p = ROOT / "projeler" / proje / fmt / "ses" / "plan.json"
    if not p.is_file():
        raise ValueError(f"{p.relative_to(ROOT)} yok: seslendirme planı henüz üretilmemiş")
    return p


def goster(proje: str, fmt: str = "ana") -> list[dict]:
    plan = json.loads(plan_yolu(proje, fmt).read_text(encoding="utf-8"))
    return [{"id": s["id"], "parcalar": [x["metin"] for x in s["parcalar"]]} for s in plan["satirlar"]]


def uygula(proje: str, degisiklik: dict, fmt: str = "ana") -> dict:
    p = plan_yolu(proje, fmt)
    ses_dir = p.parent
    plan = json.loads(p.read_text(encoding="utf-8"))
    yeni = copy.deepcopy(plan)
    degisen = []
    for s in yeni["satirlar"]:
        if s["id"] not in degisiklik:
            continue
        metinler = degisiklik[s["id"]]
        if len(metinler) != len(s["parcalar"]):
            raise ValueError(f"'{s['id']}' satırında {len(s['parcalar'])} parça var, {len(metinler)} metin geldi (parça sayısı aynı olmalı)")
        if any(not str(m).strip() or len(str(m)) > 600 for m in metinler):
            raise ValueError("her parça 1-600 karakter olmalı")
        if [str(m).strip() for m in metinler] != [x["metin"] for x in s["parcalar"]]:
            for x, m in zip(s["parcalar"], metinler):
                x["metin"] = str(m).strip()
            degisen.append(s["id"])
    if not degisen:
        return {"degisen": [], "mesaj": "metinde değişiklik yok"}
    eski_rapor = json.loads((ses_dir / "rapor.json").read_text(encoding="utf-8")) if (ses_dir / "rapor.json").is_file() else {}
    sure_once = {i: (eski_rapor.get(i) or [{}])[-1].get("fx", (eski_rapor.get(i) or [{}])[-1]).get("sure") for i in degisen}
    gecici_plan = {**yeni, "satirlar": [s for s in yeni["satirlar"] if s["id"] in degisen]}
    tmp = Path(tempfile.mkdtemp(prefix="ses-duzenle-"))
    try:
        (tmp / "plan.json").write_text(json.dumps(gecici_plan, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([str(VENV_PY), str(VOICE), str(tmp / "plan.json"), "-o", str(tmp / "cikti"), "--takes", "1", "--aday", "5"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env={**__import__("os").environ, "PYTHONUTF8": "1"})
        if r.returncode != 0:
            raise RuntimeError("ses üretimi başarısız: " + (r.stderr or r.stdout).strip()[-300:])
        yeni_rapor = json.loads((tmp / "cikti" / "rapor.json").read_text(encoding="utf-8"))
        shutil.copy2(p, p.with_suffix(".json.yedek"))
        for i in degisen:
            for ek in ("", "_fx"):
                src = tmp / "cikti" / f"{i}_take1{ek}.wav"
                if src.is_file():
                    shutil.copy2(src, ses_dir / f"{i}_take1{ek}.wav")
            eski_rapor[i] = yeni_rapor[i]
        (ses_dir / "rapor.json").write_text(json.dumps(eski_rapor, ensure_ascii=False, indent=2), encoding="utf-8")
        p.write_text(json.dumps(yeni, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sure_sonra = {i: (eski_rapor[i][-1].get("fx") or eski_rapor[i][-1]).get("sure") for i in degisen}
    fark = {i: round((sure_sonra[i] or 0) - (sure_once[i] or 0), 2) for i in degisen}
    uyari = [f"'{i}' süresi {fark[i]:+.2f} sn değişti: sahne süreleri/altyazı zamanları bu satıra bağlıysa yeniden hizalanmalı" for i in degisen if abs(fark[i]) > 0.15]
    return {"degisen": degisen, "sure_farki_sn": fark, "uyari": uyari, "mesaj": "ses yeniden üretildi; Kurgu'da sayfayı yenile"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("goster", "uygula"):
        print(__doc__)
        return 2
    fmt = a[a.index("--format") + 1] if "--format" in a else "ana"
    try:
        if a[0] == "goster":
            print(json.dumps(goster(a[1], fmt), ensure_ascii=False, indent=1))
        else:
            d = json.loads(Path(a[a.index("--duzenleme") + 1]).read_text(encoding="utf-8"))
            print(json.dumps(uygula(a[1], d, fmt), ensure_ascii=False, indent=1))
    except (ValueError, RuntimeError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
