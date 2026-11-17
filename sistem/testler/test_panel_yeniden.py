"""Panel kapatılıp hemen yeniden açılabilmeli (Linux/macOS'ta kapatılan portun TIME_WAIT durumu yüzünden "Address already in use" ile açılamıyordu)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
PJ = R / "sistem/ortam/yerel/panel.json"
S = [0, 0]
env = dict(os.environ, YST_TARAYICI_YOK="1", YST_ARKA_YOK="1", PYTHONUTF8="1")


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def baslat(ad):
    PJ.parent.mkdir(parents=True, exist_ok=True)
    PJ.unlink(missing_ok=True)
    log = Path(tempfile.gettempdir()) / f"yst-test-yeniden-{ad}.log"
    p = subprocess.Popen([sys.executable, str(R / "sistem/panel/panel.py"), "--tarayici-yok"], cwd=str(R), env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    for _ in range(120):
        time.sleep(0.5)
        if p.poll() is not None:
            return p, None, log.read_text(errors="replace")[-800:]
        if PJ.exists():
            try:
                port = json.loads(PJ.read_text())["port"]
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2).read()
                return p, port, ""
            except Exception:
                pass
    p.kill()
    return p, None, "zaman aşımı: " + log.read_text(errors="replace")[-800:]


def kapat(p, port):
    try:
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/kapat", data=b"{}", method="POST", headers={"X-Panel": "1", "Content-Type": "application/json"}), timeout=5).read()
    except Exception:
        pass
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()


p1, port1, hata1 = baslat("1")
ok(port1 is not None, "panel açıldı " + hata1)
if port1:
    import socket
    for _ in range(8):
        # bağlantıyı SUNUCU önce kapatsın (istemci yanıtı sonuna kadar okuyup sunucunun FIN'ini bekler): sunucu portunda TIME_WAIT oluşur,
        # SO_REUSEADDR kapalıysa Linux'ta aynı porta yeniden bind edilemez
        with socket.create_connection(("127.0.0.1", port1), timeout=3) as s:
            s.sendall(b"GET /api/ping HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            while s.recv(4096):
                pass
    kapat(p1, port1)
    p2, port2, hata2 = baslat("2")  # HEMEN yeniden aç
    ok(port2 is not None, "kapatıldıktan hemen sonra yeniden açılabildi: " + hata2)
    if port2:
        kapat(p2, port2)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
