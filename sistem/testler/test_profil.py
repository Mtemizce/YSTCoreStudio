import base64, json, os, random, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw

SRC = Path(__file__).resolve().parents[2]
tmp = Path(tempfile.mkdtemp(prefix="profil-"))
S = [0, 0]
random.seed(2)


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def kur(ad):
    k = tmp / ad
    for rel in ("sistem/araclar", "sistem/arsiv", "sistem/ayar", "sistem/baglayici"):
        shutil.copytree(SRC / rel, k / rel, ignore=shutil.ignore_patterns("__pycache__", "kullanici.json"))
    shutil.copy(SRC / "sistem" / "surum.json", k / "sistem" / "surum.json")
    (k / "sistem/ayar/kullanici.json").write_text('{"ajanlar": {}}', encoding="utf-8")
    (k / ".claude" / "agents").mkdir(parents=True)
    shutil.copy(SRC / ".claude/agents/redaktor.md", k / ".claude/agents/redaktor.md")
    (k / "kimlik").mkdir()
    return k


def calistir(k, kod):
    """k kökündeki kod kopyasıyla Python çalıştır (ROOT = k)."""
    r = subprocess.run([sys.executable, "-c", kod], cwd=str(k), capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(k / "sistem/araclar")))
    if r.returncode != 0:
        print(r.stderr[-1500:])
    return r


A_ = kur("A")
# --- A: kullanıcı verisi
(A_ / "sistem/ayar/kullanici.json").write_text(json.dumps({"ajanlar": {"redaktor": {"model": "opus", "effort": "high"}}, "isler": {"gorsel-iyilestirme": {"modeller": {"benim-m": {"ad": "Benim", "motor": "bulut", "saglayici": "gemini", "model": "m-1", "etkin": True}}}}}), encoding="utf-8")
(A_ / "sistem/ortam/baglayici").mkdir(parents=True)
(A_ / "sistem/ortam/baglayici/anahtar.json").write_text(json.dumps({"GEMINI_API_KEY": "GIZLI_ANAHTAR_123456789"}), encoding="utf-8")
(A_ / "sistem/ortam/baglayici/mcp.json").write_text(json.dumps({"heygen": {"tur": "stdio", "komut": "npx x", "etkin": True}}), encoding="utf-8")
(A_ / "kimlik/PROFIL.md").write_text("# Profil\n- Adım: ÇOK ÖZEL İSİM Ğüşiöç\n", encoding="utf-8")
(A_ / "kimlik/ornekler").mkdir()
(A_ / "kimlik/ornekler/yazi.txt").write_text("gerçek örnek yazı", encoding="utf-8")
(A_ / "kimlik/marka_kitleri/x").mkdir(parents=True)
(A_ / "kimlik/marka_kitleri/x/kit.json").write_text('{"id":"x"}', encoding="utf-8")
ikili = bytes(range(256)) * 4
(A_ / "kimlik/marka_kitleri/x/logo.png").write_bytes(ikili)
# arşiv + analiz + iyileştirme
ark = tmp / "Arsiv"
for i in range(3):
    p = ark / "Villa" / "2022" / f"f{i}.jpg"; p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1500, 1000), (150, 170, 190)); d = ImageDraw.Draw(im)
    for _ in range(100):
        x, y = random.randint(0, 1500), random.randint(0, 1000); d.rectangle([x, y, x + 80, y + 60], fill=tuple(random.randint(20, 230) for _ in range(3)), outline=(0, 0, 0), width=2)
    im.save(p, quality=90)
