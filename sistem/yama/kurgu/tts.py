#!/usr/bin/env python3
"""Kurgu local text-to-speech (Turkish) with EMA Lightning. Optional: nothing here is needed to edit or render.

    python3 tts.py "Merhaba dünya" [--project .] [--name intro] [--speed 1.0] [--seed 7] [--sample-rate 48000] [--lightning]

EMA Lightning (Apache-2.0, https://huggingface.co/canberkkkkkk/ema-lightning) is a ~34 MB Turkish-only, single-voice
flow-matching TTS. It runs on the machine (GPU if there is one, CPU otherwise); the two weight files (`ema.pt`, `decoder.pt`)
download once from Hugging Face on first use. Install it into the environment Kurgu runs in:
`pip install ema-lightning` (pipx: `pipx inject kurgu ema-lightning`; uv: `uv tool install --with ema-lightning ...`).

Result: a WAV in <project>/media/tts/ and its duration, so an `audio` layer can be placed on the timeline.
The seed defaults to a hash of the text, so the same text + settings always gives the same file (cached, no re-synthesis);
pass another `seed` to get a different take.
"""
import hashlib
import json
import os
import re
import sys
import threading
import unicodedata

import kurgu_paths

LANGUAGE = "tr"
SAMPLE_RATES = (48000, 24000, 16000, 8000)
DEFAULT_SAMPLE_RATE = 48000
SPEED_RANGE = (0.25, 4.0)
MAX_CHARS = 5000
OUT_SUBDIR = os.path.join("media", "tts")
HINT = "pip install ema-lightning   (pipx: pipx inject kurgu ema-lightning)"
_LOCK = threading.Lock()
_MODEL = {}                       # {"lightning": bool, "tts": EMA}: loaded once per process, the weights are the slow part


class TTSError(Exception):
    pass


def _has(mod):
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def availability():
    ok = _has("ema_lightning")
    d = {"available": ok, "model": "EMA Lightning", "language": LANGUAGE, "voices": 1, "sample_rates": list(SAMPLE_RATES),
         "default_sample_rate": DEFAULT_SAMPLE_RATE, "speed": list(SPEED_RANGE)}
    if not ok:
        d["hint"] = HINT
        d["message"] = "Text-to-speech is not installed (optional). Install EMA Lightning: " + HINT
    return d


# ---------------------------------------------------------------- settings
def check_settings(text, speed=None, seed=None, sample_rate=None):
    """-> (text, speed, seed, sample_rate) validated, with defaults. The seed defaults to a hash of the text (a stable take)."""
    text = unicodedata.normalize("NFC", str(text or "")).strip()
    if not text:
        raise TTSError("text is empty")
    if len(text) > MAX_CHARS:
        raise TTSError(f"text is {len(text)} characters; the limit is {MAX_CHARS}. Split it and call again per paragraph.")
    try:
        speed = 1.0 if speed in (None, "") else float(speed)
    except (TypeError, ValueError):
        raise TTSError(f"speed must be a number between {SPEED_RANGE[0]} and {SPEED_RANGE[1]}")
    if not SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
        raise TTSError(f"speed {speed:g} is out of range; use {SPEED_RANGE[0]} to {SPEED_RANGE[1]} (1 = normal)")
    sample_rate = DEFAULT_SAMPLE_RATE if sample_rate in (None, "") else int(sample_rate)
    if sample_rate not in SAMPLE_RATES:
        raise TTSError(f"sample_rate must be one of {', '.join(map(str, SAMPLE_RATES))}")
    if seed in (None, ""):
        seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
    else:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            raise TTSError("seed must be a non-negative integer")
        if seed < 0:
            raise TTSError("seed must be a non-negative integer")
    return text, round(speed, 3), seed, sample_rate


def slug(s, limit=32):
    """ASCII file-name stem (Turkish letters folded: ş->s, ı->i ...)."""
    s = str(s or "").translate(str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:limit].strip("-")
    return s or "speech"


def out_path(project_dir, text, speed, seed, sample_rate, name=None):
    key = hashlib.sha1(f"{text}|{speed}|{seed}|{sample_rate}".encode("utf-8")).hexdigest()[:8]
    return os.path.join(project_dir, OUT_SUBDIR, f"{slug(name or text)}-{key}.wav")


