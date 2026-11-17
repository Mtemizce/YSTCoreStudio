"""Marka kiti (sistem/marka/marka.py): çoklu logo, metinler, renk rolleri, yazı tipleri, serbest kullanım kuralları ve ajan kılavuzu. Ağ gerekmez."""
import importlib.util
import json
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


sp = importlib.util.spec_from_file_location("marka_t", R / "sistem/marka/marka.py")
M = importlib.util.module_from_spec(sp)
sys.modules["marka_t"] = M
sp.loader.exec_module(M)
tmp = Path(tempfile.mkdtemp(prefix="yst-marka-"))
M.KITLER = tmp / "kitler"
proje = R / "projeler" / "zz-marka"


def png(w=8, h=8):
    import os
    raw = b"".join(b"\x00" + os.urandom(3 * w) for _ in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")


try:
    kit = M.kaydet({"id": "deneme", "ad": "Deneme Kiti", "isim": "Acme", "slogan": "Hızlı ve sade", "iletisim": {"web": "acme.example"},
                    "renkler": {"zemin": "#101010", "metin": "#ffffff", "vurgu": "#ff6600"},
                    "ek_renkler": [{"ad": "Mercan", "hex": "#ff5a5f", "rol": "ikincil vurgu"}, {"ad": "bozuk", "hex": "kırmızı"}],
                    "yazi_tipleri": {"baslik": "inter-bold", "govde": "../kotu"},
                    "metinler": [{"ad": "Çağrı", "tur": "cta", "icerik": "acme.example'ı ziyaret et"}, {"ad": "Yasal", "tur": "gecersiz", "icerik": "Tüm hakları saklıdır."}],
                    "kullanim": [{"oge": "logo:ana", "konum": "sol-ust", "ne_zaman": "ilk 5 saniye hariç tüm video", "nasil": "ekranın %8'i, %60 opaklık", "yasak": "kapak karesinde kullanma", "acik": True},
                                 {"oge": "script:alert(1)", "nasil": "x"}, {"oge": "metin:cagri", "konum": "alt-bant", "ne_zaman": "yalnızca outro"}],
                    "notlar": "Logoyu asla döndürme."})
    ok(kit["ek_renkler"] == [{"ad": "Mercan", "hex": "#ff5a5f", "rol": "ikincil vurgu"}], "ek renkler: rolüyle saklanır, geçersiz renk atılır")
    ok(kit["yazi_tipleri"] == {"baslik": "inter-bold", "govde": ""}, "yazı tipleri: yalnızca güvenli kimlikler (../kotu atılır)")
    ok([x["tur"] for x in kit["metinler"]] == ["cta", "diger"] and kit["metinler"][0]["id"] == "cagri", "metinler: türler doğrulanır, kimlik adından üretilir")
    ok([x["oge"] for x in kit["kullanim"]] == ["logo:ana", "genel", "metin:cagri"], "kullanım kuralları: geçersiz öğe 'genel'e düşer, betik benzeri değer kabul edilmez")
    ok(kit["kullanim"][0]["konum"] == "sol-ust" and kit["kullanim"][0]["yasak"] == "kapak karesinde kullanma" and kit["kullanim"][2]["acik"] is True, "kural alanları (nerede/ne zaman/nasıl/yasak) saklanır")

    try:
        M.logo_ekle("deneme", "ana", "logo.exe", png())
        ok(False, "geçersiz biçim reddedilmeliydi")
    except ValueError:
        ok(True, "logo: geçersiz dosya biçimi reddedilir")
    try:
        M.logo_ekle("deneme", "x", "x.svg", b"<svg><script>alert(1)</script></svg>" + b" " * 100)
        ok(False, "betikli SVG reddedilmeliydi")
    except ValueError:
        ok(True, "logo: betik içeren SVG reddedilir")
    a = M.logo_ekle("deneme", "ana", "marka.png", png(), "Ana logo", "ana")
    k = M.logo_ekle("deneme", "koyu", "koyu.png", png(16, 16), "Koyu zemin için", "koyu-zemin")
    oku = M.oku("deneme")
    ok(a["dosya"] == "logo-ana.png" and oku["logo"] == "logo-ana.png" and [x["tur"] for x in oku["logolar"]] == ["ana", "koyu-zemin"], "çoklu logo: ana ve koyu zemin logosu; eski 'logo' alanı ana logoyu gösterir")
    ok((M.KITLER / "deneme" / "logo-koyu.png").is_file(), "logo dosyası kit klasörüne yazılır")

    # form kaydederken logolar yalnızca üst bilgi gönderir: dosyalar korunur, kaldırılan logonun dosyası silinir
    k2 = M.kaydet({"id": "deneme", "ad": "Deneme Kiti", "logolar": [{"id": "ana", "ad": "Birincil", "tur": "ana"}, {"id": "hayali", "ad": "olmayan", "tur": "ana"}]})
    ok([x["id"] for x in k2["logolar"]] == ["ana"] and k2["logolar"][0]["ad"] == "Birincil" and k2["logolar"][0]["dosya"] == "logo-ana.png", "kaydet: dosyası olmayan logo kaydı oluşmaz, var olanın üst bilgisi güncellenir")
    ok(not (M.KITLER / "deneme" / "logo-koyu.png").exists(), "panelden kaldırılan logonun dosyası silinir")
    M.logo_ekle("deneme", "koyu", "koyu.png", png(), "Koyu zemin için", "koyu-zemin")
    M.kaydet({**M.oku("deneme"), "kullanim": kit["kullanim"], "metinler": kit["metinler"], "ek_renkler": kit["ek_renkler"], "notlar": "Logoyu asla döndürme.", "isim": "Acme", "slogan": "Hızlı ve sade"})

    (proje / "ana").mkdir(parents=True, exist_ok=True)
    (proje / "ana" / "project.json").write_text("{}", encoding="utf-8")
    M.ROOT = R
    dok = M.uygula("zz-marka", "deneme", {"intro": True, "outro": False, "filigran": False, "iletisim": False})
    ok(dok == ["ana"] and (proje / "ana" / "media" / "marka" / "logo-ana.png").is_file() and (proje / "ana" / "media" / "marka" / "logo-koyu.png").is_file(), "uygula: tüm logolar projeye kopyalanır")
    md = (proje / "marka_kullanimi.md").read_text(encoding="utf-8")
    ok("**logo:ana** — Nerede: sol-ust · Ne zaman: ilk 5 saniye hariç tüm video · Nasıl: ekranın %8'i, %60 opaklık · YASAK: kapak karesinde kullanma" in md, "kılavuz: kullanıcının yazdığı kural aynen ajan kılavuzuna girer")
    ok("`koyu` (koyu-zemin)" in md and "Mercan #ff5a5f: ikincil vurgu" in md and "Outro: bu projede KAPALI" in md and "iletişim bilgisi GÖRÜNMEZ" in md and "Logoyu asla döndürme." in md, "kılavuz: logolar, renk rolü, proje seçimleri (intro/outro/iletişim) ve genel not")
    mj = json.loads((proje / "ana" / "remotion" / "src" / "marka.json").read_text(encoding="utf-8"))
    ok(mj["logo"] == "logo-ana.png" and mj["intro"]["acik"] is True and mj["outro"]["acik"] is False and len(mj["kullanim"]) == 3, "marka.json: eski alanlar (logo, intro/outro) ve yeni alanlar birlikte")
    ok(any(x["id"] == "deneme" and x["logo_sayisi"] == 2 and x["kural_sayisi"] == 3 for x in M.liste()), "liste: logo ve kural sayısı")

    # eski biçimli kit (yalnızca logo alanı) hâlâ açılır ve kılavuz üretir
    (M.KITLER / "eski").mkdir()
    (M.KITLER / "eski" / "kit.json").write_text(json.dumps({"id": "eski", "ad": "Eski", "isim": "X", "logo": "logo.png"}), encoding="utf-8")
    ok("- logo.png" in M.kullanim_md(M.oku("eski")) and "kullanıcı özel kural yazmamış" in M.kullanim_md(M.oku("eski")), "eski biçimli kit bozulmaz: kılavuz yine üretilir")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(proje, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
