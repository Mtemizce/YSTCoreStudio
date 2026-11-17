"""Arşiv kütüphanesi: Resim / Video / Müzik / Dosya kategorileri, kullanıcının kendi müzik arşivi, adla bulma ve projeye ekleme. Hermetik: geçici arşiv + geçici dizin."""
import importlib.util
import io
import json
import contextlib
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "araclar"))
import yol  # noqa: E402

yol.hazirla()
ok = bad = 0


def t(ad, c):
    global ok, bad
    if c:
        ok += 1
    else:
        bad += 1
        print("BAŞARISIZ:", ad)


sp = importlib.util.spec_from_file_location("arsiv_t", R / "sistem" / "arsiv" / "arsiv.py")
A = importlib.util.module_from_spec(sp)
sp.loader.exec_module(A)
tmp = Path(tempfile.mkdtemp(prefix="yst_arsiv_"))
A.DIR, A.DB, A.AYAR, A.ILERLEME = tmp / "idx", tmp / "idx" / "arsiv.db", tmp / "idx" / "ayar.json", tmp / "idx" / "ilerleme.json"

# ---------------------------------------------------------------- kullanıcının kendi müzik klasörü
muz = tmp / "Muzigim"
(muz / "Pop").mkdir(parents=True)
(muz / "Klasik").mkdir()
ffmpeg = shutil.which("ffmpeg")


def ses_yaz(yolu: Path, sn: float = 1.0, **etiket):
    if ffmpeg and etiket:
        meta = sum((["-metadata", f"{k}={v}"] for k, v in etiket.items()), [])
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={sn}", *meta, str(yolu)], check=True)
        return
    with wave.open(str(yolu), "wb") as w:   # ffmpeg yoksa etiketsiz wav
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * int(8000 * sn))


ses_yaz(muz / "Pop" / "Tarkan - Şımarık.wav", 2.0)
ses_yaz(muz / "Pop" / "Tarkan - Kuzu Kuzu.wav", 1.0)
ses_yaz(muz / "Klasik" / "track01.mp3" if ffmpeg else muz / "Klasik" / "track01.wav", 3.0, title="Ay Işığı Sonatı", artist="Beethoven")
ses_yaz(muz / "Klasik" / "Nocturne Op9 No2.flac" if ffmpeg else muz / "Klasik" / "Nocturne Op9 No2.wav", 1.0)
(muz / "Notlar.txt").write_text("şarkı sözleri", encoding="utf-8")
from PIL import Image  # noqa: E402

Image.new("RGB", (40, 30), "red").save(muz / "kapak.png")
(muz / "klip.mp4").write_bytes(b"\0" * 2048)   # içerik okunmaz (derin tarama kapalı)

r = A.ayarla(str(muz), "muzik")
t("müzik klasörü ayrı bir arşiv olarak eklenir", r["ad"] == "muzik" and r["id"])
with contextlib.redirect_stdout(io.StringIO()):
    A.tara(yazdir=lambda *a: None)
d = A.durum()
kat = {k["ad"]: k["adet"] for k in d["kategoriler"]}
t("kategoriler: Resim / Video / Müzik / Dosya", set(kat) == {"Resim", "Video", "Müzik", "Dosya"} and kat["Müzik"] == 4 and kat["Resim"] == 1 and kat["Video"] == 1 and kat["Dosya"] == 1)

# ---------------------------------------------------------------- tür adları
t("tür adı takma adları: muzik/müzik/ses → ses, resim → foto, dosya → belge", A.tur_coz("muzik") == "ses" and A.tur_coz("Müzik") == "ses" and A.tur_coz("resim") == "foto" and A.tur_coz("Dosya") == "belge")
t("ara(--tur muzik) yalnızca müzik", {x["tur"] for x in A.ara(tur="muzik")} == {"ses"} and len(A.ara(tur="muzik")) == 4)
t("ara(--tur resim,dosya)", {x["tur"] for x in A.ara(tur="resim,dosya")} == {"foto", "belge"})

# ---------------------------------------------------------------- müzik süresi ve etiketleri
ses_satir = {x["ad"]: x for x in A.ara(tur="muzik")}
if ffmpeg and shutil.which("ffprobe"):
    t("müziğin süresi dizine yazılır", any(x["sure"] and abs(x["sure"] - 2.0) < 0.5 for x in ses_satir.values()))
    adaylar = A.bul("Ay Işığı Sonatı")
    t("dosya adı farklı olsa da başlık/sanatçı etiketiyle bulunur (track01.mp3 = Ay Işığı Sonatı)", adaylar and adaylar[0]["ad"].startswith("track01") and adaylar[0]["tam"])
    t("sanatçı etiketiyle de bulunur", any(x["ad"].startswith("track01") for x in A.bul("beethoven")))
else:
    print("(ffmpeg/ffprobe yok: süre ve etiket testleri atlandı)")

