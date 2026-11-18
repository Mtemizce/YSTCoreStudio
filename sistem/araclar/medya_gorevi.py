"""Token-free specialist tasks for the active project's edit."""
import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from yerel_medya import uret
from medya_tercihi import KINDS, oku

ROLLER = {'image': 'gorsel-uretici', 'video': 'sahne-yapimcisi', 'music': 'ses-yonetmeni'}
DESCRIPTION = (
    'Delegate media production according to the active project settings to the project specialist without another LLM call. '
    'tur: image, video or music. istem: short task; sahne: storyboard row/heading identifier or empty '
    'for project overview; oran: 16:9, 9:16, 1:1, or empty (image only). '
    'The specialist uses project context and returns a verified file path. No automatic cloud fallback.'
)
SCENE = re.compile(r'^(?:#{1,6}\s+|\|\s*)')


def read_context(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return ''
    with path.open(encoding='utf-8-sig', errors='replace') as stream:
        return stream.read(64000)


def scene_excerpt(board, scene):
    rows = board.splitlines()
    target = scene.strip().casefold()
    for index, row in enumerate(rows):
        if not SCENE.match(row):
            continue
        is_table = row.startswith('|')
        label = row.strip('| ').split('|', 1)[0] if is_table else row.lstrip('# ').strip()
        label = label.strip().casefold()
        if label != target and not re.match(re.escape(target) + r'\s*[:–—-]', label):
            continue
        if is_table:
            return row.strip()[:600]
        block = [row]
        for following in rows[index + 1:]:
            if following.startswith('#'):
                break
            block.append(following)
        return '\n'.join(block).strip()[:600]
    raise ValueError('Sahne hikâye tahtasında bulunamadı. İlk sütundaki zaman aralığını veya başlığı kullan.')


def kurgu_ozeti(root, format):
    if format not in ('ana', 'reels', 'tiktok', 'shorts', 'story'):
        raise ValueError('Geçersiz kurgu biçimi.')
    try:
        edit = json.loads(read_context(root, f'{format}/project.json'))
    except ValueError:
        return ''
    if not isinstance(edit, dict):
        return ''
    parts = []
    if isinstance(edit.get('width'), int) and isinstance(edit.get('height'), int):
        parts.append(f"{edit['width']}×{edit['height']}")
    layers = edit.get('layers')
    if isinstance(layers, list):
        titles = [str(layer.get('name') or layer.get('label') or layer.get('type') or '')[:45]
                  for layer in layers[:8] if isinstance(layer, dict)]
        parts.extend(title for title in titles if title)
    return ', '.join(parts)[:220]


def api_uret(root, proje, tur, sid, istem, saniye, oran):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "baglayici"))
    from yetenek import cagir
    directory, extension = {"image": ("foto", ".png"), "video": ("video", ".mp4"),
                            "music": ("ses", ".mp3")}[tur]
    target_dir = (root / "kaynak" / directory).resolve()
    if not target_dir.is_relative_to(root / "kaynak"):
        raise ValueError("Çıktı klasörü proje dışında")
    target = target_dir / (uuid.uuid4().hex + extension)
    duration = saniye or (20 if tur == "music" else 5)
    result = cagir(KINDS[tur], {"istem": istem, "sure": duration, "sure_metin": str(duration),
                              "en_boy": oran or "16:9", "oran": oran or "16:9"},
                   target, tercih=sid, proje=proje, yedek=False)
    return Path(result["dosya"]).resolve().relative_to(root).as_posix()


