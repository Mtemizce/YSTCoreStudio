"""YSTCoreStudio kurulumu. Başlat.cmd ilk çalıştırmada bunu çağırır; elle de çalıştırabilirsin:

  python sistem/kurulum/kurulum.py            # eksik ne varsa kurar (tekrar çalıştırmak güvenlidir)
  python sistem/kurulum/kurulum.py --kontrol  # hiçbir şey kurmadan durumu söyler
  python sistem/kurulum/kurulum.py --yenile   # dış kaynakları (Kurgu, skill'ler) yeniden çekip yamayı yeniden uygular

Yöntem: dış bileşenler KENDİ depolarından, sabitlenmiş sürümle çekilir (kurulum/dis_kaynaklar.json);
bizim değişikliklerimiz yama/ klasöründen üzerlerine uygulanır. Yalnızca Python standart kütüphanesi gerekir.
Ağ kullanımı: GitHub (klonlar), npm kayıt defteri, PyPI + PyTorch indeksi, Hugging Face (model), LibreDWG yayını.
Hesap, API anahtarı, telemetri yok.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # depo kökü
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"                           # kurulumun ürettikleri (git'e girmez)
VENV = ORTAM / "venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
YEREL = ORTAM / "yerel"
MANIFEST = json.loads((SISTEM / "kurulum" / "dis_kaynaklar.json").read_text(encoding="utf-8"))


def say(msg: str) -> None:
    print(msg, flush=True)


_ADIM = {"t": None, "ad": "", "bas": time.time()}


def adim(no: int, toplam: int, ad: str) -> None:
    """Adım başlığı; önceki adımın SÜRESİ de yazılır (kurulum süresi tahmin değil ölçülür: günlükte hangi adım ne kadar sürdü görünür)."""
    simdi = time.time()
    if _ADIM["t"] is not None:
        say(f"  (süre: {int(simdi - _ADIM['t'])} sn)")
    _ADIM.update(t=simdi, ad=ad)
    say(f"\n[{no}/{toplam}] {ad}")


def calistir(cmd, cwd=None, env=None, kontrol=True):
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env)
    if kontrol and r.returncode != 0:
        raise SystemExit(f"HATA: komut başarısız ({r.returncode}): {' '.join(str(c) for c in cmd)}")
    return r.returncode


def cikti(cmd, **kw) -> str:
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=60, **kw).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def git_cek(adres: str, ref: str, hedef: Path) -> None:
    """Belirli bir commit'i (sha) hedef klasöre getirir (ince klon, .git bırakılır ki yeniden denenebilsin)."""
    if (hedef / ".git").is_dir() and cikti(["git", "-C", hedef, "rev-parse", "HEAD"]) == ref:
        return
    if hedef.exists():
        shutil.rmtree(hedef, ignore_errors=True)
    hedef.mkdir(parents=True)
    calistir(["git", "init", "-q"], cwd=hedef)
    calistir(["git", "remote", "add", "origin", adres], cwd=hedef)
    calistir(["git", "fetch", "-q", "--depth", "1", "origin", ref], cwd=hedef)
    calistir(["git", "checkout", "-q", "FETCH_HEAD"], cwd=hedef)


def kopya_agaci(kaynak: Path, hedef: Path) -> int:
    n = 0
    for f in kaynak.rglob("*"):
        if f.is_file():
            d = hedef / f.relative_to(kaynak)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, d)
            n += 1
    return n


# ------------------------------------------------------------------ adımlar
def a_kontrol() -> dict:
    d = {}
    d["python"] = sys.version_info >= (3, 10)
    d["git"] = bool(shutil.which("git"))
    node = cikti(["node", "--version"]) if shutil.which("node") else ""
    d["node"] = bool(node) and int(node.lstrip("v").split(".")[0]) >= 20
    d["npm"] = bool(shutil.which("npm"))
    d["ffmpeg"] = bool(shutil.which("ffmpeg")) or (YEREL / "veri" / "Kurgu" / "ffmpeg").exists()
    d["nvidia"] = bool(shutil.which("nvidia-smi"))
    return d


