#!/usr/bin/env python3
"""README'deki "Katkıda bulunanlar" ve "Sponsorlar" bölümlerini günceller: her kişi yuvarlak bir profil resmi olarak görünür, üstüne gelince adı (title) çıkar.

  python sistem/araclar/topluluk_readme.py [--repo SAHIP/DEPO] [--haric kullanici,...] [--deneme]

- Katkıcılar: GitHub API (`gh api repos/<depo>/contributors`); depo sahibi ve botlar listelenmez.
- Sponsorlar: GitHub GraphQL; yalnızca herkese açık sponsorlar. `SPONSORS_TOKEN` (classic jeton, `read:user` ve `read:org`) ortam değişkeni yoksa bu bölüme dokunulmaz.
- Profil resimleri yuvarlatılıp `docs/topluluk/` altına yazılır (üçüncü taraf servis yok); README'de `<!-- katkicilar:basla -->` ... `<!-- katkicilar:bitis -->`
  ve `<!-- sponsorlar:basla -->` ... `<!-- sponsorlar:bitis -->` işaretleri arasındaki metin değişir.
- Dosyaları yalnızca düzenler; commit'i çağıran yapar (.github/workflows/topluluk.yml).
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
RESIM_DIZIN = ROOT / "docs" / "topluluk"
BOYUT = 120   # saklanan resim (px); README'de 60 px gösterilir (yüksek çözünürlüklü ekranlar için)
BOS = {"katkicilar": "Henüz kimse yok: ilk katkıyı sen yap! ([CONTRIBUTING.md](CONTRIBUTING.md))",
       "sponsorlar": "Henüz sponsor yok. Sponsor olursan profil resmin burada görünür ([GitHub Sponsors](https://github.com/sponsors/Mtemizce))."}
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def html_olustur(kisiler: list[dict], bos_metin: str) -> str:
    """kisiler: [{login, ad (isteğe bağlı), dosya (README'ye göre yol)}]. Boşsa bos_metin."""
    if not kisiler:
        return bos_metin
    out = []
    for k in kisiler:
        login = k["login"]
        ad = (k.get("ad") or "").strip()
        baslik = f"{ad} (@{login})" if ad and ad != login else f"@{login}"
        out.append(f'<a href="https://github.com/{html.escape(login, quote=True)}"><img src="{html.escape(k["dosya"], quote=True)}" width="60" height="60" '
                   f'alt="{html.escape(baslik, quote=True)}" title="{html.escape(baslik, quote=True)}"></a>')
    return "\n".join(out)


def bolum_degistir(metin: str, ad: str, yeni: str) -> str:
    bas, bit = f"<!-- {ad}:basla -->", f"<!-- {ad}:bitis -->"
    m = re.search(re.escape(bas) + r".*?" + re.escape(bit), metin, flags=re.S)
    if not m:
        raise ValueError(f"README'de {bas} ... {bit} işaretleri yok")
    return metin[:m.start()] + f"{bas}\n{yeni}\n{bit}" + metin[m.end():]


def yuvarlak(png_veya_jpg: bytes, boyut: int = BOYUT) -> bytes:
    """Kare profil resmini daire biçiminde kırpar (saydam köşeler), PNG döner."""
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(png_veya_jpg)).convert("RGBA").resize((boyut, boyut), Image.LANCZOS)
    ss = 4
    maske = Image.new("L", (boyut * ss, boyut * ss), 0)
    ImageDraw.Draw(maske).ellipse((0, 0, boyut * ss - 1, boyut * ss - 1), fill=255)
    im.putalpha(maske.resize((boyut, boyut), Image.LANCZOS))
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def _gh(args: list[str], token: str | None = None) -> str:
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout


def katkicilar(depo: str, haric: set[str]) -> list[dict]:
    veri = json.loads(_gh(["api", f"repos/{depo}/contributors?per_page=100"]) or "[]")
    return [{"login": k["login"], "ad": "", "avatar": k["avatar_url"]} for k in veri
            if k.get("type") == "User" and k["login"].lower() not in haric and LOGIN_RE.match(k["login"])]


SORGU = ("query($l:String!){user(login:$l){sponsorshipsAsMaintainer(first:100, activeOnly:true, includePrivate:false){nodes{sponsorEntity{"
         "... on User{login name avatarUrl} ... on Organization{login name avatarUrl}}}}}}")


def sponsorlar(sahip: str, token: str) -> list[dict]:
    veri = json.loads(_gh(["api", "graphql", "-f", f"query={SORGU}", "-F", f"l={sahip}"], token))
    dugumler = (((veri.get("data") or {}).get("user") or {}).get("sponsorshipsAsMaintainer") or {}).get("nodes") or []
    out = []
    for d in dugumler:
        e = d.get("sponsorEntity") or {}
        if e.get("login") and LOGIN_RE.match(e["login"]):
            out.append({"login": e["login"], "ad": e.get("name") or "", "avatar": e["avatarUrl"]})
    return out


def resim_indir(url: str) -> bytes:
    if not url.startswith("https://avatars.githubusercontent.com/"):
        raise ValueError("beklenmeyen profil resmi adresi")
    sep = "&" if "?" in url else "?"
    with urllib.request.urlopen(urllib.request.Request(f"{url}{sep}s={BOYUT * 2}", headers={"User-Agent": "ystcorestudio-topluluk"}), timeout=30) as r:
        return r.read(2_000_000)


def isle(bolum: str, kisiler: list[dict], indir=resim_indir) -> str:
    """Resimleri yazar, bölüm için HTML döner. Eski bu bölüme ait resimler silinmez (başka bölümle ortak olabilir)."""
    RESIM_DIZIN.mkdir(parents=True, exist_ok=True)
    hazir = []
    for k in kisiler:
        dosya = RESIM_DIZIN / f"{k['login']}.png"
        dosya.write_bytes(yuvarlak(indir(k["avatar"])))
        hazir.append({"login": k["login"], "ad": k.get("ad"), "dosya": f"docs/topluluk/{k['login']}.png"})
    return html_olustur(hazir, BOS[bolum])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Mtemizce/YSTCoreStudio"))
    ap.add_argument("--haric", default="", help="listelenmeyecek kullanıcılar (virgülle); depo sahibi her zaman hariçtir")
    ap.add_argument("--deneme", action="store_true", help="dosyaları yazma, ne olacağını göster")
    a = ap.parse_args()
    sahip = a.repo.split("/")[0]
    haric = {x.strip().lower() for x in a.haric.split(",") if x.strip()} | {sahip.lower()}
    metin = README.read_text(encoding="utf-8")
    yeni = metin
    kat = katkicilar(a.repo, haric)
    print(f"katkıcı: {len(kat)}")
    if a.deneme:
        print(html_olustur([{"login": k["login"], "dosya": f"docs/topluluk/{k['login']}.png"} for k in kat], BOS["katkicilar"]))
    else:
        yeni = bolum_degistir(yeni, "katkicilar", isle("katkicilar", kat))
    token = os.environ.get("SPONSORS_TOKEN", "").strip()
    if token:
        try:
            sp = sponsorlar(sahip, token)
        except RuntimeError as e:
            if "required scopes" not in str(e):
                raise
            print("::warning::SPONSORS_TOKEN için read:user ve read:org gerekli. Sponsor bölümü korunuyor.")
        else:
            print(f"sponsor: {len(sp)}")
            if not a.deneme:
                yeni = bolum_degistir(yeni, "sponsorlar", isle("sponsorlar", sp))
    else:
        print("SPONSORS_TOKEN yok: sponsor bölümüne dokunulmadı")
    if yeni != metin and not a.deneme:
        README.write_text(yeni, encoding="utf-8")
        print("README güncellendi")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError) as e:
        print("HATA:", e, file=sys.stderr)
        sys.exit(1)
