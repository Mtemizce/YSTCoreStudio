#!/usr/bin/env python3
"""Yeni video projesi açar (ya da var olan projeye yeni bir çıktı biçimi ekler).

  python sistem/araclar/yeni_proje.py <kisa-ad> [--tarif "metin"] [--kaynak yol1 yol2 ...] [--format ana|reels|tiktok|shorts ...]

Klasör düzeni (hepsi `projeler/<ad>/` altında):
  kaynak/    senin dosyaların: foto/ video/ ses/ belge/ (DWG, PDF, Word, Excel). Orijinaller; kimse değiştirmez.
  hazir/     kaynaklardan türetilenler: envanter + kontak sayfası, belge çıktıları (DWG→PNG, Word→md, Excel→csv, PDF→png+md)
  ana/       Kurgu projesi, 16:9 ana film  (project.json, media/, remotion/, ses/, cikti/ = bu biçimin render'ı)
  reels/ tiktok/ shorts/   aynı yapıda 9:16 projeler (istenince açılır)
  cikti/     TESLİM: bitmiş videolar (ana.mp4, reels.mp4 …), kapaklar, paylasim_*.md   ← bakacağın yer burası
  brief.md   videonun yaratıcı özeti (prompt değerlendirmesiyle dolar)

Her biçim ayrı bir Kurgu projesidir (kendi project.json'u): Kurgu'da `projeler/<ad>/<format>` klasörünü aç.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

NW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: pythonw altında konsol alt süreçleri pencere açıp kapatmasın

HERE = os.path.dirname(os.path.abspath(__file__))
SISTEM = os.path.dirname(HERE)       # sistem/
ROOT = os.path.dirname(SISTEM)       # depo kökü
IMG = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic")
VID = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi")
SES = (".mp3", ".wav", ".m4a", ".flac", ".ogg")
BELGE = (".dwg", ".pdf", ".docx", ".xlsx", ".doc", ".xls", ".dxf", ".pptx")
BOYUT = {"ana": (1920, 1080, 45.0), "reels": (1080, 1920, 25.0), "tiktok": (1080, 1920, 25.0), "shorts": (1080, 1920, 30.0), "story": (1080, 1920, 15.0)}
KATEGORI = [(IMG, "foto"), (VID, "video"), (SES, "ses"), (BELGE, "belge")]


def slug(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = s.translate(tr).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "proje"


def kategori(f: str):
    e = os.path.splitext(f)[1].lower()
    for ekler, ad in KATEGORI:
        if e in ekler:
            return ad
    return None


def kaynak_kopyala(kaynaklar, hedef_kok):
    n = 0
    for src in kaynaklar:
        src = os.path.abspath(src)
        if os.path.isdir(src):
            dosyalar = [os.path.join(r, f) for r, _d, fs in os.walk(src) for f in sorted(fs)]
        elif os.path.isfile(src):
            dosyalar = [src]
        else:
            print("uyarı: bulunamadı:", src)
            continue
        for f in dosyalar:
            k = kategori(f)
            if not k:
                continue
            d = os.path.join(hedef_kok, "kaynak", k)
            os.makedirs(d, exist_ok=True)
            hedef = os.path.join(d, os.path.basename(f))
            if not os.path.exists(hedef):
                shutil.copy2(f, hedef)
            n += 1
    return n


def hazirla(dest):
    """kaynak/ → hazir/: envanter (foto/video) ve belge çıktıları."""
    py = sys.executable
    kaynak = os.path.join(dest, "kaynak")
    hazir = os.path.join(dest, "hazir")
    os.makedirs(hazir, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1")
    medya = [k for k in ("foto", "video") if os.path.isdir(os.path.join(kaynak, k))]
    if medya:
        subprocess.run([py, os.path.join(HERE, "medya_envanteri.py"), kaynak, "-o", hazir], env=env, creationflags=NW)
    belge = os.path.join(kaynak, "belge")
    if os.path.isdir(belge) and os.listdir(belge):
        subprocess.run([py, os.path.join(HERE, "belge_al.py"), belge, "-o", os.path.join(hazir, "belge")], env=env, creationflags=NW)


def format_ac(dest, ad, fmt):
    sub = os.path.join(dest, fmt)
    if os.path.exists(os.path.join(sub, "project.json")):
        return False
    w, h, sure = BOYUT[fmt]
    shutil.copytree(os.path.join(SISTEM, "sablon"), sub, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("brief.md"))
    for d in ("media/fonts", "media/foto", "media/foto_orijinal", "media/muzik", "media/sahne", "media/tts", "cikti"):
        os.makedirs(os.path.join(sub, d), exist_ok=True)
    fonts = os.path.join(SISTEM, "kit", "fonts")
    for f in os.listdir(fonts):
        shutil.copy(os.path.join(fonts, f), os.path.join(sub, "media", "fonts", f))
    # şablondaki göreli kit yolları bir kademe derine iner: projeler/<ad>/<format>/remotion/src → kök 5 üst, kit sistem/kit altında
    for rel in ("remotion/src/Ornek.tsx", "remotion/tsconfig.json", "remotion/package.json"):
        p = os.path.join(sub, rel)
        if os.path.isfile(p):
            t = open(p, encoding="utf-8").read()
            t = t.replace("'../../../../kit/src'", "'../../../../../sistem/kit/src'").replace('"../../../kit/src"', '"../../../../sistem/kit/src"')
            t = t.replace("node_modules", "kök node_modules").replace("kit/src", "kit/src")
            open(p, "w", encoding="utf-8").write(t)
    proj = {"version": 2, "name": f"{ad}-{fmt}", "width": w, "height": h, "fps": 30, "duration": sure, "background": "#0e1013",
            "output": f"cikti/{fmt}.mp4", "global": {"grain": 0, "vignette": 0, "loudness_lufs": -14, "fade_out": 1.5},
            "layers": [], "notes": []}
    json.dump(proj, open(os.path.join(sub, "project.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return True


SIHIRBAZ_BASLIK = {
    "seslendirme": "Seslendirme", "muzik": "Müzik", "muzik_his": "Müzik havası", "altyazi": "Altyazı", "ton": "Ton", "sure": "Süre",
    "hitap": "Hitap", "cagri": "Çağrı (video sonu)", "iletisim_goster": "İletişim bilgisi videoda görünsün mü", "platformlar": "Platformlar",
    "mutlaka": "Mutlaka olsun", "asla": "Kesinlikle olmasın", "notlar": "Söylemek istediği başka şeyler", "arsiv_ozet": "Arşivden seçim",
    "gorsel_uret": "Görsel/karakter üretimi", "gorsel_tarif": "Karakter/görsel tarifi (kullanıcının sözleri, değiştirme)", "marka_ozet": "Marka kiti",
    "arsivden_bul": "Kaynakları arşivden bul", "bulut_izni": "Bulut (ücretli servis) izni",
}


def sihirbaz_yaz(brief_yolu, cevap, dest):
    """Sihirbaz cevaplarını brief.md'ye KULLANICI BEYANI olarak ekle (yeniden sorulmaz; çelişki varsa yönetmen sorar)."""
    satir = ["", "## Sihirbaz cevapları (kullanıcı beyanı: tekrar sorma, uygula; çelişki varsa sor)"]
    for k, baslik in SIHIRBAZ_BASLIK.items():
        if cevap.get(k):
            satir.append(f"- **{baslik}:** {cevap[k]}")
    with open(brief_yolu, "a", encoding="utf-8") as f:
        f.write("\n".join(satir) + "\n")
    json.dump(cevap, open(os.path.join(dest, "sihirbaz.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ad")
    ap.add_argument("--tarif", default="")
    ap.add_argument("--kaynak", nargs="*", default=[])
    ap.add_argument("--format", nargs="*", default=["ana"], choices=list(BOYUT))
    ap.add_argument("--hazirla", action="store_true", help="yalnızca var olan projenin kaynak/ klasöründen hazir/ çıktısını yeniden üret")
    ap.add_argument("--sihirbaz", help="panel sihirbazı cevapları (JSON dosyası): brief.md'ye 'Sihirbaz cevapları' bölümü olarak yazılır")
    a = ap.parse_args()
    ad = slug(a.ad)
    dest = os.path.join(ROOT, "projeler", ad)
    if a.hazirla:
        if not os.path.isdir(os.path.join(dest, "kaynak")):
            sys.exit(f"proje yok: {dest}")
        hazirla(dest)
        print("hazır: kaynaklardan envanter ve belge çıktıları üretildi (hazir/)")
        return
    yeni = not os.path.isdir(dest)
    os.makedirs(os.path.join(dest, "kaynak"), exist_ok=True)
    os.makedirs(os.path.join(dest, "cikti"), exist_ok=True)
    brief = os.path.join(dest, "brief.md")
    if not os.path.exists(brief):
        t = open(os.path.join(SISTEM, "sablon", "brief.md"), encoding="utf-8").read().replace("<proje adı>", ad)
        if a.tarif:
            t = t.replace("- **İstek (kullanıcının sözleriyle):**", f"- **İstek (kullanıcının sözleriyle):** {a.tarif.strip()}")
        open(brief, "w", encoding="utf-8").write(t)
    if a.sihirbaz and os.path.isfile(a.sihirbaz):
        sihirbaz_yaz(brief, json.load(open(a.sihirbaz, encoding="utf-8")), dest)
    gunluk = os.path.join(dest, "calisma_gunlugu.md")
    if not os.path.exists(gunluk):
        open(gunluk, "w", encoding="utf-8").write(
            f"# Çalışma günlüğü: {ad}\n\n> Orkestratör her ajan devrini buraya ekler (yalnızca ekler). Biçim ve kurallar: `.claude/skills/video-yonetmen/orkestrasyon.md`\n\n"
            "| zaman | ajan (model) | görev | girdi | beklenen çıktı | gerçek çıktı | doğrulama (ne baktım) | karar | not |\n|---|---|---|---|---|---|---|---|---|\n")
    n = kaynak_kopyala(a.kaynak, dest)
    acilan = [f for f in a.format if format_ac(dest, ad, f)]
    print(f"proje: {dest}  ({'yeni' if yeni else 'var olana eklendi'})")
    print(f"{n} kaynak dosyası kaynak/ altına kopyalandı (orijinaller değişmedi). Açılan biçimler: {', '.join(acilan) or 'yok'}")
    if os.path.isdir(os.path.join(dest, "kaynak")) and os.listdir(os.path.join(dest, "kaynak")):
        hazirla(dest)
    print(f"Kurgu'da aç: Başlat.cmd → panel → '{ad}', ya da  kurgu projeler\\{ad}\\{a.format[0]}")


if __name__ == "__main__":
    main()
