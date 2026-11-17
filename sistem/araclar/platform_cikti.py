#!/usr/bin/env python3
"""Bir videoyu platform teslimine çevirir (TikTok / Instagram Reels / YouTube Shorts / YouTube ana): yalnızca ffmpeg, yerel.

  python platform_cikti.py <girdi.mp4> --platform reels|tiktok|shorts|youtube -o <cikti.mp4>
        [--mod blur|kirp|kopya] [--x 0.5] [--altyazi transkript.json] [--altyazi-y 0.62] [--kelime-sayisi 3]
        [--kes BAS:BIT] [--kapak 1.5] [--ses-oldugu-gibi]

--mod blur   yatay görüntü bulanık zeminin üstünde tam genişlik (hiçbir şey kesilmez)  [yatay kaynak varsayılanı]
--mod kirp   merkez/`--x` konumundan 9:16 kırpma, kaynak çözünürlüğü düşükse yumuşar (uyarı verilir)
--mod kopya  kaynak zaten dikeyse yalnızca ölçekle/kodla
--kes 3.2:28 yalnızca bu aralığı al (saniye)
--altyazi    yazi_cikar.py JSON'u; aktif kelime altın, diğerleri sıcak beyaz (ASS, libass), güvenli alanda
Ses: -14 LUFS (loudnorm), H.264 yüksek profil yuv420p, 30 fps, AAC 192k/48 kHz, +faststart. Kapak: <cikti>_kapak.jpg
Platform kuralları ve doğrulama durumu: .claude/skills/sosyal-surumler/SKILL.md (bazı sayılar kaynaklarda çelişkilidir).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "kit", "fonts")
PLATFORMS = {
    "tiktok": {"w": 1080, "h": 1920, "fps": 30},
    "reels": {"w": 1080, "h": 1920, "fps": 30},
    "shorts": {"w": 1080, "h": 1920, "fps": 30},
    "youtube": {"w": 1920, "h": 1080, "fps": 30},
}
GOLD, PAPER = "&H004DA2C9", "&H00E6EFF4"           # ASS renkleri BGR: #C9A24D altın, #F4EFE6 sıcak beyaz


def tool(n):
    p = shutil.which(n)
    if p:
        return p
    import media_tools
    return media_tools.find(n)


def ass_time(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_ass(words, w, h, y_frac, per, offset=0.0, end_limit=None):
    """Kelime-vurgulu ASS: her kelime için bir olay; satır parçası `per` kelime; aktif kelime altın."""
    size = int(w * 0.078)
    margin_v = int(h - h * y_frac)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: K,Inter SemiBold,{size},{PAPER},{PAPER},&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,{max(3, size // 14)},{max(2, size // 22)},2,{int(w * 0.11)},{int(w * 0.18)},{margin_v},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = []
    ws = [x for x in words if x["bitis"] > offset and (end_limit is None or x["baslangic"] < end_limit)]
    for i in range(0, len(ws), per):
        chunk = ws[i:i + per]
        following = ws[i + per]["baslangic"] - offset if i + per < len(ws) else None     # sonraki satır başlayınca bu satır BİTER (üst üste binme olmaz)
        for j, cur in enumerate(chunk):
            start = max(0.0, cur["baslangic"] - offset)
            if j + 1 < len(chunk):
                nxt = chunk[j + 1]["baslangic"] - offset
            else:
                nxt = cur["bitis"] - offset + 0.25
                if following is not None:
                    nxt = min(nxt, following)
            parts = []
            for k, wd in enumerate(chunk):
                txt = wd["kelime"].upper().replace("İ", "İ") if False else wd["kelime"]
                parts.append(("{\\c" + (GOLD if k == j else PAPER) + "&}") + txt)
            ev.append(f"Dialogue: 0,{ass_time(start)},{ass_time(max(start + 0.05, nxt))},K,,0,0,0,,{{\\fad(60,0)}}" + " ".join(parts))
    return head + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("girdi")
    ap.add_argument("--platform", required=True, choices=list(PLATFORMS))
    ap.add_argument("-o", "--cikti", required=True)
    ap.add_argument("--mod", choices=["blur", "kirp", "kopya"])
    ap.add_argument("--x", type=float, default=0.5)
    ap.add_argument("--altyazi")
    ap.add_argument("--altyazi-y", type=float, default=0.62)
    ap.add_argument("--kelime-sayisi", type=int, default=3)
    ap.add_argument("--kes")
    ap.add_argument("--kapak", type=float)
    ap.add_argument("--ses-oldugu-gibi", action="store_true")
    a = ap.parse_args()
    ff, fp = tool("ffmpeg"), tool("ffprobe")
    P = PLATFORMS[a.platform]
    W, H = P["w"], P["h"]
    j = json.loads(subprocess.run([fp, "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", a.girdi], capture_output=True, text=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    sw, sh = v["width"], v["height"]
    has_audio = any(s["codec_type"] == "audio" for s in j["streams"])
    mod = a.mod or ("kopya" if (sh > sw) == (H > W) else "blur" if H > W else "kopya")
    if H > W and sw >= sh and mod == "kirp":
        crop_w = sh * 9 / 16
        if sh < 1920:
            print(f"uyarı: kırpma kaynağı {sw}x{sh}; 9:16 kırpıntı genişliği {crop_w:.0f}px -> {W}px'e büyür (x{W / crop_w:.2f}), yumuşak olabilir", file=sys.stderr)
    t0 = t1 = None
    if a.kes:
        s, _, e = a.kes.partition(":")
        t0, t1 = float(s), float(e)
    tmp = tempfile.mkdtemp(prefix="kurgu-plat-")
    try:
        vf = []
        if mod == "blur":
            vf.append(f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.12:saturation=0.9[b];"
                      f"[fg]scale={W}:-2[f];[b][f]overlay=(W-w)/2:(H-h)/2")
        elif mod == "kirp":
            vf.append(f"crop='min(iw,ih*{W}/{H})':ih:'(iw-min(iw,ih*{W}/{H}))*{a.x}':0,scale={W}:{H}:flags=lanczos")
        else:
            vf.append(f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0e1013")
        vf.append(f"fps={P['fps']},format=yuv420p")
        chain = ",".join(vf) if mod != "blur" else vf[0] + "," + vf[1]
        if a.altyazi:
            tr = json.load(open(a.altyazi, encoding="utf-8"))
            ass = build_ass(tr["kelimeler"], W, H, a.altyazi_y, a.kelime_sayisi, offset=t0 or 0.0, end_limit=t1)
            open(os.path.join(tmp, "alt.ass"), "w", encoding="utf-8").write(ass)
            os.makedirs(os.path.join(tmp, "f"), exist_ok=True)
            for f in ("Inter-SemiBold.ttf", "Inter-Medium.ttf"):
                if os.path.isfile(os.path.join(FONTS, f)):
                    shutil.copy(os.path.join(FONTS, f), os.path.join(tmp, "f", f))
            chain += ",ass=alt.ass:fontsdir=f"
        cmd = [ff, "-v", "error", "-y"]
        if t0 is not None:
            cmd += ["-ss", f"{t0}", "-to", f"{t1}"]
        cmd += ["-i", os.path.abspath(a.girdi), "-vf", chain, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-movflags", "+faststart"]
        if has_audio:
            af = "loudnorm=I=-14:TP=-1.5:LRA=11" if not a.ses_oldugu_gibi else "anull"
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            cmd += ["-an"]
        out = os.path.abspath(a.cikti)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cmd += [out]
        r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            sys.exit("ffmpeg hata: " + "\n".join(r.stderr.strip().splitlines()[-6:]))
        if a.kapak is not None:
            cov = os.path.splitext(out)[0] + "_kapak.jpg"
            subprocess.run([ff, "-v", "error", "-y", "-ss", f"{a.kapak}", "-i", out, "-frames:v", "1", "-q:v", "2", cov], capture_output=True)
            print("kapak:", cov)
        print(f"tamam: {out}  ({a.platform}, mod={mod}{', altyazı' if a.altyazi else ''})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
