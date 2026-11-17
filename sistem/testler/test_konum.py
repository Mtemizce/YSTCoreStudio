import json, os, shutil, sqlite3, sys, tempfile, random
from pathlib import Path
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "arsiv"))
sys.path.insert(0, str(R / "sistem" / "araclar"))
import arsiv as A
import analiz as Z
import konum as K

tmp = Path(tempfile.mkdtemp(prefix="konum-test-"))
A.DIR = tmp / "db"; A.DB = A.DIR / "arsiv.db"; A.AYAR = A.DIR / "ayar.json"; A.ILERLEME = A.DIR / "ilerleme.json"
random.seed(1)
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def foto(p, w=1600, h=1000):
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (w, h), (150, 170, 190)); d = ImageDraw.Draw(im)
    for _ in range(80):
        x, y = random.randint(0, w), random.randint(0, h)
        d.rectangle([x, y, x + random.randint(10, 200), y + random.randint(10, 150)], fill=tuple(random.randint(20, 230) for _ in range(3)), outline=(0, 0, 0))
    im.save(p, quality=90)


# ---------- 1) v1 (eski şema) veritabanından göç
A.DIR.mkdir(parents=True)
eski_ark = tmp / "eski_arsiv"
for i in range(3):
    foto(eski_ark / "Proje X" / "2021" / f"f{i}.jpg")
c = sqlite3.connect(A.DB)
c.executescript("""
CREATE TABLE dosya (id INTEGER PRIMARY KEY, yol TEXT UNIQUE NOT NULL, klasor TEXT, ad TEXT, uzanti TEXT, tur TEXT, boyut INTEGER, mtime REAL, yil INTEGER, ay INTEGER, tarih_kaynagi TEXT, genislik INTEGER, yukseklik INTEGER, sure REAL, etiket TEXT, goruldu REAL);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE analiz (yol TEXT PRIMARY KEY, boyut INTEGER, mtime REAL, keskinlik REAL, parlaklik REAL, dhash TEXT, kopya_of TEXT, oto_kullanilabilir INTEGER, oto_puan REAL, oto_neden TEXT, oto_tarih TEXT, c_kullanilabilir INTEGER, c_puan REAL, c_neden TEXT, asama TEXT, konu TEXT, aciklama TEXT, etiketler TEXT, c_tarih TEXT);
CREATE TABLE proje_notu (klasor TEXT PRIMARY KEY, ozet TEXT, tur TEXT, tarih TEXT);
CREATE VIRTUAL TABLE dosya_fts USING fts5(etiket, tokenize='unicode61');
""")
for i in range(3):
    st = (eski_ark / "Proje X" / "2021" / f"f{i}.jpg").stat()
    c.execute("INSERT INTO dosya(id,yol,klasor,ad,uzanti,tur,boyut,mtime,yil,genislik,yukseklik,etiket,goruldu) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (100 + i, f"Proje X/2021/f{i}.jpg", "Proje X/2021", f"f{i}.jpg", ".jpg", "foto", st.st_size, st.st_mtime, 2021, 1600, 1000, "proje x villa", 1.0))
    c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)", (100 + i, "proje x villa"))
    c.execute("INSERT INTO analiz(yol,boyut,mtime,oto_kullanilabilir,oto_puan,oto_neden) VALUES (?,?,?,?,?,?)", (f"Proje X/2021/f{i}.jpg", st.st_size, st.st_mtime, 1, 9.0, ""))
c.execute("INSERT INTO proje_notu VALUES ('Proje X','not','villa','2024-01-01')")
c.commit(); c.close()
A.AYAR.write_text(json.dumps({"kok": str(eski_ark), "etiket": "TEST", "seri": 1234, "alt": "x"}), encoding="utf-8")
c = A.baglan()
ok(c.execute("PRAGMA user_version").fetchone()[0] == K.SEMA_SURUMU, "şema sürümü yükseldi")
ok(c.execute("SELECT COUNT(*) FROM dosya WHERE id BETWEEN 100 AND 102 AND kok_id=1").fetchone()[0] == 3, "dosya kayıtları ve kimlikleri korundu")
ok(c.execute("SELECT COUNT(*) FROM analiz WHERE kok_id=1").fetchone()[0] == 3, "analiz kayıtları taşındı")
ok(c.execute("SELECT COUNT(*) FROM proje_notu WHERE kok_id=1").fetchone()[0] == 1, "proje notu taşındı")
ok(len(c.execute("SELECT rowid FROM dosya_fts WHERE dosya_fts MATCH 'villa'").fetchall()) == 3, "FTS kaydı yaşıyor")
ok(A.kok_coz(c=c) == eski_ark, f"eski ayar.json yolu bu bilgisayarın kaydına dönüştü: {A.kok_coz(c=c)}")
ok(not any("Users" in str(v) for r in c.execute("SELECT yol FROM dosya") for v in r), "dosya tablosunda mutlak yol yok")

# ---------- 2) çoklu arşiv + kopyalama
ark2 = tmp / "ikinci"
for i in range(3):
    foto(ark2 / "Ofis" / "2024" / f"o{i}.jpg")
