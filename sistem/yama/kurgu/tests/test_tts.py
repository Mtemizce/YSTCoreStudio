"""tts.py (EMA Lightning, Turkish): settings, file naming, cache and the MCP `speak` tool. The model is replaced by a fake
`ema_lightning` module, so these run without torch or a download."""
import json
import os
import sys
import types
import wave

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tts  # noqa: E402


class FakeSpeech:
    def __init__(self, duration, sample_rate):
        self.duration, self.sample_rate = duration, sample_rate


class FakeEMA:
    instances = 0
    calls = []

    def __init__(self):
        FakeEMA.instances += 1
        self.fast = False

    def lightning(self):
        self.fast = True
        return self

    def say(self, text, path=None, speed=1.0, seed=None, sample_rate=48000):
        FakeEMA.calls.append({"text": text, "speed": speed, "seed": seed, "sample_rate": sample_rate, "fast": self.fast})
        dur = 0.5 + len(text) / 100.0
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(b"\x00\x00" * int(dur * sample_rate))
        return FakeSpeech(dur, sample_rate)


@pytest.fixture
def fake_ema(monkeypatch):
    mod = types.ModuleType("ema_lightning")
    mod.EMA = FakeEMA
    monkeypatch.setitem(sys.modules, "ema_lightning", mod)
    monkeypatch.setattr(tts, "_has", lambda m: m == "ema_lightning")
    monkeypatch.setattr(tts, "_MODEL", {})
    FakeEMA.instances, FakeEMA.calls = 0, []
    return mod


def test_availability_says_how_to_install(monkeypatch):
    monkeypatch.setattr(tts, "_has", lambda m: False)
    av = tts.availability()
    assert av["available"] is False and "pip install ema-lightning" in av["message"] and av["language"] == "tr"
    with pytest.raises(tts.TTSError, match="not installed"):
        tts.synthesize("/nonexistent", "Merhaba")


def test_settings_defaults_and_validation():
    text, speed, seed, sr = tts.check_settings("  Merhaba dünya  ")
    assert (text, speed, sr) == ("Merhaba dünya", 1.0, 48000)
    assert tts.check_settings("Merhaba dünya")[2] == seed            # the seed is a stable hash of the text
    assert tts.check_settings("Merhaba", seed=5)[2] == 5 and tts.check_settings("Merhaba", seed=0)[2] == 0
    for bad in ({"text": ""}, {"text": "x" * (tts.MAX_CHARS + 1)}, {"text": "a", "speed": 0.1}, {"text": "a", "speed": 4.5},
                {"text": "a", "speed": "fast"}, {"text": "a", "sample_rate": 44100}, {"text": "a", "seed": -1}, {"text": "a", "seed": "x"}):
        with pytest.raises(tts.TTSError):
            tts.check_settings(**bad)


def test_slug_folds_turkish_letters():
    assert tts.slug("Şişli'de Ağır Öğle Yemeği!") == "sisli-de-agir-ogle-yemegi"
    assert tts.slug("???") == "speech" and len(tts.slug("a" * 200)) <= 32


def test_synthesize_writes_wav_and_caches(tmp_path, fake_ema):
    r = tts.synthesize(str(tmp_path), "Merhaba, size nasıl yardımcı olabilirim?", speed=1.2, seed=7)
    assert r["path"].startswith("media/tts/merhaba-size") and r["path"].endswith(".wav") and not r["cached"]
    assert os.path.isfile(r["abs_path"]) and r["seed"] == 7 and r["speed"] == 1.2 and r["sample_rate"] == 48000
    with wave.open(r["abs_path"]) as w:
        assert abs(w.getnframes() / w.getframerate() - r["duration"]) < 0.01
    assert FakeEMA.calls[0]["speed"] == 1.2 and FakeEMA.calls[0]["seed"] == 7
    again = tts.synthesize(str(tmp_path), "Merhaba, size nasıl yardımcı olabilirim?", speed=1.2, seed=7)
    assert again["cached"] and again["path"] == r["path"] and len(FakeEMA.calls) == 1
    other = tts.synthesize(str(tmp_path), "Merhaba, size nasıl yardımcı olabilirim?", speed=1.2, seed=8)
    assert other["path"] != r["path"] and len(FakeEMA.calls) == 2
    assert FakeEMA.instances == 1                                    # weights are loaded once per process
    assert not [f for f in os.listdir(os.path.dirname(r["abs_path"])) if ".part" in f]


