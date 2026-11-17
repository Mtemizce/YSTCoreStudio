import json, os, random, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

R = Path(__file__).resolve().parents[2]
VENV_PY = Path(sys.executable)
tmp = Path(tempfile.mkdtemp(prefix="panel2-"))
random.seed(5)
S = [0, 0]
DB = R / "sistem" / "ortam" / "arsiv" / "arsiv.db"
import sqlite3
DB_YEDEK = DB.read_bytes() if DB.exists() else None
if DB_YEDEK:
    _c = sqlite3.connect(DB); assert _c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0] == 0, "gerçek arşiv kaydı var; test iptal"; _c.close()


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def foto(p, w, h, blur=0, n=120):
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (w, h), (150, 170, 190)); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = random.randint(0, w), random.randint(0, h)
        d.rectangle([x, y, x + random.randint(15, 220), y + random.randint(15, 160)], fill=tuple(random.randint(20, 230) for _ in range(3)), outline=(0, 0, 0), width=2)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    im.save(p, quality=90)


ark = tmp / "Arsivim"
for i in range(5):
    foto(ark / "Villa K" / "2023" / f"iyi{i}.jpg", 2000, 1300)
foto(ark / "Villa K" / "2023" / "kucuk.jpg", 640, 440)
foto(ark / "Villa K" / "2023" / "bulanik.jpg", 1800, 1200, blur=4)

KUL = R / "sistem" / "ayar" / "kullanici.json"; KUL_YEDEK = KUL.read_bytes()
env = dict(os.environ, YST_TARAYICI_YOK="1", YST_ARKA_YOK="1", PYTHONUTF8="1", YST_GORSEL_SAHTE="1")   # sahte görsel üretici: model kurmadan akışı dener
PANEL_LOG = Path(tempfile.gettempdir()) / "yst-test-panel-api.log"
(R / "sistem" / "ortam" / "yerel").mkdir(parents=True, exist_ok=True)
(R / "sistem" / "ortam" / "yerel" / "panel.json").unlink(missing_ok=True)  # önceki testten kalan eski port bilgisini okumayalım
srv = subprocess.Popen([str(VENV_PY), str(R / "sistem" / "panel" / "panel.py"), "--tarayici-yok"], cwd=str(R), env=env, stdout=open(PANEL_LOG, "w"), stderr=subprocess.STDOUT)
B = None
for _ in range(120):  # yavaş makinelerde (macOS runner) ilk açılış uzun sürebilir
    time.sleep(0.5)
    pj = R / "sistem" / "ortam" / "yerel" / "panel.json"
    if pj.exists():
        try:
            B = "http://127.0.0.1:%d" % json.loads(pj.read_text())["port"]
            urllib.request.urlopen(B + "/api/ping", timeout=2).read()
            break
        except Exception:
            B = None
assert B, "panel başlamadı: " + PANEL_LOG.read_text(errors="replace")[-1500:]


