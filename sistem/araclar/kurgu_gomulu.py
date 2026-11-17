#!/usr/bin/env python3
"""Kurgu editörünü, panel sayfasının İÇİNDE (iframe) açılabilecek biçimde başlatır.

Kurgu, başka bir yerel porttan gelen (same-site) tarayıcı isteklerini CSRF koruması olarak reddeder. Panel (127.0.0.1:<port>) editörü bir iframe'de gösterdiğinde
yalnızca İLK sayfa isteği (Sec-Fetch-Dest: iframe) böyle görünür. Bu başlatıcı, o isteği YALNIZCA şu koşullarda kabul ettirir: ortam değişkeni KURGU_EMBED_ORIGIN
(panelin kendi adresi) tanımlı, istek bir iframe gezinmesi ve Referer'ı tam o adres. Diğer tüm kurallar (Host, Origin, cross-site) olduğu gibi kalır.
Kullanım: kurgu_gomulu.py <proje klasörü> --port N --no-open   (kurgu komutuyla aynı argümanlar)
"""
import os
import sys


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
    yamala()
    import kurgu_cli
    sys.argv[0] = "kurgu"
    sys.exit(kurgu_cli.main())
