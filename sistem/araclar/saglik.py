#!/usr/bin/env python3
"""Stüdyo sağlık kontrolü: ortam, paketler, varlıklar, ajan/skill/komut tanımları; isteğe bağlı canlı ajan yoklaması ve proje izleri.

  python sistem/araclar/saglik.py                  statik kontroller (hızlı, ücretsiz)
  python sistem/araclar/saglik.py --canli          + her ajanı GERÇEKTEN çağırır (claude -p --agent …; küçük token maliyeti)
  python sistem/araclar/saglik.py --proje <ad>     + o projede her aşamanın bıraktığı dosyalara bakar (hat gerçekten çalıştı mı?)
Çıkış kodu: HATA varsa 1.
"""
from __future__ import annotations

import argparse
import importlib
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
ORTAM = SISTEM / "ortam"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import yol as _yol  # noqa: E402

_yol.hazirla()  # kurulumun getirdiği ffmpeg/ffprobe/rclone sistemde yoksa da bulunsun
SONUC: list[tuple[str, str, str]] = []  # (durum, başlık, ayrıntı)
MODELLER = {"opus", "sonnet", "haiku", "inherit", "fable"}
ARACLAR = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch", "WebSearch", "NotebookEdit", "Task", "Agent", "TodoWrite"}


def k(durum: str, baslik: str, ayrinti: str = "") -> None:
    SONUC.append((durum, baslik, ayrinti))


def frontmatter(p: Path) -> tuple[dict, str]:
    t = p.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", t, re.S)
    if not m:
        return {}, t
    fm = {}
    for satir in m.group(1).splitlines():
        if ":" in satir and not satir.startswith((" ", "\t")):
            a, b = satir.split(":", 1)
            fm[a.strip()] = b.strip()
    return fm, m.group(2)


def yaml_sorunu(fm: dict) -> str:
    """Tırnaksız düz YAML değerinde ': ' ya da ' #' geçersizdir: Claude tanımı SESSİZCE reddeder (ajan 'not found')."""
    for alan in ("description", "argument-hint", "name", "tools", "model"):
        v = fm.get(alan, "")
        if v and not v.startswith(('"', "'")) and (": " in v or " #" in v):
            return f"{alan} tırnaksız ve ': ' içeriyor (geçersiz YAML; değeri çift tırnağa al)"
    return ""


def yol_var(token: str) -> bool | None:
    """Belgede geçen depo yolu gerçekten var mı? Yer tutucu/jolly içerenleri atla (None)."""
    if any(c in token for c in "<>*…{}$|") or token.startswith(("http", "~", "/", "-")):
        return None
    t = token.rstrip("/.,;:)")
    if not re.match(r"^(sistem|kimlik|\.claude|projeler|kurgu)/", t):
        return None
    if t.startswith(("projeler/", "sistem/kit/sfx", "sistem/kit/muzik", "sistem/kit/referans", "sistem/ortam", "sistem/araclar/dis", "kurgu/")):  # kurulum/çalışma zamanı ürünleri
        return None
    if t in ("kimlik/zevk.md", "kimlik/zevk.json", "kimlik/ses_profili.md", "kimlik/ogrenilenler.md", "kimlik/ornekler"):  # kullanımla oluşan dosyalar
        return None
    return (ROOT / t).exists()