def test_lightning_fast_path_and_failures(tmp_path, fake_ema):
    tts.synthesize(str(tmp_path), "Hızlı deneme", lightning=True)
    assert FakeEMA.calls[-1]["fast"] is True

    def boom(self, *a, **k):
        raise RuntimeError("cuda out of memory")
    FakeEMA.say, saved = boom, FakeEMA.say
    try:
        with pytest.raises(tts.TTSError, match="synthesis failed: RuntimeError: cuda out of memory"):
            tts.synthesize(str(tmp_path), "Başka bir cümle")
    finally:
        FakeEMA.say = saved
    assert not [f for f in os.listdir(os.path.join(str(tmp_path), "media", "tts")) if ".part" in f]


def test_cli_prints_path(tmp_path, fake_ema, capsys):
    assert tts.main(["Merhaba", "--project", str(tmp_path), "--name", "giris", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["path"].startswith("media/tts/giris-") and out["duration"] > 0
    assert tts.main(["Merhaba", "--project", str(tmp_path), "--speed", "9"]) == 1


# ---------------------------------------------------------------- MCP tool, in process
def _project(tmp_path, duration=5):
    d = tmp_path / "proj"
    d.mkdir()
    (d / "project.json").write_text(json.dumps({"version": 2, "width": 1280, "height": 720, "fps": 30, "duration": duration, "layers": [
        {"id": "bg", "type": "color", "name": "bg", "start": 0, "end": duration, "color": "#000000"}]}), encoding="utf-8")
    return str(d)


def _ctx():
    return {"progress": lambda *a, **k: None, "cancel": __import__("threading").Event()}


def test_speak_tool_adds_audio_layer_and_grows_duration(tmp_path, fake_ema):
    import mcp_server as M
    d = _project(tmp_path, duration=1)
    out = M.tool_speak({"project_dir": d, "text": "Kurgu ile video yapmak çok kolay.", "start": 0.5, "volume_db": -2}, _ctx())[0]["text"]
    assert 'Added audio layer "vo_1"' in out and "Project duration extended" in out
    proj = json.load(open(os.path.join(d, "project.json"), encoding="utf-8"))
    lay = next(l for l in proj["layers"] if l["id"] == "vo_1")
    assert lay["type"] == "audio" and lay["group"] == "Voice" and lay["start"] == 0.5 and lay["volume_db"] == -2
    assert lay["src"].startswith("media/tts/") and os.path.isfile(os.path.join(d, lay["src"]))
    assert abs(lay["end"] - (0.5 + 0.5 + len("Kurgu ile video yapmak çok kolay.") / 100.0)) < 0.01
    assert proj["duration"] >= lay["end"]
    M.tool_speak({"project_dir": d, "text": "İkinci cümle.", "start": 4}, _ctx())
    ids = [l["id"] for l in json.load(open(os.path.join(d, "project.json"), encoding="utf-8"))["layers"]]
    assert "vo_2" in ids
    with pytest.raises(M.ToolError, match="already exists"):
        M.tool_speak({"project_dir": d, "text": "Yine", "start": 1, "id": "vo_1"}, _ctx())


def test_speak_tool_without_start_only_makes_the_file(tmp_path, fake_ema):
    import mcp_server as M
    d = _project(tmp_path)
    out = M.tool_speak({"project_dir": d, "text": "Sadece dosya"}, _ctx())[0]["text"]
    assert "Not on the timeline yet" in out
    assert [l["id"] for l in json.load(open(os.path.join(d, "project.json"), encoding="utf-8"))["layers"]] == ["bg"]
    with pytest.raises(M.ToolError):
        M.tool_speak({"project_dir": d, "text": "x", "start": -1}, _ctx())
    with pytest.raises(M.ToolError):
        M.tool_speak({"project_dir": d, "text": ""}, _ctx())
