"""Kalem çizimi dönüştürücüsü (sistem/araclar/kalem_cizim.py) ve ara sahne API işlevleri: tarayıcı ve ağ gerekmeden."""
import importlib.util
import json
import math
import shutil
import sys
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
    sys.modules[ad] = m
    sp.loader.exec_module(m)
    return m


K = yukle("kalem_t", R / "sistem/araclar/kalem_cizim.py")

# --- yol düzleştirme
c = K.yol_duzlestir("M 0,0 L 10,0 L 10,10 Z")
ok(len(c) == 1 and c[0][0] == (0.0, 0.0) and c[0][-1] == (0.0, 0.0) and (10.0, 10.0) in c[0], "M/L/Z: kapalı çokgen başa döner")
ok(K.yol_duzlestir("M 0,0 H 5 V 5 h -5 v -5") == [[(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0), (0.0, 0.0)]], "H/V ve göreli h/v")
yay = K.yol_duzlestir("M 0,0 A 5,5 0 0,1 10,0")[0]
ok(yay[-1] == (10.0, 0.0) and len(yay) > 8 and all(abs(math.dist((5, 0), q) - 5) < 0.05 for q in yay), "A: yarım daire, merkezden 5 uzaklıkta ve uç noktaya tam biter")
ok(abs(K.yol_duzlestir("M 0,0 A 5,5 0 0,0 10,0")[0][5][1]) > 1 and K.yol_duzlestir("M 0,0 A 5,5 0 0,1 10,0")[0][5][1] * K.yol_duzlestir("M 0,0 A 5,5 0 0,0 10,0")[0][5][1] < 0, "A: sweep bayrağı yayın yönünü çevirir")
ok(K.yol_duzlestir("M 0,0 A 0,0 0 0,0 10,0") == [[(0.0, 0.0), (10.0, 0.0)]], "A: sıfır yarıçap düz çizgiye iner")
cb = K.yol_duzlestir("M 0,0 C 0,10 10,10 10,0")[0]
ok(cb[-1] == (10.0, 0.0) and max(q[1] for q in cb) > 6, "C: kübik eğri uca varır ve kabarır")
try:
    K.yol_duzlestir("M 0,0 L 5,5 9")
    bozuk_ok = False
except ValueError:
    bozuk_ok = True
ok(bozuk_ok, "eksik sayılı yol ValueError verir")
ok(K.svg_cizgiler('<path d="M 0,0 L 5,5 9"/><path d="M 0,0 L 9,9"/>')[1]["bozuk_yol"] == 1, "bozuk yol atlanır ve sayılır, diğerleri çizilir")
ok(K.yol_duzlestir("M 1,1") == [], "tek noktalı yol çizgi sayılmaz")

# --- SVG ayrıştırma
svg = ('<svg><path id="a" d="M 0,0 L 100,0"/><path d="M 0,0 L 0,100" style="x"/><circle cx="50" cy="50" r="10"/>'
       '<text x="1">yazı</text><text>b</text><use href="#blok"/></svg>')
cizgiler, bilgi = K.svg_cizgiler(svg)
ok(len(cizgiler) == 3 and len(cizgiler[2]) == 49, "iki yol + bir daire (49 nokta)")
ok(bilgi["yazi_atlandi"] == 2 and bilgi["blok_atlandi"] == 1, "yazı ve blok eklemeleri çizilmez ama sayılır")