# ---------------------------------------------------------------- adla bulma
a1 = A.bul("tarkan şımarık", "muzik")
t("adla bulma: Türkçe harf/aksan farkı yok, en iyi eşleşme önce", a1 and a1[0]["ad"] == "Tarkan - Şımarık.wav" and a1[0]["tam"] and a1[0]["kategori"] == "Müzik")
t("adla bulma: BÜYÜK HARF ve ASCII yazım", A.bul("ŞIMARIK", "muzik")[0]["ad"] == "Tarkan - Şımarık.wav" and A.bul("simarik")[0]["tam"])
a2 = A.bul("Tarkan", "muzik")
t("belirsiz ifade: birden çok tam eşleşme listelenir", len([x for x in a2 if x["tam"]]) == 2)
t("gereksiz sözcükler (müzik, çalsın, arka planda) eşleşmeyi bozmaz", A.bul("arka planda Nocturne Op9 müzik çalsın", "muzik")[0]["ad"].startswith("Nocturne"))
t("olmayan şarkı → boş", A.bul("olmayan sarki adi xyz", "muzik") == [])
t("tür filtresi: müzik aramasında resim/dosya gelmez", all(x["tur"] == "ses" for x in A.bul("klasik")) )

# ---------------------------------------------------------------- projeye ekleme (CLI)
proje = tmp / "projeler" / "deneme"
proje.mkdir(parents=True)
ciktilar = {}


def cli(*args):
    eski = sys.argv
    sys.argv = ["arsiv.py", *args]
    tampon = io.StringIO()
    try:
        with contextlib.redirect_stdout(tampon):
            kod = A.main()
    finally:
        sys.argv = eski
    return kod, json.loads(tampon.getvalue())


kod, j = cli("bul", "tarkan şımarık", "--tur", "muzik", "--kopyala", str(proje))
t("net tek eşleşme → projeye kopyalanır (kaynak/ses/)", kod == 0 and j["eklenen"]["ok"] and (proje / "kaynak" / "ses" / "Tarkan - Şımarık.wav").is_file())
kay = json.loads((proje / "kaynak" / "arsiv_secim.json").read_text(encoding="utf-8"))
t("kaynak kaydı: hangi arşivden, kullanıcının kendi dosyası notu", kay["kullanici_dosyalari"][0]["arsiv"] == "muzik" and "kullanıcı" in kay["kullanici_dosyalari"][0]["not"] and kay["kullanici_dosyalari"][0]["projede"] == "kaynak/ses/Tarkan - Şımarık.wav")
t("arşivdeki orijinale dokunulmadı", (muz / "Pop" / "Tarkan - Şımarık.wav").is_file())
kod, j = cli("bul", "tarkan", "--tur", "muzik", "--kopyala", str(proje))
t("belirsiz ifade → KOPYALAMAZ, adayları verir (kullanıcıya sorulur)", kod == 3 and "eklenen" not in j and len(j["adaylar"]) == 2 and "net tek eşleşme yok" in j["not"])
sec = next(x["id"] for x in j["adaylar"] if "Kuzu" in x["ad"])
kod, j = cli("bul", "tarkan", "--tur", "muzik", "--kopyala", str(proje), "--id", str(sec))
t("aday listesinden --id ile seçilince kopyalanır", kod == 0 and (proje / "kaynak" / "ses" / "Tarkan - Kuzu Kuzu.wav").is_file())
kod, j = cli("bul", "olmayan sarki xyz", "--tur", "muzik", "--kopyala", str(proje))
t("hiç eşleşme yok → 3 ve 'kullanıcıya sor' notu", kod == 3 and "eşleşme yok" in j["not"])

# ---------------------------------------------------------------- panel/ajan bağlantısı
ek = (R / "sistem" / "panel" / "ek_api.py").read_text(encoding="utf-8")
pn = (R / "sistem" / "panel" / "panel.py").read_text(encoding="utf-8")
ix = (R / "sistem" / "panel" / "index.html").read_text(encoding="utf-8")
t("panel: kütüphane API'si ve müzik dinleme adresi", "/api/arsiv/kutuphane" in ek and "/api/arsiv/ses" in pn)
t("panel arayüzü: kategori sekmeleri, arama, dinleme, prompt'a ekle", "arsivKut" in ix and "Prompt'a ekle" in ix and "/api/arsiv/ses?id=" in ix)
cl = (R / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
ses = (R / ".claude" / "agents" / "ses-yonetmeni.md").read_text(encoding="utf-8")
t("orkestratör kuralı: prompt'ta adı geçen müzik/dosya arşivden bulunur (CLAUDE.md + ses-yönetmeni)", "arsiv.py bul" in cl and "arsiv.py bul" in ses)

shutil.rmtree(tmp, ignore_errors=True)
print(f"{ok} başarılı, {bad} başarısız")
