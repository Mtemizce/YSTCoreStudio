"""Resumable, size/hash checked downloads. Only verified files replace final targets."""
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.error
import zipfile


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def valid(path, size=0, digest=''):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0 or (size and path.stat().st_size != size):
        return False
    if not digest:
        return True
    receipt = path.with_suffix(path.suffix + '.verified.json')
    stat = path.stat()
    try:
        old = json.loads(receipt.read_text())
        if old == {'sha256': digest, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}:
            return True
    except (OSError, ValueError):
        pass
    if sha256(path) != digest:
        return False
    receipt.write_text(json.dumps({'sha256': digest, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}))
    return True


def download(url, path, size=0, digest='', progress=lambda n, total: None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if valid(path, size, digest):
        progress(path.stat().st_size, size or path.stat().st_size)
        return
    part = path.with_suffix(path.suffix + '.part')
    offset = part.stat().st_size if part.exists() else 0
    if size and offset >= size:
        if valid(part, size, digest):
            part.replace(path); valid(path, size, digest); return
        part.unlink(); offset = 0
    headers = {'User-Agent': 'YSTCoreStudio'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        resumed = offset and r.status == 206
        if resumed and not r.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
            raise RuntimeError('Sunucu geçersiz devam aralığı döndürdü')
        if not resumed:
            offset = 0
        expected = size or (int(r.headers.get('Content-Length', 0)) + offset)
        n = offset
        with part.open('ab' if resumed else 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b); n += len(b); progress(n, expected)
    if not n or (expected and n != expected):
        raise RuntimeError(f'İndirme eksik: {n}/{expected} bayt. Yeniden denediğinizde devam eder.')
    if digest and sha256(part) != digest:
        part.unlink(missing_ok=True)
        raise RuntimeError('SHA256 doğrulaması başarısız; dosya kullanılmadı')
    part.replace(path)
    valid(path, size, digest)


def unzip(archive, dest):
    dest = Path(dest).resolve()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target = (dest / item.filename).resolve()
            if dest not in target.parents or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Güvensiz arşiv yolu')
        z.extractall(dest)
