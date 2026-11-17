import hashlib, http.server, importlib.util, io, json, os, shutil, sys, tempfile, threading, time, zipfile
from pathlib import Path
R = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="yst_yg_"))
S = [0, 0]
def ok(c, m):
    S[0 if c else 1] += 1; print(("OK   " if c else "FAIL ") + m)
DOSYA = {
    "leejet/Z-Image-Turbo-GGUF": {"z_image_turbo-Q4_0.gguf": b"M" * 300_000, "z_image_turbo-Q3_K.gguf": b"m" * 100_000},
    "unsloth/Qwen3-4B-Instruct-2507-GGUF": {"Qwen3-4B-Instruct-2507-Q4_K_M.gguf": b"L" * 200_000},
    "black-forest-labs/FLUX.1-schnell": {"ae.safetensors": b"V" * 50_000},
}
KOTU = set()
zb = io.BytesIO()
with zipfile.ZipFile(zb, "w") as z:
    z.writestr("sd-cli.exe", b"MZ-sahte"); z.writestr("stable-diffusion.dll", b"x"); z.writestr("../kacak.txt", b"kac")
ZIPB = zb.getvalue()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path
        if p.startswith("/api/models/") and p.endswith("/tree/main"):
            depo = p[len("/api/models/"):-len("/tree/main")]
            if depo not in DOSYA: self.send_response(401); self.end_headers(); return
            self._j([{"path": n, "size": len(b), "lfs": {"oid": ("0" * 64 if n in KOTU else hashlib.sha256(b).hexdigest()), "size": len(b)}} for n, b in DOSYA[depo].items()])
        elif "/resolve/main/" in p:
            depo, ad = p[1:].split("/resolve/main/"); b = DOSYA[depo][ad]
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif p == "/repos/leejet/stable-diffusion.cpp/releases/latest":
            self._j({"assets": [{"name": "sd-master-bin-win-avx2-x64.zip", "browser_download_url": f"http://127.0.0.1:{PORT}/zip/a", "size": len(ZIPB)},
                                {"name": "sd-master-bin-win-vulkan-x64.zip", "browser_download_url": f"http://127.0.0.1:{PORT}/zip/v", "size": len(ZIPB)},
                                {"name": "sd-master-bin-linux-x64.zip", "browser_download_url": f"http://127.0.0.1:{PORT}/zip/v", "size": len(ZIPB)},
                                {"name": "sd-master-bin-Darwin-macOS-arm64.zip", "browser_download_url": f"http://127.0.0.1:{PORT}/zip/v", "size": len(ZIPB)}]})
        elif p.startswith("/zip/"):
            self.send_response(200); self.send_header("Content-Length", str(len(ZIPB))); self.end_headers(); self.wfile.write(ZIPB)
        else:
            self.send_response(404); self.end_headers()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); PORT = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update(YST_GORSEL_KOK=str(TMP), YST_HF_ADRES=f"http://127.0.0.1:{PORT}", YST_GH_ADRES=f"http://127.0.0.1:{PORT}")
sp = importlib.util.spec_from_file_location("yg_t", R / "sistem/araclar/yerel_gorsel.py"); Y = importlib.util.module_from_spec(sp); sp.loader.exec_module(Y)
# paket seçimi: gerçek yayın adlarıyla (leejet/stable-diffusion.cpp)
GERCEK = [{"name": n} for n in ["cudart-sd-bin-win-cu12-x64.zip", "sd-master-532d2c1-bin-Darwin-macOS-26.7.2-arm64.zip", "sd-master-532d2c1-bin-Linux-Ubuntu-24.04-x86_64-rocm-10.1.0.zip",
                                "sd-master-532d2c1-bin-Linux-Ubuntu-26.04-x86_64-vulkan.zip", "sd-master-532d2c1-bin-Linux-Ubuntu-26.04-x86_64.zip", "sd-master-532d2c1-bin-win-cpu-x64.zip",
                                "sd-master-532d2c1-bin-win-cuda12-x64.zip", "sd-master-532d2c1-bin-win-rocm-10.1.0-x64.zip", "sd-master-532d2c1-bin-win-vulkan-x64.zip"]]
