#!/usr/bin/env python3
"""Kurgu editörünü, panel sayfasının İÇİNDE (iframe) açılabilecek biçimde başlatır.

Kurgu, başka bir yerel porttan gelen (same-site) tarayıcı isteklerini CSRF koruması olarak reddeder. Panel (127.0.0.1:<port>) editörü bir iframe'de gösterdiğinde
yalnızca İLK sayfa isteği (Sec-Fetch-Dest: iframe) böyle görünür. Bu başlatıcı, o isteği YALNIZCA şu koşullarda kabul ettirir: ortam değişkeni KURGU_EMBED_ORIGIN
(panelin kendi adresi) tanımlı, istek bir iframe gezinmesi ve Referer'ı tam o adres. Diğer tüm kurallar (Host, Origin, cross-site) olduğu gibi kalır.
Kullanım: kurgu_gomulu.py <proje klasörü> --port N --no-open   (kurgu komutuyla aynı argümanlar)
"""
import os
import sys
import json
import subprocess
from pathlib import Path


def panel_surecleri():
    """Embedded editor must not start a second interactive agent."""
    original = subprocess.Popen
    class PanelProcess(original):
        def __init__(self, args, *a, **kw):
            argv = args if isinstance(args, (list, tuple)) else [args]
            names = {Path(str(x)).name.lower() for x in argv}
            forbidden = {'wt', 'wt.exe', 'powershell', 'powershell.exe', 'pwsh', 'pwsh.exe',
                         'xterm', 'gnome-terminal', 'terminal.app', 'osascript',
                         'claude', 'claude.exe', 'claude.cmd', 'codex', 'codex.exe', 'codex.cmd'}
            if names & forbidden or kw.get('creationflags', 0) & 0x10 or ('start' in names and ('cmd' in names or 'cmd.exe' in names)):
                raise RuntimeError('Ajan iletişimi sağdaki Orkestratör sohbetinden yürütülür. Mesajını oradan gönder.')
            if os.name == 'nt':
                kw['creationflags'] = kw.get('creationflags', 0) | 0x08000000
            super().__init__(args, *a, **kw)
    subprocess.Popen = PanelProcess


def yamala() -> None:
    import server  # Kurgu'nun sunucu modülü
    emb = os.environ.get("KURGU_EMBED_ORIGIN", "").strip().rstrip("/")
    if not emb.startswith("http://127.0.0.1:"):
        return
    orijinal = server.Handler.dispatch

    def dispatch(self, method):
        if ((self.headers.get("Sec-Fetch-Site") or "").lower() == "same-site" and (self.headers.get("Sec-Fetch-Dest") or "").lower() == "iframe"
                and (self.headers.get("Referer") or "").startswith(emb + "/")):
            del self.headers["Sec-Fetch-Site"]
        return orijinal(self, method)

    server.Handler.dispatch = dispatch


if __name__ == "__main__":
    py = Path(sys.executable)
    if os.name == 'nt' and py.with_name('pythonw.exe').exists():
        py = py.with_name('pythonw.exe')
    os.environ['KURGU_ON_SEND'] = json.dumps([str(py), str(Path(__file__).with_name('orkestrator.py')), 'enqueue', '{dir}', '{seq}'])
    os.environ['KURGU_AGENT_NAME'] = 'Orkestratör'
    panel_surecleri()
    yamala()
    import kurgu_cli
    sys.argv[0] = "kurgu"
    sys.exit(kurgu_cli.main())
