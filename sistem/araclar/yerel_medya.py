"""Project-scoped media dispatch shared by the panel and orchestrator."""
import re
import uuid

DESCRIPTION = ('Produce an asset on this computer. Pass a short visual or instrumental brief. '
               'Use image, video, or music. Returns only a project-relative asset path. '
               'Never substitute a cloud service if a local engine is unavailable.')


def komut(mesaj):
    match = re.fullmatch(r'/(görsel|gorsel|video|müzik|muzik)\s+(.+)', mesaj.strip(), re.I | re.S)
    if match:
        kind = {'görsel': 'image', 'gorsel': 'image', 'video': 'video', 'müzik': 'music', 'muzik': 'music'}
        return {'tur': kind[match[1].lower()], 'istem': match[2]}


def uret(proje, tur, istem, saniye=None, oran=None):
    import orkestrator

    if proje == '_profil':
        raise ValueError('Medya üretimi için bir proje aç.')
    root = orkestrator.project(proje).resolve()
    if not isinstance(istem, str) or not 1 <= len(istem.strip()) <= 2000:
        raise ValueError('İstem 1–2000 karakter olmalı.')
    istem = istem.strip()

    if tur == 'video':
        import yerel_video
        frames = {1: 17, 2: 49, 5: 121}.get(saniye if saniye is not None else 2)
        if frames is None:
            raise ValueError('Video süresi 1, 2 veya 5 saniye olmalı.')
        yerel_video.baslat(proje, istem, frames)
        yerel_video.THREAD.join()
        if not yerel_video.GEN.get('dosya'):
            raise RuntimeError(yerel_video.GEN.get('hata') or 'Video üretilmedi')
        return yerel_video.GEN['dosya']

    if tur not in ('image', 'music'):
        raise ValueError('Medya türü image, video veya music olmalı.')
    directory = (root / ('kaynak/foto' if tur == 'image' else 'kaynak/ses')).resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Medya klasörü proje dışında.')
    directory.mkdir(parents=True, exist_ok=True)
    suffix = '.png' if tur == 'image' else '.wav'
    target = directory / (('z-image-' if tur == 'image' else 'ace-step-') + uuid.uuid4().hex[:12] + suffix)
    if tur == 'image':
        import yerel_gorsel
        if oran == '9:16':
            yerel_gorsel.uret(istem, str(target), genislik=576, yukseklik=1024)
        elif oran == '1:1':
            yerel_gorsel.uret(istem, str(target), genislik=768, yukseklik=768)
        else:
            yerel_gorsel.uret(istem, str(target))
    else:
        import yerel_muzik
        duration = 20 if saniye is None else saniye
        if not isinstance(duration, int) or not 10 <= duration <= 60:
            raise ValueError('Müzik süresi 10–60 saniye olmalı.')
        yerel_muzik.uret(istem, target, duration)
    return target.relative_to(root).as_posix()