def gorevlendir(proje, tur, istem, sahne='', oran='', saniye=None, format='ana'):
    from orkestrator import project

    if proje == '_profil' or tur not in ROLLER:
        raise ValueError('Aktif bir proje ve image, video veya music türü gerekli.')
    if not isinstance(istem, str) or not 1 <= len(istem.strip()) <= 1000:
        raise ValueError('Görev tarifi 1–1000 karakter olmalı.')
    if not isinstance(sahne, str) or len(sahne) > 140:
        raise ValueError('Sahne etiketi en fazla 140 karakter olmalı.')
    if oran and (tur != 'image' or oran not in ('16:9', '9:16', '1:1')):
        raise ValueError('Kadraj oranı yalnızca görsel için 16:9, 9:16 veya 1:1 olabilir.')

    root = project(proje).resolve()
    from kurgu_plan import kontrol
    kontrol(root)
    choice = oku(root, tur)
    if choice == "kaynak":
        raise ValueError("Bu proje bu medya türü için mevcut kaynakları seçti.")
    if choice == "kurgu":
        raise ValueError("Bu projede medya kurgu uzmanına bırakıldı. Remotion/HyperFrames veya mevcut ses araçlarını kullan.")
    board = read_context(root, 'hikaye_tahtasi.md')
    scene = scene_excerpt(board, sahne) if sahne.strip() else board[:450]
    if tur == 'music':
        context = [
            ('Sahne ve akış', scene),
            ('Ton ve tempo', read_context(root, 'ton_rehberi.md')[:260]),
            ('Ses planı', read_context(root, 'ses_plani.md')[:200]),
        ]
    else:
        context = [
            ('Sahne ve kadraj', scene),
            ('Görsel ton', read_context(root, 'ton_rehberi.md')[:260]),
            ('Marka kısıtları', read_context(root, 'marka_kullanimi.md')[:200]),
        ]
    series = read_context(root, 'seri_baglami.md')
    if series:
        intro = series.split('##', 1)[0].strip()
        models = read_context(root, 'seri_model_seti.md') if tur != 'music' else ''
        context.insert(0, ('Dizi ve bölüm', intro[:180]))
        if models:
            context.insert(2, ('Bölümün onaylı görsel tarifleri', models[:260]))
    context.append(('Kurgu', kurgu_ozeti(root, format)))
    if tur == 'image':
        try:
            image = json.loads(read_context(root, 'uretim.json')).get('gorsel_uret') or {}
        except ValueError:
            image = {}
        context.insert(0, ('Kullanıcının görsel tarifi', str(image.get('tarif') or '')[:240]))
    if not any(value.strip() for title, value in context if title != 'Kurgu'):
        context.append(('Proje özeti', read_context(root, 'brief.md')[:550]))
    detail = '\n'.join(f'{title}: {value.strip()}' for title, value in context if value.strip())
    brief = istem.strip()
    prompt = brief + ('\n' + detail[:1999 - len(brief)] if detail else '')
    if not oran and format != 'ana' and (tur == 'image' or (tur == 'video' and choice.startswith('api:'))):
        oran = '9:16'
    if choice.startswith("api:"):
        path = api_uret(root, proje, tur, choice[4:], prompt[:2000], saniye, oran)
    elif choice == "yerel":
        path = uret(proje, tur, prompt[:2000], saniye=saniye, oran=oran or None)
    else:
        raise ValueError("Geçersiz medya yöntemi")
    asset = (root / path).resolve()
    if not asset.is_relative_to(root / 'kaynak') or not asset.is_file() or asset.stat().st_size == 0:
        raise RuntimeError('Uzman görevi doğrulanabilir bir medya dosyası bırakmadı.')
    result = {'ajan': ROLLER[tur], 'dosya': path, 'sahne': sahne, 'yontem': choice, 'bayt': asset.stat().st_size}
    journal = root / 'medya_gorevleri.jsonl'
    if journal.resolve().is_relative_to(root):
        with journal.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('proje')
    parser.add_argument('tur', choices=ROLLER)
    parser.add_argument('istem')
    parser.add_argument('--sahne', default='')
    parser.add_argument('--oran', default='')
    parser.add_argument('--saniye', type=int)
    parser.add_argument('--format', default='ana')
    args = parser.parse_args()
    try:
        print(json.dumps(gorevlendir(**vars(args)), ensure_ascii=False))
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
