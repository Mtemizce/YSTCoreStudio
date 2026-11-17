import sys, importlib.util, os, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
ok = bad = 0
def t(ad, c):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("BAŞARISIZ:", ad)
def yukle(ad, yol):
    sp = importlib.util.spec_from_file_location(ad, yol); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

B = yukle("bil", R / "sistem" / "araclar" / "bilesen.py")
d = B.durum()
t("tüm bileşenler listelenir", set(d["bilesenler"]) == {"realesrgan", "whisper", "ema", "klon", "zimage", "derinlik", "rclone", "render", "gpu"})
t("donanim kataloğuyla aynı kimlikler", set(d["bilesenler"]) == set(yukle("don", R / "sistem" / "araclar" / "donanim.py").KATALOG))
t("whisper small temel (kaldırılamaz) olarak işaretli", d["bilesenler"]["whisper"]["secenekler"]["small"]["temel"])
# kurulu olup olmadığı makineye bağlıdır: durum, gerçek paketin varlığıyla tutarlı olmalı
PAKET = importlib.util.find_spec("pocket_tts_turkish") is not None
t("klon durumu gerçek kurulumla tutarlı (kurulu ise paket var; model arka planda inerken paket var, model yok olabilir)", (not d["bilesenler"]["klon"]["secenekler"]["pocket-tr"]["kurulu"]) or PAKET)
t("boyut alanı sayı", isinstance(d["bilesenler"]["klon"]["secenekler"]["pocket-tr"]["boyut_mb"], (int, float)))
for bil in ("realesrgan", "ema", "render"):
    try: B.kaldir(bil); t(f"temel {bil} kaldırılamaz", False)
    except ValueError: t(f"temel {bil} kaldırılamaz", True)
try: B.kaldir("whisper", "small"); t("whisper small korunur", False)
except ValueError: t("whisper small korunur", True)
try: B.kaldir("whisper", "../../etc"); t("whisper geçersiz ad reddedilir", False)
except ValueError: t("whisper geçersiz ad reddedilir", True)
try: B.kaldir("bilinmeyen"); t("bilinmeyen bileşen reddedilir", False)
except ValueError: t("bilinmeyen bileşen reddedilir", True)
try: B.kur("bilinmeyen"); t("bilinmeyen kurulum reddedilir", False)
except ValueError: t("bilinmeyen kurulum reddedilir", True)
try: B.kur("whisper", "x; rm -rf"); t("whisper kurulum adı beyaz liste", False)
except ValueError: t("whisper kurulum adı beyaz liste", True)
try: B.kur("render"); t("render kurulamaz", False)
except ValueError: t("render kurulamaz", True)
# eşzamanlı iş engeli
B.IS["var"] = True
t("iş sürerken ikinci kurulum reddedilir", B.kur("derinlik").get("ok") is False)
try: B.kaldir("derinlik"); t("iş sürerken kaldırma reddedilir", False)
except ValueError: t("iş sürerken kaldırma reddedilir", True)
B.IS["var"] = False
# yalnızca ilgili bileşenin dosyaları: önbellek silme yolu kapsamı
t("silme yolu HF önbelleği içinde", str(B._repo_dizin("Systran/faster-whisper-tiny")).replace("\\", "/").endswith("models--Systran--faster-whisper-tiny"))

# pocket adaptörü
sys.path.insert(0, str(R / "sistem"))
import importlib
P = importlib.import_module("tts.pocket").MOTOR
t("pocket atıf gerektirir ve atıf metni var", P.atif_gerekir and "CC-BY-4.0" in P.atif and "wite-tech" in P.atif)
t("pocket klon + ses + duygu destekler", all(P.desteklenen[k] for k in ("klon", "ses", "duygu")))
t("pocket hazır durumu paketin varlığıyla tutarlı", (P.hazir_mi() is None) == PAKET)
class S:  # sahte model: yalnızca rıza/ses doğrulaması
    def voice_from_file(self, y): return "V"
P._tts = S()
try: P._ses({"klon": "x.wav"}, {}, "."); t("olmayan klon örneği reddedilir (rıza kapısı motorda yok)", False)
except RuntimeError as e: t("olmayan klon örneği reddedilir (rıza kapısı motorda yok)", "bulunamadı" in str(e) and "rıza" not in str(e))
try: P._ses({"klon": "yok.wav", "klon_riza": True}, {}, "."); t("olmayan örnek reddedilir", False)
except RuntimeError as e: t("olmayan örnek reddedilir", "bulunamadı" in str(e))
try: P._ses({"ses": "yok"}, {}, "."); t("bilinmeyen ses reddedilir", False)
except RuntimeError as e: t("bilinmeyen ses reddedilir", "bilinmeyen" in str(e))
t("varsayılan ses female_1", P._ses({}, {}, ".") == "female_1")
ornek = Path(os.environ.get("TEMP", ".")) / "yst_klon_deneme.wav"; ornek.write_bytes(b"RIFF")
t("klon örneği kabul edilir (plan düzeyi, klon_riza gerekmez)", P._ses({}, {"klon": str(ornek)}, ".") == "V")
ornek.unlink()
# HF önbelleği Linux/macOS düzeni: ortak hub/blobs + snapshots/ altında sembolik bağlar (Windows'ta sembolik bağ izni yoksa atlanır)
import tempfile, shutil
ev = Path(tempfile.mkdtemp(prefix="yst-hf-"))
try:
    hub = ev / "hub"
    (hub / "blobs").mkdir(parents=True)
    (hub / "blobs" / "abc123").write_bytes(b"x" * 2_000_000)
    snap = hub / "models--a--b" / "snapshots" / "rev1"
    snap.mkdir(parents=True)
    os.symlink(hub / "blobs" / "abc123", snap / "model.safetensors")
    SYM = True
except OSError:
    SYM = False
if SYM:
    t("HF boyutu sembolik bağı izler (ortak blobs)", B._repo_boyut("a/b", ev) == 2_000_000)
    t("HF kurulu: model dosyası snapshots altında aranır", B._repo_kurulu("a/b", ev))
    (hub / "blobs" / "yarim.incomplete").write_bytes(b"y" * 1000)
    t("ilerleme: yarım indirme (.incomplete) boyuta eklenir", B._repo_boyut("a/b", ev) == 2_001_000)
    (hub / "blobs" / "yarim.incomplete").unlink()
    n = B._boyut_sil(B._repo_dizin("a/b", ev))
    t("kaldır ortak blob'u da siler (başka repo kullanmıyorsa)", n == 2_000_000 and not (hub / "blobs" / "abc123").exists())
shutil.rmtree(ev, ignore_errors=True)
print(f"{ok} başarılı, {bad} başarısız")
