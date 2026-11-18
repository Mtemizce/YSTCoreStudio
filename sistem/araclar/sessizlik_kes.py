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


NW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.exit(__doc__)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else os.path.splitext(inp)[0] + "_kesik.mp4"

    def arg(flag, default):
        return float(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
    noise, min_sil, pad = arg("--db", -30.0), arg("--min", 0.6), arg("--pad", 0.12)
    dur, sils, keeps = oner(inp, noise, min_sil, pad)
    kept = sum(e - s for s, e in keeps)
    print(f"{len(sils)} sessiz aralık, {len(keeps)} parça: {dur:.1f} sn → {kept:.1f} sn")
    if "--sadece-rapor" not in sys.argv and keeps:
        from pathlib import Path
        from kurgu_plan import REQUIRED
        if any((parent / REQUIRED).exists() for parent in Path(inp).resolve().parents):
            sys.exit("Panel projesinde önce montaj_olcum.py kesim-oner ile plan oluştur, onaydan sonra kesim-uygula kullan.")
        uygula(inp, out, keeps)


def oner(inp, noise=-30.0, min_sil=0.6, pad=0.12):
    ff, fp = ffmpeg("ffmpeg"), ffmpeg("ffprobe")
    dur = float(subprocess.check_output([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", inp], creationflags=NW, timeout=30).decode().strip())
    log = subprocess.run([ff, "-i", inp, "-af", f"silencedetect=noise={noise}dB:d={min_sil}", "-f", "null", "-"], stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=NW, timeout=3600, check=True).stderr
    sils, cur = [], None
    for line in log.splitlines():
        m = re.search(r"silence_start:\s*([-\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end:\s*([-\d.]+)", line)
        if m and cur is not None:
            sils.append((cur, float(m.group(1))))
            cur = None
    if cur is not None:
        sils.append((cur, dur))
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
    return dur, sils, keeps


def uygula(inp, out, keeps):
    ff = ffmpeg()
    fc = []
    for i, (s, e) in enumerate(keeps):
        fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keeps))) + f"concat=n={len(keeps)}:v=1:a=1[v][a]")
    fd, script = tempfile.mkstemp(suffix=".txt", prefix="kurgu-sil-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("".join(fc))
    try:
        head = [ff, "-nostdin", "-y", "-v", "error", "-i", inp]
        tail = ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "18", "-c:a", "aac", "-b:a", "192k", out]
        for option in ("-/filter_complex", "-filter_complex_script"):
            result = subprocess.run([*head, option, script, *tail], creationflags=NW, timeout=7200,
                                    capture_output=True, encoding="utf-8", errors="replace")
            if result.returncode == 0:
                return
            if option != "-/filter_complex" or "Unrecognized option" not in result.stderr:
                raise RuntimeError(result.stderr.strip()[-1200:] or f"FFmpeg: {result.returncode}")
    finally:
        os.remove(script)



if __name__ == "__main__":
    main()
