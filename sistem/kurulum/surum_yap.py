#!/usr/bin/env python3
"""Sürüm paketi (portable zip) üretir ve istenirse GitHub Release olarak yayınlar. Kullanıcı depoyu KLONLAMAZ: zip'i indirir, bir klasöre açar, Başlat.cmd'yi çalıştırır.

  python sistem/kurulum/surum_yap.py                    zip + sha256 üretir (sistem/ortam/surum/ altına)
  python sistem/kurulum/surum_yap.py --yayinla          ayrıca `gh release create v<sürüm>` ile yayınlar (gh girişi gerekir)
  python sistem/kurulum/surum_yap.py --kirli            commit edilmemiş değişiklik olsa da üret (yalnızca deneme)

Sürüm numarası sistem/surum.json'dan gelir (tek kaynak). İçerik: git'te izlenen dosyalar. Zip'e GİRMEYENLER: projeler/, kimlik/ (kişisel; nötr şablonlar sistem/sablon/kimlik/ altındadır),
sistem/ayar/kullanici.json (sıfırlanır), sistem/ortam/ (kurulum ve kullanıcı verisi). Üretimden sonra zip kişisel veri
kalıntısı için taranır; bulunursa iptal edilir. Kullanıcı verisi paketle değil, Ayarlar → Profil dışa/içe aktar ile taşınır.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CIKTI = ROOT / "sistem" / "ortam" / "surum"
METIN_UZ = {".md", ".py", ".json", ".ts", ".tsx", ".js", ".mjs", ".cmd", ".ps1", ".html", ".txt", ".yml", ".yaml", ".css", ".sh"}
KENDISI = "sistem/kurulum/surum_yap.py"
# Kişisel kalıplar (ad, soyad, kullanıcı adı, e-posta…) DEPODA TUTULMAZ: bu bilgisayardaki sistem/ortam/yerel/kisisel_yasak.txt dosyasından okunur
# (satır başına bir düzenli ifade; git'e girmez). Dosya yoksa yalnızca genel desenler (anahtarlar, e-posta) taranır.
GENEL_YASAK = (r"@gmail\.com", r"sk-[A-Za-z0-9]{20,}", r"AIza[0-9A-Za-z_\-]{30,}", r"C:\\Users\\[A-Za-z0-9_.-]+\\", r"/Users/[a-z0-9_.-]+/Desktop")
KISISEL_DOSYA = ROOT / "sistem" / "ortam" / "yerel" / "kisisel_yasak.txt"


def yasak_desenler() -> list:
    ek = []
    try:
        ek = [x.strip() for x in KISISEL_DOSYA.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    except OSError:
        pass
    return [re.compile(p, re.I) for p in (*GENEL_YASAK, *ek)]


YASAK = yasak_desenler()


def calistir(*cmd) -> str:
    return subprocess.run(list(cmd), cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def dosya_icerigi(rel: str, veri: bytes) -> bytes | None:
    """None = pakete girme. Aksi halde (nötrlenmiş) bayt."""
    if (rel.startswith("projeler/") and rel != "projeler/.gitkeep") or rel.startswith("kimlik/") and rel != "kimlik/ornekler/.gitkeep":
        return None
    if rel == "sistem/ayar/kullanici.json":
        return b'{\r\n  "ajanlar": {}\r\n}\r\n'
    if Path(rel).suffix.lower() not in METIN_UZ or rel == KENDISI:
        return veri
    try:
        s = veri.decode("utf-8")
    except UnicodeDecodeError:
        return veri
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if crlf:
        s = s.replace("\n", "\r\n")
    return s.encode("utf-8")


def uret(kirli: bool = False) -> dict:
    bilgi = json.loads((ROOT / "sistem" / "surum.json").read_text(encoding="utf-8"))
    surum = bilgi["uygulama"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", surum):
        raise SystemExit(f"sürüm biçimi x.y.z olmalı: {surum}")
    if calistir("git", "status", "--porcelain").strip() and not kirli:
        raise SystemExit("commit edilmemiş değişiklik var: önce commit et (ya da deneme için --kirli)")
    dosyalar = [f for f in calistir("git", "-c", "core.quotepath=false", "ls-files").splitlines() if f]
    if kirli:  # review packages must include newly created, non-ignored source files too
        dosyalar = sorted(set(dosyalar + [f for f in calistir("git", "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard").splitlines() if f]))
    CIKTI.mkdir(parents=True, exist_ok=True)
    zip_yol = CIKTI / f"YSTCoreStudio-{surum}.zip"
    kok = f"YSTCoreStudio-{surum}"
    sayi = 0
    with zipfile.ZipFile(zip_yol, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in dosyalar:
            p = ROOT / rel
            if not p.is_file():
                continue
            veri = dosya_icerigi(rel, p.read_bytes())
            if veri is None:
                continue
            zi = zipfile.ZipInfo(f"{kok}/{rel}", date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o755 if rel.endswith((".sh", ".command")) else 0o644) << 16
            zf.writestr(zi, veri)
            sayi += 1
        for bos in ("projeler", "kimlik/ornekler"):  # boş klasörler
            if f"{bos}/.gitkeep" not in dosyalar:
                zf.writestr(f"{kok}/{bos}/.gitkeep", b"")
    # kişisel veri taraması
    sorun = []
    with zipfile.ZipFile(zip_yol) as zf:
        for ad in zf.namelist():
            if Path(ad).suffix.lower() not in METIN_UZ or ad.endswith(KENDISI):
                continue
            s = zf.read(ad).decode("utf-8", "replace")
            for r in YASAK:
                m = r.search(s)
                if m:
                    sorun.append(f"{ad}: '{m.group(0)}'")
    if sorun:
        zip_yol.unlink(missing_ok=True)
        raise SystemExit("pakette kişisel veri kalıntısı var, iptal edildi:\n  " + "\n  ".join(sorun[:15]))
    h = hashlib.sha256(zip_yol.read_bytes()).hexdigest()
    (CIKTI / f"YSTCoreStudio-{surum}.zip.sha256").write_text(f"{h}  {zip_yol.name}\n", encoding="utf-8")
    return {"surum": surum, "zip": str(zip_yol), "dosya": sayi, "boyut_mb": round(zip_yol.stat().st_size / 1e6, 2), "sha256": h}


def notlar(surum: str) -> str:
    """Sürüm sayfası açıklaması: kısa tanıtım (ayrıntılar README'dedir)."""
    return (f"**YSTCoreStudio {surum}**: bilgisayarında çalışan, Türkçe odaklı video stüdyosu (bir yapay zekâ orkestratörün kullandığı araç takımı). "
            "Tanıtım, kurulum, gereksinimler ve lisanslar için README'ye bak.")


def yayinla(r: dict) -> None:
    surum = r["surum"]
    not_dosya = CIKTI / f"notlar-{surum}.md"
    kurulum = ("\n\n## Kurulum\n1. `YSTCoreStudio-%s.zip` dosyasını indir ve bir klasöre çıkar (ör. `C:\\YST`; yol kısa olsun).\n"
               "2. İndirdiğin zip'e sağ tıkla → Özellikler → **Engellemeyi kaldır** (Windows indirilen dosyalara uyarı koyar), sonra çıkar.\n"
               "3. `Başlat.cmd`'yi çift tıkla. Eksik program varsa tarayıcıda sihirbaz söyler; kurulum süresi internet hızına bağlıdır; PyTorch, yapay zekâ paketleri ve modeller panel açıldıktan sonra arka planda iner (panel ilerlemeyi gösterir).\n"
               "4. Eski bilgisayarından taşımak istersen: panel → Ayarlar → *Profili dışa/içe aktar*.\n\n"
               "`sha256`: `%s`\n\n> Not: paket imzasızdır; Windows SmartScreen/antivirüs ilk açılışta uyarı verebilir (betik arka planda bir pencere açmadan çalışır ve internetten yalnızca "
               "belgelenmiş adreslere bağlanır). Şüphen varsa sha256'yı doğrula.") % (surum, r["sha256"])
    not_dosya.write_text(notlar(surum) + kurulum, encoding="utf-8")
    cmd = ["gh", "release", "create", f"v{surum}", r["zip"], str(CIKTI / f"YSTCoreStudio-{surum}.zip.sha256"), "--title", f"YSTCoreStudio {surum}",
           "--notes-file", str(not_dosya), "--target", "main"]
    if "-" in surum:
        cmd.append("--prerelease")
    out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit("gh release başarısız:\n" + (out.stderr or out.stdout))
    print("yayınlandı:", out.stdout.strip())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = uret("--kirli" in sys.argv)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if "--yayinla" in sys.argv:
        yayinla(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
