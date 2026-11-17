#!/usr/bin/env python3
"""Bir uzman ajanı (senarist, redaktör, ses-yonetmeni...) SEÇİLİ ÇALIŞMA ORTAMINDA (Codex, Gemini CLI, OpenCode ya da Claude) çalıştırır.

Orkestratör (varsayılan Claude Code) bir rolü başka bir aboneliğe devretmek istediğinde Agent aracı yerine bunu kullanır; hangi ajanın hangi ortamda
çalışacağı panelde Ayarlar → Ajanlar tablosundaki "Çalışma ortamı" sütunundan seçilir (ayar: ajanlar.<ad>.calisma_ortami).
API anahtarı gerekmez: her ortam kendi abonelikli CLI'ıdır (giriş yapılmış olmalı).

  python sistem/araclar/ajan_cagir.py <ajan> <gorev.md> [--proje <ad>] [--salt-okunur] [--zaman 900] [--ortam codex]
  python sistem/araclar/ajan_cagir.py ortamlar            hangi CLI kurulu
  python sistem/araclar/ajan_cagir.py plan <ajan> [proje]  hangi ortamda çalışacağını söyler (çalıştırmaz)

<gorev.md>: orkestratörün yazdığı görev (girdi dosyaları, beklenen çıktı dosyası). Ajanın rol tanımı (.claude/agents/<ajan>.md) başına eklenir.
Görev ve rol sabit bir dosyaya yazılır, CLI'a yalnızca "şu dosyayı oku ve uygula" denir (komut satırına serbest metin girmez). Çıkış: ajanın son mesajı.
Yalnızca standart kütüphane.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
NW = 0x08000000 if os.name == "nt" else 0
AJAN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
PROJE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
GOREV_DIZIN = SISTEM / "ortam" / "yerel" / "ajan_gorevleri"
GUNLUK = SISTEM / "ortam" / "yerel" / "ajan_gunlugu.jsonl"
KATALOG = SISTEM / "baglayici" / "calisma_ortamlari.json"
EN_COK_GOREV = 60_000  # karakter


def ayar_m():
    import importlib.util
    sp = importlib.util.spec_from_file_location("yst_ayar_ac", SISTEM / "ayar" / "ayar.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def ortamlar() -> dict:
    d = json.loads(KATALOG.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


_KURULU: dict = {}


def _kurulu_mu(komut: str) -> bool:
    """PATH taraması Windows'ta komut başına ~20 ms; pano her 4 sn'de soruyordu. 30 sn önbellek (yeni kurulan CLI yarım dakikada görünür)."""
    e = _KURULU.get(komut)
    if e and time.time() - e[0] < 30:
        return e[1]
    if komut in ("ollama", "lmstudio", "llamacpp"):
        try:
            import orkestrator
            v = bool(orkestrator.models(komut))
        except (OSError, ValueError):
            v = False
        _KURULU[komut] = (time.time(), v)
        return v
    e = _KURULU.get(komut)
    if e and time.time() - e[0] < 30:
        return e[1]
    v = bool(shutil.which(komut))
    _KURULU[komut] = (time.time(), v)
    return v


def ortam_listesi() -> list[dict]:
    return [{"id": k, "ad": v["ad"], "komut": v["komut"], "kurulu": _kurulu_mu(v["komut"]), "durum": v.get("durum", "")} for k, v in ortamlar().items()]


def hangi_ortam(ajan: str, proje: str | None = None) -> str:
    return ayar_m().ajan(ajan, proje)["etkin_ortam"]


def rol_metni(ajan: str) -> str:
    p = ROOT / ".claude" / "agents" / f"{ajan}.md"
    if not p.is_file():
        raise ValueError(f"ajan tanımı yok: {ajan}")
    s = p.read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", s.replace("\r\n", "\n"), count=1, flags=re.S).strip()


def komut_kur(ortam: str, istem: str, salt_okunur: bool, cikti_dosyasi: Path, model: str = "") -> list[str]:
    """Ortama göre başsız (etkileşimsiz) çalıştırma komutu. Serbest kullanıcı metni içermez: istem sabit bir cümledir."""
    exe = shutil.which(ortamlar()[ortam]["komut"])
    if not exe:
        raise RuntimeError(f"{ortamlar()[ortam]['ad']} kurulu değil ({ortamlar()[ortam]['komut']} komutu yok)")
    m = ["-m", model] if model else []
    if ortam == "codex":
        return [exe, "exec", *m, "-s", "read-only" if salt_okunur else "workspace-write", "--skip-git-repo-check", "-C", str(ROOT), "-o", str(cikti_dosyasi), istem]
    if ortam == "claude-code":
        return [exe, "-p", istem, *(["--model", model] if model else []), "--permission-mode", "default" if salt_okunur else "acceptEdits"]
    if ortam == "gemini-cli":  # belge: gemini -p "<istem>" (etkileşimsiz); yazma izni için auto_edit onayı
        return [exe, *m, "-p", istem] + ([] if salt_okunur else ["--approval-mode", "auto_edit"])
    if ortam == "opencode":  # belge: opencode run "<istem>"
        return [exe, "run", *m, istem]
    raise RuntimeError(f"bilinmeyen ortam: {ortam}")


def calistir(ajan: str, gorev_yolu: str, proje: str | None = None, salt_okunur: bool = False, zaman: int = 900, ortam: str | None = None) -> dict:
    if not AJAN_RE.match(ajan or ""):
        raise ValueError("geçersiz ajan adı")
    if proje and not PROJE_RE.match(proje):
        raise ValueError("geçersiz proje adı")
    g = Path(gorev_yolu)
    g = g if g.is_absolute() else ROOT / g
    g = g.resolve()
    if ROOT.resolve() not in g.parents or not g.is_file():
        raise ValueError("görev dosyası stüdyo klasörü içinde olmalı")
    gorev = g.read_text(encoding="utf-8")
    if len(gorev) > EN_COK_GOREV:
        raise ValueError(f"görev {EN_COK_GOREV} karakteri aşıyor")
    ortam = ortam or hangi_ortam(ajan, proje)
    if ortam not in ortamlar():
        raise ValueError(f"bilinmeyen çalışma ortamı: {ortam}")
    GOREV_DIZIN.mkdir(parents=True, exist_ok=True)
    kimlik = f"{ajan}-{int(time.time())}"
    istem_dosyasi = GOREV_DIZIN / f"{kimlik}.md"
    istem_dosyasi.write_text(
        f"# Rol: {ajan}\n\nÖnce `.claude/CLAUDE.md` dosyasını oku. Bu rolün tanımı aşağıdadır; model/araç sınırları ortamına göre senin için geçerli olanlardır.\n\n{rol_metni(ajan)}\n\n"
        f"---\n# Görev\n\n{gorev}\n\n---\nBitirince ne yaptığını ve yazdığın dosyaları kısaca özetle. "
        + ("Bu çağrı SALT OKUNURDUR: dosya yazma, yalnızca yanıt ver." if salt_okunur else "Çıktıyı görevde istenen dosyaya yaz.") + "\n", encoding="utf-8")
    rel = istem_dosyasi.relative_to(ROOT).as_posix()
    istem = f"{rel} dosyasını oku ve içindeki rolü ve görevi eksiksiz uygula."
    cikti = GOREV_DIZIN / f"{kimlik}.cikti.txt"
    model = ""
    try:
        ay = ayar_m()
        ma = ay.ajan(ajan, proje).get("model") or ""
        model = ma if (ma and ay.model_gecerli(ortam, ma) and (ortam != "claude-code" or ma != "inherit")) else ""
    except (KeyError, ValueError):
        model = ""
    t0 = time.time()
    if ortam in ('ollama', 'lmstudio', 'llamacpp'):
        # Called as an approved tool by the parent agent. Keep subordinate tools scoped:
        # generated project files only; execution/delegation remains the parent's job.
        import contextlib
        import io
        import types
        import orkestrator
        cfg = {**ayar_m().coz(proje).get('orkestrator', {}), 'calisma_ortami': ortam}
        cfg['model'] = model or cfg.get('model')
        def approve(tool, args):
            if tool != 'write' or salt_okunur or not proje:
                return {'allow': False}
            orkestrator.safe_path(args['path'], True, proje)
            return {'allow': True}
        with contextlib.redirect_stdout(io.StringIO()):
            output = orkestrator.local({'proje': proje or '_profil', 'cfg': cfg, 'history': [{'rol':'user','metin':istem_dosyasi.read_text(encoding='utf-8')}]}, ajan, approval=approve)
        cikti.write_text(output, encoding='utf-8')
        r = types.SimpleNamespace(returncode=0, stdout=output, stderr='')
    else:
        komut = komut_kur(ortam, istem, salt_okunur, cikti, model)
        r = subprocess.run(komut, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, creationflags=NW, stdin=subprocess.DEVNULL,
                           env={**os.environ, "PYTHONUTF8": "1"})
    yanit = cikti.read_text(encoding="utf-8", errors="replace").strip() if cikti.is_file() else (r.stdout or "").strip()
    sonuc = {"ok": r.returncode == 0, "ajan": ajan, "ortam": ortam, "sn": round(time.time() - t0, 1), "kod": r.returncode, "yanit": yanit[-6000:],
             "hata": (r.stderr or "")[-600:] if r.returncode != 0 else "", "gorev_dosyasi": rel}
    GUNLUK.parent.mkdir(parents=True, exist_ok=True)
    with open(GUNLUK, "a", encoding="utf-8") as f:
        f.write(json.dumps({"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "proje": proje, **{k: sonuc[k] for k in ("ajan", "ortam", "ok", "sn", "kod")}}, ensure_ascii=False) + "\n")
    return sonuc


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if a[0] == "ortamlar":
        print(json.dumps(ortam_listesi(), ensure_ascii=False, indent=1))
        return 0
    if a[0] == "plan":
        print(hangi_ortam(a[1], a[2] if len(a) > 2 else None))
        return 0
    if len(a) < 2:
        print(__doc__)
        return 2
    kw = {"proje": None, "zaman": 900, "ortam": None}
    salt = "--salt-okunur" in a
    rest = [x for x in a[2:] if x != "--salt-okunur"]
    for i in range(0, len(rest) - 1, 2):
        k = rest[i].lstrip("-")
        if k in kw:
            kw[k] = int(rest[i + 1]) if k == "zaman" else rest[i + 1]
    try:
        r = calistir(a[0], a[1], kw["proje"], salt, kw["zaman"], kw["ortam"])
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1
    print(f"[{r['ortam']}] {r['ajan']} · {r['sn']} sn · {'tamam' if r['ok'] else 'HATA kod ' + str(r['kod'])}")
    print(r["yanit"] if r["ok"] else r["hata"])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