def a_gereksinim(d: dict) -> None:
    eksik = [k for k in ("python", "git", "node", "npm") if not d[k]]
    if eksik:
        say("Eksik önkoşullar: " + ", ".join(eksik))
        say("  Python 3.10+  → https://www.python.org/downloads/  (kurarken 'Add to PATH' kutusunu işaretle)")
        say("  Node.js 20+   → https://nodejs.org/")
        say("  Git           → https://git-scm.com/download/win")
        say("  Bunları kurup Başlat.cmd'yi tekrar çalıştır. (Yönetici izni gerekmeyen kurulumlar yeterli.)")
        raise SystemExit(1)
    say("  Python, Git, Node, npm: tamam" + (" · NVIDIA GPU bulundu (GPU hızlandırma isteğe bağlı, panelden)" if d["nvidia"] else " · GPU bulunamadı (işlemci kullanılır; foto iyileştirme yavaş olur)"))


def a_kurgu(yenile: bool) -> None:
    k = MANIFEST["kurgu"]
    hedef = ROOT / "kurgu"
    if yenile and hedef.exists():
        shutil.rmtree(hedef, ignore_errors=True)
    if not (hedef / "pyproject.toml").exists():
        say(f"  Kurgu indiriliyor: {k['adres']} @ {k['ref'][:8]}")
        git_cek(k["adres"], k["ref"], hedef)
    n = kopya_agaci(SISTEM / "yama" / "kurgu", hedef)
    say(f"  Kurgu hazır; {n} dosya yamalandı (EMA konuşma entegrasyonu, belgeler).")
    kurgu_eklenti(hedef)