# --- darbeler: ölçekleme, sıralama, zamanlama
d = K.darbeler(cizgiler * 3, sure=6, fps=30)
ds = d["darbeler"]
ok(d["w"] == 1920 and d["h"] == 1080 and d["kare"] == 180, "tuval 1920x1080, 6 sn x 30 fps = 180 kare")
ok(all(0 <= q[0] <= 1920 and 0 <= q[1] <= 1080 for s in ds for q in s["p"]), "bütün noktalar tuvalin içinde")
ok(all(a["bas"] <= b["bas"] for a, b in zip(ds, ds[1:])), "darbeler zaman sırasında")
ok(max(s["bas"] + s["sure"] for s in ds) <= d["kare"] + 1, "hiçbir darbe video süresini aşmaz")
ok(ds[0]["bas"] == 0, "ilk darbe 0. karede başlar (ilk kare boş kâğıt olmaz)")
ev = R / "sistem/kit/kalem/ornek/ev-plani.svg"
dd, b2 = K.cizimden_darbeler(ev, 8, 30)
ok(b2["cizgi"] == 56 and b2["darbe"] == 56, f"örnek ev planı: 56 çizgi, 56 darbe ({b2})")
ok(dd["darbeler"][0]["L"] >= sorted(s["L"] for s in dd["darbeler"])[int(len(dd["darbeler"]) * 0.7)], "ana (uzun) çizgiler önce çizilir")
bos = False
try:
    K.darbeler([])
except RuntimeError:
    bos = True
ok(bos, "çizgisiz çizim açık hatayla reddedilir")

# --- odak kutusu: kaçak nesneler çizimi küçültmesin
nok = [(i % 100, (i * 7) % 100) for i in range(3000)] + [(10000, 10000)] * 5 + [(-9000, 8000)] * 5
x0, x1, y0, y1 = K.odak_kutusu(nok)
ok(x1 < 500 and y1 < 500 and x0 > -500, f"uzak kaçak noktalar kutuyu şişirmez ({x0:.0f}..{x1:.0f})")

# --- stil ve kaynak doğrulaması
ok(set(K.STILLER) == {"parsomen", "karakalem", "teknik"}, "üç stil")
try:
    K.video_uret(ev, Path("x.mp4"), stil="yok")
    ok(False, "bilinmeyen stil reddedilmeli")
except RuntimeError as e:
    ok("bilinmeyen stil" in str(e), "bilinmeyen stil açık hata")
try:
    K.cizimden_darbeler(Path("yok-resim.png"))
    ok(False, "olmayan resim reddedilmeli")
except RuntimeError as e:
    ok("açılamadı" in str(e), "okunamayan resim anlaşılır hata verir")
try:
    K.cizimden_darbeler(Path("a.xyz"))
    ok(False, "desteklenmeyen kaynak reddedilmeli")
except RuntimeError as e:
    ok("desteklenmeyen" in str(e), "desteklenmeyen kaynak türü reddedilir")
ok(all((R / "sistem/kit/kalem/onizleme" / f"{k}.jpg").is_file() for k in K.STILLER), "her stilin önizleme görseli var")
ok((R / "sistem/kit/kalem/sablon/cizim-genel.html").is_file() and (R / "sistem/kit/kalem/LICENSE-kalem.txt").is_file(), "sayfa şablonu ve kalem lisansı depoda")