ok(Y._paket_sec(GERCEK, "win32", "AMD64", True)["name"].endswith("win-vulkan-x64.zip"), "paket: Windows → Vulkan yapısı (cudart ve cuda/rocm seçilmez)")
ok(Y._paket_sec(GERCEK, "darwin", "arm64", False)["name"].endswith("Darwin-macOS-26.7.2-arm64.zip"), "paket: macOS → Darwin-macOS paketi")
ok(Y._paket_sec(GERCEK, "linux", "x86_64", True)["name"].endswith("26.04-x86_64-vulkan.zip"), "paket: Linux + Vulkan → vulkan yapısı (x86_64 adı tanınır)")
ok(Y._paket_sec(GERCEK, "linux", "x86_64", False)["name"].endswith("26.04-x86_64.zip"), "paket: Linux, Vulkan yok → düz yapı")
ok("rocm" not in Y._paket_sec(GERCEK, "linux", "x86_64", False)["name"] and "rocm" not in Y._paket_sec(GERCEK, "linux", "x86_64", True)["name"], "paket: AMD rocm yapısı seçilmez")
ok(Y._paket_sec(GERCEK, "darwin", "x86_64", False) is None and Y._paket_sec(GERCEK, "linux", "aarch64", True) is None, "paket: hazır paketi olmayan mimari için None (açık hata verilir)")
def bekle():
    for _ in range(80):
        time.sleep(0.25)
        if Y.IS["bitti"] and not Y.IS["var"]: return
try:
    d = Y.durum(); ok(not d["kurulu"] and d["kalite"] is None, "varsayılan: kurulu değil")
    for v, k in ((0, "Q4_0"), (3800, "Q3_K"), (4096, "Q3_K"), (6144, "Q4_0"), (8192, "Q5_0"), (16000, "Q6_K")):
        Y.vram_mb = lambda v=v: v; ok(Y.oneri()["kalite"] == k, f"VRAM {v} MB → {k}")
    try: Y.kur("../x"); ok(False, "geçersiz kalite kabul edildi")
    except ValueError: ok(True, "geçersiz kalite reddedildi")
    try: Y.uret("x", "a.png"); ok(False, "kurulu değilken üretim")
    except RuntimeError as e: ok("kurulu değil" in str(e), "kurulu değilken üretim reddedildi")
    # bozuk sağlama toplamı
    KOTU.add("z_image_turbo-Q4_0.gguf"); Y.kur("Q4_0"); bekle()
    log_ilk = list(Y.IS["log"])  # sd-cli bu ilk denemede iner; sonraki kurulum "zaten var" der
    ok(Y.IS["hata"] and "SHA256" in Y.IS["hata"], f"sağlama toplamı uyuşmazlığı reddedildi: {Y.IS['hata'][:70]}")
    ok(not list((TMP / "sistem/ortam/yerel-gorsel/modeller").glob("z_image*")), "bozuk dosya diskte bırakılmadı")
    KOTU.clear()
    # tam kurulum
    Y.kur("Q4_0"); bekle()
    d = Y.durum()
    ok(not Y.IS["hata"] and d["kurulu"] and d["kalite"] == "Q4_0", f"kurulum tamam: {Y.IS['hata'] or 'hata yok'} · kalite {d['kalite']}")
    ok(Y.IS["yuzde"] == 100, "ilerleme %100")
    ok(Y._exe() is not None and Y._exe().name == "sd-cli.exe", "sd-cli bulundu (vulkan paketi seçildi)")
    ok(not (TMP / "kacak.txt").exists() and not (TMP / "sistem/ortam/kacak.txt").exists(), "zip yol kaçışı engellendi")
    ok(any("zip/v" in x or "vulkan" in x or "-bin-" in x for x in log_ilk), "vulkan yapısı seçildi: " + ([x for x in log_ilk if "stable" in x] or ["?"])[0][9:60])
    # üretim (sahte sd-cli)
    py_kod = TMP / "fake_sd.py"  # komut satırını -o dosyasına yazar
    py_kod.write_text("import sys\na = sys.argv\nopen(a[a.index('-o') + 1], 'wb').write(' '.join(a).encode())\n", encoding="utf-8")
    if os.name == "nt":
        fake = TMP / "fake_sd.cmd"
        fake.write_text('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, py_kod), encoding="utf-8")
    else:
        fake = TMP / "fake_sd"
        fake.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, py_kod), encoding="utf-8")
        fake.chmod(0o755)
    os.environ["YST_SD_CLI"] = str(fake)
    r = Y.uret("ofis binası dış cephe", "projeler/x/gorsel.png", 1000, 570, 7, 8)
    cmd = Path(r["dosya"]).read_text()
    ok(Path(r["dosya"]).is_file() and "--offload-to-cpu" in cmd and "--diffusion-fa" in cmd and "-W 960" in cmd and "-H 512" in cmd and "-s 7" in cmd and "ofis" in cmd, f"üretim komutu doğru (boyut 64'ün katına yuvarlandı): {cmd[-70:]}")
    try: Y.uret("x" * 2500, "a.png"); ok(False, "çok uzun istem")
    except ValueError: ok(True, "çok uzun istem reddedildi")
    ok(Y.sil() > 0 and not Y.durum()["kurulu"], "kaldır: dosyalar silindi")
finally:
    srv.shutdown(); shutil.rmtree(TMP, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
