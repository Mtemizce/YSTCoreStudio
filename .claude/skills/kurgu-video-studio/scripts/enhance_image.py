#!/usr/bin/env python3
"""Düşük çözünürlüklü / bulanık / JPEG artefaktlı fotoğrafları video için iyileştirir (Real-ESRGAN, yerelde, GPU).

    python enhance_image.py girdi.jpg [-o cikti.png] [--scale 2] [--max-side 3840] [--grain 0.012] [--tile 256]
    python enhance_image.py klasor/ -o cikti_klasoru/            # klasördeki tüm görseller

Ne yapar: Real-ESRGAN x4plus ile 4x büyütür (karo karo, 6 GB VRAM yeter), sonra Lanczos ile hedef `--scale` katına
indirir (4x -> 2x: artefaktlar küçülür, keskinlik kalır), isteğe bağlı çok hafif film greni ekler (yapay "plastik" düzlükleri
gizler, video sıkıştırmasında detay hissi verir).

Güvenlik: ağırlıklar .safetensors biçimindedir (pickle yok), yalnızca aşağıdaki sabit HTTPS adresinden iner, boyutu doğrulanır.
Gerekenler: pip install spandrel safetensors pillow numpy torch   (torch: CUDA'lı sürüm; yoksa CPU'da yavaş çalışır)
Yüzler: x4plus yüzleri hafifçe bozabilir; yüz yakın planlarında önce/sonrayı karşılaştır (bkz. references/image-enhancement.md).
"""
import argparse
import hashlib
import os
import sys
import urllib.request

MODELS = {
    # ad: (url, dosya, beklenen boyut)  - kaynak: Comfy-Org/Real-ESRGAN_repackaged (xinntao/Real-ESRGAN, BSD-3-Clause)
    "realesrgan-x4plus": (
        "https://huggingface.co/Comfy-Org/Real-ESRGAN_repackaged/resolve/main/RealESRGAN_x4plus.safetensors",
        "RealESRGAN_x4plus.safetensors", 66857836),
}
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")


def models_dir():
    base = os.environ.get("KURGU_MODELS") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache"), "Kurgu", "models")
    os.makedirs(base, exist_ok=True)
    return base


def fetch(name):
    url, fname, size = MODELS[name]
    path = os.path.join(models_dir(), fname)
    if os.path.isfile(path) and os.path.getsize(path) == size:
        return path
    print(f"model indiriliyor (bir kez, {size / 1e6:.0f} MB): {url}", file=sys.stderr)
    tmp = path + ".part"
    urllib.request.urlretrieve(url, tmp)
    if os.path.getsize(tmp) != size:
        os.remove(tmp)
        raise SystemExit(f"indirilen dosya beklenen boyutta değil ({size} bayt); iptal edildi")
    os.replace(tmp, path)
    return path


def load_model(name, device):
    import torch
    from safetensors.torch import load_file
    from spandrel import ImageModelDescriptor, ModelLoader
    sd = load_file(fetch(name))
    model = ModelLoader().load_from_state_dict(sd)
    assert isinstance(model, ImageModelDescriptor)
    model = model.to(device).eval()
    if device == "cuda":
        model = model.half()
    return model


def upscale_tiled(model, arr, device, tile=256, pad=16):
    """arr: HxWx3 float32 0..1 -> (H*s)x(W*s)x3 float32. Karolar arası bindirme `pad` px, dikiş görünmez."""
    import torch
    s = model.scale
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    H, W = arr.shape[:2]
    out = torch.zeros((1, 3, H * s, W * s), dtype=torch.float32)
    dtype = torch.float16 if device == "cuda" else torch.float32
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            y0, y1, x0, x1 = max(y - pad, 0), min(y + tile + pad, H), max(x - pad, 0), min(x + tile + pad, W)
            patch = t[:, :, y0:y1, x0:x1].to(device=device, dtype=dtype)
            with torch.no_grad():
                o = model(patch).float().cpu()
            h, w = min(tile, H - y), min(tile, W - x)
            oy, ox = (y - y0) * s, (x - x0) * s
            out[:, :, y * s:(y + h) * s, x * s:(x + w) * s] = o[:, :, oy:oy + h * s, ox:ox + w * s]
    return out.squeeze(0).permute(1, 2, 0).clamp(0, 1).numpy()


def enhance(path, out, model, device, scale, max_side, grain, tile):
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    big = upscale_tiled(model, np.asarray(im, dtype=np.float32) / 255.0, device, tile=tile)
    res = Image.fromarray((big * 255 + 0.5).astype("uint8"))
    tw, th = round(w * scale), round(h * scale)
    k = min(1.0, max_side / max(tw, th))
    tw, th = max(1, round(tw * k)), max(1, round(th * k))
    if (tw, th) != res.size:
        res = res.resize((tw, th), Image.LANCZOS)
    if scale < 4:                                              # 4x'ten küçültünce hafif keskinlik geri ver
        res = res.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=2))
    if grain > 0:
        a = np.asarray(res, dtype=np.float32)
        rng = np.random.default_rng(7)                         # sabit tohum: aynı girdi = aynı sonuç
        n = rng.normal(0.0, grain * 255, a.shape[:2]).astype(np.float32)[..., None]
        res = Image.fromarray(np.clip(a + n, 0, 255).astype("uint8"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if out.lower().endswith((".jpg", ".jpeg")):
        res.save(out, quality=95, subsampling=0)
    else:
        res.save(out)
    return (w, h), res.size


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--model", default="realesrgan-x4plus", choices=list(MODELS))
    ap.add_argument("--scale", type=float, default=2.0, help="girdiye göre hedef katsayı (1-4, varsayılan 2)")
    ap.add_argument("--max-side", type=int, default=3840, help="uzun kenar üst sınırı (px)")
    ap.add_argument("--grain", type=float, default=0.012, help="film greni gücü 0-0.05 (0 = yok)")
    ap.add_argument("--tile", type=int, default=256, help="karo boyutu; bellek hatasında 128 dene")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    import torch
    device = "cpu" if a.cpu or not torch.cuda.is_available() else "cuda"
    if device == "cpu":
        print("uyarı: CUDA yok, CPU'da çalışıyor (yavaş)", file=sys.stderr)
    model = load_model(a.model, device)
    files = [a.input] if os.path.isfile(a.input) else [os.path.join(a.input, f) for f in sorted(os.listdir(a.input)) if f.lower().endswith(EXTS)]
    for f in files:
        if os.path.isdir(a.input):
            out = os.path.join(a.output or a.input.rstrip("/\\") + "_iyilestirilmis", os.path.splitext(os.path.basename(f))[0] + ".png")
        else:
            out = a.output or os.path.splitext(f)[0] + "_iyi.png"
        src_size, dst_size = enhance(f, out, model, device, a.scale, a.max_side, a.grain, a.tile)
        print(f"{os.path.basename(f)}: {src_size[0]}x{src_size[1]} -> {dst_size[0]}x{dst_size[1]}  {out}")


if __name__ == "__main__":
    main()