# --- panel API işlevleri (ek_api): şablon listesi, kaynaklar, doğrulamalar
sys.path.insert(0, str(R / "sistem/panel"))
E = yukle("ek_api_t", R / "sistem/panel/ek_api.py")
sb = E.ara_sahne_sablonlar()
ok(len(sb["sablonlar"]) == 1 and len(sb["sablonlar"][0]["stiller"]) == 3 and {"tarayici", "ffmpeg", "dwg_okuma"} <= set(sb["hazir"]), "şablon galerisi: bir şablon, üç stil, hazırlık bilgisi")
ok(E.ara_sahne_onizleme("parsomen") is not None and E.ara_sahne_onizleme("../x") is None, "önizleme yalnızca bilinen stil kimlikleriyle")
p = R / "projeler" / "zz-ars"
try:
    (p / "kaynak/belge").mkdir(parents=True, exist_ok=True)
    shutil.copy(ev, p / "kaynak/belge/plan.svg")
    (p / "kaynak/belge/not.txt").write_text("x", encoding="utf-8")
    (p / "kaynak/belge/cizim.dwg").write_bytes(b"AC1015")
    ks = E.ara_sahne_sablonlar("zz-ars")["kaynaklar"]
    ok({k["ad"] for k in ks} == {"plan.svg", "cizim.dwg"}, "kaynak listesi yalnızca .dwg/.svg")
    ok(next(k for k in ks if k["ad"] == "plan.svg")["okunur"] is True, "SVG her sistemde okunur")
    for kotu in ("yesil", "#12345", "#GGGGGG", "javascript:1"):
        try:
            E.ara_sahne_uret({"proje": "zz-ars", "stil": "karakalem", "kaynak": "kaynak/belge/plan.svg", "zemin": kotu})
            ok(False, f"geçersiz zemin rengi reddedilmeliydi: {kotu}")
        except ValueError as e:
            ok("zemin" in str(e).lower(), f"geçersiz zemin rengi reddedilir ({kotu})")
    (p / "kaynak/foto").mkdir(parents=True, exist_ok=True)
    (p / "kaynak/video").mkdir(parents=True, exist_ok=True)
    (p / "kaynak/foto/giris.png").write_bytes(b"x")
    (p / "kaynak/video/sahne.mp4").write_bytes(b"x")
    (p / "kaynak/video/ara-sahne-eski.mp4").write_bytes(b"x")
    kat = {k["ad"]: k["kat"] for k in E.ara_sahne_sablonlar("zz-ars")["kaynaklar"]}
    ok(kat.get("plan.svg") == "cizim" and kat.get("giris.png") == "resim" and kat.get("sahne.mp4") == "video", "kaynaklar: çizim, resim ve video türleriyle listelenir")
    ok("ara-sahne-eski.mp4" not in kat, "üretilmiş ara sahne videoları kaynak olarak önerilmez")
    for b, beklenen in (({"proje": "zz-ars", "stil": "yok", "kaynak": "kaynak/belge/plan.svg"}, "stil"), ({"proje": "zz-ars", "stil": "karakalem", "kaynak": "kaynak/belge/not.txt"}, "kaynak"),
                        ({"proje": "zz-ars", "stil": "karakalem", "kaynak": "../../x.svg"}, "kaynak"), ({"proje": "../x", "stil": "karakalem", "kaynak": "x"}, "proje")):
        try:
            E.ara_sahne_uret(b)
            ok(False, f"reddedilmeliydi: {b}")
        except ValueError as e:
            ok(beklenen in str(e).lower(), f"geçersiz istek reddedilir ({beklenen}): {str(e)[:60]}")
finally:
    shutil.rmtree(p, ignore_errors=True)

# --- zemin rengi
ok(K.zemin_rgb("#DCE8D2") == [220, 232, 210] and K.zemin_rgb("1e2430") == [30, 36, 48], "zemin rengi: #RRGGBB ve RRGGBB okunur")
ok(K.zemin_rgb("") is None and K.zemin_rgb(None) is None, "boş zemin: stilin kendi rengi")
try:
    K.zemin_rgb("kırmızı")
    zr_red = False
except ValueError:
    zr_red = True
ok(zr_red, "geçersiz zemin rengi ValueError verir")

# --- kalem sesi (çizim darbelerine bağlı)
import wave
import numpy as np
sahte = {"kare": 150, "darbeler": [{"bas": 30 + i * 3, "sure": 4, "p": [[0, 0], [1, 1]]} for i in range(30)] + [{"bas": 60 + (i % 25), "sure": 0.5, "p": [[0, 0], [1, 1]]} for i in range(400)]}


