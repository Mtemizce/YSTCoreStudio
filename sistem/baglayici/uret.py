#!/usr/bin/env python3
"""Bağlayıcı dağıtıcı: ücretli/bulut servislerle görsel ve ses üretimi. Ajanlar ağa/anahtara doğrudan dokunmaz, yalnızca bunu çağırır.

  python sistem/baglayici/uret.py durum [--proje <ad>]
  python sistem/baglayici/uret.py test <sağlayıcı>                       anahtarın çalıştığını doğrular (yalnızca bir "liste" isteği)
  python sistem/baglayici/uret.py gorsel --proje <ad> --istem "…" --cikti projeler/<ad>/ana/media/uretilen/x.png [--saglayici gemini|auto] [--en-boy 16:9|9:16] [--referans <png>]
  python sistem/baglayici/uret.py ses    --proje <ad> --metin "…" --cikti projeler/<ad>/ana/ses/x.mp3 --saglayici elevenlabs [--ses <voice_id>] [--hiz 1.0] [--duygu mutlu]

Politika (ortak.py): bağlayıcı ETKİN + anahtar VAR + projede bulut izni; her çağrı projeler/<ad>/bulut_gunlugu.md'ye yazılır.
Yerel ses için bu aracı kullanma: voice_studio.py (EMA).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortak  # noqa: E402

MOD = {"elevenlabs": "elevenlabs", "gemini": "gemini", "openai-gorsel": "openai_gorsel"}


def sag_modul(sid: str):
    if sid not in MOD:
        raise ortak.IzinHatasi(f"'{sid}' için doğrudan API bağdaştırıcısı yok (MCP bağlayıcıları Claude oturumuna eklenir: panel → Ayarlar → MCP)")
    p = Path(__file__).resolve().parent / "saglayici" / f"{MOD[sid]}.py"
    spec = importlib.util.spec_from_file_location(f"sag_{MOD[sid]}", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cikti_yolu(cikti: str, proje: str) -> Path:
    p = Path(cikti)
    p = (p if p.is_absolute() else ortak.ROOT / p).resolve()
    kok = (ortak.ROOT / "projeler" / proje).resolve()
    if kok not in p.parents:
        raise ortak.IzinHatasi(f"çıktı proje klasörünün içinde olmalı: {kok}")
    return p


def varsayilan_saglayici(proje: str | None, kategori: str) -> str:
    u = ortak.ayar_modul().coz(proje).get("uretim", {})
    return (u.get("gorsel_uret" if kategori == "gorsel" else "seslendirme") or {}).get("saglayici", "")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    d = sp.add_parser("durum")
    d.add_argument("--proje")
    t = sp.add_parser("test")
    t.add_argument("saglayici")
    g = sp.add_parser("gorsel")
    s = sp.add_parser("ses")
    for x in (g, s):
        x.add_argument("--proje", required=True)
        x.add_argument("--cikti", required=True)
        x.add_argument("--saglayici", default="auto")
    g.add_argument("--istem", required=True)
    g.add_argument("--en-boy", default="16:9")
    g.add_argument("--referans")
    s.add_argument("--metin", required=True)
    s.add_argument("--ses")
    s.add_argument("--hiz", type=float, default=1.0)
    s.add_argument("--duygu", default="")
    a = ap.parse_args()
    try:
        if a.k == "durum":
            for sid in ortak.katalog()["saglayicilar"]:
                b = ortak.baglayici_durumu(sid, a.proje)
                print(f"{sid:14} {'ETKİN ' if b['etkin'] else 'kapalı'}  {'yerel' if b['yerel'] else 'bulut':5}  anahtar: "
                      f"{'—' if b['anahtar_var'] is None else ('var' if b['anahtar_var'] else 'YOK')}  [{b['dogrulama']}]")
            return 0
        if a.k == "test":
            kat = ortak.katalog()["saglayicilar"].get(a.saglayici)
            if not kat or a.saglayici not in MOD:
                sys.exit("test edilecek API bağdaştırıcısı yok")
            key = ortak.anahtar_oku(kat["anahtar"])
            if not key:
                sys.exit(f"anahtar yok ({kat['anahtar']})")
            ay = ortak.sag_ayar(a.saglayici, None)
            ctx = {"key": key, "taban": (ay.get("taban_url") or kat["taban_url"]).rstrip("/"), "model": ay.get("model"), "ayar": ay}
            print(sag_modul(a.saglayici).test(ctx))
            return 0
        kategori = "gorsel" if a.k == "gorsel" else "ses"
        sid = a.saglayici if a.saglayici != "auto" else varsayilan_saglayici(a.proje, kategori)
        if not sid:
            raise ortak.IzinHatasi("sağlayıcı seçilmemiş (ayarlarda varsayılan yok)")
        if sid == "ema":
            raise ortak.IzinHatasi("yerel EMA sesi için voice_studio.py kullan")
        ctx = ortak.izin_kontrol(sid, kategori, a.proje)
        cikti = cikti_yolu(a.cikti, a.proje)
        m = sag_modul(sid)
        if a.k == "gorsel":
            ref = None
            if a.referans:
                ref = Path(a.referans)
                ref = (ref if ref.is_absolute() else ortak.ROOT / ref).resolve()
                gonder_serbest = ortak.ayar_modul().coz(a.proje)["kurallar"].get("kaynak_gorselleri_buluta_gonder")
                if "uretilen" not in ref.parts and not gonder_serbest:
                    raise ortak.IzinHatasi("referans yalnızca kendi ürettiğin görsellerden (media/uretilen/) olabilir; kaynak fotoğrafları buluta gönderme "
                                           "ayarı kapalı (Ayarlar → kurallar)")
                if not ref.is_file():
                    raise ortak.IzinHatasi(f"referans yok: {ref}")
            r = m.gorsel(ctx, a.istem, cikti, a.en_boy, ref)
            ortak.gunluk(a.proje, sid, "görsel", f"{a.en_boy} · {a.istem}" + (" · +referans" if ref else ""), str(Path(r["dosya"]).relative_to(ortak.ROOT)), r["model"])
        else:
            r = m.ses(ctx, a.metin, cikti, a.ses, a.hiz, a.duygu)
            ortak.gunluk(a.proje, sid, "ses", a.metin, str(Path(r["dosya"]).relative_to(ortak.ROOT)), f"{r['model']} · {len(a.metin)} karakter")
        print(f"tamam: {r['dosya']} ({r['bayt']} bayt, model {r['model']})")
        return 0
    except ortak.IzinHatasi as e:
        print(f"İZİN/AYAR: {e}")
        return 3
    except ortak.AgHatasi as e:
        print(f"AĞ/SERVİS: {ortak.maskele(str(e))}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