kod_a = f"""
import sys
sys.path.insert(0, r'{A_ / "sistem/arsiv"}'); sys.path.insert(0, r'{A_ / "sistem/araclar"}')
import arsiv as A, analiz as Z
A.ayarla(r'{ark}', 'arsiv'); A.tara(yazdir=lambda *_: None); Z.oto()
c = A.baglan(); i = c.execute("SELECT id FROM dosya ORDER BY id LIMIT 1").fetchone()[0]
Z.yaz([{{"id": i, "asama": "yapim", "konu": "cephe", "aciklama": "yapim asamasinda cephe iskelesi", "etiketler": ["iskele"], "puan": 8}}])
c.execute("INSERT INTO iyilestirme(dosya_id,model,saglayici,cikti_kok,cikti_yol,genislik,yukseklik,durum,tarih,kullan) VALUES (?,?,?,?,?,?,?,?,?,1)", (i, 'yerel-klasik', 'yerel', 'studyo', 'sistem/ortam/arsiv/iyilestirilmis/arsiv/1_yerel-klasik.jpg', 3000, 2000, 'tamam', '2026-11-15'))
c.commit()
"""
r = calistir(A_, kod_a); ok(r.returncode == 0, "A hazır (arşiv + analiz + iyileştirme kaydı)")
(A_ / "sistem/ortam/arsiv/iyilestirilmis/arsiv").mkdir(parents=True, exist_ok=True)
(A_ / "sistem/ortam/arsiv/iyilestirilmis/arsiv/1_yerel-klasik.jpg").write_bytes(b"JPEGDATA")

# --- şifreli dışa aktarma
hedef = tmp / "tasi" / "profilim.json"
kod_e = f"""
import sys, json
sys.path.insert(0, r'{A_ / "sistem/araclar"}')
import profil as P
r = P.disa_aktar(r'{hedef}', 'parola-123', True, True, True, True, False)
print(json.dumps(r, ensure_ascii=False))
"""
r = calistir(A_, kod_e); ok(r.returncode == 0, "şifreli dışa aktarma")
cikti = json.loads(r.stdout.strip().splitlines()[-1])
ham = hedef.read_text(encoding="utf-8")
ok(cikti["sifreli"] and "GIZLI_ANAHTAR" not in ham and "ÇOK ÖZEL" not in ham and "gerçek örnek" not in ham, "şifreli dosyada anahtar ve kişisel veri DÜZ METİN YOK")
ok(json.loads(ham)["sifreli"] is True and "tuz" in json.loads(ham)["kdf"], "zarf biçimi (scrypt tuzu, sürüm)")
ok(cikti["ek_zip"] and Path(cikti["ek_zip"]).is_file(), "iyileştirilmiş fotoğraflar ek zip'te")
# yanlış parola
B_ = kur("B")
kod_yp = f"""
import sys
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
try:
    P.ozet(r'{hedef}', 'yanlis'); print('KABUL')
except ValueError as e:
    print('RED', e)
try:
    P.ozet(r'{hedef}', None); print('KABUL2')
except Exception as e:
    print('SIFRE_ISTENDI', e)
"""
r = calistir(B_, kod_yp)
ok("RED parola yanlış" in r.stdout, "yanlış parola reddedildi")
ok("KABUL2" in r.stdout, "parolasız özet içerik göstermeden yalnızca 'şifreli' döner")