def kurgu_eklenti(hedef: Path) -> None:
    """YSTCore eklentisini (görsel, seslendirme, ara sahne düğmeleri) Kurgu'ya uygular. Kurgu'nun sürümü köklü değiştiyse yama uygulanamaz: bu HATA DEĞİLDİR,
    kurulum sürer, Kurgu düz haliyle çalışır ve bu özellikler panelin kendi araçlarından kullanılır (panel bunu proje ekranında söyler)."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("yst_kurgu_yama", SISTEM / "kurulum" / "kurgu_yama.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    r = m.otomatik(hedef)
    if r["durum"] == "tamam":
        say(f"  Kurgu eklentisi: {len(r['eklenen'])} ek uygulandı, {len(r['zaten'])} zaten vardı, {len(r['kopyalanan'])} dosya kopyalandı (görsel, seslendirme, ara sahne).")
    elif r["durum"] == "kapali":
        say("  Kurgu eklentisi kapalı (düz Kurgu): " + r["neden"])
    else:
        say("  BİLGİ: Kurgu'nun bu sürümüne stüdyo eklentisi uygulanamadı; Kurgu düz haliyle çalışacak.\n    " + r["neden"].replace(chr(10), chr(10) + "    ")
            + "\n    Görsel/seslendirme/ara sahne panelin kendi araçlarından kullanılır; ayrıntı: docs/KULLANIM.md → Kurgu'nun içinde.")


def a_venv(d: dict) -> None:
    if not PY.exists():
        say("  sanal ortam oluşturuluyor (.venv)")
        calistir([sys.executable, "-m", "venv", VENV])
    calistir([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    # PyTorch ve ona bağlı ağır paketler (EMA, Real-ESRGAN çalıştırıcı, ses klonlama, derinlik) burada KURULMAZ: paneli açmak için gerekmiyorlar.
    # Panel açılınca arka planda kurulur (sistem/araclar/arka_indirme.py): panel neyin indiğini, neyin sırada olduğunu ve ne işe yaradığını gösterir.
    # NVIDIA ekran kartı varsa GPU hızlandırma (CUDA, ~2,7 GB) ayrıca İSTEĞE BAĞLIDIR (panel önerir).
    if d["nvidia"]:
        say("  NVIDIA ekran kartı bulundu: GPU hızlandırma panelden isteğe bağlı kurulabilir")
    say("  Python paketleri (çekirdek) kuruluyor")
    calistir([PY, "-m", "pip", "install", "-q", "-r", SISTEM / "kurulum" / "gereksinim.txt"])
    calistir([PY, "-m", "pip", "install", "-q", "-e", ROOT / "kurgu"])


def a_npm() -> None:
    npm = shutil.which("npm") or "npm"
    calistir([npm, "ci", "--no-audit", "--no-fund"], cwd=ROOT)
    # Remotion render için Chrome Headless Shell (~130 MB) gerekir; ilk render'da sürpriz indirme olmasın diye şimdi indir.
    say("  Remotion tarayıcısı (Chrome Headless Shell) hazırlanıyor")
    calistir(["node", ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js", "browser", "ensure"], cwd=ROOT)


def a_skills(yenile: bool) -> None:
    kok = YEREL / "kaynak"
    kaynaklar = MANIFEST["kaynaklar"]
    for kid, m in kaynaklar.items():
        if m["tur"] == "git":
            git_cek(m["adres"], m["ref"], kok / kid)
    sayac = 0
    for e in MANIFEST["skill_dosyalari"]:
        m = kaynaklar[e["kaynak"]]
        src = (kok / e["kaynak"] / e["yol"]) if m["tur"] == "git" else (ROOT / "node_modules" / m["adres"] / m.get("kok", "dist/skills") / e["yol"])
        if not src.is_file():
            say(f"  UYARI kaynak yok, atlandı: {e['hedef']}")
            continue
        d = ROOT / e["hedef"]
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, d)
        sayac += 1
    y = kopya_agaci(SISTEM / "yama" / "skills", ROOT / ".claude" / "skills")
    say(f"  skill'ler hazır: {sayac} dosya kaynak depolardan, {y} dosya bizim yama")


def a_ffmpeg() -> None:
    sys.path.insert(0, str(SISTEM / "araclar"))
    import yol
    yol.hazirla()  # önceki bir kurulumdan kalan ffmpeg'i de say
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        say("  ffmpeg var")
        return
    say("  ffmpeg bulunamadı; Kurgu'nun kendi indiricisi çalışıyor (yönetici izni gerekmez)")
    env = dict(os.environ, KURGU_DATA=str(YEREL / "veri"))
    calistir([VENV / ("Scripts/kurgu.exe" if os.name == "nt" else "bin/kurgu"), "setup-ffmpeg"], env=env)
    yol.hazirla()
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        say("  UYARI: ffmpeg indirildi ama bulunamadı; panel açılışta kendi klasöründen kullanır (sistem/ortam/yerel/veri/)")


def a_config() -> None:
    """Kurgu'nun kullanıcı ayarı depo İÇİNDE (sistem/ortam/kurgu-ayar/): başka bilgisayarda %APPDATA% ayarına dokunmaz."""
    node_mod = (ROOT / "node_modules").as_posix()
    kurgu_exe = str(VENV / ("Scripts/kurgu.exe" if os.name == "nt" else "bin/kurgu"))
    cfg = {
        "render_adaptors": {
            "remotion": ["node", f"{node_mod}/@remotion/cli/remotion-cli.js", "render", "src/index.ts", "{unit}", "{out}", "--log=warn"],
            "hyperframes": ["node", f"{node_mod}/hyperframes/dist/cli.js", "render", ".", "--composition", "{unit}.html",
                            "--output", "{out}", "--fps", "{fps}", "--quality", "delivery", "--quiet"],
        },
        "on_send": [kurgu_exe, "wake", "claude", "{dir}", "{seq}"],
    }
    d = ORTAM / "kurgu-ayar"
    d.mkdir(exist_ok=True)
    (d / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    say("  Kurgu ayarı yazıldı (sistem/ortam/kurgu-ayar/config.json): Remotion ve HyperFrames render adaptörleri bu klasöre bağlı")


def a_kimlik() -> None:
    """Kimlik dosyaları kullanıcıya özeldir ve depoda YOKTUR: nötr şablondan oluşturulur (var olana dokunulmaz)."""
    try:
        sys.path.insert(0, str(SISTEM / "araclar"))
        import kimlik_sablon
        yeni = kimlik_sablon.kur()
        say("  Kimlik dosyaları: " + (f"{len(yeni)} dosya şablondan oluşturuldu (Ayarlar → Kimlik'ten doldur)" if yeni else "zaten var, dokunulmadı"))
    except Exception as e:  # noqa: BLE001
        say(f"  UYARI: kimlik şablonu kurulamadı ({type(e).__name__}); panel açılışında yeniden denenir.")


def a_gizle() -> None:
    """Windows Gezgini'nde kök dizini sade tut: teknik dosyalar GİZLİ özniteliğe alınır (Gezgini'nde 'Gizli öğeleri göster' ile görünür)."""
    if os.name != "nt":
        return
    for ad in (".git", ".gitignore", ".gitattributes", ".claude", ".mcp.json", "node_modules", "package.json", "package-lock.json"):
        p = ROOT / ad
        if p.exists():
            subprocess.run(["attrib", "+h", str(p)], capture_output=True)


def a_son() -> None:
    """Kurulum bitti: işareti yaz, bu klasörün yerini ve Python sürümünü kaydet (taşıma onarımı bunlara bakar)."""
    YEREL.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SISTEM / "araclar"))
    sys.path.insert(0, str(SISTEM / "arsiv"))
    try:
        import konum as K
        import arsiv as A
        K.damga_yaz({"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"})
        c = A.baglan()
        K.studyo_guncelle(c)
        c.close()
    except Exception as e:  # noqa: BLE001
        say(f"  UYARI: konum kaydı yazılamadı ({e}); sonraki açılışta Başlat.cmd yeniden dener")
    (YEREL / "kurulum.ok").write_text(json.dumps({"tarih": time.strftime("%Y-%m-%d %H:%M:%S"), "kok": str(ROOT)}, ensure_ascii=False), encoding="utf-8")


