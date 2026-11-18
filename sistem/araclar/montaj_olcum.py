"""Local draft checks and timing data."""
import argparse
import json
import math
import subprocess
from pathlib import Path

from sessizlik_kes import NW, ffmpeg, oner, uygula


def ff(args, **kwargs):
    return subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', *args], check=True,
                          creationflags=NW, timeout=900, **kwargs)


def ilk_kare(source, target):
    from PIL import Image, ImageStat

    if target.resolve() == source.resolve():
        raise ValueError('Çıktı, kaynak dosyayla aynı olamaz.')
    target.parent.mkdir(parents=True, exist_ok=True)
    ff(['-y', '-i', str(source), '-frames:v', '1', str(target)], capture_output=True)
    with Image.open(target) as frame:
        width, height = frame.size
        gray = frame.convert('L')
        gray.thumbnail((320, 320))
        pixels = gray.histogram()
        dark = sum(pixels[:17]) / (gray.width * gray.height)
        variance = ImageStat.Stat(gray).var[0]
    return {'dosya': str(target), 'genislik': width, 'yukseklik': height,
            'karanlik_orani': round(dark, 3), 'kontrast': round(variance, 1),
            'incelenmeli': dark > .95 or variance < 12}


def vuruslar(source):
    import numpy as np

    # Compute positive spectral flux of successive 40 ms PCM windows.
    rate, hop, window = 16000, 320, 640
    result = ff(['-i', str(source), '-vn', '-ac', '1', '-ar', str(rate), '-t', '900',
                 '-f', 's16le', '-'], capture_output=True)
    samples = np.frombuffer(result.stdout, dtype='<i2').astype(np.float32) / 32768
    if len(samples) < rate:
        return {'bpm_tahmin': None, 'vuruslar': [], 'sure_sn': len(samples) / rate}
    taper = np.hanning(window)
    previous = np.zeros(window // 2 + 1)
    flux = []
    for offset in range(0, len(samples) - window + 1, hop):
        spectrum = np.log1p(16 * np.abs(np.fft.rfft(samples[offset:offset + window] * taper)))
        flux.append(float(np.maximum(spectrum - previous, 0).sum()))
        previous = spectrum
    values = np.asarray(flux)
    maximum = float(values.max())
    peaks = []
    for i in range(1, len(values) - 1):
        threshold = max(maximum * .025, float(np.median(values[max(0, i - 15):i + 16])) * 2)
        if values[i] <= threshold or not (values[i] > values[i - 1] and values[i] >= values[i + 1]):
            continue
        if peaks and i - peaks[-1] < 9:
            if values[i] > values[peaks[-1]]:
                peaks[-1] = i
        else:
            peaks.append(i)
    intervals = np.diff(peaks) * hop / rate
    bpm = None
    intervals = intervals[(intervals >= .25) & (intervals <= 1.5)]
    if len(intervals) >= 4:
        median = float(np.median(intervals))
        if float(np.median(np.abs(intervals - median))) < median * .15:
            bpm = round(60 / median, 1)
    return {'bpm_tahmin': bpm, 'sure_sn': round(len(samples) / rate, 3), 'vuruslar': [
        {'sn': round((i * hop + window / 2) / rate, 3), 'guc': round(float(values[i] / maximum), 3)}
        for i in peaks
    ]}


def yeniden_zamanla(words, ranges):
    offset = 0.0
    result = []
    for start, end in ranges:
        for word in words:
            a, b = float(word['baslangic']), float(word['bitis'])
            midpoint = (a + b) / 2
            if start <= midpoint < end:
                result.append({**word, 'baslangic': round(offset + max(a, start) - start, 3),
                               'bitis': round(offset + min(end, b) - start, 3)})
        offset += end - start
    return {'zaman': 'kesilmis', 'sure': round(offset, 3), 'kelimeler': result}


def stamp(source):
    stat = source.stat()
    return [stat.st_size, stat.st_mtime_ns]


def kesim_oner(root, source):
    relative = source.resolve().relative_to(root).as_posix()
    duration, silences, ranges = oner(str(source))
    return {'kaynak': relative, 'kaynak_imzasi': stamp(source), 'sure': duration,
            'sessizlik': silences, 'korunan': ranges}


def kesim_uygula(root, target, transcript):
    # This editing operation requires the same proposal acknowledged in the panel.
    from kurgu_plan import durum
    if not durum(root)['onayli']:
        raise ValueError('Önce kesim önerisini içeren storyboard’u panelden onayla.')
    proposal = json.loads((root / 'kesim_oneri.json').read_text(encoding='utf-8'))
    source = (root / proposal['kaynak']).resolve()
    dest = target.resolve()
    if not source.is_relative_to(root) or not dest.is_relative_to(root / 'hazir'):
        raise ValueError('Çıktıyı proje içindeki hazir klasörüne yaz.')
    if dest.exists() or stamp(source) != proposal['kaynak_imzasi']:
        raise ValueError('Kaynak değişmiş veya çıktı zaten var.')
    ranges = proposal['korunan']
    duration = proposal['sure']
    if not ranges or any(not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration)
                         for a, b in ranges) or any(x[1] > y[0] for x, y in zip(ranges, ranges[1:])):
        raise ValueError('Kesim aralıkları geçersiz.')
    words = json.loads(transcript.read_text(encoding='utf-8'))['kelimeler']
    data = yeniden_zamanla(words, ranges)
    dest.parent.mkdir(parents=True, exist_ok=True)
    uygula(str(source), str(dest), ranges)
    dest.with_suffix('.kelimeler.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return {'dosya': str(dest), 'sure': data['sure'], 'kelime': len(data['kelimeler'])}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('islem', choices=['ilk-kare', 'vurus', 'kesim-oner', 'kesim-uygula'])
    cli.add_argument('girdi', type=Path)
    cli.add_argument('cikti', type=Path)
    cli.add_argument('--proje', type=Path)
    args = cli.parse_args()
    source = args.girdi.resolve()
    output = args.cikti.resolve()
    if args.islem == 'ilk-kare':
        result = ilk_kare(source, output)
    elif args.islem == 'kesim-uygula':
        if args.proje is None:
            cli.error('--proje gerekli')
        result = kesim_uygula(args.proje.resolve(), output, source)
    else:
        if args.islem == 'kesim-oner':
            if args.proje is None or output != args.proje.resolve() / 'kesim_oneri.json':
                cli.error('Kesim önerisi proje kökündeki kesim_oneri.json olmalı')
            result = kesim_oner(args.proje.resolve(), source)
        else:
            result = vuruslar(source)
        if output == source:
            cli.error("Çıktı, kaynak dosyayla aynı olamaz")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'dosya': str(output), 'islem': args.islem,
                      **({'incelenmeli': result['incelenmeli']} if 'incelenmeli' in result else {})},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
