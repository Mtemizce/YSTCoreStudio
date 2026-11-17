#!/usr/bin/env python3
"""Tarayıcı sahnelerinden kare yakalayıcı (kalem-çizim hattı).

  python sistem/kit/kalem/ortak/yakala.py <sayfa.html> <cikis klasörü> [genislik yukseklik] [--kare N]

Sayfa `/ortak/surucu.js`'i `kur()` / `kare(f)` ile çağırır; kareler `cikis/0000.png ...` olarak yazılır. Zaman kare numarasından gelir
(Math.random yok): iki koşu aynı kareyi verir. `--kare N` yalnızca ilk N kareyi yakalar (deneme).

Kaynak: github.com/leodavincs/kalem `ortak/yakala.py` (MIT, © 2026 Leo), YSTCore için uyarlandı:
  - Tarayıcı bulma: CHROME ortam değişkeni, yoksa kurulumun Remotion chrome-headless-shell'i, yoksa sistemdeki Chrome/Edge/Chromium.
  - Sunucu YALNIZCA izinli yolları sunar: /ortak/ (bu klasör), /node_modules/paper/, /sahne/ (sayfanın kendi klasörü). Depo kökü sunulmaz.
  - macOS'a özgü bayraklar (metal) kaldırıldı; Windows/Linux/macOS'ta çalışır.
"""
import http.server
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ORTAK = Path(__file__).resolve().parent
ROOT = ORTAK.parents[3]  # sistem/kit/kalem/ortak → depo kökü
IZINLI = {"/ortak/": ORTAK, "/node_modules/paper/": ROOT / "node_modules" / "paper"}


def tarayici() -> list[str]:
    """Başsız çalıştırılabilir bir Chromium: [yol, ...ek bayraklar]."""
    ov = os.environ.get("CHROME")
    if ov and Path(ov).is_file():
        return [ov, "--headless=new"]
    hs = ROOT / "node_modules" / ".remotion" / "chrome-headless-shell"
    if hs.is_dir():
        exe = "chrome-headless-shell.exe" if os.name == "nt" else "chrome-headless-shell"
        for p in hs.rglob(exe):
            if p.is_file():
                return [str(p)]  # zaten başsız: --headless gerekmez
    adaylar = []
    if os.name == "nt":
        for kok in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("LOCALAPPDATA", "")):
            adaylar += [Path(kok) / "Google/Chrome/Application/chrome.exe", Path(kok) / "Microsoft/Edge/Application/msedge.exe"]
    elif sys.platform == "darwin":
        adaylar = [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for ad in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        b = shutil.which(ad)
        if b:
            adaylar.append(Path(b))
    for p in adaylar:
        if p.is_file():
            return [str(p), "--headless=new"]
    sys.exit("Başsız tarayıcı bulunamadı: Remotion'un chrome-headless-shell'i kurulu değil (kurulumu tamamla) ya da CHROME=<yol> ver.")


def main() -> int:
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    kare_sinir = None
    if "--kare" in sys.argv:
        kare_sinir = int(sys.argv[sys.argv.index("--kare") + 1])
        a = [x for x in a if x != str(kare_sinir)]
    if len(a) < 2:
        print(__doc__)
        return 2
    sayfa = Path(a[0]).resolve()
    cikis = Path(a[1]).resolve()
    W, H = (int(a[2]), int(a[3])) if len(a) > 3 else (1920, 1080)
    if not sayfa.is_file():
        sys.exit(f"Sayfa yok: {sayfa}")
    if cikis.is_dir():  # yalnızca bu betiğin yazdığı kare klasörü silinir; başka dosya varsa dokunma
        yabanci = [f for f in os.listdir(cikis) if not re.fullmatch(r"\d{4}\.png", f)]
        if yabanci:
            sys.exit(f"{cikis} içinde kare dışı dosyalar var ({', '.join(yabanci[:3])}...). Boş ya da yeni bir klasör ver.")
        shutil.rmtree(cikis)
    cikis.mkdir(parents=True)
    SAHNE = sayfa.parent
    bitti = threading.Event()
    durum = {"hata": None, "son": time.time(), "kare": 0}

    class I(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *x):
            pass

        def handle(self):
            try:
                super().handle()
            except (ConnectionError, TimeoutError):
                pass  # tarayıcı kapanırken bağlantıyı koparır: hata değil

        def _dosya(self):
            yol = unquote(urlparse(self.path).path)
            if yol == "/sayfa.html":
                p = sayfa
            elif yol.startswith("/sahne/"):
                p = SAHNE / yol[len("/sahne/"):]
            else:
                p = None
                for on, kok in IZINLI.items():
                    if yol.startswith(on):
                        p = kok / yol[len(on):]
                        break
            if p is None:
                return None
            p = p.resolve()
            kok_ok = [SAHNE.resolve(), *[k.resolve() for k in IZINLI.values()]]
            if not any(k == p or k in p.parents for k in kok_ok) or not p.is_file():
                return None  # yol kaçışı (..) ve izinli olmayan klasörler reddedilir
            return p

        def do_GET(self):
            p = self._dosya()
            if p is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            b = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(p))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            veri = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            durum["son"] = time.time()
            if u.path == "/kare":
                i = int(q["i"][0])
                if 0 <= i < 100000:
                    durum["kare"] += 1
                    (cikis / f"{i:04d}.png").write_bytes(veri)
            elif u.path == "/log":
                print("[sayfa]", veri.decode("utf-8", "replace"), flush=True)
            elif u.path == "/bitti":
                m = veri.decode("utf-8", "replace")
                print("[sayfa] bitti:", m, flush=True)
                if m.startswith("hata"):
                    durum["hata"] = m
                bitti.set()
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    http.server.ThreadingHTTPServer.allow_reuse_address = os.name != "nt"
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), I)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = tempfile.mkdtemp(prefix="yst-kalem-")
    exe = tarayici()
    bayrak = ["--no-first-run", "--disable-gpu", f"--window-size={W},{H}", f"--user-data-dir={prof}"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        bayrak.append("--no-sandbox")  # kök kullanıcı (CI/konteyner) kum havuzuyla açılamaz
    url = f"http://127.0.0.1:{port}/sayfa.html" + (f"?kare={kare_sinir}" if kare_sinir else "")
    p = subprocess.Popen(exe + bayrak + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tamam = False
    try:
        while not tamam:  # 60 sn hiç ses gelmezse sayfa yüklenmemiştir (çoğu zaman JS sözdizimi hatası)
            tamam = bitti.wait(timeout=2)
            if not tamam and time.time() - durum["son"] > 60:
                print(f"ZAMAN AŞIMI: 60 sn sayfadan ses yok ({durum['kare']} kare geldi). Sözdizimini sına: node --check <js>")
                break
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
        shutil.rmtree(prof, ignore_errors=True)
        srv.shutdown()
    if not tamam:
        return 2
    return 1 if durum["hata"] else 0


if __name__ == "__main__":
    sys.exit(main())
