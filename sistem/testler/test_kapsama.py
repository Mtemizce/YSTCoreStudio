"""Tek klasör kuralı: stüdyonun indirdiği/ürettiği her şey klasörün içinde kalır (yol.kapsama), eski klasör dışı modeller klasöre kopyalanır (yol.hf_tasi),
artıklar kaldir.py ile bulunup yalnızca stüdyoya özgü olanlar silinir. Ağ gerekmez; gerçek kullanıcı klasörlerine dokunmaz."""
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def yukle(ad, yol):
    sp = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


yol = yukle("yol_t", R / "sistem" / "araclar" / "yol.py")
kal = yukle("kaldir_t", R / "sistem" / "kurulum" / "kaldir.py")
tmp = Path(tempfile.mkdtemp(prefix="yst-kapsama-"))
try:
    # --- kapsama: her yol stüdyo klasörünün içinde
    e = yol.kapsama()
    yollar = {k: v for k, v in e.items() if os.sep in v or "/" in v}
    ok({"HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME", "npm_config_cache", "KURGU_DATA", "KURGU_MODELS", "KURGU_CONFIG"} <= set(yollar), "kapsama: Hugging Face, torch, XDG, npm, Kurgu verisi/modelleri/ayarı yönlendirilir")
    ok(all(Path(v).resolve().is_relative_to(R.resolve()) for v in yollar.values()), "kapsama: yönlendirilen HER yol stüdyo klasörünün içinde")
    ok(Path(e["HF_HOME"]).resolve() == (R / "sistem" / "ortam" / "modeller" / "hf").resolve(), "kapsama: HF_HOME = sistem/ortam/modeller/hf (derinlik modeliyle aynı yer)")
    ok(e["PIP_NO_CACHE_DIR"] == "1", "kapsama: pip önbelleği kapalı (klasör şişmez)")
    ok(e.get("HYPERFRAMES_BROWSER_PATH") is None or Path(e["HYPERFRAMES_BROWSER_PATH"]).resolve().is_relative_to(R.resolve()), "kapsama: HyperFrames tarayıcısı varsa klasördeki Remotion Chrome'u")
    ok("ev_yonlendir.cjs" in e.get("NODE_OPTIONS", "") and Path(e["YST_NODE_EV"]).resolve().is_relative_to(R.resolve()), "kapsama: HyperFrames ev dizini ön yükleyicisi (NODE_OPTIONS) klasöre yönlendirilmiş")
    node = shutil.which("node")
    if node:
        import subprocess
        sahte = tmp / "ev_deneme"
        zorla = {**os.environ, **e, "YST_NODE_EV": str(sahte)}
        diger = subprocess.run([node, "-e", "console.log(require('os').homedir())"], env=zorla, capture_output=True, text=True).stdout.strip()
        ok(diger == str(Path.home()), "ön yükleyici: hyperframes olmayan Node süreçlerinin ev dizinine dokunmaz")
        os.makedirs(tmp / "x" / "node_modules" / "hyperframes" / "dist", exist_ok=True)
        (tmp / "x" / "node_modules" / "hyperframes" / "dist" / "cli.js").write_text("console.log(require('os').homedir())", encoding="utf-8")
        hf = subprocess.run([node, str(tmp / "x" / "node_modules" / "hyperframes" / "dist" / "cli.js")], env=zorla, capture_output=True, text=True).stdout.strip()
        ok(Path(hf).resolve() == sahte.resolve(), "ön yükleyici: hyperframes sürecinin ev dizini stüdyo klasörüne çevrilir")
    env = {"PATH": os.environ.get("PATH", "")}
    yol.hazirla(env)
    ok(env.get("HF_HOME") == e["HF_HOME"], "hazirla(): verilen ortam sözlüğüne de kapsama uygulanır")
    # çağıran ortam komut dosyaları ve başlatıcılar kapsamayı kullanır (elle yazılmış ortam sözlükleri geri gelmesin)
    for dosya in ("sistem/panel/panel.py", "sistem/kurulum/kurulum.py", "sistem/kurulum/baslat.py"):
        ok("kapsama()" in (R / dosya).read_text(encoding="utf-8"), f"{dosya}: ortamı yol.kapsama() ile kuruyor")

    # --- hf_tasi: sahte ev + sahte stüdyo klasörü
    ev = tmp / "ev"
    hub = ev / ".cache" / "huggingface" / "hub"
    for ad in ("models--wite-tech--pocket-tts-turkish", "models--Systran--faster-whisper-small", "models--baska--ilgisiz-model"):
        (hub / ad / "snapshots" / "x").mkdir(parents=True)
        (hub / ad / "snapshots" / "x" / "w.bin").write_bytes(b"1234")
    yol.ORTAM = tmp / "studyo" / "sistem" / "ortam"
    eski_home = Path.home
    Path.home = staticmethod(lambda: ev)
    try:
        t = yol.hf_tasi()
        ok(sorted(t) == ["models--Systran--faster-whisper-small", "models--wite-tech--pocket-tts-turkish"], "hf_tasi: yalnızca stüdyo modelleri kopyalandı (ilgisiz model alınmadı)")
        yeni = yol.ORTAM / "modeller" / "hf" / "hub"
        ok((yeni / "models--wite-tech--pocket-tts-turkish" / "snapshots" / "x" / "w.bin").read_bytes() == b"1234", "hf_tasi: dosyalar birebir kopyalandı")
        ok(not (yeni / "models--baska--ilgisiz-model").exists(), "hf_tasi: ilgisiz model klasöre girmedi")
        ok((hub / "models--wite-tech--pocket-tts-turkish").exists(), "hf_tasi: eski konuma dokunulmadı (kopya, taşıma değil)")
        ok(yol.hf_tasi() == [], "hf_tasi: ikinci çalıştırma idempotent (tekrar kopyalamaz)")
    finally:
        Path.home = eski_home

    # --- kaldir: tarama + silme
    (ev / ".cache" / "hyperframes" / "chrome").mkdir(parents=True)
    (ev / ".cache" / "hyperframes" / "chrome" / "c.exe").write_bytes(b"x" * 100)
    (ev / ".cache" / "ezdxf").mkdir(parents=True)
    (ev / ".cache" / "ezdxf" / "f.json").write_text("{}", encoding="utf-8")
    yerel = tmp / "yerel"
    (yerel / "Kurgu" / "ffmpeg").mkdir(parents=True)
    (yerel / "Kurgu" / "ffmpeg" / "ffmpeg.exe").write_bytes(b"y" * 50)
    (yerel / "pip").mkdir()
    (yerel / "pip" / "onbellek").write_bytes(b"z")
    o = kal.tara(ev, yerel)
    ids = {x["id"]: x for x in o}
    ok({"hf-pocket", "hf-whisper", "hyperframes", "ezdxf", "kurgu-veri"} <= set(ids) and "hf-ema" not in ids, "kaldir: klasör dışı stüdyo artıkları bulundu, olmayanlar listelenmedi")
    ok(ids["hf-pocket"]["tur"] == "ozgu" and ids["hyperframes"]["tur"] == "ozgu" and ids["ezdxf"]["tur"] == "paylasilan" and ids["kurgu-veri"]["tur"] == "paylasilan",
       "kaldir: özgü / paylaşılan ayrımı (ezdxf ve Kurgu verisi başka programlarla paylaşılabilir)")
    ok(not any(str(yerel / "pip") in x["yol"] for x in o), "kaldir: pip/npm ortak önbelleklerine hiç bakmaz")
    silinen = kal.sil(o, None)
    ok(len(silinen) == 3 and not (ev / ".cache" / "hyperframes").exists() and not (hub / "models--wite-tech--pocket-tts-turkish").exists(), "kaldir --sil: yalnızca stüdyoya özgü olanlar silindi")
    ok((ev / ".cache" / "ezdxf" / "f.json").exists() and (yerel / "Kurgu" / "ffmpeg" / "ffmpeg.exe").exists(), "kaldir --sil: paylaşılabilir olanlara dokunulmadı")
    ok((hub / "models--baska--ilgisiz-model").exists(), "kaldir --sil: başka programların Hugging Face modeli yerinde")
    ok(Path(R / "sistem").is_dir(), "kaldir: stüdyo klasörünün kendisini silmez")
    # soru modu: hayır deyince silmez
    (ev / ".cache" / "hyperframes").mkdir(parents=True)
    (ev / ".cache" / "hyperframes" / "a").write_bytes(b"1")
    ogeler = [x for x in kal.tara(ev, yerel) if x["id"] == "hyperframes"]
    ok(kal.sil(ogeler, lambda _s: "h") == [] and (ev / ".cache" / "hyperframes").exists(), "kaldir: 'hayır' cevabında silmez")
    ok(len(kal.sil(ogeler, lambda _s: "e")) == 1, "kaldir: 'evet' cevabında siler")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{S[0]} başarılı, {S[1]} başarısız")
sys.exit(1 if S[1] else 0)