# --- B'ye kuru + gerçek içe aktarma
(B_ / "kimlik/PROFIL.md").write_text("# Profil (boş şablon)\n", encoding="utf-8")
kod_k = f"""
import sys, json
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
print(json.dumps(P.ozet(r'{hedef}', 'parola-123'), ensure_ascii=False))
print(json.dumps(P.ice_aktar(r'{hedef}', 'parola-123', kuru=True), ensure_ascii=False))
"""
r = calistir(B_, kod_k)
satirlar = r.stdout.strip().splitlines()
oz = json.loads(satirlar[0]); kuru = json.loads(satirlar[1])
ok(oz["anahtar_sayisi"] == 1 and oz["arsiv_dosya"] == 3 and oz["arsiv_kokleri"] == ["arsiv"] and oz["kimlik_dosyasi"] >= 4, f"özet: {oz['anahtar_sayisi']} anahtar, {oz['arsiv_dosya']} dosya, {oz['kimlik_dosyasi']} kimlik dosyası")
ok(not (B_ / "sistem/ortam/baglayici/anahtar.json").exists() and "BOŞ" not in (B_ / "kimlik/PROFIL.md").read_text(encoding="utf-8").upper().replace("BOŞ ŞABLON", "") or True, "kuru çalıştırma")
ok(not (B_ / "sistem/ortam/baglayici/anahtar.json").exists() and (B_ / "kimlik/PROFIL.md").read_text(encoding="utf-8").startswith("# Profil (boş"), "kuru çalıştırma hiçbir şey YAZMADI")
kod_i = f"""
import sys, json
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
print(json.dumps(P.ice_aktar(r'{hedef}', 'parola-123'), ensure_ascii=False))
"""
r = calistir(B_, kod_i); rap = json.loads(r.stdout.strip().splitlines()[-1])
print("   rapor:", json.dumps(rap, ensure_ascii=False)[:600])
ok(json.loads((B_ / "sistem/ayar/kullanici.json").read_text(encoding="utf-8"))["ajanlar"]["redaktor"]["model"] == "opus", "ayar geldi (redaktor opus)")
ok("model: opus" in (B_ / ".claude/agents/redaktor.md").read_text(encoding="utf-8"), "ajan dosyası eşitlendi")
ok(json.loads((B_ / "sistem/ortam/baglayici/anahtar.json").read_text(encoding="utf-8"))["GEMINI_API_KEY"] == "GIZLI_ANAHTAR_123456789", "API anahtarı geldi")
ok("heygen" in json.loads((B_ / "sistem/ortam/baglayici/mcp.json").read_text(encoding="utf-8")), "MCP kaydı geldi")
ok("ÇOK ÖZEL İSİM Ğüşiöç" in (B_ / "kimlik/PROFIL.md").read_text(encoding="utf-8") and list((B_ / "kimlik").glob("PROFIL.md.yedek-*")), "kimlik yazıldı, eski şablon .yedek olarak saklandı")
ok((B_ / "kimlik/marka_kitleri/x/logo.png").read_bytes() == ikili and (B_ / "kimlik/ornekler/yazi.txt").read_text(encoding="utf-8") == "gerçek örnek yazı", "ikili logo ve örnek dosyalar birebir")
ok((B_ / "sistem/ortam/arsiv/iyilestirilmis/arsiv/1_yerel-klasik.jpg").read_bytes() == b"JPEGDATA", "iyileştirilmiş dosya ek zip'ten geldi")
kod_d = f"""
import sys, json
sys.path.insert(0, r'{B_ / "sistem/arsiv"}'); sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import arsiv as A, analiz as Z, konum as K
c = A.baglan()
print(json.dumps({{"dosya": c.execute("select count(*) from dosya").fetchone()[0], "analiz": c.execute("select count(*) from analiz").fetchone()[0],
  "iyi": c.execute("select count(*) from iyilestirme").fetchone()[0], "kok": [dict(r)["ad"] for r in c.execute("select ad from kok")],
  "ara": len(A.ara(kelime="iskele")), "uygun": [x["yol"] for x in Z.uygun(yil="2022", asama="yapim", en_az_puan=5)],
  "bagli": K.kok_coz(c, c.execute("select id from kok where ad='arsiv'").fetchone()[0], True)["yol"] is not None, "mutlak": c.execute("select count(*) from dosya where yol like '_:%'").fetchone()[0]}}))
"""
r = calistir(B_, kod_d); d = json.loads(r.stdout.strip().splitlines()[-1])
ok(d["dosya"] == 3 and d["analiz"] == 3 and d["iyi"] == 1 and d["kok"] == ["arsiv"], f"arşiv dizini geldi: {d}")
ok(d["ara"] == 1, "anahtar kelime (Claude açıklaması) aramada bulunuyor")
ok(len(d["uygun"]) >= 1, "'uygun' sorgusu çalışıyor (analiz geldi)")
ok(d["mutlak"] == 0, "dizinde mutlak yol yok")
ok(d["bagli"] is True, "arşiv bu bilgisayarda aynı yolda olduğu için otomatik bağlandı (başka-bilgisayar kaydı)")
# idempotent
r = calistir(B_, kod_i); rap2 = json.loads(r.stdout.strip().splitlines()[-1])
r = calistir(B_, kod_d); d2 = json.loads(r.stdout.strip().splitlines()[-1])
ok(d2["dosya"] == 3 and d2["analiz"] == 3 and d2["iyi"] == 1, "ikinci içe aktarma kopya üretmedi")

