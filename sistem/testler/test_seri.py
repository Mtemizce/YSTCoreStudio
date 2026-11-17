"""Seri modülü (sistem/araclar/seri.py): görsel stil, model seti (karakter/nesne/mekân + görseller), bölüm ekleme/düzenleme, senaryo, bölüme model eşleme ve ajan bağlamı."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ["YST_GORSEL_SAHTE"] = "1"
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "araclar"))
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


import gorsel_kutuphane as G
import seri as D

tmp = Path(tempfile.mkdtemp(prefix="yst-seri-"))
G.KOK, G.TASLAK, G.ONAYLI, G.INDEKS = tmp / "g", tmp / "g" / "taslak", tmp / "g" / "onayli", tmp / "g" / "index.json"
D.KOK = tmp / "seriler"
SID = "zz-dizi"
projeler = [R / "projeler" / D.proje_adi(SID, 1, 1), R / "projeler" / D.proje_adi(SID, 1, 2)]
try:
    k = D.olustur("ZZ Dizi", "dizi", "Ofiste geçen komedi", [], "sıcak, kısa cümleler", "anime-gunluk")
    ok(k["id"] == SID and k["gorsel_stil"] == "anime-gunluk" and k["model_seti"] == [] and k["surum"] == 2, "seri: görsel stil ve boş model seti ile oluşur")
    for kotu, ne in (((" ZZ Dizi",), "aynı ad"), (("Başka", "dizi", "", None, "", "yok-stil"), "bilinmeyen stil"), (("Başka", "film"), "geçersiz tür")):
        try:
            D.olustur(*kotu)
            ok(False, f"reddedilmeliydi: {ne}")
        except ValueError:
            ok(True, f"geçersiz seri reddedilir ({ne})")
    ok(any(s["id"] == SID and s["model"] == 0 for s in D.liste()), "liste: model sayısı görünür")

    taslak = G.uret_tek("kısa saçlı bir kadın", "anime-gunluk", 512, 512, 3)
    onayli1 = G.onayla(G.uret_tek("kısa saçlı bir kadın, ofis", "anime-gunluk", 512, 512, 4)["id"], arsive=False)
    onayli2 = G.onayla(G.uret_tek("kısa saçlı bir kadın, yan profil", "anime-gunluk", 512, 512, 5)["id"], arsive=False)
    m = D.model_ekle(SID, "karakter", "Ayşe", "kısa siyah saç, mavi gömlek", "short black hair, blue shirt, round glasses")
    ok(m["id"] == "ayse" and m["gorseller"] == [] and m["ana"] == "", "model seti: karakter eklenir (görselsiz)")
    for kotu, ne in ((("kisi", "X"), "geçersiz tür"), (("karakter", "Ayşe"), "aynı model")):
        try:
            D.model_ekle(SID, *kotu)
            ok(False, f"reddedilmeliydi: {ne}")
        except ValueError:
            ok(True, f"model: {ne} reddedilir")
    try:
        D.model_gorsel(SID, "ayse", taslak["id"])
        ok(False, "taslak görsel bağlanmamalıydı")
    except ValueError as e:
        ok("onaylı" in str(e), "model: yalnızca onaylı görsel bağlanır (taslak reddedilir)")
    m = D.model_gorsel(SID, "ayse", onayli1["id"])
    ok(m["ana"] == onayli1["id"], "model: ilk görsel ana görsel olur")
    m = D.model_gorsel(SID, "ayse", onayli2["id"], ana=True)
    ok(m["ana"] == onayli2["id"] and len(m["gorseller"]) == 2, "model: ana görsel değiştirilebilir")
    m = D.model_gorsel(SID, "ayse", onayli2["id"], kaldir=True)
    ok(m["ana"] == onayli1["id"] and m["gorseller"] == [onayli1["id"]], "model: ana görsel kaldırılınca diğeri ana olur")
    D.model_ekle(SID, "nesne", "Kırmızı Fincan", "porselen, kırmızı", "red porcelain cup")
    D.model_ekle(SID, "mekan", "Ofis", "açık plan ofis", "open plan office, large windows")
    ok(len(D.oku(SID)["model_seti"]) == 3, "model seti: karakter + nesne + mekân")
    eki, stil = D.model_istemi(SID, "ayse", "kahve içiyor")
    ok(eki == "kahve içiyor, short black hair, blue shirt, round glasses" and stil == "anime-gunluk", "model istemi: sabit istem eki ve serinin görsel stili birleşir")

    b1 = D.bolum_ekle(SID, 1, "İlk gün", "Ayşe işe başlar", proje_ac=False, senaryo="Sahne 1: Ayşe kapıdan girer.", gorunenler=["ayse", "ofis"])
    b2 = D.bolum_ekle(SID, 1, "Fincan", "Fincan kaybolur", proje_ac=False, gorunenler=["kirmizi-fincan"])
    ok(b1["no"] == 1 and b2["no"] == 2 and b1["proje"] == projeler[0].name and b1["gorunenler"] == ["ayse", "ofis"], "bölümler art arda numaralanır; görünen modeller bölüme işlenir")
    try:
        D.bolum_ekle(SID, 1, "Hata", proje_ac=False, gorunenler=["yok-model"])
        ok(False, "olmayan model reddedilmeliydi")
    except ValueError:
        ok(True, "bölüm: model setinde olmayan model reddedilir")

    for p in projeler:
        (p / "kaynak").mkdir(parents=True, exist_ok=True)
    D.bolum_guncelle(SID, 1, 1, senaryo="Sahne 1: Ayşe kapıdan girer. Sahne 2: fincanı bulur.", ozet="Ayşe'nin ilk günü")
    pr = projeler[0]
    ok((pr / "kaynak" / "belge" / "senaryo.md").read_text(encoding="utf-8").count("fincanı bulur") == 1, "düzenleme: senaryo projenin kaynak/belge/senaryo.md dosyasına yazılır")
    ayse = [f.name for f in (pr / "kaynak" / "foto").glob("model-ayse-*.png")]
    ok(len(ayse) == 1 and ayse[0] == f"model-ayse-{onayli1['id']}.png", "düzenleme: bölümde görünen karakterin onaylı görseli projeye kopyalanır")
    md = (pr / "seri_model_seti.md").read_text(encoding="utf-8")
    ok("## Ayşe (karakter)" in md and "short black hair" in md and "(ana görsel)" in md and "Kırmızı Fincan" not in md, "seri_model_seti.md: yalnızca bu bölümdeki modeller, sabit istem eki ve ana görsel işareti")
    bg = D.baglam(SID, 1, 2)
    ok("Anime: günlük yaşam" in bg and "BU BÖLÜMDE GÖRÜNÜR" in bg and "Ayşe'nin ilk günü" in bg and "[PLAN; henüz üretilmedi]" in bg, "bağlam: görsel stil, model işaretleri ve önceki bölüm özeti")
    D.bolum_guncelle(SID, 1, 2, gorunenler=["ayse"])
    ok(D.oku(SID)["sezonlar"][0]["bolumler"][1]["gorunenler"] == ["ayse"], "bölümde görünen modeller sonradan değiştirilebilir")
    try:
        D.bolum_guncelle(SID, 1, 9, ad="yok")
        ok(False, "olmayan bölüm reddedilmeliydi")
    except ValueError:
        ok(True, "olmayan bölüm düzenlenemez")
    try:
        D.bolum_guncelle(SID, 1, 1, durum="bilinmeyen")
        ok(False, "geçersiz durum reddedilmeliydi")
    except ValueError:
        ok(True, "geçersiz bölüm durumu reddedilir")

    k2 = D.guncelle(SID, aciklama="Yeni açıklama", gorsel_stil="anime-aksiyon")
    ok(k2["aciklama"] == "Yeni açıklama" and k2["gorsel_stil"] == "anime-aksiyon" and len(k2["model_seti"]) == 3 and len(D.bolumler(SID)) == 2, "seri düzenleme: model seti ve bölümler korunur")
    D.model_sil(SID, "ofis")
    ok(D.oku(SID)["sezonlar"][0]["bolumler"][0]["gorunenler"] == ["ayse"] and len(D.oku(SID)["model_seti"]) == 2, "model silinince bölümlerden de çıkar")
    D.ozet_yaz(SID, 1, 1, "Ayşe işe başladı ve fincanı buldu.")
    ok("fincanı buldu" in D.baglam(SID, 1, 2) and D.oku(SID)["sezonlar"][0]["bolumler"][0]["durum"] == "bitti", "biten bölüm özeti sonraki bölümün bağlamına girer")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    for p in projeler:
        shutil.rmtree(p, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
