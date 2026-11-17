"""README topluluk bölümü (sistem/araclar/topluluk_readme.py): işaret arası değiştirme, güvenli HTML, yuvarlak profil resmi. Ağ gerekmez."""
import importlib.util
import io
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


sp = importlib.util.spec_from_file_location("topluluk_t", R / "sistem/araclar/topluluk_readme.py")
T = importlib.util.module_from_spec(sp)
sys.modules["topluluk_t"] = T
sp.loader.exec_module(T)

md = "# Başlık\n<!-- katkicilar:basla -->\neski\n<!-- katkicilar:bitis -->\nson\n<!-- sponsorlar:basla -->\nx\n<!-- sponsorlar:bitis -->\n"
yeni = T.bolum_degistir(md, "katkicilar", "YENİ")
ok("YENİ" in yeni and "eski" not in yeni and "<!-- sponsorlar:basla -->\nx\n" in yeni and yeni.startswith("# Başlık") and "son\n" in yeni, "yalnızca ilgili işaretler arası değişir, diğer bölüm ve metin korunur")
ok(T.bolum_degistir(yeni, "katkicilar", "YENİ") == yeni, "aynı içerikle tekrar çalıştırmak değişiklik üretmez (idempotent)")
try:
    T.bolum_degistir("işaret yok", "katkicilar", "x")
    yok = False
except ValueError:
    yok = True
ok(yok, "işaretler yoksa açık hata verir")

ok(T.html_olustur([], "boş metin") == "boş metin", "kimse yoksa yer tutucu metin gösterilir")
h = T.html_olustur([{"login": "ali-veli", "ad": 'Ali "Veli" <b>', "dosya": "docs/topluluk/ali-veli.png"}, {"login": "x1", "ad": "", "dosya": "docs/topluluk/x1.png"}], "")
ok('title="Ali &quot;Veli&quot; &lt;b&gt; (@ali-veli)"' in h and "<b>" not in h, "ad HTML'e güvenli yazılır (tırnak ve etiket kaçırılır)")
ok('title="@x1"' in h and 'href="https://github.com/x1"' in h and 'width="60"' in h, "adı olmayan kişide @kullanıcı başlığı, profil bağlantısı ve 60 px boyut")
ok("style=" not in h, "style özniteliği yok (GitHub zaten siler; yuvarlama resimde yapılır)")

from PIL import Image
kare = io.BytesIO()
Image.new("RGB", (300, 300), (200, 30, 30)).save(kare, "PNG")
png = T.yuvarlak(kare.getvalue(), 120)
im = Image.open(io.BytesIO(png)).convert("RGBA")
ok(im.size == (120, 120) and im.getpixel((0, 0))[3] == 0 and im.getpixel((119, 119))[3] == 0 and im.getpixel((60, 60))[3] == 255, "profil resmi daire: köşeler saydam, merkez dolu")

tmp = Path(tempfile.mkdtemp(prefix="yst-topluluk-"))
try:
    T.RESIM_DIZIN = tmp / "topluluk"
    cikti = T.isle("katkicilar", [{"login": "deneme", "ad": "Deneme Kişi", "avatar": "https://avatars.githubusercontent.com/u/1"}], indir=lambda u: kare.getvalue())
    ok((tmp / "topluluk" / "deneme.png").is_file() and "docs/topluluk/deneme.png" in cikti, "resim yazılır ve README'ye göreli yolla bağlanır")
    try:
        T.resim_indir("http://kotu.example/avatar.png")
        kotu = False
    except ValueError:
        kotu = True
    ok(kotu, "yalnızca avatars.githubusercontent.com adresinden indirilir")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