def _arka_bekliyor() -> bool:
    """PyTorch / yapay zekâ paketleri arka plan kuyruğunda bekliyor mu? (kurulum bunları panel açıldıktan sonra yapar)"""
    try:
        import importlib.util
        sp = importlib.util.spec_from_file_location("yst_arka_saglik", SISTEM / "araclar" / "arka_indirme.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        e = m.eksikler(taze=True)
        return "pytorch" in e or "paketler" in e
    except Exception:  # noqa: BLE001
        return False


def ortam() -> None:
    k("OK" if sys.version_info >= (3, 10) else "HATA", "Python", sys.version.split()[0])
    venv = (ORTAM / "venv").exists() and Path(sys.prefix).resolve() == (ORTAM / "venv").resolve()
    k("OK" if venv else "UYARI", "Sanal ortam (.venv) kullanılıyor", "" if venv else "bu betik .venv dışından çalışıyor; paket kontrolleri yanıltıcı olabilir")
    for mod, ad in (("numpy", "numpy"), ("PIL", "Pillow"), ("ema_lightning", "ema-lightning (TTS)"), ("faster_whisper", "faster-whisper"),
                    ("spandrel", "spandrel (foto iyileştirme)"), ("parselmouth", "parselmouth (ton ölçümü)"),
                    ("pypdfium2", "pypdfium2 (PDF)"), ("pypdf", "pypdf (PDF metni)"), ("torch", "PyTorch")):
        try:
            m = importlib.import_module(mod)
            ek = ""
            if mod == "torch":
                ek = f"{m.__version__}, CUDA {'var' if m.cuda.is_available() else 'YOK (CPU)'}"
                k("OK" if m.cuda.is_available() else "UYARI", ad, ek)
                continue
            k("OK", ad)
        except Exception as e:  # noqa: BLE001
            if mod in ("ema_lightning", "spandrel", "torch") and _arka_bekliyor():
                k("UYARI", ad, "henüz kurulmadı: panel açıldıktan sonra arka planda kuruluyor (panelde ilerleme görünür)")
            else:
                k("HATA", ad, f"içe aktarılamadı: {type(e).__name__}")
    for exe, ad in (("node", "Node.js"), ("npm", "npm"), ("git", "git"), ("ffmpeg", "ffmpeg"), ("ffprobe", "ffprobe")):
        yol = shutil.which(exe)  # PATH, yol.hazirla() ile kurulumun ffmpeg klasörünü de içerir
        k("OK" if yol else "HATA", ad, yol or "bulunamadı")
    k("OK" if shutil.which("claude") else "UYARI", "Claude Code (claude)", "" if shutil.which("claude") else "PATH'te yok: panel 'Claude ile üret' çalışmaz")


def kurulum() -> None:
    k("OK" if (ORTAM / "yerel" / "kurulum.ok").exists() else "HATA", "Kurulum tamamlandı işareti")
    k("OK" if (ROOT / "kurgu" / "pyproject.toml").exists() else "HATA", "Kurgu (kurgu/)")
    if (ROOT / "kurgu" / "pyproject.toml").exists():   # YSTCore eklentisi (görsel, seslendirme, ara sahne): kurulumda Kurgu'ya uygulanır
        try:
            import importlib.util
            sp = importlib.util.spec_from_file_location("yst_kurgu_yama", ROOT / "sistem" / "kurulum" / "kurgu_yama.py")
            ym = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(ym)
            kt = ym.kontrol(ROOT / "kurgu")
            if kt["tamam"]:
                k("OK", "Kurgu eklentisi (görsel, seslendirme, ara sahne)")
            else:
                eksik = [a_ for a_, d_ in kt["ekler"].items() if d_ != "uygulanmis"] + [y for y, v in kt["dosyalar"].items() if not v]
                k("UYARI", "Kurgu eklentisi uygulanmamış", "eksik: " + ", ".join(eksik) + " → python sistem/kurulum/kurgu_yama.py")
        except Exception as e:  # noqa: BLE001
            k("UYARI", "Kurgu eklentisi denetlenemedi", str(e)[:120])
    cfg = ORTAM / "kurgu-ayar" / "config.json"
    if cfg.exists():
        try:
            c = json.loads(cfg.read_text(encoding="utf-8"))
            eksik = []
            for ad, kom in c.get("render_adaptors", {}).items():
                dosya = next((x for x in kom if x.endswith(".js")), None)
                if dosya and not Path(dosya).exists():
                    eksik.append(f"{ad}: {dosya}")
            k("OK" if not eksik else "HATA", "Kurgu render adaptörleri (Remotion/HyperFrames)", "; ".join(eksik))
        except Exception as e:  # noqa: BLE001
            k("HATA", "Kurgu ayarı (sistem/ortam/kurgu-ayar/config.json)", f"okunamadı: {e}")
    else:
        k("HATA", "Kurgu ayarı (sistem/ortam/kurgu-ayar/config.json)", "yok: kurulum çalışmamış")
    hs = ROOT / "node_modules" / ".remotion" / "chrome-headless-shell"
    k("OK" if hs.exists() else "HATA", "Remotion tarayıcısı (Chrome Headless Shell)", "" if hs.exists() else "yok: render alınamaz (kurulum 'remotion browser ensure' çalıştırır)")
    for paket in ("@remotion/cli", "hyperframes", "sharp", "gsap"):
        k("OK" if (ROOT / "node_modules" / paket).exists() else "HATA", f"npm: {paket}")
    r = subprocess.run([sys.executable, str(SISTEM / "varlik" / "varlik.py"), "durum"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONUTF8="1"))
    son = (r.stdout.strip().splitlines() or ["?"])[-1]
    k("OK" if r.returncode == 0 and " 0 eksik" in son else "UYARI", "Varlıklar (ses efektleri, modeller, LibreDWG)", son)
    k("OK" if (SISTEM / "araclar" / "dis" / "libredwg" / "dwg2SVG.exe").exists() else "UYARI", "LibreDWG (DWG alımı)")
    s = ROOT / ".claude" / "settings.json"
    try:
        sj = json.loads(s.read_text(encoding="utf-8"))
        ok = any("hyperframes auth" in x for x in sj.get("permissions", {}).get("deny", [])) and sj.get("env", {}).get("HYPERFRAMES_NO_TELEMETRY") == "1"
        k("OK" if ok else "HATA", "Yerel kural kilidi (.claude/settings.json: bulut komutları yasak, telemetri kapalı)")
    except Exception:  # noqa: BLE001
        k("HATA", "Yerel kural kilidi", ".claude/settings.json okunamadı")


def tanimlar() -> list[str]:
    ajanlar = []
    for f in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        fm, govde = frontmatter(f)
        ad = f.stem
        sorunlar = []
        if yaml_sorunu(fm):
            sorunlar.append(yaml_sorunu(fm))
        if fm.get("name") != ad:
            sorunlar.append(f"name='{fm.get('name')}' dosya adıyla uyuşmuyor")
        if len(fm.get("description", "")) < 30:
            sorunlar.append("description kısa/boş (Claude ajanı ne zaman çağıracağını bilemez)")
        if fm.get("model") not in MODELLER:
            sorunlar.append(f"model='{fm.get('model')}' geçersiz")
        araclar = [a.strip() for a in fm.get("tools", "").split(",") if a.strip()]
        if not araclar:
            sorunlar.append("tools boş")
        bil = [a for a in araclar if a not in ARACLAR]
        if bil:
            sorunlar.append(f"bilinmeyen araç: {bil}")
        ref = [t for t in re.findall(r"`([^`\s]+)`", govde) if yol_var(t) is False]
        if ref:
            sorunlar.append("var olmayan yollara atıf: " + ", ".join(sorted(set(ref))[:5]))
        k("OK" if not sorunlar else "HATA", f"ajan {ad} ({fm.get('model')})", "; ".join(sorunlar))
        ajanlar.append(ad)
    for f in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        fm, govde = frontmatter(f)
        ad = f.parent.name
        sorunlar = []
        if yaml_sorunu(fm):
            sorunlar.append(yaml_sorunu(fm))
        if not fm.get("description"):
            sorunlar.append("description yok")
        if fm.get("name") and fm["name"] != ad:
            sorunlar.append(f"name='{fm['name']}' klasör adıyla uyuşmuyor")
        yerel = ad in {"video-yonetmen", "kisilik-ve-ton", "marka-kilidi", "kaba-kurgu", "sosyal-surumler", "hook-ve-kapak", "kurgu-video-studio"}
        if yerel:
            ref = [t for t in re.findall(r"`([^`\s]+)`", govde) if yol_var(t) is False]
            if ref:
                sorunlar.append("var olmayan yollara atıf: " + ", ".join(sorted(set(ref))[:5]))
        k("OK" if not sorunlar else ("HATA" if yerel else "UYARI"), f"skill {ad}", "; ".join(sorunlar))
    for f in sorted((ROOT / ".claude" / "commands").glob("*.md")):
        fm, _ = frontmatter(f)
        sorun = yaml_sorunu(fm) or ("" if fm.get("description") else "description yok")
        k("OK" if not sorun else "HATA", f"komut /{f.stem}", sorun)
    return ajanlar


def canli(ajanlar: list[str]) -> None:
    claude = shutil.which("claude")
    if not claude:
        k("HATA", "canlı yoklama", "claude bulunamadı")
        return
    for ad in ajanlar:
        fm, _ = frontmatter(ROOT / ".claude" / "agents" / f"{ad}.md")
        beklenen = fm.get("model", "")
        t0 = time.time()
        r = subprocess.run([claude, "-p", "--agent", ad, "--output-format", "json", "--no-session-persistence", "--max-budget-usd", "0.50",
                            f"Yoklama. Araç kullanma, dosya okuma. Yalnızca şu tek satırı yaz: HAZIR-{ad}"],
                           cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        sure = time.time() - t0
        try:
            j = json.loads(r.stdout)
            metin = str(j.get("result", ""))
            modeller = list((j.get("modelUsage") or {}).keys())
            ok_metin = f"HAZIR-{ad}" in metin
            ok_model = (not beklenen or beklenen == "inherit") or any(beklenen in m.lower() for m in modeller)
            ayr = f"{sure:.0f} sn, modeller: {', '.join(modeller) or '?'}"
            if not ok_metin:
                k("HATA", f"canlı: {ad}", f"beklenen yanıt gelmedi ({metin[:80]!r}); {ayr}")
            elif not ok_model:
                k("UYARI", f"canlı: {ad}", f"yanıt verdi ama model '{beklenen}' görünmüyor; {ayr}")
            else:
                k("OK", f"canlı: {ad}", ayr)
        except Exception:  # noqa: BLE001
            k("HATA", f"canlı: {ad}", (r.stderr or r.stdout or "çıktı yok").strip()[-160:])


# aşama → (açıklama, kanıt dosyası desenleri; projeler/<ad>/ altında)
ASAMALAR = [
    ("Kaynaklar alındı (kaynak/)", ["kaynak/*/*"]),
    ("Envanter + belge çıktıları (hazir/)", ["hazir/envanter.json", "hazir/belge/belgeler.md"]),
    ("Brief dolduruldu", ["brief.md"]),
    ("senarist: ton rehberi + senaryo + tahta", ["ton_rehberi.md", "senaryo.md", "hikaye_tahtasi.md"]),
    ("gorsel-iyilestirici: iyileştirilmiş foto", ["*/media/foto/*", "*/media/foto_orijinal/*"]),
    ("ses-yonetmeni: seslendirme + rapor", ["ses_plani.md", "*/ses/rapor.json", "*/ses/plan.json"]),
    ("sahne-yapimcisi: Remotion/HyperFrames sahneleri", ["*/remotion/src/*.tsx", "*/hyperframes/*.html"]),
    ("Kurgu projesi (project.json katmanları)", ["*/project.json"]),
    ("Render çıktısı (biçim cikti/)", ["*/cikti/*.mp4"]),
    ("elestirmen: bağımsız inceleme raporu", ["kalite_raporu.md", "elestirmen*.md", "*/elestirme*.md"]),
    ("TESLİM (cikti/)", ["cikti/*.mp4"]),
]


def proje_izleri(ad: str) -> None:
    kok = ROOT / "projeler" / ad
    if not kok.is_dir():
        k("HATA", f"proje {ad}", "klasör yok")
        return
    for baslik, desenler in ASAMALAR:
        bulunan = []
        for d in desenler:
            bulunan += [p for p in kok.glob(d) if p.is_file() and p.stat().st_size > 0]
        k("OK" if bulunan else "UYARI", f"[{ad}] {baslik}", f"{len(bulunan)} dosya" if bulunan else "iz yok (aşama çalışmamış ya da dosya bırakmamış)")
    # orkestratör denetimi: her ajan devri günlüğe işlenmiş mi? (orkestrasyon.md §5)
    gunluk = kok / "calisma_gunlugu.md"
    if gunluk.exists():
        satirlar = [s for s in gunluk.read_text(encoding="utf-8").splitlines() if s.startswith("|") and not s.startswith(("| zaman", "|---"))]
        dolu = [s for s in satirlar if any(c.strip() for c in s.strip("|").split("|"))]
        kararsiz = [s for s in dolu if not re.search(r"kabul|revize|ret|kullanıcıya", s, re.I)]
        k("OK" if dolu else "UYARI", f"[{ad}] orkestratör çalışma günlüğü", f"{len(dolu)} devir kaydı" + (f"; {len(kararsiz)} kaydın kararı yok" if kararsiz else "") if dolu else "boş: ajan devirleri kaydedilmemiş")
    else:
        k("UYARI", f"[{ad}] orkestratör çalışma günlüğü", "calisma_gunlugu.md yok")


def kimlik_arsiv() -> None:
    """Kimlik katmanları ve arşiv: yalnızca bilgi/uyarı (üretimi engellemez)."""
    try:
        sys.path.insert(0, str(SISTEM / "araclar"))
        import kimlik_olc
        metin = (ROOT / "kimlik" / "PROFIL.md").read_text(encoding="utf-8")
        r = kimlik_olc.olc(metin)
        kat = kimlik_olc.katmanlar()
        k("OK" if r["kritik_yuzde"] >= 60 else "UYARI", "Kimlik doluluğu", f"%{r['yuzde']} genel, kritik alanlar %{r['kritik_yuzde']}" +
          ("" if r["kritik_yuzde"] >= 60 else " (panel → Kimlik → 'Claude ile kimliği tamamla')"))
        k("OK" if kat["ornekler_yeterli"] else "UYARI", "Kimlik: gerçek yazı/ses örnekleri (kimlik/ornekler)", f"{kat['ornekler']} dosya" + ("" if kat["ornekler_yeterli"] else " (en az 3 koy)"))
        k("OK" if kat["zevk"] else "UYARI", "Kimlik: zevk testi (kimlik/zevk.md)", "" if kat["zevk"] else "yapılmamış (panel → Kimlik → Zevk testi)")
    except Exception as e:  # noqa: BLE001
        k("UYARI", "Kimlik ölçümü", f"yapılamadı: {type(e).__name__}")
    ayar = ORTAM / "arsiv" / "ayar.json"
    if ayar.exists():
        try:
            sys.path.insert(0, str(SISTEM / "arsiv"))
            import arsiv
            d = arsiv.durum()
            k("OK" if d.get("bagli") else "UYARI", "Arşiv (harici disk)", f"{'bağlı' if d.get('bagli') else 'DİSK BAĞLI DEĞİL'}; {d.get('toplam', 0)} dosya dizinde")
        except Exception as e:  # noqa: BLE001
            k("UYARI", "Arşiv", f"okunamadı: {type(e).__name__}")
    else:
        k("OK", "Arşiv", "henüz ayarlanmadı (isteğe bağlı: panel → Arşiv)")


def ayarlar_ve_baglayicilar() -> None:
    """Model/effort ayarı, bağlayıcılar, marka kiti ve arşiv analizi modülü: yüklenebiliyor mu, ajan dosyalarıyla uyumlu mu, sır sızıyor mu?"""
    try:
        sys.path.insert(0, str(SISTEM / "ayar"))
        import ayar as A
        cz = A.coz()
        sorun = []
        for ad, v in cz["ajanlar"].items():
            fm, _ = frontmatter(ROOT / ".claude" / "agents" / f"{ad}.md")
            if not fm:
                sorun.append(f"{ad}: ajan dosyası yok")
            elif fm.get("model") != v["model"] or fm.get("effort") != v["effort"]:
                sorun.append(f"{ad}: dosya ({fm.get('model')}/{fm.get('effort')}) ayarla ({v['model']}/{v['effort']}) uyuşmuyor: `python sistem/ayar/ayar.py esitle`")
        k("OK" if not sorun else "UYARI", "Ajan ayarı (model/effort)", f"{len(cz['ajanlar'])} ajan" if not sorun else "; ".join(sorun[:3]))
        bulut = [x for x, v in cz.get("baglayicilar", {}).items() if isinstance(v, dict) and v.get("etkin") and x != "ema"]
        k("OK", "Bağlayıcılar (ücretli, isteğe bağlı)", ("etkin: " + ", ".join(bulut)) if bulut else "hepsi kapalı (yalnızca yerel)")
    except Exception as e:  # noqa: BLE001
        k("HATA", "Ayar modülü", f"{type(e).__name__}: {e}")
    anahtar = ORTAM / "baglayici" / "anahtar.json"
    if anahtar.exists():
        try:
            takipte = subprocess.run(["git", "ls-files", "--error-unmatch", str(anahtar)], cwd=str(ROOT), capture_output=True).returncode == 0
            k("HATA" if takipte else "OK", "API anahtar dosyası", "GİT'TE TAKİP EDİLİYOR: hemen çıkar" if takipte else "yerel, git'e girmiyor")
        except Exception:  # noqa: BLE001
            pass
    kit = ROOT / "kimlik" / "marka_kitleri" / "varsayilan" / "kit.json"
    k("OK" if kit.is_file() else "UYARI", "Marka kiti (varsayilan)", "" if kit.is_file() else "yok: panel → Ayarlar → Marka kitleri")
    try:
        sys.path.insert(0, str(SISTEM / "arsiv"))
        import analiz  # noqa: F401
        k("OK", "Arşiv analizi modülü")
    except Exception as e:  # noqa: BLE001
        k("HATA", "Arşiv analizi modülü", f"{type(e).__name__}: {e}")


def konum_ve_tasinabilirlik() -> None:
    """Taşınabilirlik: veritabanı şeması, kök kayıtları, arşiv bağlantısı, kayıtlarda mutlak yol, eski kök kalıntısı, venv sağlığı, sistem önkoşulları."""
    try:
        sys.path.insert(0, str(SISTEM / "araclar"))
        sys.path.insert(0, str(SISTEM / "arsiv"))
        sys.path.insert(0, str(SISTEM / "kurulum"))
        import arsiv as A
        import konum as K
        c = A.baglan()
        v = c.execute("PRAGMA user_version").fetchone()[0]
        k("OK" if v == K.SEMA_SURUMU else "UYARI", "Veritabanı şeması", f"sürüm {v}")
        kokler = K.kok_listesi(c)
        st = next((x for x in kokler if x["tur"] == "studyo"), None)
        k("OK" if st and st["bagli"] else "UYARI", "Stüdyo kökü kaydı", (st["yol"] if st else "kayıt yok: Başlat.cmd bir kez açılınca yazılır"))
        for a in [x for x in kokler if x["tur"] == "arsiv"]:
            k("OK" if a["bagli"] else "UYARI", f"Arşiv '{a['ad']}'", f"{a['yol']} ({a['yontem']}), {a['dosya']} dosya" if a["bagli"] else (a["not"] or "bağlı değil (disk takılı mı?)"))
        mutlak = c.execute("SELECT COUNT(*) FROM dosya WHERE yol LIKE '_:%' OR yol LIKE '/%' OR yol LIKE ?", ("%:" + chr(92) + "%",)).fetchone()[0]
        k("OK" if not mutlak else "HATA", "Dizinde mutlak yol", "yok (kök + göreli yol)" if not mutlak else f"{mutlak} kayıt mutlak yol içeriyor")
        c.close()
        d = K.denetle()
        k("OK" if not d["bulgu"] else "UYARI", "Proje/ayar dosyalarında mutlak yol", "yok" if not d["bulgu"] else "; ".join(f"{b['dosya']} ({b['ornek']})" for b in d["bulgu"][:3]))
        dm = K.damga_oku()
        k("OK" if dm.get("kok", "").lower() == str(ROOT).lower() else "UYARI", "Konum damgası", "güncel" if dm.get("kok", "").lower() == str(ROOT).lower() else "klasör taşınmış: Başlat.cmd onarır")
    except Exception as e:  # noqa: BLE001
        k("HATA", "Taşınabilirlik denetimi", f"{type(e).__name__}: {e}")
    try:
        import onkosul as OK
        t = OK.tara(ag=False)
        eksik = [o["ad"] for o in t["ogeler"] if o["seviye"] == "zorunlu" and o["durum"] in ("eksik", "eski")]
        k("OK" if not eksik else "UYARI", "Sistem önkoşulları", "tamam" if not eksik else "eksik: " + ", ".join(eksik))
    except Exception as e:  # noqa: BLE001
        k("UYARI", "Sistem önkoşulları", f"{type(e).__name__}: {e}")


def yaz(json_cikti: bool) -> int:
    if json_cikti:
        print(json.dumps([{"durum": a, "baslik": b, "ayrinti": c} for a, b, c in SONUC], ensure_ascii=False, indent=1))
    else:
        simge = {"OK": "[ OK  ]", "UYARI": "[UYARI]", "HATA": "[HATA ]"}
        for a, b, c in SONUC:
            print(f"{simge[a]} {b}" + (f": {c}" if c else ""))
        n = {x: sum(1 for s in SONUC if s[0] == x) for x in ("OK", "UYARI", "HATA")}
        print(f"\nözet: {n['OK']} tamam, {n['UYARI']} uyarı, {n['HATA']} hata")
    return 1 if any(s[0] == "HATA" for s in SONUC) else 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canli", action="store_true")
    ap.add_argument("--proje")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ortam()
    kurulum()
    ajanlar = tanimlar()
    kimlik_arsiv()
    ayarlar_ve_baglayicilar()
    konum_ve_tasinabilirlik()
    if a.canli:
        canli(ajanlar)
    if a.proje:
        proje_izleri(a.proje)
    return yaz(a.json)


if __name__ == "__main__":
    sys.exit(main())