def ortam() -> dict:
    """Her şeyin depo içinde kalması için süreç ortamı (Başlat.cmd ile aynı): pip/npm/Hugging Face indirmeleri ve önbellekleri stüdyo klasörüne yazılır."""
    e = dict(os.environ)
    sys.path.insert(0, str(SISTEM / "araclar"))
    import yol
    e.update(yol.kapsama())   # tek klasör kuralı
    return e


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = set(sys.argv[1:])
    d = a_kontrol()
    if "--kontrol" in args:
        for k, v in d.items():
            say(f"{k:8} {'tamam' if v else 'YOK'}")
        say(f"kurulum {'tamam' if (YEREL / 'kurulum.ok').exists() else 'yapılmadı'}")
        return 0
    yenile = "--yenile" in args
    os.environ.update(ortam())   # tüm alt süreçler (pip, npm, node, git) önbellekleri klasör içine yazar
    toplam = 7
    say("YSTCoreStudio kurulumu: tamamen yerel, hesapsız. Süre internet hızına bağlıdır. Ağır parçalar (PyTorch, yapay zekâ paketleri, modeller) panel açıldıktan sonra ARKA PLANDA iner; panelde ne indiği ve sırada neyin olduğu görünür.")
    try:
        sys.path.insert(0, str(SISTEM / "araclar"))
        import donanim
        pl = donanim.ilk_kurulum()
        say(f"Panel açılana kadar yaklaşık {pl['kurulumda_gb']} GB iner (+ panel açılınca arka planda {pl['arka_plan_gb']} GB). Boş disk: {pl['bos_disk_gb']} GB.")
        for x in pl["parcalar"]:
            say(f"  - {x['ad']}: ~{x['gb']} GB" + ("" if x["zaman"] == "kurulumda" else f" ({x['zaman']})"))
        if not pl["disk_yeterli"]:
            say(f"HATA: disk yetersiz: en az {pl['toplam_gb']} GB (önerilen {pl['onerilen_bos_disk_gb']} GB) boş yer gerekir. Yer açıp Başlat'ı tekrar çalıştır.")
            return 1
    except ImportError:
        pass
    adim(1, toplam, "Önkoşullar")
    a_gereksinim(d)
    adim(2, toplam, "Kurgu (kendi deposundan) + yama")
    a_kurgu(yenile)
    adim(3, toplam, "Python ortamı (.venv)")
    a_venv(d)
    adim(4, toplam, "Remotion / HyperFrames (npm)")
    a_npm()
    adim(5, toplam, "ffmpeg")
    a_ffmpeg()
    adim(6, toplam, "Üçüncü taraf skill'ler (kendi depolarından) + yama")
    a_skills(yenile)
    adim(7, toplam, "Ayarlar")
    a_config()
    a_kimlik()
    a_gizle()
    a_son()
    say(f"  (süre: {int(time.time() - _ADIM['t'])} sn)")
    gecen = int(time.time() - _ADIM["bas"])
    say(f"\nToplam kurulum süresi: {gecen // 60} dk {gecen % 60} sn")
    say("\nKurulum bitti. PyTorch, yapay zekâ paketleri ve modeller panel açılınca arka planda iner (panel gösterir). Başlat.cmd ile paneli aç.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