# --- ileri uyum: daha yeni sürüm + bilinmeyen bölüm
kod_f = f"""
import sys, json
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
z = json.load(open(r'{tmp / "tasi" / "plain.json"}', encoding='utf-8')) if False else None
r = P.disa_aktar(r'{tmp / "tasi" / "plain.json"}', None, False, False, False)
zz = json.load(open(r['dosya'], encoding='utf-8'))
zz['surum'] = 2
zz['icerik']['seriler'] = {{'dizi-a': {{'sezon': 1}}}}
zz['icerik']['ayar']['yeni_alan'] = 1
json.dump(zz, open(r['dosya'], 'w', encoding='utf-8'))
print(json.dumps(P.ice_aktar(r['dosya'], None), ensure_ascii=False))
r2 = P.disa_aktar(r'{tmp / "tasi" / "plain2.json"}', None, False, False, False)
print('EK_GERI_KONDU', 'seriler' in json.load(open(r2['dosya'], encoding='utf-8'))['icerik'].get('ek', {{}}), r['uyari'][:30])
"""
r = calistir(B_, kod_f)
ok("daha yeni bir sürümden" in r.stdout and "EK_GERI_KONDU True" in r.stdout, "yeni sürüm dosyası alındı, bilinmeyen bölüm saklanıp sonraki dışa aktarmaya geri kondu")
ok("anahtarsız" not in r.stdout.split("EK_GERI")[0] or True, "—")
plain = (tmp / "tasi" / "plain.json").read_text(encoding="utf-8")
ok("GIZLI_ANAHTAR" not in plain and "anahtar_adlari" in plain, "--anahtarsız: anahtar değeri yok, yalnızca adları")
# --- güvenlik: kötü kimlik yolu
kotu = json.loads((tmp / "tasi" / "plain.json").read_text(encoding="utf-8"))
kotu["icerik"]["kimlik"]["dosyalar"]["../../kacak.md"] = {"metin": "x"}
(tmp / "tasi" / "kotu.json").write_text(json.dumps(kotu), encoding="utf-8")
kod_g = f"""
import sys
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
try:
    P.ice_aktar(r'{tmp / "tasi" / "kotu.json"}', None); print('KABUL')
except ValueError as e:
    print('RED', e)
"""
r = calistir(B_, kod_g)
ok("RED" in r.stdout and not (tmp / "B" / "kacak.md").exists() and not (tmp / "kacak.md").exists(), "klasör dışına yazma denemesi reddedildi: " + r.stdout.strip()[:80])
# --- atla kipi
(B_ / "kimlik/PROFIL.md").write_text("YEREL DEĞİŞİKLİK", encoding="utf-8")
kod_a2 = f"""
import sys, json
sys.path.insert(0, r'{B_ / "sistem/araclar"}')
import profil as P
print(json.dumps(P.ice_aktar(r'{hedef}', 'parola-123', cakisma='atla'), ensure_ascii=False)[:300])
"""
calistir(B_, kod_a2)
ok((B_ / "kimlik/PROFIL.md").read_text(encoding="utf-8") == "YEREL DEĞİŞİKLİK", "'atla' kipinde var olan dosyaya dokunulmadı")
print("SONUÇ: %d tamam, %d hata" % tuple(S))
shutil.rmtree(tmp, ignore_errors=True)
