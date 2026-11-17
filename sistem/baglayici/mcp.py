#!/usr/bin/env python3
"""İsteğe bağlı MCP sunucuları (ör. HeyGen): kullanıcının eklediği sunucular Claude oturumuna kendiliğinden bağlanır.

  python sistem/baglayici/mcp.py liste
  python sistem/baglayici/mcp.py yol        etkin sunucular varsa Claude'a verilecek --mcp-config dosyasını üretip yolunu yazar (yoksa boş)
  python sistem/baglayici/mcp.py ortam      etkin sunucuların API anahtarlarını cmd'ye `set "AD=değer"` satırları olarak yazar (dosyaya YAZILMAZ)

Kayıt: sistem/ortam/baglayici/mcp.json (git'e girmez). Anahtarlar config dosyasında DEĞİL, ortam değişkeni olarak (${AD}) verilir.
GÜVENLİK: stdio sunucusu bilgisayarında bir KOMUT çalıştırır; yalnızca güvendiğin kaynağın (resmî belge) komutunu ekle.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortak  # noqa: E402

MCP = ortak.ORTAM_B / "mcp.json"
AKTIF = ortak.ORTAM_B / "mcp_aktif.json"
AD_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def _oku() -> dict:
    try:
        return json.loads(MCP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sunucular": {}}


def liste() -> dict:
    return _oku()["sunucular"]


def kaydet(ad: str, tur: str, komut: str = "", url: str = "", anahtar_adi: str = "", etkin: bool = True) -> dict:
    if not AD_RE.match(ad or ""):
        raise ValueError("sunucu adı: küçük harf, rakam, tire")
    if tur not in ("stdio", "http"):
        raise ValueError("tür stdio ya da http olmalı")
    if anahtar_adi and not ortak.ENV_RE.match(anahtar_adi):
        raise ValueError("anahtar adı BÜYÜK_HARF_ve_alt_çizgi olmalı")
    kayit = {"tur": tur, "etkin": bool(etkin), "anahtar_adi": anahtar_adi or ""}
    if tur == "stdio":
        parcalar = shlex.split(komut or "", posix=False)
        if not parcalar:
            raise ValueError("komut gerekli (örn. npx -y paket-adi)")
        kayit["komut"], kayit["args"] = parcalar[0].strip('"'), [x.strip('"') for x in parcalar[1:]]
    else:
        ortak._url_kontrol(url or "")
        kayit["url"] = url
    d = _oku()
    d["sunucular"][ad] = kayit
    ortak.ORTAM_B.mkdir(parents=True, exist_ok=True)
    MCP.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return kayit


def sil(ad: str) -> None:
    d = _oku()
    d["sunucular"].pop(ad, None)
    ortak.ORTAM_B.mkdir(parents=True, exist_ok=True)
    MCP.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def olustur() -> Path | None:
    sunucular = {}
    for ad, k in liste().items():
        if not k.get("etkin"):
            continue
        if k["tur"] == "stdio":
            c = {"command": k["komut"], "args": k.get("args", [])}
            if k.get("anahtar_adi"):
                c["env"] = {k["anahtar_adi"]: "${" + k["anahtar_adi"] + "}"}
        else:
            c = {"type": "http", "url": k["url"]}
            if k.get("anahtar_adi"):
                c["headers"] = {"Authorization": "Bearer ${" + k["anahtar_adi"] + "}"}
        sunucular[ad] = c
    if not sunucular:
        AKTIF.unlink(missing_ok=True)
        return None
    ortak.ORTAM_B.mkdir(parents=True, exist_ok=True)
    AKTIF.write_text(json.dumps({"mcpServers": sunucular}, indent=1), encoding="utf-8")
    return AKTIF


def ortam_satirlari() -> list[str]:
    out = []
    for k in liste().values():
        an = k.get("anahtar_adi")
        if k.get("etkin") and an:
            v = ortak.anahtar_oku(an)
            if v and re.fullmatch(r"[A-Za-z0-9_\-\.~+/=:]{8,600}", v):  # cmd'de güvenli karakter kümesi
                out.append(f'set "{an}={v}"')
    return out


def main() -> int:
    k = (sys.argv[1:] or ["liste"])[0]
    if k == "liste":
        for ad, s in liste().items():
            print(f"{ad:14} {s['tur']:5} {'ETKİN' if s.get('etkin') else 'kapalı'}  {s.get('komut', s.get('url', ''))} {' '.join(s.get('args', []))}")
    elif k == "yol":
        p = olustur()
        if p:
            print(p)
    elif k == "ortam":
        print("\n".join(ortam_satirlari()))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
