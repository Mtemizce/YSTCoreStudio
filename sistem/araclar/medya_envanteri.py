#!/usr/bin/env python3
"""Kaynak envanteri: foto/video dosyalarını ölçer, kalite sınıfı ve kullanım önerisi verir, kontak sayfası çıkarır.

  python medya_envanteri.py <klasör|dosya> [<klasör|dosya> ...] [-o proje_klasoru] [--hedef 1920x1080]

Çıktı (-o verilirse): <o>/envanter.json, <o>/envanter_kontak.jpg ; ekrana özet tablo.
Ölçüt (tam ekran 1080p için): uzun kenar >= 1920 "yüksek", 1200-1919 "orta", < 1200 "düşük". Keskinlik = Laplace varyansı (göreli).
Öneri: yuksek -> "olduğu gibi" · orta -> "iyilestir (2x) ya da kart" · dusuk -> "iyilestir + kart/blurlu zemin, zoom<=1.08".
Hiçbir dosyayı DEĞİŞTİRMEZ.
"""
import argparse
import json
import os
import subprocess
import sys

IMG = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
VID = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi")


NW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def ffprobe():
    from shutil import which
    p = which("ffprobe")
    if p:
        return p
    try:
        import media_tools
        return media_tools.find("ffprobe")
    except Exception:
        return None


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _d, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith(IMG + VID):
                        out.append(os.path.join(root, f))
        elif os.path.isfile(p):
            out.append(p)
    return out


def sharpness(im):
    """Laplace varyansı (gri, 512 px'e indirilmiş): kaba ama kıyaslanabilir keskinlik ölçüsü."""
    import numpy as np
    from PIL import ImageOps
    g = ImageOps.grayscale(im)
    g.thumbnail((512, 512))
    a = np.asarray(g, dtype="float32")
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    return float(lap.var())


def classify(long_side):
    return "yuksek" if long_side >= 1920 else "orta" if long_side >= 1200 else "dusuk"


ADVICE = {"yuksek": "olduğu gibi (derecelendirme yeter)",
          "orta": "iyileştir (2x) ya da kart olarak kullan",
          "dusuk": "iyileştir + kart/blurlu zemin; zoom <= 1.08"}


def inspect_image(path):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    cls = classify(max(w, h))
    import numpy as np
    lum = float(np.asarray(im.resize((32, 32)).convert("L"), dtype="float32").mean())
    d = {"tur": "foto", "dosya": path, "genislik": w, "yukseklik": h, "yon": "dikey" if h > w else "yatay" if w > h else "kare",
         "megapiksel": round(w * h / 1e6, 2), "sinif": cls, "keskinlik": round(sharpness(im), 1), "parlaklik": round(lum / 255, 2),
         "oneri": ADVICE[cls]}
    if h > w:
        d["oneri"] += "; dikey: yatay filmde blurlu zemin + çerçeveli kart, 9:16'da tam ekran"
    if lum / 255 < 0.25:
        d["uyari"] = "karanlık: önce pozlama/renk düzelt"
    return d, im


def inspect_video(path):
    fp = ffprobe()
    if not fp:
        return {"tur": "video", "dosya": path, "hata": "ffprobe yok"}, None
    r = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,channels",
                        "-of", "json", path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=NW, stdin=subprocess.DEVNULL)
    j = json.loads(r.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    fps = round(float(num) / float(den or 1), 2) if float(den or 1) else 0
    d = {"tur": "video", "dosya": path, "genislik": w, "yukseklik": h, "sure_sn": round(float(j.get("format", {}).get("duration") or 0), 2),
         "fps": fps, "ses": bool(a), "yon": "dikey" if h > w else "yatay" if w > h else "kare", "sinif": classify(max(w, h)), "kodek": v.get("codec_name")}
    d["oneri"] = ("9:16 için doğal; yatay filmde blurlu zemin/kırpma" if d["yon"] == "dikey" else
                  "yatay film için doğal; 9:16 için akıllı kırp (özneyi izle) ya da blurlu-zemin") + ("; konuşma varsa yazıya dök (yazi_cikar.py)" if a else "")
    thumb = None
    try:
        from PIL import Image
        import tempfile
        from shutil import which
        ff = which("ffmpeg")
        if ff:
            fd, tmp = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            subprocess.run([ff, "-v", "error", "-y", "-ss", str(min(1.0, d["sure_sn"] / 3)), "-i", path, "-frames:v", "1", tmp], capture_output=True, timeout=30, creationflags=NW, stdin=subprocess.DEVNULL)
            if os.path.getsize(tmp) > 0:
                thumb = Image.open(tmp).convert("RGB")
                thumb.load()
            os.remove(tmp)
    except Exception:
        pass
    return d, thumb


def contact_sheet(items, out_path, cols=6, tw=300, th=225):
    from PIL import Image, ImageDraw, ImageOps
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), "#111")
    dr = ImageDraw.Draw(sheet)
    for i, (d, im) in enumerate(items):
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        if im is not None:
            t = ImageOps.contain(im, (tw, th))
            sheet.paste(t, (x + (tw - t.width) // 2, y + 34 + (th - t.height) // 2))
        col = {"yuksek": "#9fe6a0", "orta": "#e6cc86", "dusuk": "#ff9d8a"}.get(d.get("sinif"), "#ffffff")
        dr.text((x + 4, y + 3), f"{i + 1}. {os.path.basename(d['dosya'])[:34]}", fill="#ffffff")
        dr.text((x + 4, y + 17), f"{d.get('genislik')}x{d.get('yukseklik')} {d.get('sinif')} {d['tur']}", fill=col)
    sheet.save(out_path, quality=88)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    files = collect(a.paths)
    if not files:
        sys.exit("medya bulunamadı")
    items = []
    for f in files:
        try:
            items.append(inspect_image(f) if f.lower().endswith(IMG) else inspect_video(f))
        except Exception as e:
            items.append(({"tur": "?", "dosya": f, "hata": f"{type(e).__name__}: {e}"}, None))
    data = [d for d, _ in items]
    cnt = {k: sum(1 for d in data if d.get("sinif") == k) for k in ("yuksek", "orta", "dusuk")}
    summary = {"toplam": len(data), "foto": sum(d.get("tur") == "foto" for d in data), "video": sum(d.get("tur") == "video" for d in data),
               "siniflar": cnt, "dikey": sum(d.get("yon") == "dikey" for d in data),
               "video_toplam_sn": round(sum(d.get("sure_sn", 0) for d in data if d.get("tur") == "video"), 1)}
    print(f"{summary['toplam']} dosya: {summary['foto']} foto, {summary['video']} video | kalite yüksek/orta/düşük: {cnt['yuksek']}/{cnt['orta']}/{cnt['dusuk']} | dikey: {summary['dikey']}")
    for i, d in enumerate(data, 1):
        print(f"{i:>3}. {os.path.basename(d['dosya'])[:40]:40} {d.get('genislik', '?')}x{d.get('yukseklik', '?')} {d.get('sinif', '?'):6} {d.get('yon', '?'):6} {d.get('oneri', d.get('hata', ''))[:70]}")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump({"ozet": summary, "dosyalar": data}, open(os.path.join(a.out, "envanter.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        contact_sheet(items, os.path.join(a.out, "envanter_kontak.jpg"))
        print(f"yazıldı: {os.path.join(a.out, 'envanter.json')}, envanter_kontak.jpg")


if __name__ == "__main__":
    main()
