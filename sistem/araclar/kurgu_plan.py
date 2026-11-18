"""Storyboard review tied to the exact plan accepted in the panel."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from kurgu_stilleri import stiller

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = '.storyboard-gerekli'
APPROVAL = 'storyboard_onayi.json'
FILES = ('hikaye_tahtasi.md', 'senaryo.md', 'uretim.json', 'kesim_oneri.json')


def normalized(value):
    value = value.casefold().replace('ı', 'i')
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))


def oner(prompt, chosen='sade'):
    text = normalized(prompt)
    catalog = stiller()
    candidates = []

    def hits(terms):
        return sum(bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text)) for term in terms)

    for key, style in catalog.items():
        terms = {normalized(key), normalized(style['ad'])}
        words = {normalized(word) for word in style.get('kelimeler', [])}
        score = 10 * hits(terms) + hits(words)
        if score:
            candidates.append((score, key))
    result = [key for _, key in sorted(candidates, key=lambda item: -item[0]) if key != chosen][:3]
    return [{'id': key, **catalog[key]} for key in result]


def beceriler():
    root = ROOT / '.claude' / 'skills'
    ids = {file.parent.name for file in root.glob('*/SKILL.md')}
    manifest = ROOT / 'sistem' / 'kurulum' / 'dis_kaynaklar.json'
    paths = {f['hedef'] for f in json.loads(manifest.read_text(encoding='utf-8'))['skill_dosyalari']
             if f['hedef'].endswith('/SKILL.md')}
    return {name: {'yol': f'.claude/skills/{name}/SKILL.md', 'kurulu': name in ids}
            for name in sorted(ids | {path.split('/')[-2] for path in paths})}


def snapshot(root):
    collected = {}
    stamp = hashlib.sha256()
    for name in FILES:
        file = root / name
        if not file.is_file():
            continue
        if not file.resolve().is_relative_to(root.resolve()):
            raise ValueError('Plan dosyası proje dışında.')
        if file.stat().st_size > 512_000:
            raise ValueError('Plan dosyası izin verilen boyutu aşıyor.')
        raw = file.read_bytes()
        stamp.update(name.encode())
        stamp.update(hashlib.sha256(raw).digest())
        collected[name] = raw.decode('utf-8-sig')
    return stamp.hexdigest(), collected


def durum(root):
    digest, files = snapshot(root)
    try:
        saved = json.loads((root / APPROVAL).read_text(encoding='utf-8'))
        approved = isinstance(saved, dict) and saved.get('sha256') == digest
    except (OSError, ValueError):
        approved = False
    board = files.get('hikaye_tahtasi.md', '').strip()
    proposal = json.loads(files['kesim_oneri.json']) if 'kesim_oneri.json' in files else None
    return {'gerekli': (root / REQUIRED).exists(), 'onayli': bool(board and approved),
            'revizyon': digest, 'storyboard': board, 'kesim': proposal}


def onayla(root, revision):
    current = durum(root)
    if not current['storyboard']:
        raise ValueError('Onaylanacak storyboard henüz yok.')
    if current['revizyon'] != revision:
        raise ValueError('Plan değişti. Güncel storyboard’u incele ve tekrar onayla.')
    temp = root / 'storyboard_onayi.tmp'
    temp.write_text(json.dumps({'sha256': revision}), encoding='utf-8')
    temp.replace(root / APPROVAL)
    return current


def kontrol(root):
    if (root / REQUIRED).exists() and not durum(root)['onayli']:
        raise ValueError('Önce güncel storyboard’u panelden onayla.')
