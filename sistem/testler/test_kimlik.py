import os, re, sys, shutil, tempfile, json, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
ok = bad = 0
def t(ad, c):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("BAŞARISIZ:", ad)

tmp = Path(tempfile.mkdtemp())
shutil.copytree(R / "sistem" / "sablon", tmp / "sistem" / "sablon")
os.environ["YST_KIMLIK_KOK"] = str(tmp)
sp = importlib.util.spec_from_file_location("ks", R / "sistem" / "araclar" / "kimlik_sablon.py")
K = importlib.util.module_from_spec(sp); sp.loader.exec_module(K)

# kişisel kalıplar bu bilgisayardaki yerel dosyadan okunur (depoda kişisel ad bulunmaz)
YEREL = R / "sistem" / "ortam" / "yerel" / "kisisel_yasak.txt"
KALIP = [x.strip().lower() for x in YEREL.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")] if YEREL.is_file() else []
# şablonda kişisel veri yok
for f in (R / "sistem" / "sablon").rglob("*"):
    if f.is_file():
        s = f.read_text(encoding="utf-8").lower()
        t(f"şablonda kişisel veri yok: {f.name}", not any(re.search(k, s) for k in KALIP))

yeni = K.kur()
t("3 dosya oluştu", len(yeni) == 3 and (tmp / "kimlik" / "PROFIL.md").exists() and (tmp / "kimlik" / "marka_kitleri" / "varsayilan" / "kit.json").exists())
t("ikinci kur hiçbir şeyi ezmez", K.kur() == [])
t("başlangıçta kimlik boş", K.durum()["dolu"] is False)
d = K.kaydet("Ayşe Yılmaz", "Yılmaz Mimarlık", "Mimar", "Ankara")
t("kaydet sonrası dolu", d["dolu"] and d["ad_marka"] == "Ayşe Yılmaz / Yılmaz Mimarlık" and d["kit_isim"] == "Yılmaz Mimarlık")
s = (tmp / "kimlik" / "PROFIL.md").read_text(encoding="utf-8")
t("rol ve şehir yazıldı", "- Rolüm / işim: Mimar" in s and "- Şehir / çalıştığım bölge: Ankara" in s)
t("diğer bölümler bozulmadı", "## 4. Konuşma tarzım" in s and s.count("[ ]") > 10)
# boş alan mevcut cevabı silmez
K.kaydet("", "", "Yönetmen", "")
s = (tmp / "kimlik" / "PROFIL.md").read_text(encoding="utf-8")
t("boş bırakılan alan silmez", "Ayşe Yılmaz / Yılmaz Mimarlık" in s and "Yönetmen" in s)
# satır sonu enjeksiyonu
K.kaydet("A\nB", "", "", "")
t("satır sonu temizlendi", "\n- Adım / marka adım: A B" in (tmp / "kimlik" / "PROFIL.md").read_text(encoding="utf-8").replace("\r\n", "\n"))
# kullanıcının var olan dosyası ezilmez
(tmp / "kimlik" / "MARKA.md").write_text("KENDİ MARKAM", encoding="utf-8")
K.kur()
t("var olan MARKA.md korundu", (tmp / "kimlik" / "MARKA.md").read_text(encoding="utf-8") == "KENDİ MARKAM")
# gerçek depo: kur hiçbir şey oluşturmaz ve gerçek dosyalar duruyor
os.environ.pop("YST_KIMLIK_KOK")
sp2 = importlib.util.spec_from_file_location("ks2", R / "sistem" / "araclar" / "kimlik_sablon.py")
K2 = importlib.util.module_from_spec(sp2); sp2.loader.exec_module(K2)
K2.kur()  # eksikse şablondan oluşturur
t("kimlik dosyaları var ve ikinci kur dokunmaz", K2.kur() == [] and (R / "kimlik" / "PROFIL.md").exists())
# sürüm betiği: kişisel kalıplar yerel dosyadan, depoda yok
sy = (R / "sistem" / "kurulum" / "surum_yap.py").read_text(encoding="utf-8").lower()
t("surum_yap.py içinde yerel kişisel kalıplardan biri yok", not any(re.search(k, sy) for k in KALIP))
sys.path.insert(0, str(R / "sistem" / "kurulum"))
import surum_yap as S
BS = chr(92)  # kaynakta gerçek yol/e-posta kalıbı bulunmasın: sürüm paketinin kişisel veri taraması testleri de tarar
ORNEK_YOL = "C:" + BS + "Users" + BS + "Biri" + BS + "Desktop"
ORNEK_EPOSTA = "ornek@" + "gmail" + ".com"
t("genel desenler yüklendi", any(p.search(ORNEK_YOL) for p in S.YASAK) and any(p.search(ORNEK_EPOSTA) for p in S.YASAK))
t("kimlik/ pakete girmez", S.dosya_icerigi("kimlik/PROFIL.md", b"x") is None and S.dosya_icerigi("sistem/sablon/kimlik/PROFIL.md", b"x") is not None)
shutil.rmtree(tmp, ignore_errors=True)
print(f"{ok} başarılı, {bad} başarısız")
