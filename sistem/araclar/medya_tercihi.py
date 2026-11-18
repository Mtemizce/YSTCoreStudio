"""Media choices shared by project setup and production."""
import json
from pathlib import Path

KINDS = {"image": "gorsel-uret", "video": "video-uret", "music": "muzik"}
ROOT = Path(__file__).resolve().parents[2]


def dogrula(secim, katalog):
    if not isinstance(secim, dict) or set(secim) - set(KINDS):
        raise ValueError("Geçersiz medya tercihleri")
    result = {}
    for kind, ability in KINDS.items():
        value = secim.get(kind, "kaynak")
        if value in ("kaynak", "kurgu", "yerel"):
            result[kind] = value
            continue
        if not isinstance(value, str) or not value.startswith("api:"):
            raise ValueError("Medya yöntemi geçersiz")
        provider = katalog.get(value[4:])
        offered = (provider or {}).get("tur", [])
        if ability not in offered and not (kind == "image" and "gorsel" in offered):
            raise ValueError(f"Seçilen sağlayıcı {ability} sunmuyor")
        result[kind] = value
    return result


def oku(project_dir, kind):
    # Earlier project files keep their original behavior.
    try:
        production = json.loads((project_dir / "uretim.json").read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return "yerel"
    options = production.get("medya")
    if isinstance(options, dict):
        return options.get(kind, "kaynak")
    legacy = production.get("gorsel_uret") or {}
    if kind == "image" and legacy.get("acik"):
        provider = legacy.get("saglayici")
        return "api:" + provider if provider and provider != "yerel-zimage" else "yerel"
    return "yerel"
