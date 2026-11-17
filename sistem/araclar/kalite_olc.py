#!/usr/bin/env python3
"""Teslim ölçümü: çözünürlük/fps/süre, ses seviyesi (LUFS, tepe), donmuş kare ve siyah kare, platform uygunluğu. Yalnızca ffmpeg.

  python kalite_olc.py <video.mp4> [--platform ana|tiktok|reels|shorts] [--json]

Ölçüt tablosu (varsayılanlar; kaynaklar için sosyal-surumler skill'i): ana 1920x1080 ~30 fps, -14±1 LUFS, tepe <= -1 dBTP;
dikey sürümler 1080x1920, 30 fps, -14±1 LUFS, tepe <= -1 dBTP, hedef süre 15-45 sn (Reels/TikTok 20-35 ideal).
Çıkış: konsol raporu + (varsa) kırmızı bayraklar. Dinleme/izleme YERİNE GEÇMEZ; yalnızca ölçülebilir şeyleri söyler.
"""
import argparse
import json
import re
import subprocess
from shutil import which

TARGETS = {
    "ana": {"w": 1920, "h": 1080, "dur": (10, 180)},
    "tiktok": {"w": 1080, "h": 1920, "dur": (8, 60)},
    "reels": {"w": 1080, "h": 1920, "dur": (8, 90)},
    "shorts": {"w": 1080, "h": 1920, "dur": (8, 60)},
}


def tool(n):
    p = which(n)
    if p:
        return p
    import media_tools
    return media_tools.find(n)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--platform", default="ana", choices=list(TARGETS))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ff, fp = tool("ffmpeg"), tool("ffprobe")
    j = json.loads(subprocess.run([fp, "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels",
                                   "-of", "json", a.video], capture_output=True, text=True).stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    au = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    num, _, den = v.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1)
    dur = float(j["format"]["duration"])
    r = {"dosya": a.video, "boyut": f'{v.get("width")}x{v.get("height")}', "fps": round(fps, 2), "sure_sn": round(dur, 2), "mb": round(int(j["format"].get("size", 0)) / 1e6, 1),
         "video_kodek": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"), "ses": au["codec_name"] if au else None}
    flags = []
    t = TARGETS[a.platform]
    if (v.get("width"), v.get("height")) != (t["w"], t["h"]):
        flags.append(f'çözünürlük {r["boyut"]} (beklenen {t["w"]}x{t["h"]})')
    if not t["dur"][0] <= dur <= t["dur"][1]:
        flags.append(f'süre {dur:.1f} sn (beklenen {t["dur"][0]}-{t["dur"][1]} sn)')
    if v.get("pix_fmt") != "yuv420p":
        flags.append(f'pix_fmt {v.get("pix_fmt")} (yuv420p değil: bazı platformlarda renk/oynatma sorunu)')
    if au:
        txt = subprocess.run([ff, "-hide_banner", "-nostats", "-i", a.video, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
        peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
        r["lufs"], r["tepe_db"] = (float(lufs[-1]) if lufs else None), (float(peak[-1]) if peak else None)
        if r["lufs"] is not None and abs(r["lufs"] + 14) > 1.5:
            flags.append(f'ses {r["lufs"]} LUFS (hedef -14±1)')
        if r["tepe_db"] is not None and r["tepe_db"] > -0.9:
            flags.append(f'ses tepesi {r["tepe_db"]} dB (<= -1 olmalı)')
    else:
        flags.append("ses akışı yok")
    fz = subprocess.run([ff, "-hide_banner", "-nostats", "-i", a.video, "-vf", "freezedetect=n=-60dB:d=1.2,blackdetect=d=0.3:pic_th=0.99:pix_th=0.03", "-an", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    freezes = re.findall(r"freeze_start: ([\d.]+)", fz)
    ends = re.findall(r"freeze_duration: ([\d.]+)", fz)
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", fz)
    r["donmus_kare"] = [{"baslangic": float(s), "sure": float(d)} for s, d in zip(freezes, ends)]
    r["siyah_kare"] = [{"baslangic": float(s), "bitis": float(e)} for s, e in blacks]
    if r["donmus_kare"]:
        flags.append(f'{len(r["donmus_kare"])} donmuş görüntü aralığı (>=1.2 sn hareketsiz): ' + ", ".join(f'{x["baslangic"]:.1f} sn' for x in r["donmus_kare"][:6]) + " (bilerek durağan başlık olabilir: kontrol et)")
    mid_black = [b for b in r["siyah_kare"] if 0.5 < b["baslangic"] < dur - 2.5]
    if mid_black:
        flags.append("ortada siyah kare: " + ", ".join(f'{b["baslangic"]:.1f} sn' for b in mid_black[:6]))
    r["bayraklar"] = flags
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    print(f'{r["dosya"]}\n  {r["boyut"]} {r["fps"]} fps {r["sure_sn"]} sn {r["mb"]} MB  {r["video_kodek"]}/{r["pix_fmt"]}  ses:{r["ses"]}  LUFS:{r.get("lufs")} tepe:{r.get("tepe_db")}')
    print("  " + ("TEMİZ (ölçülebilir kapılar geçti)" if not flags else "BAYRAKLAR:\n   - " + "\n   - ".join(flags)))


if __name__ == "__main__":
    main()
