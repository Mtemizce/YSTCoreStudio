#!/usr/bin/env python3
"""YSTCoreStudio başlatıcısı (Başlat.cmd bunu çağırır). Sistem Python'u ile çalışır, yalnızca standart kütüphane.

  baslat.py            (varsayılan) sessizce başlat: taşıma onarımı → sistem analizi → (gerekirse kurulum sihirbazı) → paneli arka planda aç
  baslat.py claude     Claude Code'u bu klasörde, ortamla birlikte aç
  baslat.py varlik     inmeyen müzik/ses efektlerini tamamla
  baslat.py durdur     arka planda çalışan paneli kapat
  baslat.py kontrol    yalnızca sistem analizi + taşıma durumu (hiçbir şey değiştirmez)

Konsol penceresi gerekmez: pythonw ile çalıştırıldığında çıktı sistem/ortam/yerel/baslat.log'a yazılır, bir sorun olursa pencere kutusu çıkar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
YEREL = ORTAM / "yerel"
VENV = ORTAM / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
VENV_PYW = VENV / "Scripts" / "pythonw.exe"  # yalnızca Windows
VENV_BIN = VENV / ("Scripts" if os.name == "nt" else "bin")
PANEL_DOSYA = YEREL / "panel.json"
NW = 0x08000000 if os.name == "nt" else 0
DETACHED = (0x00000008 | 0x00000200 | 0x08000000) if os.name == "nt" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
sys.path.insert(0, str(SISTEM / "kurulum"))
sys.path.insert(0, str(SISTEM / "araclar"))


def log_ac():
    YEREL.mkdir(parents=True, exist_ok=True)
    p = YEREL / "baslat.log"
    try:
        if p.exists() and p.stat().st_size > 400_000:
            p.replace(YEREL / "baslat.eski.log")
    except OSError:
        pass
    f = open(p, "a", encoding="utf-8", buffering=1)
    f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv[1:])} ({ROOT}) ===\n")
    return f


def tarayici_ac(url: str) -> None:
    if not os.environ.get("YST_TARAYICI_YOK"):  # test/CI için kapatılabilir
        webbrowser.open(url)


def kutu(baslik: str, mesaj: str) -> None:
    """pythonw'de konsol yok: önemli bir sorunu pencere kutusuyla göster."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, mesaj[:1800], baslik, 0x10)
        except Exception:  # noqa: BLE001
            pass


def ortam() -> dict:
    e = dict(os.environ)
    sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
    import yol
    e.update(yol.kapsama())   # tek klasör kuralı: indirmeler ve önbellekler stüdyo klasörüne
    e["YST_KOK"] = str(ROOT)
    e["PATH"] = str(VENV_BIN) + os.pathsep + e.get("PATH", "")
    return e


