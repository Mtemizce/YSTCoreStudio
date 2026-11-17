import sys, json, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sp = importlib.util.spec_from_file_location("donanim", str(Path(__file__).resolve().parents[2] / "sistem/araclar/donanim.py"))
D = importlib.util.module_from_spec(sp); sp.loader.exec_module(D)
ok = 0; bad = 0
def t(ad, kosul):
    global ok, bad
    if kosul: ok += 1
    else: bad += 1; print("BAŞARISIZ:", ad)

gercek = D.sistem()
t("ram okundu", gercek["ram_gb"] > 1)
t("cpu okundu", gercek["cpu"] != "bilinmiyor" and gercek["mantiksal_cekirdek"] >= 1)
t("disk okundu", gercek["disk_bos_gb"] > 0)

def sis(ram, vram, disk, cuda=True):
    g = [{"ad": "Test GPU", "vram_gb": vram, "cuda": cuda}] if vram or not cuda else []
    return {"ram_gb": ram, "ram_bos_gb": ram, "gpuler": g, "en_iyi_gpu": g[0] if g else None, "cuda": cuda and bool(vram), "vram_gb": vram,
            "disk_bos_gb": disk, "disk_toplam_gb": 500, "cpu": "x", "mantiksal_cekirdek": 8, "os": "t"}

guc = sis(64, 24, 500)
t("güçlü makinede z-image Q6_K yeterli", D.degerlendir("zimage", guc)["secenekler"]["Q6_K"]["durum"] == "yeterli")
t("güçlü makinede hepsi yeterli", all(b["durum"] == "yeterli" for b in D.hepsi.__globals__["KATALOG"] and [D.degerlendir(k, guc) for k in D.KATALOG]))

zayif = sis(4, 0, 3, cuda=False)
z = D.degerlendir("zimage", zayif)
t("zayıf makinede z-image yetersiz (disk+ram)", z["secenekler"]["Q3_K"]["durum"] == "yetersiz")
t("zayıf makinede neden satırları var", any(s["durum"] == "yok" for s in z["secenekler"]["Q3_K"]["satirlar"]))
w = D.degerlendir("whisper", zayif)
t("ekran kartı yok: whisper small 4 GB RAM'de sınırda/yeterli, çökmez", w["secenekler"]["small"]["durum"] in ("yeterli", "sınırda"))
t("ekran kartı yok: large-v3 yetersiz (RAM 8 gerekir)", w["secenekler"]["large-v3"]["durum"] == "yetersiz")
t("GPU isteğe bağlı bileşen VRAM'siz yetersiz DEĞİL (yalnızca sınırda)", all(l["durum"] != "yok" for l in D.degerlendir("derinlik", sis(8, 0, 50, cuda=False))["secenekler"]["small"]["satirlar"] if "VRAM" in l["etiket"]))
t("render GPU gerektirmez", any(l["etiket"] == "Ekran kartı" and l["durum"] == "ok" for l in D.degerlendir("render", zayif)["secenekler"]["render"]["satirlar"]))

orta = sis(16, 6, 100)
t("6 GB VRAM + 16 GB RAM: Q4_0 uygun (RAM'e taşınır)", D.degerlendir("zimage", orta)["secenekler"]["Q4_0"]["durum"] == "yeterli")
t("uygun nedenini söyler", "RAM'e taşınır" in str(D.degerlendir("zimage", orta)["secenekler"]["Q4_0"]["satirlar"]))
t("6 GB VRAM + 64 GB RAM: Q6_K sınırda (yetersiz değil)", D.degerlendir("zimage", sis(64, 6, 100))["secenekler"]["Q6_K"]["durum"] == "sınırda")
t("6 GB VRAM + 8 GB RAM: Q4_0 hâlâ sınırda (RAM da dar)", D.degerlendir("zimage", sis(8, 6, 100))["secenekler"]["Q4_0"]["durum"] in ("sınırda", "yetersiz"))
t("taşıma yalnızca z-image'da: whisper large-v3 6 GB VRAM'de", D.degerlendir("whisper", sis(64, 4, 100))["secenekler"]["large-v3"]["durum"] == "sınırda")
t("6 GB VRAM: Q3_K yeterli", D.degerlendir("zimage", orta)["secenekler"]["Q3_K"]["durum"] == "yeterli")

# disk
dar = sis(32, 12, 6.2)
t("disk sınırı: 6 GB model 6.2 GB boşta sınırda", D.degerlendir("zimage", dar)["secenekler"]["Q3_K"]["durum"] == "sınırda")
t("disk çok az: yetersiz", D.degerlendir("zimage", sis(32, 12, 2))["secenekler"]["Q3_K"]["durum"] == "yetersiz")

# kurulum bütçesi
p_cuda = D.ilk_kurulum(sis(32, 8, 100))
p_cpu = D.ilk_kurulum(sis(32, 0, 100, cuda=False))
t("kurulum GPU olsa da olmasa da küçük CPU PyTorch ile aynı (CUDA isteğe bağlı bileşen)", p_cpu["kurulumda_gb"] == p_cuda["kurulumda_gb"] and p_cuda["kurulumda_gb"] < 3)
t("GPU hızlandırma isteğe bağlı bileşen olarak katalogda", D.KATALOG["gpu"]["varsayilan"] is False and D.KATALOG["gpu"]["gpu"] == "gerekir")
t("derinlik planda listede (arka planda iner)", any("Depth Anything" in x["ad"] and x["zaman"] == "arka planda" for x in p_cuda["parcalar"]))
t("z-image toplamda YOK", not any("Z-Image" in x["ad"] for x in p_cuda["parcalar"]))
t("toplam = kurulumda + arka plan + sonra", abs(p_cuda["toplam_gb"] - (p_cuda["kurulumda_gb"] + p_cuda["arka_plan_gb"] + p_cuda["ilk_kullanimda_gb"])) < 0.11)
t("PyTorch, yapay zekâ paketleri ve modeller arka planda", p_cuda["arka_plan_gb"] > 1 and any(x["zaman"] == "arka planda" and "PyTorch" in x["ad"] for x in p_cuda["parcalar"]) and p_cuda["kurulumda_gb"] < 2)
t("disk yetersiz bayrağı", D.ilk_kurulum(sis(32, 8, 3))["disk_yeterli"] is False and p_cuda["disk_yeterli"] is True)
t("önerilen boş disk toplamdan büyük", p_cuda["onerilen_bos_disk_gb"] > p_cuda["toplam_gb"])

# hepsi json'a çevrilebilir
t("hepsi JSON", len(json.dumps(D.hepsi(), ensure_ascii=False)) > 500)
# her bileşende kaynak alanı geçerli
t("kaynaklar geçerli", all(sec["kaynak"] in ("olculdu", "yayimlanan", "tahmin") for b in D.KATALOG.values() for sec in b["secenekler"].values()))
# kurulum.py sözdizimi + toplam adım
src = open(str(Path(__file__).resolve().parents[2] / "sistem/kurulum/kurulum.py"), encoding="utf-8").read()
compile(src, "kurulum.py", "exec")
t("kurulum 7 adım", "toplam = 7" in src and 'adim(7, toplam' in src and "adim(8, toplam" not in src)
t("transformers (yapay zekâ paketleri) gereksinim-ml.txt'te: arka planda kurulur", "transformers" in open(str(Path(__file__).resolve().parents[2] / "sistem/kurulum/gereksinim-ml.txt"), encoding="utf-8").read())
print(f"{ok} başarılı, {bad} başarısız")
