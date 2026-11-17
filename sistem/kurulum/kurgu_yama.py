#!/usr/bin/env python3
"""Kurgu'ya YSTCore eklentisini uygular: Kurgu kendi deposundan (sabit commit) çekildikten SONRA çalışır.

  python sistem/kurulum/kurgu_yama.py [kurgu_klasoru] [--kontrol] [--kuru]

Ne yapar:
  1. `sistem/yama/kurgu_ek/` altındaki YENİ dosyaları Kurgu'ya kopyalar (yst_ek.py sunucu eklentisi, web/js/yst.js, web/yst.css).
  2. Kurgu'nun MEVCUT dosyalarına yalnızca birkaç bağlantı satırı ekler (aşağıdaki EKLER): server.py'ye import + `/api/yst/` yönlendirmesi,
     web/index.html'e betik ve stil bağlantısı, pyproject.toml'a modül adı. Her ek sabit bir çapaya bağlanır; çapa dosyada tam bir kez
     bulunmalıdır, yoksa HİÇBİR dosyaya dokunulmadan anlaşılır bir hatayla durur (Kurgu'nun sabitlenmiş sürümü değiştiyse bu bir uyarıdır).
  3. Idempotent: ek zaten uygulanmışsa atlanır; yeni dosyalar her çalışmada güncellenir. Kurgu yeniden çekilirse yeniden uygulanır.

--kontrol yalnızca durumu söyler (uygulanmış mı), --kuru hiçbir şey yazmadan ne yapacağını söyler. Yalnızca Python standart kütüphanesi gerekir.

YAMA KURGU'YU ASLA ENGELLEMEZ:
  - Çapa tutmazsa (Kurgu'nun sürümü köklü değiştiyse) hiçbir dosyaya dokunulmaz; Kurgu kendi düz haliyle çalışır, panel kullanıcıya "bu özellikler Kurgu'da
    yok, panelden kullan" bilgisini gösterir (panel.py → kurgu_ac). Kurulum ve Onar bu durumda hata vermez, uyarı yazar (`otomatik()` asla istisna fırlatmaz).
  - Yama uygulanmış olsa bile eklenti içeriden korunur: server.py'deki import try/except içindedir, /api/yst/ rotası yalnızca eklenti yüklüyse vardır,
    yst.js ayrı bir modüldür (bozulursa Kurgu'nun kendi arayüzü etkilenmez).
  - --kaldir yamayı tamamen geri alır (Kurgu'nun düz hali) ve yeniden uygulanmasın diye bir işaret bırakır; --ac işareti kaldırıp yeniden uygular.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SISTEM = Path(__file__).resolve().parents[1]
KAYNAK = SISTEM / "yama" / "kurgu_ek"
KAPALI = SISTEM / "ortam" / "yerel" / "kurgu_eklenti.kapali"   # varsa kurulum/onar/panel yamayı uygulamaz (kullanıcı düz Kurgu istedi)
ISARET = "YST-EK"

# Her ek: dosya, ad, ve şunlardan biri: sonra (çapadan SONRA ekle) / once (çapadan ÖNCE ekle) / degistir (eski → yeni).
# `capa`: dosyada TAM BİR KEZ geçen metin. `metin`: eklenen satırlar (ISARET içerir: yeniden uygulamada tanınır).
EKLER = [
    {"dosya": "server.py", "ad": "sunucu-import", "sonra": "import agent_notes\n",
     "metin": (f"sys.path[:0] = [p for p in [os.path.dirname(os.path.abspath(__file__))] if p not in sys.path]  # {ISARET}: eklenti bu klasörde; editable kurulumun modül listesine bağlı kalma\n"
               f"try:  # {ISARET}: eklenti bozulsa da Kurgu açılır\n    import yst_ek  # {ISARET}\nexcept Exception:  # {ISARET}\n    yst_ek = None  # {ISARET}\n")},
    {"dosya": "server.py", "ad": "sunucu-rota", "once": '        else:\n            raise HttpError(404, "not found")\n        raise HttpError(405, "method not allowed")',
     "metin": f'        elif yst_ek is not None and path.startswith("/api/yst/"):  # {ISARET}\n            return yst_ek.api(self, method, path, q)  # {ISARET}\n'},
    {"dosya": "web/index.html", "ad": "arayuz-stil", "once": "</head>", "metin": f'<link rel="stylesheet" href="/web/yst.css"><!-- {ISARET} -->\n'},
    {"dosya": "web/index.html", "ad": "arayuz-betik", "once": "</body>", "metin": f'<script type="module" src="/web/js/yst.js"></script><!-- {ISARET} -->\n'},
    {"dosya": "pyproject.toml", "ad": "paket-modul", "degistir": ('"guidance_gen"]', '"guidance_gen", "yst_ek"]'), "isaret": '"yst_ek"'},
]


class YamaHatasi(Exception):
    pass


def _oku(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


def _yaz(p: Path, s: str, crlf: bool) -> None:
    p.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


def _durum(s: str, ek: dict) -> str:
    """'uygulanmis' | 'uygulanabilir' | 'capa-yok' | 'capa-belirsiz'"""
    if ek.get("isaret", ISARET) in s:
        return "uygulanmis"
    capa = ek.get("sonra") or ek.get("once") or ek["degistir"][0]
    n = s.count(capa)
    return "uygulanabilir" if n == 1 else ("capa-yok" if n == 0 else "capa-belirsiz")


def _uygula_metin(s: str, ek: dict) -> str:
    if "sonra" in ek:
        i = s.index(ek["sonra"]) + len(ek["sonra"])
        return s[:i] + ek["metin"] + s[i:]
    if "once" in ek:
        i = s.index(ek["once"])
        return s[:i] + ek["metin"] + s[i:]
    return s.replace(ek["degistir"][0], ek["degistir"][1], 1)


def kontrol(kurgu: Path) -> dict:
    """Her ekin durumu ve yeni dosyaların varlığı. {'tamam': bool, 'ekler': {ad: durum}, 'dosyalar': {yol: var mı}}"""
    kurgu = Path(kurgu)
    out = {"ekler": {}, "dosyalar": {}}
    for ek in EKLER:
        p = kurgu / ek["dosya"]
        out["ekler"][ek["ad"]] = _durum(_oku(p).replace("\r\n", "\n"), ek) if p.is_file() else "dosya-yok"
    for f in sorted(KAYNAK.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            out["dosyalar"][f.relative_to(KAYNAK).as_posix()] = (kurgu / f.relative_to(KAYNAK)).is_file()
    out["tamam"] = all(v == "uygulanmis" for v in out["ekler"].values()) and all(out["dosyalar"].values())
    return out


def uygula(kurgu: Path, kuru: bool = False) -> dict:
    """Eklentiyi uygular. Önce hepsini doğrular; bir çapa bulunamazsa YamaHatasi (hiçbir şey yazılmaz)."""
    kurgu = Path(kurgu)
    if not (kurgu / "server.py").is_file() or not (kurgu / "web" / "index.html").is_file():
        raise YamaHatasi(f"Kurgu klasörü değil: {kurgu}")
    if not KAYNAK.is_dir():
        raise YamaHatasi(f"yama kaynağı yok: {KAYNAK}")
    plan, sorun = {}, []
    for ek in EKLER:
        p = kurgu / ek["dosya"]
        if not p.is_file():
            sorun.append(f"{ek['dosya']}: dosya yok")
            continue
        ham = _oku(p)
        crlf = "\r\n" in ham
        s = ham.replace("\r\n", "\n")
        d = _durum(s, ek)
        if d in ("capa-yok", "capa-belirsiz"):
            sorun.append(f"{ek['dosya']} [{ek['ad']}]: çapa {'bulunamadı' if d == 'capa-yok' else 'birden çok yerde'} (Kurgu'nun sürümü değişmiş olabilir)")
        plan.setdefault(ek["dosya"], {"yol": p, "s": s, "crlf": crlf, "ekler": []})["ekler"].append((ek, d))
    if sorun:
        raise YamaHatasi("Kurgu yaması uygulanamadı, hiçbir dosyaya dokunulmadı:\n  - " + "\n  - ".join(sorun))
    sonuc = {"eklenen": [], "zaten": [], "kopyalanan": []}
    for dosya, bilgi in plan.items():
        s = bilgi["s"]
        degisti = False
        for ek, d in bilgi["ekler"]:
            if d == "uygulanmis":
                sonuc["zaten"].append(ek["ad"])
                continue
            s = _uygula_metin(s, ek)
            degisti = True
            sonuc["eklenen"].append(ek["ad"])
        if degisti and not kuru:
            _yaz(bilgi["yol"], s, bilgi["crlf"])
    for f in sorted(KAYNAK.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            hedef = kurgu / f.relative_to(KAYNAK)
            if not kuru:
                hedef.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, hedef)
            sonuc["kopyalanan"].append(f.relative_to(KAYNAK).as_posix())
    return sonuc


def geri_al(kurgu: Path) -> dict:
    """Yamayı geri alır: eklenen satırları ve eklenti dosyalarını siler (Kurgu'nun düz hali). Idempotent."""
    kurgu = Path(kurgu)
    sonuc = {"geri_alinan": [], "silinen": []}
    for dosya in sorted({e["dosya"] for e in EKLER}):
        p = kurgu / dosya
        if not p.is_file():
            continue
        ham = _oku(p)
        crlf = "\r\n" in ham
        s = ham.replace("\r\n", "\n")
        yeni = s
        for ek in EKLER:
            if ek["dosya"] != dosya:
                continue
            onceki = yeni
            if "degistir" in ek:
                yeni = yeni.replace(ek["degistir"][1], ek["degistir"][0], 1)
            elif ek["metin"] in yeni:
                yeni = yeni.replace(ek["metin"], "", 1)    # eklenen metni birebir çıkar (satır ortasına eklenmiş olsa da bozmaz)
            else:   # eklenti metni sonradan değişmiş eski bir uygulama: işaretli satırları sil
                yeni = "".join(satir for satir in yeni.splitlines(keepends=True) if ISARET not in satir)
            if yeni != onceki:
                sonuc["geri_alinan"].append(ek["ad"])
        if yeni != s:
            _yaz(p, yeni, crlf)
    for f in sorted(KAYNAK.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            hedef = kurgu / f.relative_to(KAYNAK)
            if hedef.is_file():
                hedef.unlink()
                sonuc["silinen"].append(f.relative_to(KAYNAK).as_posix())
    return sonuc


def otomatik(kurgu: Path) -> dict:
    """Kurulum, Onar ve panelin çağırdığı güvenli sarmalayıcı: HİÇBİR durumda istisna fırlatmaz.
    {'durum': 'tamam' | 'kapali' | 'uygulanamadi', 'neden': str, ...}  ('uygulanamadi' = Kurgu düz haliyle çalışır, özellikler panelden)"""
    if KAPALI.exists():
        return {"durum": "kapali", "neden": "eklenti kapatıldı (python sistem/kurulum/kurgu_yama.py --ac ile açılır)"}
    try:
        return {"durum": "tamam", "neden": "", **uygula(kurgu)}
    except YamaHatasi as e:
        return {"durum": "uygulanamadi", "neden": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"durum": "uygulanamadi", "neden": f"beklenmeyen hata: {e}"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--yardim" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    kurgu = Path(a[0]) if a else SISTEM.parent / "kurgu"
    try:
        if "--kaldir" in sys.argv:
            r = geri_al(kurgu)
            KAPALI.parent.mkdir(parents=True, exist_ok=True)
            KAPALI.write_text("Kurgu eklentisi kapatıldı; yeniden açmak için: python sistem/kurulum/kurgu_yama.py --ac\n", encoding="utf-8")
            print(f"Kurgu eklentisi kaldırıldı ({len(r['geri_alinan'])} ek geri alındı, {len(r['silinen'])} dosya silindi). Kurgu düz haliyle çalışır; kurulum ve Onar yeniden uygulamaz.")
            return 0
        if "--ac" in sys.argv:
            KAPALI.unlink(missing_ok=True)
        if "--kontrol" in sys.argv:
            k = kontrol(kurgu)
            for ad, d in k["ekler"].items():
                print(f"  {ad:18} {d}")
            for yol, var in k["dosyalar"].items():
                print(f"  {yol:22} {'var' if var else 'YOK'}")
            print("durum:", "tamam" if k["tamam"] else "eksik")
            return 0 if k["tamam"] else 1
        r = uygula(kurgu, "--kuru" in sys.argv)
        print(f"Kurgu eklentisi: {len(r['eklenen'])} ek uygulandı, {len(r['zaten'])} zaten vardı, {len(r['kopyalanan'])} dosya kopyalandı" + (" (kuru çalıştırma)" if "--kuru" in sys.argv else ""))
        return 0
    except YamaHatasi as e:
        print("HATA:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
