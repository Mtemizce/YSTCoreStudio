#!/usr/bin/env python3
"""Vektör çizimi (DWG ya da SVG) kalemle kademeli çizilen bir ara sahne videosuna çevirir. Tamamen yerel, kod yazdırmadan.

  python sistem/araclar/kalem_cizim.py <cizim.dwg|cizim.svg> -o ara-sahne.mp4 [--stil parsomen|karakalem|teknik] [--sure 8] [--fps 30]
  python sistem/araclar/kalem_cizim.py <resim.jpg|png> -o ara-sahne.mp4 --gecis [--bekle 2]   resmi kalemle çiz, bekle sn sonra gerçek resme dönüştür
  python sistem/araclar/kalem_cizim.py <video.mp4> -o giris.mp4 [--bekle 2]                   videonun ilk karesini çiz, gerçeğe dönüşüp video devam etsin
  (her komuta --zemin "#DCE8D4" eklenirse kâğıt rengi değişir: açık, koyu ya da yeşilimsi)
  python sistem/araclar/kalem_cizim.py --stiller                   stil listesi (JSON)
  python sistem/araclar/kalem_cizim.py <cizim> --darbe-yaz darbeler.json   yalnızca darbe dosyasını üretir (tarayıcı gerekmez)

Akış: DWG → (LibreDWG dwg2SVG, yalnızca Windows'ta paketli) SVG → yol/daire düzleştirme → ölçekleme (1920x1080) → darbelere böl ve sırala (önce uzun/ana çizgiler,
sonra ayrıntı; yakın darbeler peş peşe) → `sistem/kit/kalem/sablon/cizim-genel.html` sayfası kare kare çizer (`ortak/yakala.py`, Remotion'un başsız Chrome'u) → ffmpeg → mp4.
Yazılar (<text>) ve blok eklemeleri (<use>) çizilmez; yalnızca çizgi, yay, eğri ve daireler. Ölçü/ölçek iddiası için orijinal çizim esastır: bu bir ANLATIM görselidir.

Kaynak: çizim görünümü ve yakalama hattı github.com/leodavincs/kalem'den (MIT, © 2026 Leo) uyarlandı; DWG→darbe dönüştürücü bu depoya özgüdür.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))  # kalem_resim
RESIM_UZ = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
VIDEO_UZ = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi")
ROOT = HERE.parents[1]
KALEM = ROOT / "sistem" / "kit" / "kalem"
DWG2SVG = HERE / "dis" / "libredwg" / "dwg2SVG.exe"
W, H = 1920, 1080
KENAR = 96  # px: çizimin etrafındaki boşluk
STILLER = {
    "parsomen": {"ad": "Parşömen eskizi", "aciklama": "Bej kâğıt, kahverengi mürekkep, tüy kalem; eski defter hissi."},
    "karakalem": {"ad": "Kara kalem", "aciklama": "Beyaz kâğıt, koyu grafit, kurşun kalem; sade ve temiz."},
    "teknik": {"ad": "Mavi teknik çizim", "aciklama": "Lacivert zemin, açık çizgi; mühendislik/mimari anlatımı."},
}
SAYI = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


# ----------------------------------------------------------------------------------------------- SVG → çizgiler
def _yay(x1, y1, rx, ry, fi, fa, fs, x2, y2):
    """SVG uç-nokta yayını (A) noktalara çevirir (W3C F.6.5)."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    c, s = math.cos(math.radians(fi)), math.sin(math.radians(fi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = c * dx + s * dy, -s * dx + c * dy
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    pay = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    kok = math.sqrt(max(0.0, pay / (rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2))) * (-1 if fa == fs else 1)
    cxp, cyp = kok * rx * y1p / ry, -kok * ry * x1p / rx
    cx, cy = c * cxp - s * cyp + (x1 + x2) / 2, s * cxp + c * cyp + (y1 + y2) / 2

    def aci(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = aci(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = aci((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(4, int(abs(dt) / math.radians(6)) + 1)
    out = []
    for i in range(1, n + 1):
        a = t1 + dt * i / n
        px, py = rx * math.cos(a), ry * math.sin(a)
        out.append((c * px - s * py + cx, s * px + c * py + cy))
    out[-1] = (x2, y2)
    return out


def yol_duzlestir(d: str) -> list[list[tuple[float, float]]]:
    """SVG yol verisi → polyline listesi. M/L/H/V/C/Q/A/Z (mutlak ve göreli); S/T uç noktaya düz çizgi olarak yaklaşıklanır."""
    jt = SAYI.findall(d)
    i, kom = 0, ""
    cizgiler, cur = [], []
    x = y = bx = by = 0.0

    def al(n):
        nonlocal i
        v = [float(t) for t in jt[i:i + n]]
        if len(v) < n:
            raise ValueError("eksik sayı")
        i += n
        return v

    while i < len(jt):
        if re.fullmatch(r"[A-Za-z]", jt[i]):
            kom = jt[i]
            i += 1
            if kom in "Zz":
                if cur:
                    cur.append((bx, by))
                    cizgiler.append(cur)
                    cur = []
                x, y = bx, by
                continue
        rel = kom.islower()
        k = kom.upper()
        if k == "M":
            a, b = al(2)
            x, y = (x + a, y + b) if rel else (a, b)
            if cur:
                cizgiler.append(cur)
            cur, bx, by = [(x, y)], x, y
            kom = "l" if rel else "L"
        elif k == "L":
            a, b = al(2)
            x, y = (x + a, y + b) if rel else (a, b)
            cur.append((x, y))
        elif k == "H":
            (a,) = al(1)
            x = x + a if rel else a
            cur.append((x, y))
        elif k == "V":
            (a,) = al(1)
            y = y + a if rel else a
            cur.append((x, y))
        elif k == "C":
            x1, y1, x2, y2, x3, y3 = al(6)
            if rel:
                x1, y1, x2, y2, x3, y3 = x + x1, y + y1, x + x2, y + y2, x + x3, y + y3
            for j in range(1, 13):
                t = j / 12
                u = 1 - t
                cur.append((u ** 3 * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3, u ** 3 * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3))
            x, y = x3, y3
        elif k == "Q":
            x1, y1, x2, y2 = al(4)
            if rel:
                x1, y1, x2, y2 = x + x1, y + y1, x + x2, y + y2
            for j in range(1, 9):
                t = j / 8
                u = 1 - t
                cur.append((u * u * x + 2 * u * t * x1 + t * t * x2, u * u * y + 2 * u * t * y1 + t * t * y2))
            x, y = x2, y2
        elif k == "A":
            rx, ry, fi, fa, fs, a, b = al(7)
            if rel:
                a, b = x + a, y + b
            cur.extend(_yay(x, y, rx, ry, fi, int(fa), int(fs), a, b))
            x, y = a, b
        elif k in "ST":
            n = 4 if k == "S" else 2
            v = al(n)
            a, b = (x + v[-2], y + v[-1]) if rel else (v[-2], v[-1])
            cur.append((a, b))
            x, y = a, b
        else:
            break
    if cur:
        cizgiler.append(cur)
    return [c for c in cizgiler if len(c) >= 2]


def svg_cizgiler(svg: str) -> tuple[list[list[tuple[float, float]]], dict]:
    """SVG metninden polyline'lar. Yazı ve blok eklemeleri çizilmez (sayılır)."""
    cizgiler, bozuk = [], 0
    for d in re.findall(r'<path\b[^>]*?\sd="([^"]+)"', svg):
        try:
            cizgiler += yol_duzlestir(d)
        except (ValueError, IndexError):
            bozuk += 1
    for m in re.finditer(r"<circle\b([^>]*)>", svg):
        a = dict(re.findall(r'(\w+)="([^"]+)"', m.group(1)))
        try:
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
        except (KeyError, ValueError):
            continue
        if r > 0:
            cizgiler.append([(cx + r * math.cos(2 * math.pi * k / 48), cy + r * math.sin(2 * math.pi * k / 48)) for k in range(49)])
    return cizgiler, {"yazi_atlandi": len(re.findall(r"<text\b", svg)), "blok_atlandi": len(re.findall(r"<use\b", svg)), "bozuk_yol": bozuk}


def dwg_svg(dwg: Path) -> str:
    if os.name != "nt" or not DWG2SVG.exists():
        raise RuntimeError("DWG okuma yalnızca Windows'ta paketli LibreDWG ile yapılır; çizimi SVG olarak dışa aktarıp ver (.svg kabul edilir)")
    r = subprocess.run([str(DWG2SVG), str(dwg)], capture_output=True, timeout=180)
    s = r.stdout.decode("utf-8", "replace")
    if "<path" not in s:
        raise RuntimeError("dwg2SVG çizim üretmedi (bu DWG sürümü desteklenmiyor olabilir)")
    return s


# ----------------------------------------------------------------------------------------------- ölçekleme, darbeler
def _uzunluk(p):
    return sum(math.dist(a, b) for a, b in zip(p, p[1:]))


def sadelestir(p, eps=0.6):
    """Ramer-Douglas-Peucker (yinelemesiz)."""
    if len(p) < 3:
        return p
    tut = [False] * len(p)
    tut[0] = tut[-1] = True
    yigin = [(0, len(p) - 1)]
    while yigin:
        a, b = yigin.pop()
        (x1, y1), (x2, y2) = p[a], p[b]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        en, ei = 0.0, -1
        for i in range(a + 1, b):
            if l2 == 0:
                d = math.dist(p[i], p[a])
            else:
                t = max(0, min(1, ((p[i][0] - x1) * dx + (p[i][1] - y1) * dy) / l2))
                d = math.dist(p[i], (x1 + t * dx, y1 + t * dy))
            if d > en:
                en, ei = d, i
        if en > eps and ei > 0:
            tut[ei] = True
            yigin += [(a, ei), (ei, b)]
    return [q for q, t in zip(p, tut) if t]


def hilbert(x, y, n=1024):
    d, s = 0, n // 2
    while s > 0:
        rx, ry = (x & s) > 0, (y & s) > 0
        d += s * s * ((3 * rx) ^ ry)
        if not ry:
            if rx:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        s //= 2
    return d


def odak_kutusu(noktalar):
    """Çizimin asıl bulunduğu kutu. DWG sayfalarında uzak köşelerde kaçak nesneler olur (çizimi küçücük bırakır): önce %1-%99 aralığı, sonra nokta yoğunluğu
    ızgarasında (48x48) en çok nokta taşıyan bitişik bölge (2 hücre boşluk köprülenir) alınır; bölge tüm kutunun %85'inden küçükse ona yakınlaşılır."""
    xs = sorted(q[0] for q in noktalar)
    ys = sorted(q[1] for q in noktalar)
    pay = lambda a, q: a[min(len(a) - 1, max(0, int(len(a) * q)))]  # noqa: E731
    x0, x1, y0, y1 = pay(xs, 0.01), pay(xs, 0.99), pay(ys, 0.01), pay(ys, 0.99)
    px, py = (x1 - x0) * 0.04, (y1 - y0) * 0.04
    x0, x1, y0, y1 = x0 - px, x1 + px, y0 - py, y1 + py
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    G = 48
    hucre: dict = {}
    for a, b in noktalar:
        k = (min(G - 1, max(0, int((a - x0) / w * G))), min(G - 1, max(0, int((b - y0) / h * G))))
        hucre[k] = hucre.get(k, 0) + 1
    esik = max(hucre.values()) * 0.02
    dolu = {k for k, v in hucre.items() if v >= esik}
    kalan, kumeler = set(dolu), []
    while kalan:
        bas = kalan.pop()
        kume, sira = {bas}, [bas]
        while sira:
            ci, cj = sira.pop()
            for di in range(-2, 3):
                for dj in range(-2, 3):
                    n = (ci + di, cj + dj)
                    if n in kalan:
                        kalan.discard(n)
                        kume.add(n)
                        sira.append(n)
        kumeler.append(kume)
    if kumeler:
        en = max(kumeler, key=lambda c: sum(hucre[k] for k in c))
        cx0, cx1 = x0 + min(k[0] for k in en) / G * w, x0 + (max(k[0] for k in en) + 1) / G * w
        cy0, cy1 = y0 + min(k[1] for k in en) / G * h, y0 + (max(k[1] for k in en) + 1) / G * h
        if (cx1 - cx0) < w * 0.85 or (cy1 - cy0) < h * 0.85:
            mx, my = (cx1 - cx0) * 0.05, (cy1 - cy0) * 0.05
            return cx0 - mx, cx1 + mx, cy0 - my, cy1 + my
    return x0, x1, y0, y1


def darbeler(cizgiler, sure=8.0, fps=30, en_cok=4000, kutu=None, kenar=KENAR):
    """Çizgileri ekrana oturtur, sıralar ve zamanlar. {w,h,kare,yer,darbeler:[{p,L,bas,sure}]}
    kutu=(x0,x1,y0,y1): çizimin kapladığı alan elle verilir (resim modu: resmin tamamı; odak kırpması yapılmaz). kenar: tuval kenar boşluğu (resimde 0: gerçek resim aynı hizada açılsın)."""
    if not cizgiler:
        raise RuntimeError("çizimde çizgi bulunamadı")
    if kutu is not None:
        x0, x1, y0, y1 = kutu
    else:
        ham = [q for c in cizgiler for q in c]
        ex = max(max(q[0] for q in ham) - min(q[0] for q in ham), max(q[1] for q in ham) - min(q[1] for q in ham), 1e-6)
        adim = ex / 250.0
        yogun = []  # uzun düz çizgilerin yalnızca iki ucu vardır: yoğunluk hesabı için çizgi boyunca nokta eklenir
        for c in cizgiler:
            for a, b in zip(c, c[1:]):
                n = max(1, min(400, int(math.dist(a, b) / adim)))
                yogun += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
        x0, x1, y0, y1 = odak_kutusu(yogun or ham)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    olcek = min((W - 2 * kenar) / w, (H - 2 * kenar) / h)
    ox, oy = (W - w * olcek) / 2, (H - h * olcek) / 2
    aday = []
    for c in cizgiler:
        cx, cy = sum(q[0] for q in c) / len(c), sum(q[1] for q in c) / len(c)
        if kutu is None and not (x0 <= cx <= x1 and y0 <= cy <= y1):
            continue
        p = [((q[0] - x0) * olcek + ox, (q[1] - y0) * olcek + oy) for q in c]
        disarda = sum(1 for q in p if not (-20 <= q[0] <= W + 20 and -20 <= q[1] <= H + 20))
        if disarda > 0.4 * len(p):
            continue  # çoğu ekran dışında kalan darbe (kesik görünür): çizilmez
        p = sadelestir(p)
        L = _uzunluk(p)
        if L >= 3.0:
            aday.append((p, L))
    if not aday:
        raise RuntimeError("ölçeklenen çizimde görünür çizgi kalmadı")
    aday.sort(key=lambda a: -a[1])
    aday = aday[:en_cok]
    uzunlar = sorted(a[1] for a in aday)
    esik = uzunlar[int(len(uzunlar) * 0.8)]
    ana = [a for a in aday if a[1] >= esik]
    ayr = [a for a in aday if a[1] < esik]
    sira = lambda a: hilbert(int(min(1023, max(0, a[0][0][0] / W * 1024))), int(min(1023, max(0, a[0][0][1] / H * 1024))))  # noqa: E731
    ana.sort(key=sira)
    ayr.sort(key=sira)
    sirali = ana + ayr
    kare = int(round(sure * fps))
    bekle = min(24, kare // 6)  # son kareler sakin
    aralik = max(1, kare - bekle)
    agirlik = [4 + a[1] ** 0.75 for a in sirali]
    k = aralik / sum(agirlik)
    cur, out = 0.0, []
    for (p, L), a in zip(sirali, agirlik):
        s = max(0.5, a * k * 1.6)  # hafif örtüşme: kalem bir sonrakine geçerken öncekini bitirir
        out.append({"p": [[round(q[0], 1), round(q[1], 1)] for q in p], "L": round(L, 1), "bas": round(cur, 2), "sure": round(s, 2)})
        cur += a * k
    return {"w": W, "h": H, "fps": fps, "kare": kare, "yer": {"x": round(ox, 2), "y": round(oy, 2), "w": round(w * olcek, 2), "h": round(h * olcek, 2)}, "darbeler": out}


def cizimden_darbeler(kaynak: Path, sure=8.0, fps=30, gecis=False, bekle=2.0, gecis_sure=1.2, tut=1.5, detay=0.8, tarama=0.8) -> tuple[dict, dict]:
    """Kaynak: .dwg/.svg (vektör) ya da resim (.jpg/.png/...). gecis=True (yalnızca resim): çizim bitince `bekle` sn sonra çizim bulanıklaşıp gerçek resme dönüşür
    (`gecis_sure` sn), ardından `tut` sn gerçek resim kalır."""
    kaynak = Path(kaynak)
    uz = kaynak.suffix.lower()
    if uz == ".dwg":
        svg = dwg_svg(kaynak)
    elif uz == ".svg":
        svg = kaynak.read_text(encoding="utf-8", errors="replace")
    elif uz in RESIM_UZ:
        from kalem_resim import resim_ac, resimden_cizgiler, tarama_darbeleri
        en = int(800 + 600 * max(0.0, min(1.0, detay)))
        try:
            cizgiler, (iw, ih) = resimden_cizgiler(kaynak, en_genis=en, detay=detay)
            im_t = resim_ac(kaynak, 1920)   # tarama çıkış çözünürlüğünde: çizgi aralığı ekranda ~4-6 px
            tar = tarama_darbeleri(im_t, max(0.0, min(1.0, tarama))) if tarama > 0 else []
        except (OSError, ValueError) as e:
            raise RuntimeError(f"resim açılamadı: {kaynak.name} ({str(e)[:80]})") from e
        d = darbeler(cizgiler, sure * (0.38 if tar else 1.0), fps, kutu=(0, iw, 0, ih), kenar=0)   # önce konturlar, sonra tarama
        bilgi = {"cizgi": len(cizgiler), "darbe": len(d["darbeler"]), "resim": True}
        if tar:
            if len(tar) > 16000:
                tar = tar[::-(-len(tar) // 16000)]
            yer = d["yer"]
            olcek, ox, oy = yer["w"] / im_t.width, yer["x"], yer["y"]
            kare_t = int(round(sure * fps))
            t0 = d["kare"] - min(24, d["kare"] // 6)
            bitis = kare_t - min(24, kare_t // 6)
            agirlik = [1.2 + s["L"] ** 0.6 for s in tar]
            k = max(1, bitis - t0) / sum(agirlik)
            cur = float(t0)
            for s, a in zip(tar, agirlik):
                p = [[round(x * olcek + ox, 1), round(y * olcek + oy, 1)] for x, y in s["p"]]
                L = round(s["L"] * olcek, 1)
                d["darbeler"].append({"p": p, "L": L, "bas": round(cur, 2), "sure": round(max(0.4, a * k * 1.3), 2), "a": s["a"], "w": 0.8})
                cur += a * k
            d["kare"] = kare_t
            bilgi["tarama"] = len(tar)
        if gecis:
            cizim = d["kare"]
            d["cizim_kare"] = cizim
            d["gecis"] = {"bas": cizim + int(round(bekle * fps)), "sure": max(1, int(round(gecis_sure * fps)))}
            d["kare"] = d["gecis"]["bas"] + d["gecis"]["sure"] + int(round(tut * fps))
        return d, bilgi
    else:
        raise RuntimeError(f"desteklenmeyen kaynak: {kaynak.suffix} (.dwg, .svg ya da resim ver)")
    if gecis:
        raise RuntimeError("gerçeğe geçiş yalnızca resim ve video kaynağında olur (DWG/SVG'nin gerçek karşılığı yok)")
    cizgiler, bilgi = svg_cizgiler(svg)
    d = darbeler(cizgiler, sure, fps)
    bilgi.update(cizgi=len(cizgiler), darbe=len(d["darbeler"]))
    return d, bilgi


# ----------------------------------------------------------------------------------------------- video
# ----------------------------------------------------------------------------------------------- kalem sesi
SFX_DIZIN = ROOT / "sistem" / "kit" / "sfx-wyzowl" / "sounds" / "writing-and-drawing"   # CC0 ses efektleri (isteğe bağlı indirilir; yoksa kodla üretilir)
SES_SR = 48000


def _sfx_oku(ad):
    """Kurulumdaki gerçek kalem kaydını (CC0) mono float32 okur; yoksa None."""
    import numpy as np
    yol = SFX_DIZIN / f"{ad}.wav"
    if not yol.is_file() or not shutil.which("ffmpeg"):
        return None
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(yol), "-ac", "1", "-ar", str(SES_SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy() if r.returncode == 0 and r.stdout else None


def _dongu(klip, n, rng, xf=0.03):
    """Kaydın rastgele başlangıçlı parçalarını çapraz geçişle uç uca ekleyip n örneklik sürekli bir 'yatak' yapar (tekrar fark edilmesin)."""
    import numpy as np
    parca = int(len(klip) * 0.6)
    k = int(SES_SR * xf)
    out = np.zeros(n + parca + 2 * k, dtype=np.float32)
    pos, ilk = 0, True
    while pos < n:
        b = int(rng.integers(0, max(1, len(klip) - parca)))
        p = klip[b:b + parca].copy()
        if not ilk:
            w = np.linspace(0, 1, k, dtype=np.float32)
            out[pos:pos + k] = out[pos:pos + k] * (1 - w) + p[:k] * w
            out[pos + k:pos + len(p)] = p[k:]
        else:
            out[pos:pos + len(p)] = p
        pos += len(p) - k
        ilk = False
    return out[:n]


def _sentez(n, rng, alt, ust):
    """Kayıt yoksa yedek: bant geçiren gürültü + yavaş genlik dalgalanması (kâğıt üstünde kalem hışırtısı)."""
    import numpy as np
    from scipy import signal
    g = rng.standard_normal(n).astype(np.float32)
    sos = signal.butter(4, [alt, ust], btype="band", fs=SES_SR, output="sos")
    g = signal.sosfilt(sos, g).astype(np.float32)
    mod = signal.sosfilt(signal.butter(2, 6, btype="low", fs=SES_SR, output="sos"), rng.standard_normal(n)).astype(np.float32)
    mod = 0.55 + 0.45 * mod / (np.abs(mod).max() + 1e-9)
    return g * mod / (np.abs(g).max() + 1e-9)


def kalem_sesi(d: dict, fps: int, hedef: Path, tohum: int = 3) -> float | None:
    """Çizim darbelerinin zamanlamasına bağlı kalem sesi üretir (mono WAV, tüm giriş süresi kadar; çizim yokken sessiz).
    Seyrek konturlarda uzun kalem çizgisi kaydı, yoğun taramada hızlı karalama kaydı öne çıkar. Kurulumdaki CC0 kayıtlar yoksa sentezlenmiş hışırtı kullanılır.
    Süreyi (sn) döndürür; çizim yoksa None."""
    import wave
    import numpy as np
    from scipy import ndimage as ndi
    nf = int(d.get("kare") or 0)
    ds = d.get("darbeler") or []
    if nf <= 0 or not ds:
        return None
    aktif = np.zeros(nf + 2, dtype=np.float32)
    basl = np.zeros(nf + 2, dtype=np.float32)
    for s in ds:
        b = max(0, int(s["bas"]))
        e = min(nf, int(math.ceil(s["bas"] + s["sure"])) + 1)
        aktif[b:e] = 1.0
        basl[min(nf, b)] += 1.0
    yog = ndi.uniform_filter1d(basl, size=max(3, int(fps * 0.4)))
    yogun = np.clip(np.log1p(yog) / math.log1p(20.0), 0, 1)                  # 0: seyrek kontur, 1: yoğun tarama
    ortak = ndi.maximum_filter1d(aktif, size=max(3, int(fps * 0.25)))       # kısa boşlukları kapat: kalem havada ama çizim sürüyor
    ortak = ndi.uniform_filter1d(ortak, size=max(3, int(fps * 0.12)))      # yumuşak giriş/çıkış
    n = int(round(nf / fps * SES_SR))
    t = np.arange(n) / SES_SR * fps
    ort = np.interp(t, np.arange(len(ortak)), ortak).astype(np.float32)
    yg = np.interp(t, np.arange(len(yogun)), yogun).astype(np.float32)
    rng = np.random.default_rng(tohum)
    cizgi, karala = _sfx_oku("writing-pencil-draw"), _sfx_oku("writing-scribble")
    a = _dongu(cizgi, n, rng) if cizgi is not None else _sentez(n, rng, 1800, 7000)
    b = _dongu(karala, n, rng) if karala is not None else _sentez(n, rng, 2500, 9000)
    mix = a * ort * (0.55 + 0.25 * yg) + b * ort * np.clip((yg - 0.5) / 0.45, 0, 1) * 0.8
    tepe = float(np.abs(mix).max())
    if tepe < 1e-6:
        return None
    mix = mix / tepe * 0.8
    Path(hedef).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(hedef), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SES_SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    return n / SES_SR


KAGIT_RENK = {"parsomen": "0xE8D9B8", "karakalem": "0xF3F1EC", "teknik": "0x0F2A4A"}


def zemin_rgb(zemin) -> list[int] | None:
    """Zemin (kâğıt) rengi: '#RRGGBB' ya da 'RRGGBB'. None/boş: stilin kendi rengi. Geçersizse ValueError."""
    if zemin is None or str(zemin).strip() == "":
        return None
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(zemin).strip())
    if not m:
        raise ValueError(f"zemin rengi #RRGGBB biçiminde olmalı: {zemin!r}")
    h = m.group(1)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _ffmpeg(args, hata):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(hata + ": " + r.stderr.strip()[-250:])


def video_uret(kaynak: Path, cikti: Path, stil="parsomen", sure=8.0, fps=30, kare_sinir=None, gecis=False, bekle=2.0, video: Path | None = None, zemin=None, detay=0.8, tarama=0.8, cizim_kaynagi: Path | None = None, ses_efekti=True) -> dict:
    """kaynak: çizim (dwg/svg) ya da resim. video verilirse: videonun İLK KARESİ kalemle çizilir, bekle sn sonra çizim gerçek kareye dönüşür ve video kesintisiz devam eder
    (çıktı = giriş + video, tek mp4)."""
    if stil not in STILLER:
        raise RuntimeError(f"bilinmeyen stil '{stil}' ({', '.join(STILLER)})")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg bulunamadı")
    with tempfile.TemporaryDirectory(prefix="yst-kalem-sahne-") as td:
        td = Path(td)
        gercek = None
        if video is not None:
            video = Path(video)
            if not video.is_file():
                raise RuntimeError(f"video yok: {video}")
            gercek = td / "kaynak-kare.png"
            _ffmpeg(["-i", str(video), "-frames:v", "1", str(gercek)], "videonun ilk karesi alınamadı")
            kaynak, gecis = (Path(cizim_kaynagi) if cizim_kaynagi else gercek), True   # çizilen resim, gerçek karenin temiz hâli olabilir (aynı kadraj)
        elif gecis:
            gercek = Path(kaynak)
        d, bilgi = cizimden_darbeler(kaynak, sure, fps, gecis=gecis, bekle=bekle, tut=0.0 if video is not None else 1.5, detay=detay, tarama=tarama)
        d["stil"] = stil
        zr = zemin_rgb(zemin)
        if zr:
            d["zemin"] = zr  # sayfa kâğıt rengini değiştirir; mürekkep zemine göre koyu/açık seçilir
        if gecis:
            from kalem_resim import resim_ac
            resim_ac(gercek, 1920).save(td / "gercek.jpg", quality=93)  # sayfa gerçek resmi buradan açar (aynı hizada)
            d["gercek"] = "gercek.jpg"
        (td / "strokes.json").write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
        kalem_wav = td / "kalem.wav"
        kalem_var = bool(ses_efekti) and kalem_sesi(d, fps, kalem_wav) is not None
        shutil.copy(KALEM / "sablon" / "cizim-genel.html", td / "sahne.html")
        kareler = td / "kareler"
        cmd = [sys.executable, str(KALEM / "ortak" / "yakala.py"), str(td / "sahne.html"), str(kareler)] + (["--kare", str(kare_sinir)] if kare_sinir else [])
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500, env={**os.environ, "PYTHONUTF8": "1"})
        n = len(list(kareler.glob("*.png"))) if kareler.is_dir() else 0
        if r.returncode != 0 or n == 0:
            raise RuntimeError("kareler yakalanamadı: " + ((r.stdout + r.stderr).strip().splitlines() or ["bilinmeyen hata"])[-1][:300])
        cikti = Path(cikti)
        cikti.parent.mkdir(parents=True, exist_ok=True)
        giris = td / "giris.mp4" if video is not None else (td / "sessiz.mp4" if kalem_var else cikti)
        _ffmpeg(["-framerate", str(fps), "-i", str(kareler / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(giris)], "mp4 yazılamadı")
        if video is None and kalem_var:   # yalnızca çizim: kalem sesini ekle
            _ffmpeg(["-i", str(giris), "-i", str(kalem_wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(cikti)], "kalem sesi eklenemedi")
        if video is not None:
            # video çizimin son karesiyle AYNI hizada başlar: aynı sığdırma (oran korunur, ortalanır, kâğıt renginde dolgu)
            ses = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip() != ""
            vf = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={("0x%02X%02X%02X" % tuple(zr)) if zr else KAGIT_RENK[stil]},setsar=1,format=yuv420p"
            girdiler = ["-i", str(giris), "-i", str(video)]
            sure_de = lambda dosya: subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dosya)], capture_output=True, text=True).stdout.strip()  # noqa: E731
            if ses or kalem_var:
                gs = sure_de(giris)
                if kalem_var:   # giriş sesi = kalem sesi (çizim bitince sessizlik)
                    girdiler += ["-i", str(kalem_wav)]
                    a0 = f"[2:a]aresample=48000,apad,atrim=0:{gs},aformat=channel_layouts=stereo[a0]"
                else:
                    girdiler += ["-f", "lavfi", "-t", gs, "-i", "anullsrc=r=48000:cl=stereo"]
                    a0 = "[2:a]aresample=48000[a0]"
                if ses:
                    a1 = "[1:a]aresample=48000,aformat=channel_layouts=stereo[a1]"
                else:   # videonun sesi yok: kalem sesi varken giriş+video birleşebilsin diye sessizlik
                    girdiler += ["-f", "lavfi", "-t", sure_de(video), "-i", "anullsrc=r=48000:cl=stereo"]
                    a1 = "[3:a]aresample=48000[a1]"
                fc = f"[0:v]setsar=1[v0];[1:v]{vf}[v1];{a0};{a1};[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
                esle = ["-map", "[v]", "-map", "[a]"]
                ses = True
            else:
                fc = f"[0:v]setsar=1[v0];[1:v]{vf}[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
                esle = ["-map", "[v]"]
            _ffmpeg([*girdiler, "-filter_complex", fc, *esle, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", *(["-c:a", "aac", "-b:a", "192k"] if ses else []), str(cikti)],
                    "giriş ile video birleştirilemedi")
    bilgi.update(kare=n, stil=stil, cikti=str(cikti))
    return bilgi


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kaynak", nargs="?")
    ap.add_argument("-o", "--cikti")
    ap.add_argument("--stil", default="parsomen")
    ap.add_argument("--detay", type=float, default=0.8, help="resim kaynağında çizgi ayrıntısı 0-1 (yüksek: daha çok darbe, yüz gibi ince ayrıntılar için 1)")
    ap.add_argument("--tarama", type=float, default=0.8, help="resim kaynağında ton taraması 0-1: koyu yerler kalem taramasıyla (çapraz çizgiler) gölgelenir; 0 = yalnızca kontur çizgileri")
    ap.add_argument("--cizim-kaynagi", help="video girişinde: videonun ilk karesi yerine bu resim (aynı kadrajda, ör. vinyetsiz ve grensiz hâli) çizilir")
    ap.add_argument("--sessiz", action="store_true", help="kalem çizim sesini ekleme (varsayılan: çizim darbelerine bağlı kalem sesi eklenir)")
    ap.add_argument("--zemin", help="kâğıt (zemin) rengi #RRGGBB: açık, koyu ya da yeşilimsi; boşsa stilin kendi rengi")
    ap.add_argument("--sure", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--kare", type=int, help="yalnızca ilk N kareyi yakala (deneme)")
    ap.add_argument("--gecis", action="store_true", help="resim kaynağında: çizim bitince gerçek resme dönüşür")
    ap.add_argument("--bekle", type=float, default=2.0, help="çizim bittikten kaç saniye sonra gerçeğe geçilsin")
    ap.add_argument("--video", help="videonun ilk karesini çizerek başla, bekle sn sonra gerçeğe dönüşüp video devam etsin (kaynak olarak videoyu ver)")
    ap.add_argument("--stiller", action="store_true")
    ap.add_argument("--darbe-yaz")
    a = ap.parse_args()
    if a.stiller:
        print(json.dumps(STILLER, ensure_ascii=False, indent=1))
        return 0
    if not a.kaynak:
        ap.error("çizim dosyası ver")
    try:
        if a.darbe_yaz:
            d, bilgi = cizimden_darbeler(Path(a.kaynak), a.sure, a.fps, gecis=a.gecis, bekle=a.bekle)
            Path(a.darbe_yaz).write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
            print(json.dumps(bilgi, ensure_ascii=False))
            return 0
        if not a.cikti:
            ap.error("-o <video.mp4> ver")
        kaynak, video = Path(a.kaynak), None
        if kaynak.suffix.lower() in VIDEO_UZ:
            video = kaynak
        print(json.dumps(video_uret(kaynak, Path(a.cikti), a.stil, a.sure, a.fps, a.kare, gecis=a.gecis, bekle=a.bekle, video=video, zemin=a.zemin, detay=a.detay, tarama=a.tarama, cizim_kaynagi=Path(a.cizim_kaynagi) if a.cizim_kaynagi else None, ses_efekti=not a.sessiz), ensure_ascii=False))
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        print("HATA:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
