#!/usr/bin/env python3
"""Yerel konuşma→yazı (faster-whisper), KELİME zamanlı. Altyazı ve konuşmaya dayalı kaba kurgu için.

  python yazi_cikar.py <video|ses> -o transkript.json [--dil tr] [--model small] [--srt]

Çıktı JSON: {dil, sure, model, cihaz, kelimeler:[{baslangic,bitis,kelime}], cumleler:[{baslangic,bitis,metin}]}  (saniye, KAYNAK dosya zamanı)
Model ağırlığı ilk kullanımda Hugging Face'ten bir kez iner (yalnızca dosya); ses dosyanız hiçbir yere gönderilmez.
Modeller: tiny, base, small (varsayılan; Türkçe için iyi denge), medium, large-v3-turbo (en iyi, yavaş/çok VRAM).
Cihaz: CUDA kullanılabilirse GPU (float16), değilse CPU (int8). Türkçe özel adlar (Örnekoğlu…) hatalı yazılabilir: `--duzeltme duzeltme.json`
({"yanlis": "doğru"}) ile bul-değiştir uygulanır.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def ffmpeg():
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    import media_tools
    return media_tools.ffmpeg()


def to_wav(src):
    fd, wav = tempfile.mkstemp(suffix=".wav", prefix="kurgu-stt-")
    os.close(fd)
    r = subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], capture_output=True, text=True)
    if r.returncode != 0 or os.path.getsize(wav) < 2000:
        os.remove(wav)
        sys.exit("ses okunamadı: " + (r.stderr.strip().splitlines() or ["ffmpeg hata"])[-1])
    return wav


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("girdi")
    ap.add_argument("-o", "--cikti", required=True)
    ap.add_argument("--dil", default="tr")
    ap.add_argument("--model", default="small")
    ap.add_argument("--srt", action="store_true")
    ap.add_argument("--duzeltme", help="JSON: {yanlış: doğru} bul-değiştir")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    device, ctype = "cpu", "int8"
    if not a.cpu:
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                device, ctype = "cuda", "float16"
        except Exception:
            pass
    fix = json.load(open(a.duzeltme, encoding="utf-8")) if a.duzeltme else {}

    def apply_fix(s):
        for k, v in fix.items():
            s = s.replace(k, v)
        return s
    wav = to_wav(a.girdi)
    import wave
    import numpy as np
    with wave.open(wav) as w:                                           # PyAV'e dosya yolu vermeyiz (sürüm uyuşmazlığı): diziyi biz veririz
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768.0
    try:
        try:
            model = WhisperModel(a.model, device=device, compute_type=ctype)
            segs, info = model.transcribe(audio, language=None if a.dil == "auto" else a.dil, word_timestamps=True, condition_on_previous_text=False, vad_filter=True)
            segs = list(segs)                                           # CUDA hatası burada patlar
        except Exception as e:
            if device == "cuda":
                print(f"uyarı: GPU çalışmadı ({type(e).__name__}); CPU int8'e geçiliyor", file=sys.stderr)
                device, ctype = "cpu", "int8"
                model = WhisperModel(a.model, device=device, compute_type=ctype)
                segs, info = model.transcribe(audio, language=None if a.dil == "auto" else a.dil, word_timestamps=True, condition_on_previous_text=False, vad_filter=True)
                segs = list(segs)
            else:
                raise
    finally:
        os.remove(wav)
    words, sents = [], []
    for s in segs:
        sents.append({"baslangic": round(s.start, 3), "bitis": round(s.end, 3), "metin": apply_fix(s.text.strip())})
        for w in (s.words or []):
            if w.word.strip():
                words.append({"baslangic": round(w.start, 3), "bitis": round(w.end, 3), "kelime": apply_fix(w.word.strip())})
    out = {"dil": info.language, "sure": round(info.duration, 2), "model": a.model, "cihaz": device, "kelimeler": words, "cumleler": sents}
    os.makedirs(os.path.dirname(os.path.abspath(a.cikti)), exist_ok=True)
    json.dump(out, open(a.cikti, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.srt:
        with open(os.path.splitext(a.cikti)[0] + ".srt", "w", encoding="utf-8") as f:
            for i, s in enumerate(sents, 1):
                f.write(f"{i}\n{srt_time(s['baslangic'])} --> {srt_time(s['bitis'])}\n{s['metin']}\n\n")
    print(f"{len(words)} kelime, {len(sents)} cümle, {out['sure']} sn, dil {info.language}, {device} ({a.model}) -> {a.cikti}")


if __name__ == "__main__":
    main()