def call(m, u, b=None, hdr=True):
    h = {"X-Panel": "1", "Content-Type": "application/json"} if hdr else {}
    req = urllib.request.Request(B + u, data=json.dumps(b).encode() if b is not None else None, method=m, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


try:
    s, r = call("GET", "/api/ping"); ok(s == 200 and r["app"] == "YSTPanel", "ping")
    s, r = call("GET", "/api/arka-indirme"); ok(s == 200 and r.get("kod") in ("tamam", "bekliyor", "calisiyor", "sorun", "atlandi") and "ozet" in r, "arka plan indirme durumu")
    s, r = call("POST", "/api/arka-indirme/atla", hdr=False); ok(s == 403, "arka plan indirme: X-Panel başlığı olmadan reddedilir")
    # güvenlik başlıkları; Referrer-Policy no-referrer OLMAMALI: Kurgu editörü iframe isteğinde panelin adresini Referer olarak bekler
    with urllib.request.urlopen(B + "/", timeout=5) as h:
        hd = {k.lower(): v for k, v in h.headers.items()}
    ok(hd.get("x-content-type-options") == "nosniff" and "frame-ancestors 'none'" in hd.get("content-security-policy", ""), "arayüz: nosniff + frame-ancestors başlıkları")
    ok(hd.get("cache-control") == "no-store", "arayüz dosyası önbelleğe alınmaz")
    ok(hd.get("referrer-policy") in ("strict-origin", "strict-origin-when-cross-origin", "origin", "same-origin", None) and hd.get("referrer-policy") != "no-referrer", "Referrer-Policy Kurgu iframe'ini bozmaz")
    # kapak resmi (Pano > Üretilen videolar): geçersiz ad reddedilir, videosuz proje 404, videolu proje JPEG döner
    kp = R / "projeler" / "zz-kapak"
    try:
        (kp / "cikti").mkdir(parents=True, exist_ok=True)
        for u_, beklenen in (("/api/kapak?proje=../x", 400), ("/api/kapak?proje=yok-boyle-proje", 400), ("/api/kapak?proje=zz-kapak", 404)):
            try:
                urllib.request.urlopen(B + u_, timeout=10)
                kod = 200
            except urllib.error.HTTPError as e:
                kod = e.code
            ok(kod == beklenen, f"kapak {u_.split('=')[1]}: {kod}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=3", "-pix_fmt", "yuv420p", str(kp / "cikti" / "ana.mp4")], check=True)
        with urllib.request.urlopen(B + "/api/kapak?proje=zz-kapak", timeout=30) as rr:
            veri = rr.read()
            ok(rr.status == 200 and veri[:3] == bytes([255, 216, 255]) and rr.headers.get("Content-Type") == "image/jpeg", f"videolu projenin kapağı JPEG ({len(veri)} bayt)")
    finally:
        shutil.rmtree(kp, ignore_errors=True)
        for f in (R / "sistem" / "ortam" / "yerel" / "kapak").glob("zz-kapak-*.jpg"):
            f.unlink(missing_ok=True)
    # görsel kütüphanesi: yerel sağlayıcı listede, üret → kontrol → onayla → projeye ekle (sahte üretici)
    gp = R / "projeler" / "zz-gorsel-api"
    uretilen = []
    try:
        (gp / "ana").mkdir(parents=True, exist_ok=True)
        s, g = call("GET", "/api/gorsel"); ok(s == 200 and g["kurulu"] and len(g["stiller"]) >= 12 and any(x["grup"] == "anime" for x in g["stiller"]), "görsel: durum ve stil listesi (anime dahil)")
        s, bg = call("GET", "/api/baglayici"); yz = next((x for x in bg["saglayicilar"] if x["id"] == "yerel-zimage"), None)
        ok(yz and yz["yerel"] and yz["etkin"] and "gorsel" in yz["tur"] and bg["saglayicilar"][0]["id"] == "yerel-zimage", "'Görseli üret' listesinde yerel Z-Image en başta ve (kuruluysa) etkin")
        s, r = call("POST", "/api/gorsel/uret", {"istem": "ofis gibi bir oda", "stil": "anime-aksiyon", "boyut": "yatay", "adet": 2}); ok(s == 200 and r["adet"] == 2, "görsel üretimi başladı")
        for _ in range(60):
            time.sleep(0.5)
            s, g = call("GET", "/api/gorsel")
            if not g["is"]["calisiyor"]:
                break
        uretilen = g["is"]["idler"]
        ok(len(uretilen) == 2 and not g["is"]["hata"], f"2 görsel üretildi: {g['is']['mesaj']}")
        s, r = call("POST", "/api/gorsel/uret", {"istem": "x"}); ok(s == 400, "çok kısa istem reddedilir")
        with urllib.request.urlopen(B + f"/api/gorsel/dosya?id={uretilen[0]}&k=1", timeout=10) as rr:
            ok(rr.status == 200 and rr.read(3) == bytes([255, 216, 255]), "küçük önizleme JPEG döner")
        try:
            urllib.request.urlopen(B + "/api/gorsel/dosya?id=../x", timeout=10)
            kod = 200
        except urllib.error.HTTPError as e:
            kod = e.code
        ok(kod == 404, "geçersiz görsel kimliği 404")
        s, r = call("POST", "/api/gorsel/onayla", {"id": uretilen[0]}); ok(s == 200 and r["oge"]["durum"] == "onayli", "beğenilen görsel kütüphaneye eklenir (onaylı)")
        s, r = call("POST", "/api/gorsel/reddet", {"id": uretilen[1]}); ok(s == 200 and r["oge"]["durum"] == "reddedildi", "beğenilmeyen görsel reddedilir")
        s, l = call("GET", "/api/gorsel/liste?durum=onayli"); ok(s == 200 and any(x["id"] == uretilen[0] for x in l["ogeler"]), "kütüphane listesi (onaylı)")
        s, r = call("POST", "/api/gorsel/projeye", {"id": uretilen[0], "proje": "zz-gorsel-api", "format": "ana"}); ok(s == 200 and (gp / r["media"]).is_file() and (gp / r["kaynak"]).is_file(), "görsel projeye (kaynak/foto + Kurgu media) eklenir")
        s, r = call("POST", "/api/gorsel/projeye", {"id": uretilen[0], "proje": "../x"}); ok(s == 400, "geçersiz proje adı reddedilir")
        s, r = call("POST", "/api/gorsel/onayla", {"id": uretilen[0]}, hdr=False); ok(s == 403, "görsel işlemleri X-Panel olmadan reddedilir (CSRF)")
    finally:
        for gid in uretilen:
            call("POST", "/api/gorsel/sil", {"id": gid})
        shutil.rmtree(gp, ignore_errors=True)
    # dizi: oluştur (görsel stil), model seti, görsel bağla, bölüm düzenle, detay; marka kiti: çoklu logo ve kural
    sk = R / "kimlik" / "seriler" / "zz-api-dizi"
    mk = R / "kimlik" / "marka_kitleri" / "zz-api-kit"
    gids = []
    try:
        s, r = call("POST", "/api/seri/olustur", {"ad": "ZZ API Dizi", "tur": "dizi", "aciklama": "deneme", "gorsel_stil": "anime-retro-90"}); ok(s == 200 and r["seri"]["gorsel_stil"] == "anime-retro-90", "dizi: görsel stille oluşur")
        s, r = call("POST", "/api/seri/olustur", {"ad": "ZZ API Dizi 2", "gorsel_stil": "yok"}); ok(s == 400, "dizi: bilinmeyen görsel stil reddedilir")
        s, r = call("POST", "/api/seri/model/ekle", {"seri": "zz-api-dizi", "tur": "karakter", "ad": "Deniz", "aciklama": "uzun saç", "istem_eki": "long hair"}); ok(s == 200 and r["model"]["id"] == "deniz", "model seti: karakter eklenir")
        s, r = call("POST", "/api/gorsel/uret", {"istem": "ofiste bir kadın", "boyut": "kare", "adet": 1, "model": {"seri": "zz-api-dizi", "id": "deniz"}}); ok(s == 200, "model kilitli görsel üretimi başladı")
        for _ in range(60):
            time.sleep(0.5)
            s, g = call("GET", "/api/gorsel")
            if not g["is"]["calisiyor"]:
                break
        gids = g["is"]["idler"]
        s, l = call("GET", "/api/gorsel/liste?seri=zz-api-dizi"); ok(s == 200 and len(l["ogeler"]) == 1 and "long hair" in l["ogeler"][0]["istem"] and l["ogeler"][0]["stil"] == "anime-retro-90", "model kilidi: sabit istem eki ve serinin görsel stili uygulanır, görsel seriye etiketlenir")
        s, r = call("POST", "/api/seri/model/gorsel", {"seri": "zz-api-dizi", "id": "deniz", "gorsel": gids[0]}); ok(s == 400, "taslak görsel modele bağlanamaz (önce onayla)")
        call("POST", "/api/gorsel/onayla", {"id": gids[0]})
        s, r = call("POST", "/api/seri/model/gorsel", {"seri": "zz-api-dizi", "id": "deniz", "gorsel": gids[0]}); ok(s == 200 and r["model"]["ana"] == gids[0], "onaylı görsel modele bağlanır (ana görsel)")
        s, d = call("GET", "/api/seri/detay?id=zz-api-dizi"); ok(s == 200 and d["seri"]["model_seti"][0]["gorsel_var"] == gids, "dizi detayı: modelin görselleri")
        s, r = call("POST", "/api/seri/guncelle", {"id": "zz-api-dizi", "aciklama": "yeni açıklama", "gorsel_stil": "anime-aksiyon"}); ok(s == 200 and r["seri"]["gorsel_stil"] == "anime-aksiyon" and len(r["seri"]["model_seti"]) == 1, "dizi düzenleme: model seti korunur")
        s, r = call("POST", "/api/seri/bolum/guncelle", {"seri": "zz-api-dizi", "sezon": 1, "bolum": 1, "ad": "x"}); ok(s == 400, "olmayan bölüm düzenlenemez")
        s, r = call("POST", "/api/marka/kaydet", {"kit": {"id": "zz-api-kit", "ad": "ZZ Kit", "kullanim": [{"oge": "genel", "nasil": "ölçülü kullan"}], "metinler": [{"ad": "Çağrı", "tur": "cta", "icerik": "ara bizi"}]}})
        ok(s == 200 and r["kit"]["kullanim"][0]["nasil"] == "ölçülü kullan" and r["kit"]["metinler"][0]["id"] == "cagri", "marka kiti: kullanım kuralı ve metin kaydedilir")
        png = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + os.urandom(200)
        rq = urllib.request.Request(B + "/api/marka/logo?kit=zz-api-kit&ad=l.png&id=koyu&tur=koyu-zemin&etiket=Koyu", data=png, method="POST", headers={"X-Panel": "1"})
        lg = json.loads(urllib.request.urlopen(rq, timeout=10).read())
        ok(lg["logo"]["dosya"] == "logo-koyu.png" and lg["logo"]["tur"] == "koyu-zemin", "marka kiti: adlandırılmış logo yüklenir")
        with urllib.request.urlopen(B + "/api/marka/dosya?kit=zz-api-kit&dosya=logo-koyu.png", timeout=10) as rr:
            ok(rr.status == 200 and rr.headers.get("Content-Type") == "image/png", "marka kiti: logo önizlemesi sunulur")
        try:
            urllib.request.urlopen(B + "/api/marka/dosya?kit=zz-api-kit&dosya=kit.json", timeout=10)
            kod = 200
        except urllib.error.HTTPError as e:
            kod = e.code
        ok(kod == 404, "marka kiti: logo olmayan dosya (kit.json) sunulmaz")
    finally:
        for gid in gids:
            call("POST", "/api/gorsel/sil", {"id": gid})
        shutil.rmtree(sk, ignore_errors=True)
        shutil.rmtree(mk, ignore_errors=True)
    s, k = call("GET", "/api/konum"); ok(s == 200 and k["makine"] and any(x["tur"] == "studyo" and x["bagli"] for x in k["kokler"]), "konum: stüdyo kökü otomatik kayıtlı")
    s, g = call("POST", "/api/konum/gozat", {"yol": ""}); ok(s == 200 and g["girdiler"], "gözat: sürücüler")
    s, g = call("POST", "/api/konum/gozat", {"yol": str(tmp)}); ok(s == 200 and any(x["ad"] == "Arsivim" for x in g["girdiler"]), "gözat: klasörler")
    s, g = call("POST", "/api/konum/gozat", {"yol": str(tmp)}, hdr=False); ok(s == 403, "gözat X-Panel olmadan reddedildi (CSRF)")
    s, g = call("POST", "/api/konum/gozat", {"yol": str(tmp / "yok")}); ok(s == 400, "gözat: olmayan klasör hata")
    s, r = call("POST", "/api/arsiv/ayarla", {"ad": "arsiv", "yol": str(ark)}); ok(s == 200 and r["ayar"]["yol"] == str(ark), f"arşiv eklendi: {r}")
    s, d = call("GET", "/api/arsiv/durum"); ok(d["ayarli"] and d["bagli"] and len(d["arsivler"]) == 1, "arşiv durumu bağlı")
    s, r = call("POST", "/api/arsiv/tara", {"derin": False, "analiz": True}); ok(s == 200 and r["ok"], "tarama + analiz başladı")
    for _ in range(60):
        time.sleep(1)
        s, d = call("GET", "/api/arsiv/durum")
        if not d["calisiyor"]:
            break
    ok(d["toplam"] == 7 and d["analiz"] and d["analiz"]["foto"]["otomatik_analiz"] == 7, f"7 dosya tarandı ve analiz edildi: {d['toplam']} / {d.get('analiz')}")
    s, r = call("POST", "/api/arsiv/ara", {"tur": ["foto"], "derinlik": 2}); ok(s == 200 and r["gruplar"], "arama (kök filtresiz)")
    kid = d["arsivler"][0]["id"]
    s, r = call("POST", "/api/arsiv/ara", {"tur": ["foto"], "derinlik": 2, "kok": kid}); ok(s == 200 and r["gruplar"], "arama (kök filtreli)")
    # iyileştirme
    s, m = call("GET", "/api/arsiv/iyilestirme/modeller"); ok(s == 200 and {x["id"] for x in m["modeller"]} >= {"yerel-realesrgan", "yerel-klasik"}, "iyileştirme modelleri listelendi")
    s, a = call("POST", "/api/arsiv/iyilestirme/adaylar", {"limit": 20}); adaylar = a["adaylar"]
    ok(s == 200 and {x["ad"] for x in adaylar} >= {"kucuk.jpg"}, f"adaylar: {[(x['ad'], x['puan']) for x in adaylar]}")
    ids = [x["id"] for x in adaylar]
    s, r = call("POST", "/api/arsiv/iyilestirme/baslat", {"idler": ids, "model": "gemini-iyilestir"}); ok(s == 400, "kapalı bulut modeli reddedildi: " + str(r.get("hata"))[:70])
    s, r = call("POST", "/api/arsiv/iyilestirme/baslat", {"idler": [], "model": "yerel-klasik"}); ok(s == 400, "boş seçim reddedildi")
    s, r = call("POST", "/api/arsiv/iyilestirme/baslat", {"idler": ids, "model": "yerel-klasik", "olcek": 2, "keskinlik": 0.5}); ok(s == 200 and r["ok"], "iyileştirme başladı")
    for _ in range(60):
        time.sleep(1)
        s, d = call("GET", "/api/arsiv/iyilestirme/durum")
        if d["bitti"]:
            break
    ok(d["tamam"] == len(ids) and d["hata"] == 0, f"{d['tamam']}/{len(ids)} tamam: {d['mesaj']}")
    iy = d["sonuclar"][0]
    ok(iy.get("iy_id") and iy["sonraki_puan"] >= (iy["onceki_puan"] or 0), f"önce/sonra puan: {iy['onceki_puan']} → {iy['sonraki_puan']}")
    with urllib.request.urlopen(B + f"/api/arsiv/iyilestirme/onizleme?id={iy['iy_id']}") as rr:
        ok(rr.status == 200 and rr.headers["Content-Type"] == "image/jpeg" and len(rr.read()) > 1000, "sonuç önizlemesi (JPEG)")
    with urllib.request.urlopen(B + f"/api/arsiv/onizleme?id={iy['dosya_id']}") as rr:
        ok(rr.status == 200, "orijinal önizlemesi")
    s, r = call("POST", "/api/arsiv/iyilestirme/kullan", {"id": iy["iy_id"], "kullan": False}); ok(s == 200, "kullan kapatıldı")
    s, r = call("POST", "/api/arsiv/iyilestirme/sil", {"id": iy["iy_id"]}); ok(s == 200, "sonuç silindi")
    # işler ve modeller ayarı
    s, a = call("GET", "/api/ayar"); ok("gorsel-iyilestirme" in a["isler"], "ayar özeti isler içeriyor")
    s, r = call("POST", "/api/ayar", {"yama": {"isler": {"gorsel-iyilestirme": {"modeller": {"benim-model": {"ad": "Benim Gemini", "motor": "bulut", "saglayici": "gemini", "model": "gpt 555", "etkin": True}}}}}}); ok(s == 400 and "Bağlan" in r.get("hata", ""), "elle yazılmış/uydurma model REDDEDİLDİ (liste alınmadan): " + r.get("hata", "")[:70])
    s, r = call("POST", "/api/baglayici/ayar", {"saglayici": "gemini", "modeller": {"gorsel-uret": "gpt 555"}}); ok(s == 400, "bağlayıcıda da uydurma model reddedildi")
    s, r = call("POST", "/api/baglayici/kesfet", {"saglayici": "gemini"}); ok(s == 400 and "anahtar" in r.get("hata", "").lower(), "anahtarsız keşif anlaşılır hata verdi: " + r.get("hata", "")[:60])
    s, o = call("GET", "/api/orkestrator"); ok(s == 200 and o["secili"] == "claude-code" and any(x["id"] == "claude-code" and x["durum"] == "tam" for x in o["liste"]), "orkestratör varsayılanı Claude Code")
    s, r = call("POST", "/api/ayar", {"yama": {"orkestrator": {"calisma_ortami": "bilinmeyen"}}}); ok(s == 400, "geçersiz orkestratör reddedildi")
    s, o = call("GET", "/api/on-ayar"); ok(s == 200 and {x["id"] for x in o["on_ayarlar"]} >= {"openai", "anthropic", "ollama", "lmstudio"}, "ön ayar listesi")
    s, r = call("POST", "/api/ayar", {"yama": {"isler": {"gorsel-iyilestirme": {"modeller": {"KÖTÜ AD": {"ad": "x"}}}}}}); ok(s == 400, "geçersiz model kimliği reddedildi")
    s, r = call("POST", "/api/ayar", {"yama": {"isler": {"gorsel-iyilestirme": {"modeller": {"abc": {"motor": "rm -rf"}}}}}}); ok(s == 400, "geçersiz motor reddedildi")
    s, r = call("POST", "/api/ayar", {"yama": {"isler": {"gorsel-iyilestirme": {"varsayilan": "yok-boyle"}}}}); ok(s == 400, "olmayan varsayılan reddedildi")
    # sistem, yedek
    s, t = call("GET", "/api/sistem"); ok(s == 200 and any(o["id"] == "git" for o in t["ogeler"]), "sistem analizi")
    s, y = call("POST", "/api/profil/disa-aktar", {}); ok(s == 400, "parola ya da 'şifresiz' seçimi zorunlu")
    s, y = call("POST", "/api/profil/disa-aktar", {"sifre": "kisa"}); ok(s == 400, "kısa parola reddedildi")
    s, y = call("POST", "/api/profil/disa-aktar", {"sifre": "uzun-parola-1", "iyilestirilmis": True}); ok(s == 200 and y["sifreli"], f"profil dışa aktarıldı: {y.get('icerik')}")
    with urllib.request.urlopen(B + "/api/profil/indir?ad=" + y["ad"]) as rr:
        veri = rr.read(); ok(rr.status == 200 and b"yst-profil" in veri[:200] and b"gemini" not in veri.lower(), "indirme (şifreli, düz metin sızıntısı yok)")
    req = urllib.request.Request(B + "/api/profil/yukle", data=veri, method="POST", headers={"X-Panel": "1", "X-Dosya-Adi": "tasinan.json"})
    yk = json.loads(urllib.request.urlopen(req).read()); ok(yk["ok"] and yk["ozet"]["sifreli"], "yükleme + şifreli özet")
    s, r = call("POST", "/api/profil/ice-aktar", {"ad": "tasinan.json", "sifre": "yanlis-parola", "kuru": True}); ok(s == 400 and "parola" in r["hata"], "yanlış parola reddedildi")
    s, r = call("POST", "/api/profil/ice-aktar", {"ad": "tasinan.json", "sifre": "uzun-parola-1", "kuru": True}); ok(s == 200 and r["kuru"] and r["yazilan"] is not None, f"kuru içe aktarma: {r.get('yazilan')}")
    s, r = call("POST", "/api/profil/ice-aktar", {"ad": "../etc.json", "kuru": True}); ok(s == 400, "yol gezintisi reddedildi")
    s, r = call("GET", "/api/profil/indir?ad=..%5C..%5Csistem.json"); ok(s in (400, 404) or "hata" in r, "indirmede yol gezintisi reddedildi")
    for f in (R / "sistem" / "ortam" / "yedek").glob("*"):
        f.unlink(missing_ok=True)
    # arşiv silme: dosyalara dokunmaz
    s, r = call("POST", "/api/konum/arsiv-sil", {"id": 999}); ok(s == 400, "olmayan kök silinemez")
    s, k = call("GET", "/api/konum"); stid = next(x["id"] for x in k["kokler"] if x["tur"] == "studyo")
    s, r = call("POST", "/api/konum/arsiv-sil", {"id": stid}); ok(s == 400, "stüdyo kökü silinemez")
    s, r = call("POST", "/api/konum/arsiv-sil", {"id": kid}); ok(s == 200 and (ark / "Villa K" / "2023" / "kucuk.jpg").exists(), "arşiv kaydı silindi, dosyalar yerinde")
    # kapat
    s, r = call("POST", "/api/kapat", {}); ok(s == 200, "kapat çağrıldı")
    time.sleep(2)
    try:
        urllib.request.urlopen(B + "/api/ping", timeout=2); ok(False, "panel kapanmalıydı")
    except Exception:
        ok(True, "panel kapandı")
finally:
    if srv.poll() is None:
        srv.terminate()
    time.sleep(0.5)
    KUL.write_bytes(KUL_YEDEK)
    DB.unlink(missing_ok=True)
    if DB_YEDEK:
        DB.write_bytes(DB_YEDEK)
    (R / "sistem" / "ortam" / "arsiv" / "ilerleme.json").unlink(missing_ok=True)
    shutil.rmtree(R / "sistem" / "ortam" / "arsiv" / "iyilestirilmis", ignore_errors=True)
    shutil.rmtree(R / "sistem" / "ortam" / "arsiv" / "analiz_sayfalari", ignore_errors=True)
    for z in (R / "sistem" / "ortam" / "yedek").glob("*"):
        z.unlink(missing_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
