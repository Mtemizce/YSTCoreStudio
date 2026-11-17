"""Bir resimden (fotoğraf, çizim, video karesi) kalem darbeleri çıkarır: kenar bulma → inceltme → çizgi izleme → sadeleştirme.

Yalnızca numpy + scipy + Pillow (OpenCV gerekmez). Çıktı `kalem_cizim.py`'nin darbe hattına girer: darbeler resmin üstünde TAM aynı hizada çizilir,
böylece çizim bitince gerçek resim aynı yerde açılabilir.

  cizgiler, (genislik, yukseklik) = resimden_cizgiler("foto.jpg")
"""
from __future__ import annotations

import math
from pathlib import Path

RESIM_UZ = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
VIDEO_UZ = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi")


def resim_ac(yol, en_genis=960):
    """RGB PIL görüntüsü (EXIF yönü uygulanmış), genişliği en_genis'i geçmeyecek biçimde küçültülmüş."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(yol)).convert("RGB")
    if im.width > en_genis:
        im = im.resize((en_genis, max(1, round(im.height * en_genis / im.width))), Image.LANCZOS)
    return im


def kenar_haritasi(gri, sigma=1.3, yuzde_yuksek=93.0, alt_oran=0.45):
    """Canny benzeri: Gauss + Sobel + en büyük olmayanı bastırma (incelik) + çift eşik/histerezis. Dönüş: bool dizisi (1 piksel kalınlığında kenarlar)."""
    import numpy as np
    from scipy import ndimage as ndi
    g = ndi.gaussian_filter(gri.astype("float32"), sigma)
    gx, gy = ndi.sobel(g, axis=1), ndi.sobel(g, axis=0)
    mag = np.hypot(gx, gy)
    if mag.max() <= 1e-6:
        return np.zeros_like(gri, dtype=bool)
    aci = (np.rad2deg(np.arctan2(gy, gx)) + 180.0) % 180.0
    # gradyan yönüne (4 yön) göre iki komşuyla karşılaştır
    d = np.zeros(mag.shape, dtype=np.int8)
    d[(aci >= 22.5) & (aci < 67.5)] = 1
    d[(aci >= 67.5) & (aci < 112.5)] = 2
    d[(aci >= 112.5) & (aci < 157.5)] = 3
    ofs = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (1, -1)}   # gradyan yönü boyunca komşu (satır, sütun); y aşağı doğru artar
    nms = np.zeros(mag.shape, dtype=bool)
    for k, (dy, dx) in ofs.items():
        a = np.roll(mag, (dy, dx), axis=(0, 1))
        b = np.roll(mag, (-dy, -dx), axis=(0, 1))
        nms |= (d == k) & (mag >= a) & (mag >= b)
    yuksek = np.percentile(mag, yuzde_yuksek)
    if yuksek < 0.02 * mag.max():   # seyrek içerik (düz zemin üstünde yazı, logo): yüzdelik ~0 kalır ve tüm kenarlar elenirdi; eşiği en güçlü kenara göre kur
        yuksek = 0.2 * mag.max()
    if yuksek <= 1e-6:
        return np.zeros_like(nms)
    alt = yuksek * alt_oran
    zayif = nms & (mag > alt)
    etiket, n = ndi.label(zayif, structure=np.ones((3, 3)))
    if n == 0:
        return np.zeros_like(nms)
    guclu = np.zeros(n + 1, dtype=bool)
    guclu[np.unique(etiket[nms & (mag > yuksek)])] = True
    guclu[0] = False
    return guclu[etiket]


def _komsular(p, y, x, kume):
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dy or dx) and (y + dy, x + dx) in kume:
                out.append((y + dy, x + dx))
    return out


def cizgi_izle(kenar):
    """1 piksellik kenar haritasını polyline'lara çevirir: uç ve kavşak noktalarından başlayıp komşuları izler. [[(x,y),...],...]"""
    import numpy as np
    pts = [tuple(p) for p in np.argwhere(kenar)]
    kume = set(pts)
    komsu = {p: _komsular(p, p[0], p[1], kume) for p in pts}
    # basamaklı köşelerde (L biçimi) gereksiz çapraz bağı at: bir komşu iki başka komşunun da komşusuysa kısa devre sayılır
    for p in pts:
        ks = komsu[p]
        if len(ks) >= 2:
            dik = [k for k in ks if k[0] == p[0] or k[1] == p[1]]
            comp = [k for k in ks if k not in dik]
            komsu[p] = dik + [k for k in comp if not any(abs(k[0] - o[0]) <= 1 and abs(k[1] - o[1]) <= 1 for o in dik)]
    gorulen = set()  # (a, b) kenarları

    def kenar_anahtar(a, b):
        return (a, b) if a < b else (b, a)

    cizgiler = []

    def yuru(bas, ilk):
        yol = [bas, ilk]
        gorulen.add(kenar_anahtar(bas, ilk))
        onceki, cur = bas, ilk
        while len(komsu[cur]) == 2:
            sonra = next((k for k in komsu[cur] if k != onceki and kenar_anahtar(cur, k) not in gorulen), None)
            if sonra is None:
                break
            gorulen.add(kenar_anahtar(cur, sonra))
            yol.append(sonra)
            onceki, cur = cur, sonra
        return yol

    baslar = [p for p in pts if len(komsu[p]) != 2]  # uçlar ve kavşaklar
    for b in baslar:
        for k in komsu[b]:
            if kenar_anahtar(b, k) not in gorulen:
                cizgiler.append(yuru(b, k))
    for p in pts:  # kalan kapalı halkalar
        for k in komsu[p]:
            if kenar_anahtar(p, k) not in gorulen:
                cizgiler.append(yuru(p, k))
    return [[(x, y) for (y, x) in c] for c in cizgiler]


