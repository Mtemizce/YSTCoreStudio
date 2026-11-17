#!/usr/bin/env python3
"""Sessizlik kesici (yalnızca ffmpeg): konuşma videosundaki ölü havayı keser, parçaları birleştirir (A/V senkron, tek re-encode).

  python sessizlik_kes.py <girdi.mp4> [cikti.mp4] [--db -30] [--min 0.6] [--pad 0.12] [--sadece-rapor]

Not: Hatalı alım/yeniden başlama (flub) kesimi AYRIDIR ve insan onaylıdır: `kaba-kurgu` skill'i. Önce flub'lar (ham zaman), sonra sessizlik.
Eşik (--db) kişinin sesine/mikrofonuna göre ayarlanır: çok düşük = cümle sonlarını yer, çok yüksek = ölü hava kalır.
Uyarlanmıştır: avenoxai/avenoxskills (MIT) remove-silence.py. Geçici dosya yolu platform bağımsız yapıldı.
"""
import os
import re
import subprocess
import sys
import tempfile


def ffmpeg(name="ffmpeg"):
    from shutil import which
    p = which(name)
    if p:
        return p
    import media_tools
    return media_tools.find(name)


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.exit(__doc__)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else os.path.splitext(inp)[0] + "_kesik.mp4"

    def arg(flag, default):
        return float(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
    noise, min_sil, pad = arg("--db", -30.0), arg("--min", 0.6), arg("--pad", 0.12)
    ff, fp = ffmpeg("ffmpeg"), ffmpeg("ffprobe")
    dur = float(subprocess.check_output([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", inp]).decode().strip())
    log = subprocess.run([ff, "-i", inp, "-af", f"silencedetect=noise={noise}dB:d={min_sil}", "-f", "null", "-"], stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace").stderr
    sils, cur = [], None
    for line in log.splitlines():
        m = re.search(r"silence_start:\s*([-\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end:\s*([-\d.]+)", line)
        if m and cur is not None:
            sils.append((cur, float(m.group(1))))
            cur = None
    keeps, pos = [], 0.0
    for s, e in sils:
        if s - pos > 0.05:
            keeps.append([max(0, pos - pad), min(dur, s + pad)])
        pos = e
    if dur - pos > 0.05:
        keeps.append([max(0, pos - pad), dur])
    merged = []
    for k in keeps:
        if merged and k[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], k[1])
        else:
            merged.append(k)
    keeps = [k for k in merged if k[1] - k[0] > 0.10]
    kept = sum(k[1] - k[0] for k in keeps)
    print(f"{len(sils)} sessiz aralık, {len(keeps)} parça: {dur:.1f} sn -> {kept:.1f} sn (%{100 * (1 - kept / dur):.0f} kesildi)")
    if "--sadece-rapor" in sys.argv or not keeps:
        return
    fc = []
    for i, (s, e) in enumerate(keeps):
        fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keeps))) + f"concat=n={len(keeps)}:v=1:a=1[v][a]")
    fd, script = tempfile.mkstemp(suffix=".txt", prefix="kurgu-sil-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("".join(fc))
    try:
        r = subprocess.run([ff, "-y", "-v", "error", "-i", inp, "-filter_complex_script", script, "-map", "[v]", "-map", "[a]",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", out])
    finally:
        os.remove(script)
    print(("bitti: " + out) if r.returncode == 0 else f"HATA: ffmpeg {r.returncode}")


if __name__ == "__main__":
    main()