# ---------------------------------------------------------------- model
def _load(lightning):
    """The EMA model, loaded once. `lightning` = the optional NVIDIA fast path (`EMA().lightning()`)."""
    if _MODEL.get("tts") is None:
        try:
            from ema_lightning import EMA
        except ImportError:
            raise TTSError(availability()["message"])
        try:
            _MODEL["tts"] = EMA()
        except Exception as e:
            raise TTSError(f"could not load EMA Lightning: {e}. The first run needs an internet connection (weights download once).")
        _MODEL["lightning"] = False
    if lightning and not _MODEL["lightning"]:
        try:
            _MODEL["tts"] = _MODEL["tts"].lightning() or _MODEL["tts"]       # in place or returned: both forms work
            _MODEL["lightning"] = True
        except Exception as e:
            raise TTSError(f"lightning fast path failed ({type(e).__name__}: {e}); retry with lightning=false (CPU, or no NVIDIA GPU)")
    return _MODEL["tts"]


def synthesize(project_dir, text, name=None, speed=None, seed=None, sample_rate=None, lightning=False, use_cache=True, progress=None):
    """Speak `text` into <project>/media/tts/<name>-<hash>.wav. Blocks. -> {path (project-relative, forward slashes), abs_path,
    duration, sample_rate, seed, speed, chars, cached}. Raises TTSError."""
    progress = progress or (lambda stage, frac, message: None)
    if not availability()["available"]:
        raise TTSError(availability()["message"])
    text, speed, seed, sample_rate = check_settings(text, speed, seed, sample_rate)
    dest = out_path(project_dir, text, speed, seed, sample_rate, name)
    rel = os.path.relpath(dest, project_dir).replace(os.sep, "/")
    meta = dest[:-4] + ".json"
    if use_cache and os.path.isfile(dest) and os.path.isfile(meta):
        try:
            with open(meta, encoding="utf-8") as f:
                m = json.load(f)
            progress("done", 1.0, "From cache")
            return {**m, "path": rel, "abs_path": dest, "cached": True}
        except (OSError, ValueError):
            pass
    with _LOCK:
        progress("loading", 0.1, "Loading EMA Lightning (weights download once on first use)")
        tts = _load(bool(lightning))
        progress("speaking", 0.5, "Speaking")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        part = kurgu_paths.tmp_path(dest, ".part.wav")
        try:
            speech = tts.say(text, path=part, speed=speed, seed=seed, sample_rate=sample_rate)
            if not os.path.isfile(part) or os.path.getsize(part) < 100:
                raise TTSError("EMA Lightning produced no audio")
            os.replace(part, dest)
        except TTSError:
            raise
        except Exception as e:
            raise TTSError(f"synthesis failed: {type(e).__name__}: {e}")
        finally:
            if os.path.exists(part):
                os.remove(part)
    res = {"duration": round(float(speech.duration), 3), "sample_rate": int(speech.sample_rate), "seed": seed, "speed": speed,
           "chars": len(text)}
    with open(meta, "w", encoding="utf-8") as f:
        json.dump({**res, "text": text}, f, ensure_ascii=False)
    progress("done", 1.0, "Done")
    return {**res, "path": rel, "abs_path": dest, "cached": False}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("text", help="Turkish text to speak")
    ap.add_argument("--project", default=".", help="project folder; the WAV lands in <project>/media/tts/")
    ap.add_argument("--name", help="file name stem (default: from the text)")
    ap.add_argument("--speed", type=float, help=f"{SPEED_RANGE[0]}-{SPEED_RANGE[1]}, default 1")
    ap.add_argument("--seed", type=int, help="another seed = another take (default: stable per text)")
    ap.add_argument("--sample-rate", type=int, choices=SAMPLE_RATES)
    ap.add_argument("--lightning", action="store_true", help="NVIDIA fast path (EMA().lightning())")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = synthesize(os.path.abspath(a.project), a.text, a.name, a.speed, a.seed, a.sample_rate, a.lightning,
                       progress=lambda s, f, m: print(f"{s} {f:.2f} {m}", file=sys.stderr))
    except TTSError as e:
        print("ERROR " + str(e), file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else f'{r["path"]}  ({r["duration"]:.2f} s, {r["sample_rate"]} Hz, seed {r["seed"]})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
