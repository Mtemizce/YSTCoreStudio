"""BAKIM ARACI: yeni bir dış skill/belge klasörünü kurulum manifestine (dis_kaynaklar.json) ekler. Kurulum sırasında ÇALIŞMAZ.

Dış dosyalar depoya konmaz: kurulum bunları kendi kaynağından çeker. Bu araç yalnızca "nereden, hangi dosya" listesini yazar.

  git deposu :  python sistem/kurulum/dis_ekle.py git <kaynak-id> <https-adres> <yerel-klon-klasörü> <klon-içi-alt-yol> <hedef>
  npm paketi :  python sistem/kurulum/dis_ekle.py npm <paket-adı> <paket-içi-alt-yol> <hedef> [--kok ""]

Örnekler:
  python sistem/kurulum/dis_ekle.py git gsap-skills https://github.com/greensock/gsap-skills C:/tmp/gsap-skills skills/gsap-core .claude/skills/gsap-core
  python sistem/kurulum/dis_ekle.py npm gl-transitions skills/gl-transitions .claude/skills/gl-transitions

Klon, kurulumun çekeceği commit'tir (git rev-parse HEAD kaydedilir). Eklemeden ÖNCE skill'i okuyup `skill_tara.py` ile tara
(.claude/CLAUDE.md "Üçüncü taraf skill alma politikası"); hedef klasörü .gitignore'a da ekle.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sistem" / "kurulum" / "dis_kaynaklar.json"


def main() -> int:
    a = sys.argv[1:]
    if len(a) < 4:
        print(__doc__)
        return 2
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    kaynaklar, dosyalar = m["kaynaklar"], m["skill_dosyalari"]
    tur = a[0]
    if tur == "git":
        kid, adres, klon, alt, hedef = a[1], a[2], Path(a[3]), a[4].strip("/"), a[5].strip("/")
        ref = subprocess.run(["git", "-C", str(klon), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if len(ref) != 40:
            sys.exit("klon bir git deposu değil")
        eski = kaynaklar.get(kid)
        if eski and eski.get("ref") != ref:
            sys.exit(f"'{kid}' zaten {eski['ref'][:8]} olarak kayıtlı; aynı kaynaktan farklı commit eklenemez")
        kaynaklar[kid] = {"tur": "git", "adres": adres, "ref": ref}
        kok = klon / alt
    elif tur == "npm":
        paket, alt, hedef = a[1], a[2].strip("/"), a[3].strip("/")
        kaynaklar_id = "npm-" + paket.replace("/", "-").lstrip("@")
        kid = kaynaklar_id
        pj = json.loads((ROOT / "node_modules" / paket / "package.json").read_text(encoding="utf-8"))
        kaynaklar[kid] = {"tur": "npm", "adres": paket, "surum": pj["version"], "kok": ""}
        kok = ROOT / "node_modules" / paket / alt
    else:
        sys.exit("tür git|npm olmalı")
    if not kok.is_dir():
        sys.exit(f"klasör yok: {kok}")
    # aynı hedefe ait eski girişleri temizle
    dosyalar[:] = [d for d in dosyalar if not d["hedef"].startswith(hedef + "/")]
    n = 0
    for f in sorted(kok.rglob("*")):
        if f.is_file() and ".git" not in f.relative_to(kok).parts:
            rel = f.relative_to(kok).as_posix()
            dosyalar.append({"hedef": f"{hedef}/{rel}", "kaynak": kid, "yol": f"{alt}/{rel}" if alt else rel})
            n += 1
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n} dosya eklendi: {kid} → {hedef}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
