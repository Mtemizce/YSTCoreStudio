"""Opt-in Wan 2.2 Pascal recipe (alexturkey, MIT). No model downloads on import/startup."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
from indirme import download, valid, unzip

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'sistem/ortam/yerel-video'
REPO = 'https://github.com/alexturkey/wan22-pascal-4gb'
TAG = 'v0.1.0'
NW = 0x08000000 if os.name == 'nt' else 0
LOCK = threading.Lock()
IS = {'var': False, 'bitti': False, 'hata': '', 'adim': '', 'yuzde': 0}
GEN = {'var': False, 'hata': '', 'proje': '', 'dosya': '', 'iptal': False}
PROC = None
THREAD = None
FILES = [
    ('Wan2.2-TI2V-5B-Q8_0.gguf', 'QuantStack/Wan2.2-TI2V-5B-GGUF', '57437632ddd08bdcbd1508c866aa22e126ed51d2', 'Wan2.2-TI2V-5B-Q8_0.gguf', 5400179040, '57bece983817ab2f957546683bb670f13be7d99022d45674840cd999a050ea8f'),
    ('Wan2.2_VAE.safetensors', 'QuantStack/Wan2.2-TI2V-5B-GGUF', '57437632ddd08bdcbd1508c866aa22e126ed51d2', 'VAE/Wan2.2_VAE.safetensors', 1409400960, 'e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156'),
    ('umt5-xxl-encoder-Q5_K_M.gguf', 'city96/umt5-xxl-encoder-gguf', 'b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7', 'umt5-xxl-encoder-Q5_K_M.gguf', 4145878880, 'eaea358bb438c5d211721a4feecc162000e3636e9cb96f51e216f1f44ebd12ce'),
]
PACKAGES = [
    ('wan22-pascal-4gb-v0.1.0-win-x64-cuda12.8-sm61.zip', 'e23d53eeab5fbe8945db50e927fa8dcdefe8664b85b1ef522c4bc71f94e7f112'),
    ('cudart-cuda12.8-win-x64.zip', 'a17da465766934bef0654f4e1a75ce7ad973ac18ab68f972dd111ccf74165377'),
]


def exe():
    return next((DIR / 'bin').rglob('sd-cli.exe'), None)


def script():
    return next((DIR / 'source').rglob('scripts/generate.py'), None)


def supported():
    if os.name != 'nt' or not shutil.which('nvidia-smi'):
        return False, 'Bu hazır paket Windows x64 ve NVIDIA CUDA 12.8 uyumlu sürücü gerektirir.'
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True, creationflags=NW, timeout=10)
        if max((int(v.strip()) for v in r.stdout.splitlines()), default=0) < 4000:
            return False, 'En az 4 GB NVIDIA VRAM gerekli.'
    except (OSError, ValueError, subprocess.SubprocessError):
        return False, 'NVIDIA sürücüsü okunamadı.'
    return True, 'Pascal için hazırlanmış CUDA 12.8 paketi; diğer GPU’larda uyumluluk üretim denemesiyle doğrulanmalıdır.'


def durum():
    # Polling checks receipts and file stats; a full hash is done by the installer, not every 1.5 seconds.
    complete = exe() and script() and (DIR / 'kurulum.json').is_file()
    complete = bool(complete and all((DIR / 'models' / n).is_file() and (DIR / 'models' / n).stat().st_size == size for n, _, _, _, size, _ in FILES))
    return {'kurulu': complete, 'is': dict(IS), 'uretim': dict(GEN), 'tahmini_indirme_gb': 12,
            'destek': 'Windows / NVIDIA, en az 4 GB VRAM, CUDA 12.8 sürücüsü; yaklaşık 12 GB disk ve 8 GB boş RAM.',
            'not': 'İsteğe bağlı. GTX 1050 Ti ölçümünde 2 sn video ~26 dk, 5 sn ~158 dk; bu bilgisayarın hızı farklı olabilir.'}


def _install():
    try:
        ok, reason = supported()
        if not ok:
            raise RuntimeError(reason)
        missing = sum(size for n, _, _, _, size, sha in FILES if not valid(DIR / 'models' / n, size, sha))
        if shutil.disk_usage(ROOT).free < missing + 2_000_000_000:
            raise RuntimeError(f'Kalan kurulum için en az {(missing + 2_000_000_000) / 1e9:.1f} GB boş disk gerekli.')
        jobs = [(REPO + '/releases/download/' + TAG + '/' + n, DIR / n, 0, sha) for n, sha in PACKAGES]
        jobs += [(f'https://huggingface.co/{repo}/resolve/{rev}/{path}', DIR / 'models' / n, size, sha) for n, repo, rev, path, size, sha in FILES]
        for i, (url, target, size, sha) in enumerate(jobs):
            IS['adim'] = target.name + ': bağlantı kuruluyor…'
            def progress(n, total):
                IS.update(adim=f'{target.name}: {n // 1000000}/{total // 1000000} MB', yuzde=int((i + n / total if total else i) * 90 / len(jobs)))
            download(url, target, size, sha, progress)
            if target.suffix == '.zip':
                unzip(target, DIR / 'bin')
        IS['adim'] = 'Üretim betiği ve lisanslar indiriliyor…'
        source = DIR / 'source.zip'
        download(REPO + '/archive/refs/tags/' + TAG + '.zip', source)
        unzip(source, DIR / 'source')
        if not exe() or not script():
            raise RuntimeError('Paketin çalıştırıcısı veya üretim betiği bulunamadı')
        for dll in (DIR / 'bin').rglob('*.dll'):
            if dll.parent != exe().parent:
                shutil.copy2(dll, exe().parent / dll.name)
        if not (Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/vcruntime140_1.dll').exists():
            r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'sistem/kurulum/on_kur.ps1'), '-Bilesen', 'vcredist'], capture_output=True, creationflags=NW, timeout=1800)
            if r.returncode:
                raise RuntimeError('Microsoft Visual C++ çalışma zamanı kurulamadı')
        (DIR / 'kurulum.json').write_text(json.dumps({'repo': REPO, 'tag': TAG, 'models': [f[0] for f in FILES]}), encoding='utf-8')
        IS.update(yuzde=100, adim='Dosyalar doğrulandı; üretime hazır')
    except Exception as e:
        IS['hata'] = str(e)
    finally:
        IS.update(var=False, bitti=True)


def kur():
    with LOCK:
        if IS['var'] or GEN['var']:
            raise ValueError('Video kurulumu veya üretimi sürüyor')
        IS.update(var=True, bitti=False, hata='', adim='Başlıyor', yuzde=0)
        threading.Thread(target=_install, daemon=True).start()
    return {'ok': True}


def _generate(proje, prompt, frames):
    global PROC
    try:
        # Every run has its own copy of the upstream recipe and output directory.
        work = DIR / 'jobs' / uuid.uuid4().hex
        shutil.copytree(script().parent.parent, work)
        existing = {p.resolve(): p.stat().st_mtime_ns for p in work.rglob('video.mp4')}
        py = ROOT / 'sistem/ortam/venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not py.exists():
            py = Path(sys.executable)
        cmd = [str(py), str(Path(__file__).resolve()), 'worker', str(work / 'scripts/generate.py'), '--models-dir', str(DIR / 'models'), '--sd-cli', str(exe()), '--prompt', prompt, '--frames', str(frames)]
        with (work / 'generation.log').open('w', encoding='utf-8') as log:
            with LOCK:
                if GEN['iptal']:
                    return
                PROC = subprocess.Popen(cmd, cwd=str(work), stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=NW)
            rc = PROC.wait()
        if GEN['iptal']:
            return
        if rc:
            raise RuntimeError((work / 'generation.log').read_text(encoding='utf-8', errors='replace')[-2000:])
        output = next((p for p in work.rglob('video.mp4') if existing.get(p.resolve()) != p.stat().st_mtime_ns), None)
        if not output or output.stat().st_size == 0:
            raise RuntimeError('MP4 üretilemedi. ffmpeg kurulumunu ve üretim günlüğünü kontrol edin.')
        target = ROOT / 'projeler' / proje / 'kaynak/video' / ('wan-' + work.name[:10] + '.mp4')
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(output, target)
        GEN['dosya'] = target.relative_to(ROOT / 'projeler' / proje).as_posix()
        (target.parent / (target.stem + '-ATIF.txt')).write_text('AI-generated video. Wan 2.2 TI2V-5B (Apache-2.0). Recipe/patches: alexturkey/wan22-pascal-4gb (MIT). Engine: stable-diffusion.cpp / ggml (MIT).\n' + REPO, encoding='utf-8')
    except Exception as e:
        if not GEN['iptal']:
            GEN['hata'] = str(e)
    finally:
        with LOCK:
            PROC = None; GEN['var'] = False


def baslat(proje, prompt, frames=49):
    global THREAD
    import orkestrator
    if proje == '_profil':
        raise ValueError('Video üretimi için bir proje seçin')
    orkestrator.project(proje)
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000 or int(frames) not in (17, 49, 121):
        raise ValueError('İstem gerekli; kare sayısı 17, 49 veya 121 olmalı')
    if not durum()['kurulu']:
        raise ValueError('Wan 2.2 kurulu değil; Ayarlar → Servisler’den indir')
    with LOCK:
        if IS['var'] or GEN['var']:
            raise ValueError('Video motoru şu anda meşgul')
        GEN.update(var=True, hata='', proje=proje, dosya='', iptal=False)
        THREAD = threading.Thread(target=_generate, args=(proje, prompt, int(frames)), daemon=True)
        THREAD.start()
    return {'ok': True}


if __name__ == '__main__' and sys.argv[1:2] == ['worker']:
    # Upstream Python recipe also launches sd-cli and ffmpeg. Hide those children too.
    import runpy
    if os.name == 'nt':
        original = subprocess.Popen
        class HiddenProcess(original):
            def __init__(self, *args, **kwargs):
                kwargs['creationflags'] = kwargs.get('creationflags', 0) | NW
                super().__init__(*args, **kwargs)
        subprocess.Popen = HiddenProcess
    sys.argv = sys.argv[2:]
    runpy.run_path(sys.argv[0], run_name='__main__')


def iptal(proje=None):
    with LOCK:
        if proje and GEN['proje'] != proje:
            return {'ok': True}
        GEN['iptal'] = True
        p = PROC
    if p and p.poll() is None:
        subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True, creationflags=NW, timeout=30)
        p.wait(timeout=30)
    if THREAD and THREAD.is_alive():
        THREAD.join(timeout=30)
        if THREAD.is_alive():
            raise RuntimeError('Video üretimi henüz durmadı; proje korunuyor')
    return {'ok': True}
