"""BAKIM ARACI (yalnızca geliştirici): çalışan bir kurulumdaki üçüncü taraf dosyaları, sabitlenmiş upstream
sürümleriyle karşılaştırıp (1) 'aynı olanları' manifeste, (2) 'bizim değiştirdiklerimizi' yama katmanına yazar.

Böylece depoya yalnızca bizim farkımız girer; kurulum upstream'i kendi deposundan çeker, sonra yamayı üstüne uygular.

Kullanım (depo kökünden):
  python sistem/kurulum/yama_cikar.py --eski <eski kurulum kökü> --kaynaklar <upstream klonlarının klasörü>
Bu betik kurulum SIRASINDA çalışmaz; kurulum yalnızca dis_kaynaklar.json + yama/ kullanır.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"


def norm_hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()


def agac(kok: Path):
    for p in sorted(kok.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(kok).parts:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eski", required=True, help="eski kurulum kökü (kurguuu)")
    ap.add_argument("--kaynaklar", required=True, help="upstream klonlarının bulunduğu klasör")
    a = ap.parse_args()
    eski, kl = Path(a.eski), Path(a.kaynaklar)
    skills_eski = eski / "studio" / ".claude" / "skills"

    # id: (tür, adres, yerel klasör, ref)
    kaynaklar = {
        "remotion-skills": ("git", "https://github.com/remotion-dev/skills", kl / "up_skills"),
        "motion-video-kit": ("git", "https://github.com/echris6/motion-video-kit", kl / "up_motion-video-kit"),
        "hf-director": ("git", "https://github.com/artificialguybr/hyperframes-video-director", kl / "up_hyperframes-video-director"),
        "anthropic-skills": ("git", "https://github.com/anthropics/skills", kl / "aday" / "anthropics_skills"),
        "npm-hyperframes": ("npm", "hyperframes", eski / "studio" / "node_modules" / "hyperframes" / "dist" / "skills"),
    }
    # dizin: karma -> (id, göreli yol)
    dizin: dict[str, tuple[str, str]] = {}
    meta = {}
    for kid, (tur, adres, yol) in kaynaklar.items():
        for f in agac(yol):
            dizin.setdefault(norm_hash(f), (kid, f.relative_to(yol).as_posix()))
        meta[kid] = {"tur": tur, "adres": adres}
        if tur == "git":
            meta[kid]["ref"] = git(yol, "rev-parse", "HEAD")
        else:
            pkg = json.loads((eski / "studio" / "node_modules" / "hyperframes" / "package.json").read_text("utf-8"))
            meta[kid]["surum"] = pkg["version"]

    ucuncu = ["remotion-best-practices", "hyperframes", "hyperframes-cli", "business-motion-film", "hyperframes-video-director", "frontend-design"]
    dosyalar, yama_say = [], 0
    yama_kok = SISTEM / "yama"
    if (yama_kok / "skills").exists():
        shutil.rmtree(yama_kok / "skills")
    for ad in ucuncu:
        for f in agac(skills_eski / ad):
            rel = f.relative_to(skills_eski).as_posix()
            hedef = f".claude/skills/{rel}"
            h = norm_hash(f)
            if h in dizin:
                kid, yol = dizin[h]
                dosyalar.append({"hedef": hedef, "kaynak": kid, "yol": yol})
            else:
                dst = yama_kok / "skills" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                yama_say += 1

    # Kurgu yaması: upstream'e göre farklı + yeni dosyalar
    kurgu_eski = eski
    kurgu_yama = yama_kok / "kurgu"
    if kurgu_yama.exists():
        shutil.rmtree(kurgu_yama)
    durum = subprocess.run(["git", "-C", str(kurgu_eski), "status", "--porcelain"], capture_output=True, text=True).stdout
    kurgu_dosya = []
    for satir in durum.splitlines():
        yol = satir[3:].strip().strip('"')
        if yol.startswith(("studio", "archive", ".pytest_cache", "kurgu.egg-info", "__pycache__")) or yol.endswith(".cmd") or yol == "KULLANIM.md":
            continue
        p = kurgu_eski / yol
        if p.is_file():
            kurgu_dosya.append(yol)
    for yol in kurgu_dosya:
        dst = kurgu_yama / yol
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kurgu_eski / yol, dst)
    kurgu_ref = git(kurgu_eski, "rev-parse", "HEAD")

    manifest = {
        "kurgu": {"adres": git(kurgu_eski, "remote", "get-url", "origin"), "ref": kurgu_ref, "yama_dosyalari": kurgu_dosya},
        "kaynaklar": meta,
        "skill_dosyalari": dosyalar,
    }
    (SISTEM / "kurulum" / "dis_kaynaklar.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"skill: {len(dosyalar)} dosya upstream'den, {yama_say} dosya yama katmanında")
    print(f"kurgu: ref {kurgu_ref[:8]}, {len(kurgu_dosya)} yama dosyası: {kurgu_dosya}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
