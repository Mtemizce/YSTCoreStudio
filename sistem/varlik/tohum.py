"""BAKIM ARACI: varlıklar.db'yi mevcut (eski) kurulumdan bir kez tohumlar. Kurulum sırasında ÇALIŞMAZ.
  python sistem/varlik/tohum.py --eski C:\\...\\kurguuu --libredwg-zip <l.zip>
"""
import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import varlik as V  # noqa: E402


def ekle(c, kimlik, tur, ad, hedef, kt, kaynak, sha, boyut, lisans, lisans_url=None, notlar=None):
    c.execute("INSERT OR REPLACE INTO varlik VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (kimlik, tur, ad, hedef, kt, kaynak, sha, boyut, lisans, lisans_url, notlar, time.strftime("%Y-%m-%d")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eski", required=True)
    ap.add_argument("--libredwg-zip", required=True)
    a = ap.parse_args()
    eski = Path(a.eski)
    npmkok = eski / "studio" / "node_modules" / "hyperframes"
    media = npmkok / "dist" / "skills" / "media-use"
    idx = {}
    for f in media.rglob("*"):
        if f.is_file():
            idx.setdefault(hashlib.sha1(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), f)
    c = V.baglan()
    c.execute("DELETE FROM varlik")
    sayac = {"sfx": 0, "referans": 0, "yok": []}
    for klasor, tur, lisans, lurl in (("sfx", "sfx", "Pixabay Content License", "https://pixabay.com/service/license-summary/"),
                                      ("referans/medya", "referans", "Apache-2.0 (HeyGen hyperframes)", None)):
        for f in sorted((eski / "studio" / "kit" / klasor).rglob("*")):
            if not f.is_file():
                continue
            h = hashlib.sha1(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            kaynak = idx.get(h)
            if kaynak is None:
                sayac["yok"].append(str(f.relative_to(eski)))
                continue
            rel = kaynak.relative_to(npmkok).as_posix()
            hedef = f"sistem/kit/{klasor}/{f.relative_to(eski / 'studio' / 'kit' / klasor).as_posix()}"
            ekle(c, f"{tur}-{f.relative_to(eski / 'studio' / 'kit' / klasor).as_posix().replace('/', '-')}", tur, f.name, hedef,
                 "npm", f"hyperframes::{rel}", V.sha256(f), f.stat().st_size, lisans, lurl,
                 "hyperframes npm paketinin içinden kopyalanır (kurulumda node_modules hazır olunca)")
            sayac[tur] += 1
    # model
    model = Path(os.environ["LOCALAPPDATA"]) / "Kurgu" / "models" / "RealESRGAN_x4plus.safetensors"
    ekle(c, "model-realesrgan-x4plus", "model", "Real-ESRGAN x4plus (foto iyileştirme)", "sistem/ortam/modeller/RealESRGAN_x4plus.safetensors", "url",
         "https://huggingface.co/Comfy-Org/Real-ESRGAN_repackaged/resolve/main/RealESRGAN_x4plus.safetensors",
         V.sha256(model), model.stat().st_size, "BSD-3-Clause (xinntao/Real-ESRGAN)",
         "https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE")
    z = Path(a.libredwg_zip)
    ekle(c, "arac-libredwg-0.14-win32", "arac", "LibreDWG 0.14 (DWG→SVG, yerel)", "sistem/araclar/dis/libredwg", "zip-url",
         "https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14-win32.zip", V.sha256(z), z.stat().st_size,
         "GPL-3.0-or-later", "https://www.gnu.org/licenses/gpl-3.0.html", "Depoya konmaz; kurulumda resmî yayından indirilir.")
    c.commit()
    print(sayac)


if __name__ == "__main__":
    main()
