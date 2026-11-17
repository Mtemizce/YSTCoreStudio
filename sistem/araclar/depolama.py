#!/usr/bin/env python3
"""Dış depolama: rclone üzerinden (Drive, Dropbox, OneDrive, S3, WebDAV… 70+ servis) dosya çekme/gönderme ve storage.to ile geçici paylaşım bağlantısı.
Yetkilendirme (OAuth, jeton) bizim kodumuzda DEĞİL, rclone'dadır: `rclone config` ile bir kez sen yetkilendirirsin. Biz yalnızca `rclone copy/lsjson` çağırırız.
Arşiv için en kolay yol: `rclone mount uzak: X:` ile sürücü harfi yap, sonra Ayarlar → Konumlar'da o klasörü arşiv olarak göster (klasör adaptörü).

  python sistem/araclar/depolama.py durum                      rclone kurulu mu, hangi uzak hedefler tanımlı
  python sistem/araclar/depolama.py liste <uzak:yol> [--derinlik 1]
  python sistem/araclar/depolama.py indir <uzak:yol> <proje>   dosyaları projeler/<proje>/kaynak/ altına KOPYALAR (uzaktan yalnızca okunur)
  python sistem/araclar/depolama.py yukle <dosya> <uzak:yol> --onay        çıktıyı uzak depoya yükler (yazma: açık onay ister)
  python sistem/araclar/depolama.py paylas <dosya> --onay                   storage.to ile geçici bağlantı (anonim, süreli): dosya DIŞARI çıkar, onay ister

Güvenlik: komutlar liste olarak çalıştırılır (kabuk yok); uzak yol deseni doğrulanır; yerel hedef yalnızca proje kaynak klasörü; yükleme/paylaşım yalnızca proje çıktıları
(projeler/*/cikti, projeler/*/ana/out vb.) ve sistem/ortam/yedek içindeki dosyalar için; her dış gönderim sistem/ortam/arsiv/bulut_gunlugu.md'ye yazılır.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[2]
NW = 0x08000000 if os.name == "nt" else 0
UZAK_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\- ]{0,60}:[^\x00-\x1f]{0,400}$")
PROJE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
STORAGE_TO = "https://storage.to/api/sharex/upload"
sys.path.insert(0, str(ROOT / "sistem" / "baglayici"))


def _bd():
    import importlib.util as _u
    if "yst_bulut_disk" not in sys.modules:
        sp = _u.spec_from_file_location("yst_bulut_disk", Path(__file__).with_name("bulut_disk.py"))
        m = _u.module_from_spec(sp)
        sys.modules["yst_bulut_disk"] = m
        sp.loader.exec_module(m)
    return sys.modules["yst_bulut_disk"]


def rclone() -> str | None:
    return _bd().rclone()


def _calistir(args: list[str], zaman: int = 600) -> subprocess.CompletedProcess:
    exe = rclone()
    if not exe:
        raise RuntimeError("rclone kurulu değil: https://rclone.org/install/ (kurduktan sonra `rclone config` ile uzak hedefini yetkilendir)")
    return subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, creationflags=NW, env=_bd()._env())


def _uzak(u: str) -> str:
    if not isinstance(u, str) or u.startswith("-") or not UZAK_RE.match(u):
        raise ValueError("uzak yol 'ad:klasör/yol' biçiminde olmalı (örn. surucum:Arsiv/2023)")
    return u


def durum() -> dict:
    exe = rclone()
    d = {"kurulu": bool(exe), "yol": exe, "uzaklar": [], "surum": None}
    if exe:
        v = _calistir(["version"], 30)
        d["surum"] = (v.stdout or "").splitlines()[0] if v.stdout else None
        r = _calistir(["listremotes"], 30)
        d["uzaklar"] = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    return d


def liste(uzak: str, derinlik: int = 1) -> list[dict]:
    r = _calistir(["lsjson", _uzak(uzak), "--max-depth", str(max(1, min(int(derinlik), 4))), "--files-only"], 300)
    if r.returncode != 0:
        raise RuntimeError("rclone: " + (r.stderr or "")[-300:])
    return [{"yol": x["Path"], "boyut": x.get("Size"), "tarih": x.get("ModTime")} for x in json.loads(r.stdout or "[]")]


def _proje_kaynak(proje: str) -> Path:
    if not PROJE_RE.match(proje or ""):
        raise ValueError("geçersiz proje adı")
    p = ROOT / "projeler" / proje
    if not p.is_dir():
        raise ValueError("proje yok")
    return p / "kaynak" / "uzak"


def indir(uzak: str, proje: str, en_cok_gb: float = 8.0) -> dict:
    """Uzaktan projeye KOPYALAR (uzaktaki dosyalara yazılmaz/silinmez: yalnızca 'copy')."""
    hedef = _proje_kaynak(proje)
    hedef.mkdir(parents=True, exist_ok=True)
    r = _calistir(["copy", _uzak(uzak), str(hedef), "--transfers", "4", "--max-transfer", f"{int(en_cok_gb)}G", "--cutoff-mode", "cautious"], 7200)
    if r.returncode not in (0, 8):  # 8 = --max-transfer aşıldı
        raise RuntimeError("rclone: " + (r.stderr or "")[-300:])
    n = sum(1 for p in hedef.rglob("*") if p.is_file())
    return {"hedef": str(hedef.relative_to(ROOT)).replace("\\", "/"), "dosya": n, "sinir_asildi": r.returncode == 8}


def _cikti_dosyasi(dosya: str) -> Path:
    """Dışarı gönderilebilecek dosyalar: proje çıktıları ve yedek klasörü. Kaynak/kimlik/anahtar dosyaları gönderilemez."""
    p = Path(dosya)
    p = (p if p.is_absolute() else ROOT / p).resolve()
    izinli = [ROOT / "sistem" / "ortam" / "yedek"]
    pr = ROOT / "projeler"
    if pr in p.parents:
        rel = p.relative_to(pr).parts
        if len(rel) >= 3 and rel[1] in ("cikti", "ana", "reels", "tiktok", "shorts", "story") and not any(x in ("kaynak", "node_modules") for x in rel):
            izinli.append(p.parent)
    if not p.is_file() or not any(i.resolve() in p.parents or i.resolve() == p.parent for i in izinli):
        raise ValueError("yalnızca proje çıktıları (cikti/ ve biçim klasörleri) ya da yedek dosyaları dışarı gönderilebilir")
    if p.name.lower() in ("anahtar.json",) or "anahtar" in p.name.lower():
        raise ValueError("anahtar dosyaları gönderilemez")
    return p


def yukle(dosya: str, uzak: str, onay: bool) -> dict:
    if not onay:
        raise ValueError("uzak depoya yazma açık onay ister (--onay / panelde onay kutusu)")
    p = _cikti_dosyasi(dosya)
    r = _calistir(["copyto", str(p), _uzak(uzak)], 7200)
    if r.returncode != 0:
        raise RuntimeError("rclone: " + (r.stderr or "")[-300:])
    import ortak
    ortak.arsiv_gunluk("rclone", "yukle", f"{p.name} ({p.stat().st_size // 1024} KB) → {uzak.split(':')[0]}:…", "")
    return {"dosya": p.name, "uzak": uzak}


class _Akis:
    """multipart gövdesini belleğe almadan akıtır (büyük videolar için)."""

    def __init__(self, parcalar):
        self.parcalar, self.i, self.f = parcalar, 0, None

    def read(self, n=-1):
        out = b""
        while (n < 0 or len(out) < n) and self.i < len(self.parcalar):
            p = self.parcalar[self.i]
            if isinstance(p, bytes):
                out += p
                self.i += 1
            else:
                if self.f is None:
                    self.f = open(p, "rb")
                blok = self.f.read((n - len(out)) if n >= 0 else 1 << 20)
                if not blok:
                    self.f.close()
                    self.f, self.i = None, self.i + 1
                else:
                    out += blok
        return out


def paylas(dosya: str, onay: bool, uc: str = STORAGE_TO) -> dict:
    """storage.to anonim yükleme (ShareX uç noktası: multipart 'file'). DOSYA DIŞARI ÇIKAR: açık onay şart. Yanıttaki bağlantı bulunup döndürülür."""
    if not onay:
        raise ValueError("bu işlem dosyayı storage.to servisine yükler (anonim, süreli bağlantı): açık onay gerekli")
    p = _cikti_dosyasi(dosya)
    import ortak
    ortak._url_kontrol(uc)
    sinir = uuid.uuid4().hex
    bas = (f'--{sinir}\r\nContent-Disposition: form-data; name="file"; filename="{p.name.encode("ascii", "replace").decode()}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
    son = f"\r\n--{sinir}--\r\n".encode()
    boyut = len(bas) + p.stat().st_size + len(son)
    istek = urllib.request.Request(uc, data=_Akis([bas, str(p), son]), method="POST",
                                   headers={"Content-Type": f"multipart/form-data; boundary={sinir}", "Content-Length": str(boyut), "User-Agent": ortak.UA})
    try:
        with urllib.request.urlopen(istek, timeout=3600) as r:
            govde = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"storage.to HTTP {e.code}: {ortak.maskele(e.read().decode('utf-8', 'replace'))[:200]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"storage.to'ya bağlanılamadı: {e.reason}") from None
    try:
        veri = json.loads(govde)
    except ValueError:
        veri = {"yanit": govde[:300]}
    bagl = [m for m in re.findall(r"https://[^\s\"'<>\\]+", json.dumps(veri, ensure_ascii=False))]
    if not bagl:
        raise RuntimeError("servis bağlantı döndürmedi (yanıt biçimi değişmiş olabilir): " + govde[:160])
    ortak.arsiv_gunluk("storage.to", "paylas", f"{p.name} ({p.stat().st_size // 1024} KB)", bagl[0][:60])
    return {"baglanti": bagl[0], "tum_baglantilar": bagl[:4], "uyari": "Anonim ve süreli bağlantı (yaklaşık 3 gün [kaynak: storage.to belgesi]); bağlantıyı bilen herkes indirebilir."}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    try:
        if not a or a[0] == "durum":
            print(json.dumps(durum(), ensure_ascii=False, indent=1))
        elif a[0] == "liste":
            for f in liste(a[1], int(a[a.index("--derinlik") + 1]) if "--derinlik" in a else 1):
                print(f"{f['boyut'] or 0:>12} {f['yol']}")
        elif a[0] == "indir":
            print(json.dumps(indir(a[1], a[2]), ensure_ascii=False))
        elif a[0] == "yukle":
            print(json.dumps(yukle(a[1], a[2], "--onay" in a), ensure_ascii=False))
        elif a[0] == "paylas":
            print(json.dumps(paylas(a[1], "--onay" in a), ensure_ascii=False))
        else:
            print(__doc__)
            return 2
    except (ValueError, RuntimeError, IndexError, OSError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
