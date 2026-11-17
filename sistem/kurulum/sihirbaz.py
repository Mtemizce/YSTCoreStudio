#!/usr/bin/env python3
"""Kurulum sihirbazı: tarayıcıda, yalnızca 127.0.0.1'de. Başlat.cmd eksik önkoşul ya da ilk kurulum varsa bunu açar.

Akış: sistem analizi → eksikler listelenir (kopyalanabilir komut + indirme adresi) → kullanıcı kurar → 'Devam et' → analiz YENİDEN çalışır →
sorun yoksa kurulum (kurulum.py) başlar, ilerleme ve günlük sayfada akar → bitince panel açılır.
Yalnızca standart kütüphane (Python'dan başka bir şey henüz kurulu olmayabilir).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
YEREL = ORTAM / "yerel"
KURULUM_LOG = YEREL / "kurulum.log"
NW = 0x08000000 if os.name == "nt" else 0
sys.path.insert(0, str(SISTEM / "kurulum"))
import onkosul  # noqa: E402

D = {  # paylaşılan durum
    "kurulum": {"calisiyor": False, "bitti": False, "hata": None, "adim": "", "no": 0, "toplam": 0, "log": [], "bas": None},
    "onar": {}, "son_istek": time.time(), "kapat": False, "panel_url": None, "ilk": True,
}
kilit = threading.Lock()


def python_exe() -> str:
    """Konsol penceresi açmadan alt işlem için python.exe (pythonw.exe ile çalışıyorsak yanındaki python.exe)."""
    e = sys.executable
    if e.lower().endswith("pythonw.exe"):
        p = Path(e).with_name("python.exe")
        if p.exists():
            return str(p)
    return e


def log_ekle(satir: str) -> None:
    with kilit:
        l = D["kurulum"]["log"]
        l.append(satir.rstrip()[:400])
        if len(l) > 400:
            del l[:100]
    try:
        YEREL.mkdir(parents=True, exist_ok=True)
        with open(KURULUM_LOG, "a", encoding="utf-8") as f:
            f.write(satir.rstrip() + "\n")
    except OSError:
        pass


def kurulum_calistir() -> None:
    k = D["kurulum"]
    k.update({"calisiyor": True, "bitti": False, "hata": None, "bas": time.time(), "adim": "başlıyor", "no": 0, "toplam": 7})
    env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1", HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    log_ekle(f"=== kurulum başladı {time.strftime('%Y-%m-%d %H:%M:%S')} ({ROOT}) ===")
    try:
        missing = onkosul.tara(ag=False)["engel"]
        for item in ("python", "git", "node", "claude"):
            if item not in missing:
                continue
            if os.name != "nt":
                raise RuntimeError("Bu işletim sisteminde önkoşulu paket yöneticinizle kurun: " + item)
            k["adim"] = item + " kuruluyor"
            pre = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SISTEM / "kurulum/on_kur.ps1"), "-Bilesen", item],
                                   cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NW)
            for line in pre.stdout:
                log_ekle(line.decode("utf-8", "replace"))
            if pre.wait() != 0:
                raise RuntimeError(item + " kurulamadı; günlükteki nedeni giderip yeniden deneyin.")
            onkosul.yol_yenile()
            for tool in ("git", "node", "npm", "claude"):
                exe = onkosul.bul(tool)
                if exe:
                    os.environ["PATH"] = str(Path(exe).parent) + os.pathsep + os.environ.get("PATH", "")
            check = tara_yenile()
            if item in check["engel"]:
                raise RuntimeError(item + " yükleyicisi bitti ancak araç doğrulanamadı.")
        if not tara_yenile()["tamam"]:
            raise RuntimeError("Eksikler: " + ", ".join(D["tarama"]["engel"]))
        env.update(PATH=os.environ.get("PATH", ""))
        p = subprocess.Popen([python_exe(), "-u", str(SISTEM / "kurulum" / "kurulum.py")], cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=NW)
        for ham in iter(p.stdout.readline, b""):
            s = ham.decode("utf-8", "replace")
            log_ekle(s)
            m = re.match(r"\s*\[(\d+)/(\d+)\]\s*(.*)", s)
            if m:
                k.update({"no": int(m.group(1)), "toplam": int(m.group(2)), "adim": m.group(3).strip()})
        rc = p.wait()
        if rc == 0 and (YEREL / "kurulum.ok").exists():
            k.update({"bitti": True, "no": k["toplam"], "adim": "tamam"})
            log_ekle("=== kurulum bitti ===")
        else:
            k["hata"] = f"kurulum {rc} koduyla durdu. Günlüğün son satırlarına bak; eksiği giderip 'Yeniden dene'."
            log_ekle(f"=== kurulum HATA ({rc}) ===")
    except Exception as e:  # noqa: BLE001
        k["hata"] = f"kurulum başlatılamadı: {e}"
        log_ekle(k["hata"])
    finally:
        k["calisiyor"] = False


def durum_json() -> dict:
    with kilit:
        k = dict(D["kurulum"])
        k["log"] = list(k["log"][-120:])
    k["gecen_sn"] = int(time.time() - k["bas"]) if k.get("bas") else 0
    if D["panel_url"]:
        D["panel_url_goruldu"] = True  # sayfa panel adresini aldı: yönlenecek
    if "plan" not in D:
        try:
            sys.path.insert(0, str(SISTEM / "araclar"))
            import donanim
            D["plan"] = donanim.ilk_kurulum()
        except Exception:  # noqa: BLE001
            D["plan"] = None
    return {"plan": D["plan"], "onkosul": D.get("tarama"), "kurulum": k, "onar": D["onar"], "kok": str(ROOT), "panel_url": D["panel_url"], "log_dosyasi": str(KURULUM_LOG)}


def tara_yenile() -> dict:
    D["tarama"] = onkosul.tara()
    return D["tarama"]


def devam() -> dict:
    """'Devam et': analizi yeniden çalıştır; sorun yoksa (ve kurulum gerekiyorsa) kurulumu başlat."""
    with kilit:
        if D["kurulum"]["calisiyor"]:
            return {"ok": True, "mesaj": "kurulum zaten sürüyor"}
        t = tara_yenile()
        blockers = [x for x in t["engel"] if x not in ("python", "git", "node", "claude")]
        if blockers:
            return {"ok": False, "mesaj": "Önce giderilmesi gereken: " + ", ".join(blockers)}
        if (YEREL / "kurulum.ok").exists() and t["tamam"]:
            D["kurulum"].update({"bitti": True, "adim": "tamam"})
            return {"ok": True, "mesaj": "kurulu: panel açılıyor"}
        D["kurulum"]["calisiyor"] = True
        threading.Thread(target=kurulum_calistir, daemon=True).start()
        return {"ok": True, "mesaj": "Eksikler sırayla kuruluyor; ilerleme bu panelde gösterilir."}



class Sunucu(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"  # Windows'ta SO_REUSEADDR başka bir dinleyicinin portuna da bağlanmaya izin verir: kapalı; Linux/macOS'ta TIME_WAIT için gerekli


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "YSTSihirbaz"

    def log_message(self, *a):
        pass

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def _json(self, obj, kod=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        D["son_istek"] = time.time()
        if not self._host_ok():
            return self._json({"hata": "yasak"}, 403)
        if self.path in ("/", "/index.html"):
            b = (Path(__file__).parent / "sihirbaz.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
            return
        if self.path.startswith("/api/durum"):
            return self._json(durum_json())
        self._json({"hata": "yok"}, 404)

    def do_POST(self):
        D["son_istek"] = time.time()
        if not self._host_ok() or self.headers.get("X-Panel") != "1":
            return self._json({"hata": "yasak"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            b = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            b = {}
        if self.path == "/api/tara":
            tara_yenile()
            return self._json(durum_json())
        if self.path == "/api/devam":
            return self._json(devam())
        if self.path == "/api/atla":
            if b.get("id") in {o["id"] for o in (D.get("tarama") or {}).get("ogeler", []) if o.get("atlanabilir")}:
                onkosul.atla(b["id"])
            tara_yenile()
            return self._json(durum_json())
        if self.path == "/api/kimlik":
            try:
                sys.path.insert(0, str(SISTEM / "araclar"))
                import kimlik_sablon
                return self._json({"ok": True, **kimlik_sablon.kaydet(str(b.get("ad") or ""), str(b.get("marka") or ""), str(b.get("rol") or ""), str(b.get("sehir") or ""))})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "hata": str(e)}, 500)
        if self.path == "/api/kapat":
            D["kapat"] = True
            return self._json({"ok": True})
        self._json({"hata": "yok"}, 404)


def sun(onar_ozeti: dict | None = None, port: int = 8701):
    """Sihirbaz sunucusunu arka planda başlatır → (sunucu, url). Port doluysa sıradakini dener."""
    D["onar"] = onar_ozeti or {}
    srv = None
    for p in range(port, port + 30):
        try:
            srv = Sunucu(("127.0.0.1", p), H)
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError("sihirbaz için boş port bulunamadı")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tara_yenile()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def bekle(srv, bos_sure: int = 1800) -> bool:
    """Kurulum bitene kadar bekler. True = bitti, False = kullanıcı kapattı ya da uzun süre kimse gelmedi."""
    otomatik = D.get("tarama", {}).get("tamam") and not D["kurulum"]["calisiyor"] and not D["kurulum"]["bitti"]
    if otomatik:  # eksik yoksa kullanıcıyı bekletme: kurulum kendiliğinden başlar
        devam()
    while True:
        time.sleep(0.5)
        if D["kapat"]:
            return False
        if D["kurulum"]["bitti"]:
            return True
        if not D["kurulum"]["calisiyor"] and time.time() - D["son_istek"] > bos_sure:
            return False
