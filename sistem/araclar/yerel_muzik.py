"""Optional ACE-Step runtime. The panel must explicitly request installation."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading

from indirme import download, unzip
from medya_kilit import uretim_kilidi

DIR = Path(__file__).resolve().parents[1] / 'ortam/yerel-muzik'
REPO = 'https://github.com/ace-step/ACE-Step-1.5'
TAG = 'v0.1.8'
NW = 0x08000000 if os.name == 'nt' else 0
IS = {'var': False, 'adim': '', 'hata': ''}
LOCK = threading.Lock()


def source():
    return DIR / f'ACE-Step-1.5-{TAG[1:]}'


def executable(env, name):
    return env / ('Scripts' if os.name == 'nt' else 'bin') / (name + ('.exe' if os.name == 'nt' else ''))


def runtime():
    return executable(source() / '.venv', 'python')


def durum():
    try:
        ready = (DIR / 'kurulum.txt').read_text(encoding='utf-8') == TAG and runtime().is_file()
    except OSError:
        ready = False
    return {'kurulu': ready, 'is': dict(IS)}


def run(args, log, timeout, *, offline=False):
    import yol
    env = {**os.environ, **yol.kapsama(), 'UV_CACHE_DIR': str(DIR / 'uv-cache'),
           'UV_PYTHON_INSTALL_DIR': str(DIR / 'python'),
           'UV_PROJECT_ENVIRONMENT': str(source() / '.venv'), 'HF_HUB_OFFLINE': '1' if offline else '0'}
    env.pop('VIRTUAL_ENV', None)
    with log.open('ab') as stream:
        result = subprocess.run([str(a) for a in args], cwd=source(), env=env, stdout=stream,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=NW, timeout=timeout)
    if result.returncode:
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 1800))
            tail = stream.read().decode('utf-8', errors='replace')
        raise RuntimeError(tail.strip() or f'ACE-Step çıkış kodu: {result.returncode}')


def install():
    try:
        (DIR / 'kurulum.txt').unlink(missing_ok=True)
        archive = DIR / f'{TAG}.zip'
        download(f'{REPO}/archive/refs/tags/{TAG}.zip', archive)
        unzip(archive, DIR)
        log = DIR / 'kurulum.log'
        log.write_bytes(b'')
        bootstrap = DIR / 'bootstrap'
        uv = executable(bootstrap, 'uv')
        IS['adim'] = 'Ayrı Python ortamı hazırlanıyor'
        if not uv.exists():
            py = Path(sys.executable).with_name('python.exe') if os.name == 'nt' else Path(sys.executable)
            run([py, '-m', 'venv', bootstrap], log, 300)
            run([executable(bootstrap, 'python'), '-m', 'pip', 'install', 'uv'], log, 600)
        IS['adim'] = 'ACE-Step bağımlılıkları indiriliyor'
        run([uv, 'sync', '--locked', '--python', '3.12'], log, 7200)
        IS['adim'] = 'Turbo modeli indiriliyor ve yükleniyor'
        with uretim_kilidi():
            run([runtime(), Path(__file__).resolve(), 'prepare'], log, 7200)
        (DIR / 'kurulum.txt').write_text(TAG, encoding='utf-8')
        IS['adim'] = 'Model yükleme kontrolü tamamlandı'
    except Exception as exc:
        IS['hata'] = str(exc)
    finally:
        IS['var'] = False


def kur():
    with LOCK:
        if IS['var']:
            raise ValueError('Müzik kurulumu zaten sürüyor')
        if durum()['kurulu']:
            return {'ok': True}
        IS.update(var=True, adim='ACE-Step indiriliyor', hata='')
        threading.Thread(target=install, daemon=True).start()
    return {'ok': True}


def uret(istem, cikti, saniye):
    if not durum()['kurulu']:
        raise ValueError('ACE-Step kurulu değil. Ayarlar → Servisler ve modeller bölümünden kur.')
    log = DIR / 'uretim.log'
    with uretim_kilidi():
        log.write_bytes(b'')
        run([runtime(), Path(__file__).resolve(), 'generate', json.dumps(
            {'istem': istem, 'dosya': str(cikti), 'saniye': saniye}, ensure_ascii=False)],
            log, 7200, offline=True)
    if not cikti.is_file() or cikti.stat().st_size <= 44:
        raise RuntimeError('ACE-Step geçerli bir WAV üretmedi')


def worker():
    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    import shutil
    import tempfile

    handler = AceStepHandler()
    gpu = torch.cuda.is_available()
    status, ok = handler.initialize_service(
        project_root=str(source()), config_path='acestep-v15-turbo', device='auto',
        use_flash_attention=False, compile_model=False,
        offload_to_cpu=gpu, offload_dit_to_cpu=gpu,
    )
    if not ok:
        raise RuntimeError(status)
    if sys.argv[1] == 'prepare':
        return
    job = json.loads(sys.argv[2])
    params = GenerationParams(
        caption=job['istem'], lyrics='[Instrumental]', duration=job['saniye'],
        task_type='text2music', thinking=False, inference_steps=8,
        use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
    )
    config = GenerationConfig(batch_size=1, audio_format='wav')
    with tempfile.TemporaryDirectory(dir=DIR) as temp:
        result = generate_music(handler, LLMHandler(), params, config, save_dir=temp)
        if not result.success:
            raise RuntimeError(result.error)
        audio = next(Path(temp).rglob('*.wav'), None)
        if not audio or audio.stat().st_size <= 44:
            raise RuntimeError('Geçerli WAV bulunamadı')
        target = Path(job['dosya'])
        partial = target.with_suffix('.wav.part')
        try:
            shutil.copyfile(audio, partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


if __name__ == '__main__':
    worker()