def rms_sn(yol):
    with wave.open(str(yol)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        sr = w.getframerate()
    return x, sr


import tempfile as _tf
tmp_s = Path(_tf.mkdtemp(prefix="yst-kalem-ses-"))
try:
    for ad, dizin in (("yedek (kit yok)", tmp_s / "yok"), ("kit varsa gerçek kayıt", K.SFX_DIZIN)):
        K.SFX_DIZIN = dizin
        wav = tmp_s / "k.wav"
        sure = K.kalem_sesi(sahte, 30, wav)
        x, sr = rms_sn(wav)
        sn = lambda a, b: float(np.sqrt((x[int(a * sr):int(b * sr)] ** 2).mean()))  # noqa: E731
        ok(sure is not None and abs(sure - 5.0) < 0.01 and sr == 48000, f"kalem sesi: giriş süresi kadar (5 sn), 48 kHz [{ad}]")
        ok(sn(0.0, 0.8) < 0.003, f"kalem sesi: çizim başlamadan sessiz [{ad}]")
        ok(sn(1.8, 3.0) > 0.01 and sn(1.8, 3.0) > 8 * sn(0.0, 0.8), f"kalem sesi: çizim sürerken duyulur [{ad}]")
        ok(float(np.abs(x).max()) < 0.95, f"kalem sesi: kırpılmaz [{ad}]")
        K.kalem_sesi(sahte, 30, tmp_s / "k2.wav")
        ok(rms_sn(tmp_s / "k2.wav")[0].tobytes() == x.tobytes(), f"kalem sesi: aynı çizim aynı sesi verir (tohumlu) [{ad}]")
    ok(K.kalem_sesi({"kare": 90, "darbeler": []}, 30, tmp_s / "bos.wav") is None, "çizim yoksa kalem sesi üretilmez")
finally:
    shutil.rmtree(tmp_s, ignore_errors=True)
    K.SFX_DIZIN = R / "sistem" / "kit" / "sfx-wyzowl" / "sounds" / "writing-and-drawing"

# --- resimden kalem: kenar çıkarımı, hizalama, gerçeğe geçiş zamanlaması
import tempfile
from PIL import Image, ImageDraw
RS = yukle("kalem_resim_t", R / "sistem/araclar/kalem_resim.py")
tmp = Path(tempfile.mkdtemp(prefix="yst-kalem-test-"))
try:
    im = Image.new("RGB", (400, 200), (235, 235, 235))
    dr = ImageDraw.Draw(im)
    dr.rectangle((60, 40, 200, 160), fill=(30, 30, 30))
    dr.ellipse((250, 50, 350, 150), fill=(120, 120, 120))
    im.save(tmp / "t.png")
    cz, (iw, ih) = RS.resimden_cizgiler(tmp / "t.png")
    ok((iw, ih) == (400, 200) and len(cz) >= 2, f"resimden çizgi çıkar ({len(cz)} çizgi), boyut korunur")
    xs = [q[0] for c in cz for q in c]
    ys = [q[1] for c in cz for q in c]
    ok(55 <= min(xs) <= 66 and 195 <= max(xs) <= 356 and 35 <= min(ys) <= 56, "çizgiler şeklin kenarında (dikdörtgen ve daire sınırı)")
    d = K.darbeler(cz, sure=4, fps=30, kutu=(0, iw, 0, ih), kenar=0)
    y = d["yer"]
    ok(abs(y["w"] / y["h"] - 2.0) < 0.01 and y["w"] <= 1920 and y["h"] <= 1080, "resim kutusu oranı korur ve tuvale sığar")
    ok(abs(y["x"] + y["w"] / 2 - 960) < 1 and abs(y["y"] + y["h"] / 2 - 540) < 1, "resim tuvalde ortalanır (gerçek resim aynı hizada açılır)")
    ok(all(q[0] >= y["x"] - 1 and q[0] <= y["x"] + y["w"] + 1 for s_ in d["darbeler"] for q in s_["p"]), "darbeler resmin alanını aşmaz")
    dg, bg = K.cizimden_darbeler(tmp / "t.png", sure=4, fps=30, gecis=True, bekle=2, gecis_sure=1, tut=1)
    ok(dg["cizim_kare"] == 120 and dg["gecis"] == {"bas": 180, "sure": 30} and dg["kare"] == 240, "geçiş zamanı: çizim 120 kare, 2 sn bekleme, 1 sn geçiş, 1 sn tutma")
    ok(bg.get("resim") is True, "resim kaynağı işaretlenir")
    # --- ton taraması (hatching)
    tr = RS.tarama_darbeleri(im, 1.0)
    ok(len(tr) > 20 and all("a" in t_ and len(t_["p"]) == 2 for t_ in tr), f"koyu bölge kalem taramasıyla doldurulur ({len(tr)} darbe)")
    orta = [((t_["p"][0][0] + t_["p"][1][0]) / 2, (t_["p"][0][1] + t_["p"][1][1]) / 2) for t_ in tr]
    ok(sum(1 for x_, y_ in orta if 55 <= x_ <= 205 and 35 <= y_ <= 165) / len(orta) > 0.7, "tarama koyu dikdörtgenin içinde yoğunlaşır")
    ok(not any(x_ < 40 and y_ < 30 for x_, y_ in orta), "açık zeminde tarama çizgisi yok")
    ok(RS.tarama_darbeleri(im, 1.0) == tr, "aynı resim her seferinde aynı taramayı verir (tohumlu, rastgelelik yok)")
    ok(len({t_["kat"] for t_ in tr}) >= 2 and RS.tarama_darbeleri(im, 0.0) == [], "koyu yerler çok katmanlı taranır; tarama 0 ise yok")
    dt, bt = K.cizimden_darbeler(tmp / "t.png", sure=4, fps=30, tarama=0.8)
    ok(bt.get("tarama", 0) > 0 and dt["kare"] == 120 and any("a" in d_ for d_ in dt["darbeler"]), "tarama darbeleri zamanlamaya girer, süre değişmez")
    ok(all(d_["bas"] >= 0 and d_["bas"] + d_["sure"] <= dt["kare"] + 2 for d_ in dt["darbeler"]), "hiçbir darbe çizim süresini aşmaz")
    d0, b0 = K.cizimden_darbeler(tmp / "t.png", sure=4, fps=30, tarama=0)
    ok("tarama" not in b0 and all("a" not in d_ for d_ in d0["darbeler"]), "tarama kapalıyken yalnızca kontur çizgileri")
    try:
        (tmp / "a.svg").write_text('<svg><path d="M 0,0 L 10,10"/></svg>', encoding="utf-8")
        K.cizimden_darbeler(tmp / "a.svg", gecis=True)
        gecis_red = False
    except RuntimeError:
        gecis_red = True
    ok(gecis_red, "vektör çizimde gerçeğe geçiş istenirse açıkça reddedilir")
    try:
        K.cizimden_darbeler(tmp / "x.xyz")
        uz_red = False
    except RuntimeError as e:
        uz_red = "desteklenmeyen" in str(e)
    ok(uz_red, "desteklenmeyen uzantı anlaşılır hata verir")
    Image.new("RGB", (300, 200), (200, 200, 200)).save(tmp / "duz.png")
    try:
        K.cizimden_darbeler(tmp / "duz.png")
        bos = False
    except RuntimeError:
        bos = True
    ok(bos, "düz renkli resimde çizgi çıkmaz ve anlaşılır hata verir")
    # seyrek içerik: siyah zemin üstünde küçük açık yazı/şekil (kenar yüzdeliği ~0 kalırdı: "çizgi bulunamadı")
    from PIL import ImageDraw
    sey = Image.new("RGB", (640, 360), (0, 0, 0))
    ImageDraw.Draw(sey).rectangle((280, 160, 360, 200), outline=(255, 255, 255), width=3)
    ImageDraw.Draw(sey).ellipse((400, 150, 440, 190), outline=(255, 255, 255), width=3)
    sey.save(tmp / "seyrek.png")
    try:
        sd = K.cizimden_darbeler(tmp / "seyrek.png")
        sey_ok = bool(sd[0]["darbeler"])
    except RuntimeError:
        sey_ok = False
    ok(sey_ok, "seyrek içerikli resimde (siyah zemin + küçük şekiller) çizgiler bulunur")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