def _rdp(p, eps):
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


def ton_haritasi(im):
    """Koyuluk 0..1 (1 = koyu). Renkli yüzeyler (ör. kırmızı bayrak) düz parlak saymak için değer (max kanal) ile parlaklık karışımı; yüzdelik germe ile kontrast."""
    import numpy as np
    a = np.asarray(im.convert("RGB"), dtype="float32") / 255.0
    luma = a[:, :, 0] * 0.299 + a[:, :, 1] * 0.587 + a[:, :, 2] * 0.114
    ton = 0.8 * a.max(axis=2) + 0.2 * luma
    lo, hi = np.percentile(ton, [1.5, 99])
    return 1.0 - np.clip((ton - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


# (koyuluk eşiği, çizgi açısı, çizgi aralığı px, çizgi koyuluğu): koyu bölgeler daha çok kat ve sıklıkla taranır (çapraz tarama)
TARAMA_KATMANLARI = [(0.38, 52, 6.0, 0.42), (0.52, 128, 5.2, 0.50), (0.66, 8, 4.5, 0.58), (0.80, 96, 3.8, 0.66)]


def _kar(i, j=0):
    """Tohumlu 0..1 sayı (Math.random yok: aynı resim her seferinde aynı çizimi verir)."""
    h = (i * 374761393 + j * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 4294967296.0


def tarama_darbeleri(im, guc=0.8):
    """Resmin koyu bölgelerini kalem taramasıyla (kısa paralel çizgiler) doldurur. guc 0..1: kaç katman. Dönüş: [{p:[(x,y),(x,y)], L, a, kat}] resim pikselinde,
    katman sırasıyla ve her katmanda çizgi çizgi (gidiş-dönüş) sıralı."""
    import numpy as np
    from scipy import ndimage as ndi
    kuru = ndi.gaussian_filter(ton_haritasi(im), 1.8)
    h, w = kuru.shape
    n = max(0, min(len(TARAMA_KATMANLARI), int(round(guc * len(TARAMA_KATMANLARI)))))
    diag = math.hypot(w, h)
    cx, cy = w / 2, h / 2
    ts = np.arange(-diag / 2, diag / 2, 1.0)
    out = []
    for k, (esik, aci, aralik, alfa) in enumerate(TARAMA_KATMANLARI[:n]):
        th = math.radians(aci)
        dx, dy = math.cos(th), math.sin(th)
        nx, ny = -dy, dx
        cs = np.arange(-diag / 2, diag / 2, aralik)
        X = cx + ts[None, :] * dx + cs[:, None] * nx
        Y = cy + ts[None, :] * dy + cs[:, None] * ny
        ic = (X >= 1) & (X <= w - 2) & (Y >= 1) & (Y <= h - 2)
        val = ndi.map_coordinates(kuru, [np.clip(Y, 0, h - 1), np.clip(X, 0, w - 1)], order=1, mode="nearest")
        esik_s = np.array([esik + 0.06 * (_kar(i, k) - 0.5) for i in range(len(cs))])[:, None]
        mask = ic & (val > esik_s)
        pad = np.pad(mask, ((0, 0), (1, 1))).astype(np.int8)
        d = np.diff(pad, axis=1)
        bas = np.argwhere(d == 1)
        bit = np.argwhere(d == -1)
        for (li, s), (_l2, e) in zip(bas, bit):
            uz = e - s
            if uz < 4:
                continue
            maxl = 22 + 26 * _kar(int(li), int(s) + 7 * k)
            a0 = int(s)
            while a0 < e:
                b0 = int(min(e, a0 + maxl))
                if b0 - a0 >= 3:
                    p0, p1 = (float(X[li, a0]), float(Y[li, a0])), (float(X[li, b0 - 1]), float(Y[li, b0 - 1]))
                    if int(li) % 2:
                        p0, p1 = p1, p0   # gidiş-dönüş
                    out.append({"p": [p0, p1], "L": math.dist(p0, p1), "a": alfa, "kat": k, "sira": (k, int(li), a0 if int(li) % 2 == 0 else -a0)})
                a0 = int(b0 + 1 + 2 * _kar(int(li), a0))
    out.sort(key=lambda s: s["sira"])
    for s in out:
        del s["sira"]
    return out


def resimden_cizgiler(yol, en_genis=960, en_kisa=6.0, detay=0.8):
    """Resim → (çizgiler, (genislik, yukseklik)). Koordinatlar çalışma boyutundaki resmin pikselidir; en_kisa: bundan kısa darbeler (gürültü) atılır.
    detay 0..1: yüksek = daha çok ayrıntı (daha çok darbe)."""
    en_kisa = en_kisa + 8.0 * (1.0 - max(0.0, min(1.0, detay)))   # düşük ayrıntıda kısa kıymıkları (cilt dokusu gibi) at
    import numpy as np
    im = resim_ac(yol, en_genis)
    gri = np.asarray(im.convert("L"), dtype="float32") / 255.0
    kenar = kenar_haritasi(gri, yuzde_yuksek=96.0 - 6.0 * max(0.0, min(1.0, detay)))
    kenar[:2, :] = kenar[-2:, :] = False  # çerçeve kenarında sahte çizgiler
    kenar[:, :2] = kenar[:, -2:] = False
    ham = cizgi_izle(kenar)
    cizgiler = []
    for c in ham:
        c = _rdp(c, 0.9)
        L = sum(math.dist(a, b) for a, b in zip(c, c[1:]))
        if L >= en_kisa and len(c) >= 2:
            cizgiler.append(c)
    return cizgiler, im.size