A.ayarla(str(ark2), "ofis")
s = A.tara(yazdir=lambda *_: None)
ok(s["arsiv"] == "arsiv, ofis", f"iki arşiv de tarandı: {s['arsiv']}")
kid_ofis = c.execute("SELECT id FROM kok WHERE ad='ofis'").fetchone()[0]
ok(len(A.ara(kok_id=kid_ofis)) == 3 and len(A.ara()) == 6, "kök filtresi çalışıyor")
Z.oto()
hedef = tmp / "proje_kaynak"
ids = [r["id"] for r in A.ara(limit=100)]
k = A.kopyala(ids, str(hedef))
ok(k["kopyalanan"] == 6, f"iki arşivden kopyalandı: {k['kopyalanan']}")

# ---------- 3) arşiv başka yere taşındı: eski yol yok
tas = tmp / "yeni_yer" / "ofis_arsivi"
tas.parent.mkdir()
shutil.move(str(ark2), str(tas))
K._onbellek.clear()
ok(A.kok_coz(kid_ofis, c) is None, "taşınan arşiv bulunamadı (kullanıcıdan istenir)")
ok(K.kok_coz(c, kid_ofis, True)["not"].startswith("bu bilgisayarda bulunamadı"), "kullanıcıya yol gösteren mesaj")
s = A.tara(yazdir=lambda *_: None)
ok("atlanan" in s and c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid_ofis,)).fetchone()[0] == 3, "bağlı olmayan arşivin kayıtları SİLİNMEDİ, tarama diğerine devam etti")
# yanlış klasör gösterilirse reddet
yanlis = tmp / "alakasiz"; foto(yanlis / "baska.jpg")
try:
    A.ayarla(str(yanlis), "ofis"); ok(False, "yanlış klasör reddedilmeli")
except ValueError as e:
    ok("benzemiyor" in str(e), "yanlış klasör reddedildi")
r = A.ayarla(str(tas), "ofis")
ok(r["yol"] == str(tas), "doğru yeni yol kabul edildi")
K._onbellek.clear()
s = A.tara(yazdir=lambda *_: None)
ok(c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid_ofis,)).fetchone()[0] == 3 and s.get("silinen_kayit") == 0, "kayıtlar aynı kaldı (göreli yol sayesinde), silinen yok")
ok(Z.oto()["islenen"] == 0, "analiz yeniden yapılmadı (dosya aynı)")

# ---------- 4) başka bilgisayar simülasyonu
os.environ["YST_MAKINE"] = "baska-pc"
K._onbellek.clear()
z = K.kok_coz(c, kid_ofis, True)
ok(z["yol"] == tas and z["yontem"] == "baska-bilgisayar-yolu", f"yeni bilgisayarda aynı yol geçerliyse otomatik buldu ({z['yontem']})")
ok(c.execute("SELECT COUNT(*) FROM kok_yol WHERE kok_id=?", (kid_ofis,)).fetchone()[0] == 2, "bu bilgisayarın kaydı eklendi")
# ortam değişkeni geçersiz kılar
alt = tmp / "env_yeri"; shutil.copytree(tas, alt)
os.environ["YST_OFIS"] = str(alt)
K._onbellek.clear()
z = K.kok_coz(c, kid_ofis, True)
ok(z["yol"] == alt and z["yontem"] == "ortam-degiskeni", "YST_OFIS ortam değişkeni önceliklidir")
del os.environ["YST_OFIS"]
del os.environ["YST_MAKINE"]

# ---------- 5) bulutta-yalnızca öznitelik
class _S: st_file_attributes = 0x400000
class _N: st_file_attributes = 0x20
ok(K.bulutta_mi(_S()) and not K.bulutta_mi(_N()), "bulutta-yalnızca dosya tespiti")
ok(K.tur_tespit(chr(92).join(["C:", "Users", "x", "Google Drive", "Arsiv"]))["tur"] == "bulut-esitleme", "Google Drive klasörü tanındı")  # yol parçalı: paket taraması gerçek yol sanmasın
ok(os.name != "nt" or K.tur_tespit(r"\\NAS\paylasim\arsiv")["tur"] == "ag", "ağ paylaşımı tanındı (UNC yolu yalnızca Windows'ta anlamlıdır)")

# ---------- 6) gözat
g = K.gozat("")
ok(len(g["girdiler"]) >= 1, f"gözat: sürücüler listelendi ({len(g['girdiler'])})")
g = K.gozat(str(tmp))
ok(any(x["ad"] == "yeni_yer" for x in g["girdiler"]) and g["ust"], "gözat: alt klasörler listelendi")
# ---------- 7) kök silme dosyalara dokunmaz
n = K.kok_sil(c, kid_ofis)
ok(n == 3 and (tas / "Ofis" / "2024" / "o0.jpg").exists(), "kök silindi, dosyalar yerinde")
print("SONUÇ: %d tamam, %d hata" % tuple(S))
shutil.rmtree(tmp, ignore_errors=True)