def panel_bilgi() -> dict | None:
    try:
        return json.loads(PANEL_DOSYA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ping(port: int, zaman: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=zaman) as r:
            d = json.loads(r.read())
            return d if d.get("app") == "YSTPanel" else None
    except Exception:  # noqa: BLE001
        return None


def calisan_panel() -> tuple[int, dict] | None:
    """Bu klasörün paneli zaten çalışıyor mu? (aynı kök)"""
    b = panel_bilgi()
    if b and b.get("port"):
        d = ping(int(b["port"]))
        if d and os.path.normcase(d.get("kok", "")) == os.path.normcase(str(ROOT)):
            return int(b["port"]), d
    return None


def panel_baslat(log) -> str:
    """Paneli konsolsuz, ayrı bir süreç olarak başlatır; hazır olunca adresi döndürür."""
    py = VENV_PYW if VENV_PYW.exists() else VENV_PY
    out = open(YEREL / "panel.log", "a", encoding="utf-8", buffering=1)
    out.write(f"\n=== panel {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    PANEL_DOSYA.unlink(missing_ok=True)
    ek = {"creationflags": DETACHED} if os.name == "nt" else {"start_new_session": True}  # Linux/macOS: terminal kapanınca ölmesin
    subprocess.Popen([str(py), str(SISTEM / "panel" / "panel.py"), "--tarayici-yok"], cwd=str(ROOT), env=ortam(), stdin=subprocess.DEVNULL,
                     stdout=out, stderr=out, close_fds=True, **ek)
    for _ in range(80):
        time.sleep(0.25)
        c = calisan_panel()
        if c:
            return f"http://127.0.0.1:{c[0]}"
    raise RuntimeError("panel başlamadı; ayrıntı: sistem/ortam/yerel/panel.log")


def baslat(log) -> int:
    import onar as O
    import onkosul as OK
    log.write("taşıma denetimi\n")
    onar_ozeti = O.onar(yazdir=lambda s: log.write(s + "\n"))
    # zaten çalışıyorsa yeni süreç açma
    c = calisan_panel()
    if c:
        tarayici_ac(f"http://127.0.0.1:{c[0]}")
        log.write("panel zaten çalışıyor: tarayıcı açıldı\n")
        return 0
    t = OK.tara()
    kurulu = (YEREL / "kurulum.ok").exists() and VENV_PY.exists()
    srv = None
    sih = None
    if not kurulu or not t["tamam"]:
        import sihirbaz as S
        sih = S
        srv, url = S.sun(onar_ozeti)
        log.write(f"sihirbaz: {url} (eksik: {t['engel']}, kurulu: {kurulu})\n")
        tarayici_ac(url)
        if not S.bekle(srv):
            log.write("sihirbaz kapatıldı / kurulum tamamlanmadı\n")
            return 1
    try:
        url = panel_baslat(log)
    except RuntimeError as e:
        log.write(f"HATA: {e}\n")
        kutu("YSTCoreStudio", f"Panel başlatılamadı.\n\n{e}\n\nGünlük: {YEREL}")
        return 1
    log.write(f"panel: {url}\n")
    if sih:
        sih.D["panel_url"] = url  # sihirbaz sayfası kendiliğinden panele yönlenir
        for _ in range(90):  # sayfa adresi alana kadar bekle (arka plandaki sekme zamanlayıcısı yavaşlatılmış olabilir)
            time.sleep(0.5)
            if sih.D.get("panel_url_goruldu"):
                time.sleep(3)
                break
        else:
            tarayici_ac(url)  # sayfa yönlenmedi (sekme kapanmış olabilir): paneli doğrudan aç
    else:
        tarayici_ac(url)
    return 0


def durdur() -> int:
    b = panel_bilgi()
    if not b:
        print("çalışan panel yok")
        return 0
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{b['port']}/api/kapat", data=b"{}", method="POST", headers={"X-Panel": "1", "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=4).read()
        print("panel kapatıldı")
    except Exception:  # noqa: BLE001
        # panel yanıt vermiyor. PID eski kalmış olabilir (başka bir programa geçmiş olabilir): yalnızca komut satırı BU panel ise sonlandır
        if os.name == "nt" and b.get("pid"):
            r = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(b['pid'])}').CommandLine"],
                               capture_output=True, text=True, creationflags=NW, timeout=30)
            if "panel.py" in (r.stdout or "") and os.path.normcase(str(ROOT)) in os.path.normcase(r.stdout or ""):
                subprocess.run(["taskkill", "/PID", str(b["pid"]), "/F"], capture_output=True, creationflags=NW)
                print("panel yanıt vermiyordu, sonlandırıldı")
            else:
                print("panel zaten kapalı (eski kayıt temizlendi)")
        elif b.get("pid"):  # Linux/macOS: komut satırı BU panel ise sonlandır
            try:
                r = subprocess.run(["ps", "-o", "command=", "-p", str(int(b["pid"]))], capture_output=True, text=True, timeout=10)
                if "panel.py" in (r.stdout or "") and str(ROOT) in (r.stdout or ""):
                    os.kill(int(b["pid"]), 15)
                    print("panel yanıt vermiyordu, sonlandırıldı")
                else:
                    print("panel zaten kapalı (eski kayıt temizlendi)")
            except (OSError, subprocess.SubprocessError, ValueError):
                print("panel zaten kapalı (eski kayıt temizlendi)")
    PANEL_DOSYA.unlink(missing_ok=True)
    return 0


def main() -> int:
    mod = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if sys.stdout is None or sys.stderr is None or mod in ("", "sessiz"):
        f = log_ac()
        sys.stdout = sys.stderr = f
        log = f
    else:
        class _T:  # konsolda hem ekrana hem günlüğe
            def __init__(self, f):
                self.f = f

            def write(self, s):
                sys.__stdout__.write(s)
                self.f.write(s)

        log = _T(log_ac())
    try:
        if mod in ("", "sessiz", "panel"):
            return baslat(log)
        if mod == "durdur":
            return durdur()
        if mod == "kontrol":
            import onar as O
            import onkosul as OK
            print("taşıma durumu:", json.dumps({k: v for k, v in O.K.damga_oku().items()}, ensure_ascii=False))
            return OK.main()
        if mod == "claude":
            import onar as O
            O.onar()
            return subprocess.call(["cmd", "/c", "claude"] if os.name == "nt" else ["claude"], cwd=str(ROOT), env=ortam())
        if mod == "varlik":
            import onar as O
            O.onar()
            # arka plan kuyruğunu bu pencerede yürütür: eksik PyTorch/paketler/modeller + (açıkça istendiği için) müzik ve ses efektleri
            return subprocess.call([str(VENV_PY), str(SISTEM / "araclar" / "arka_indirme.py"), "calis", "ses"], cwd=str(ROOT), env=ortam())
        print(__doc__)
        return 2
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc(file=log)
        kutu("YSTCoreStudio", f"Beklenmeyen hata:\n{e}\n\nAyrıntı: {YEREL / 'baslat.log'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
