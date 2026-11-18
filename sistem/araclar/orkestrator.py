"""Panel-owned orchestration. Workers never create a terminal; permissions use JSON IPC."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / 'sistem/ortam/yerel/orkestrator'
NW = 0x08000000 if os.name == 'nt' else 0
LOCK = threading.RLock()
JOBS = {}
LOCAL = {'ollama': 'http://127.0.0.1:11434', 'lmstudio': 'http://127.0.0.1:1234/v1', 'llamacpp': 'http://127.0.0.1:8080/v1'}


def config():
    sys.path.insert(0, str(ROOT / 'sistem/ayar'))
    import ayar
    return ayar


def endpoint(kind, cfg=None):
    cfg = cfg if cfg is not None else config().coz().get('orkestrator', {})
    url = (cfg.get('yerel_adresler', {}).get(kind) or LOCAL[kind]).rstrip('/')
    p = urllib.parse.urlparse(url)
    # Local orchestration must never silently send source material to a remote service.
    if p.scheme != 'http' or p.hostname not in ('localhost', '127.0.0.1', '::1') or p.username or p.password or p.query or p.fragment:
        raise ValueError('Yerel model adresi http://localhost veya 127.0.0.1 olmalı.')
    return url


def request(url, body=None, timeout=15):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def models(kind, cfg=None):
    u = endpoint(kind, cfg)
    d = request(u + ('/api/tags' if kind == 'ollama' else '/models'), timeout=3)
    return [{'id': m.get('name') or m.get('id'), 'ad': m.get('name') or m.get('id')}
            for m in d.get('models' if kind == 'ollama' else 'data', []) if m.get('name') or m.get('id')]


def project(name):
    if name == '_profil':
        return ROOT / 'kimlik'
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,60}', name or ''):
        raise ValueError('Geçersiz proje adı')
    p = ROOT / 'projeler' / name
    if not p.is_dir() or p.resolve().parent != (ROOT / 'projeler').resolve():
        raise ValueError('Proje bulunamadı veya klasör bağlantısı geçersiz')
    return p


def history_path(name):
    project(name)
    return STORE / (name + '.json')


def read_state(name):
    try:
        return json.loads(history_path(name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'mesajlar': [], 'session': None, 'durum': 'bekliyor', 'izin': None}


def save(name, d):
    STORE.mkdir(parents=True, exist_ok=True)
    p = history_path(name)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


def state(name):
    project(name)
    with LOCK:
        d = read_state(name)
        job = JOBS.get(name)
        if d['durum'] in ('calisiyor', 'izin') and not (job and job['p'].poll() is None):
            d.update(durum='kesildi', izin=None)
        return {**d, 'mesajlar': d['mesajlar'][-150:], 'bekleyen_not': len(list((STORE / 'queue' / name).glob('*.json')))}


def enqueue(directory, seq):
    """Kurgu wake hook: durable delivery only; never start an independent agent."""
    path = Path(directory).resolve()
    projects = (ROOT / 'projeler').resolve()
    if projects not in path.parents:
        raise ValueError('Kurgu projesi stüdyo dışında')
    name = path.relative_to(projects).parts[0]
    project(name)
    queue = STORE / 'queue' / name
    queue.mkdir(parents=True, exist_ok=True)
    prefix = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    current = None
    if (path / 'project.json').is_file():
        current = {n['id']: n for n in json.loads((path / 'project.json').read_text(encoding='utf-8')).get('notes', []) if 'id' in n}
    for line in (path / '.kurgu/inbox.jsonl').read_text(encoding='utf-8').splitlines():
        entry = json.loads(line)
        number = int(entry['seq'])
        if number > int(seq):
            continue
        if current is not None:
            entry['notes'] = [n for n in entry['notes'] if n.get('id') in current and not current[n['id']].get('done') and current[n['id']].get('status') != 'done']
            if not entry['notes']:
                continue
        stamp = hashlib.sha256(line.encode()).hexdigest()[:12]
        target = queue / f'{prefix}-{number:012d}-{stamp}.json'
        if target.exists() or target.with_suffix('.done').exists():
            continue
        tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps({'directory': str(path), 'entry': entry}, ensure_ascii=False), encoding='utf-8')
        tmp.replace(target)


def drain(name, approved=False):
    project(name)
    with LOCK:
        files = sorted((STORE / 'queue' / name).glob('*.json'))
        if not files:
            return {'ok': True}
        if not trust(approved):
            return {'ok': False, 'guven_gerekli': True, 'kok': str(ROOT)}
        if name in JOBS and (JOBS[name]['p'].poll() is None or JOBS[name]['thread'].is_alive()):
            return {'ok': True, 'kuyrukta': True}
        # Keep full frame/timecode/mark metadata in the inbox; send a bounded pointer and note text.
        item = json.loads(files[0].read_text(encoding='utf-8'))
        prompt = ('Kurgu editöründen gelen notları uygula. Önce .claude/CLAUDE.md dosyasını oku. '
                  'Notların kare, zaman ve işaret bilgilerini bu klasördeki .kurgu/inbox.jsonl ve NOTLAR.md dosyalarından oku: '
                  + item['directory'] + '\nGönderim: ' + str(item['entry']['seq']) + '\n'
                  + '\n'.join(str(n.get('timecode', '')) + ' ' + str(n.get('text', '')) for n in item['entry']['notes'])[:30000]
                  + '\nİş bitince kurgu notes done ile notları yanıtla. Yeni terminal veya bağımsız ajan oturumu açma.')
        result = start(name, prompt, format=Path(item['directory']).name)
        if result.get('ok'):
            files[0].replace(files[0].with_suffix('.done'))
        return result


def pump():
    while True:
        if trust():
            for directory in (STORE / 'queue').glob('*'):
                try:
                    import guncelleme
                    with guncelleme.KILIT:
                        if not guncelleme.engel():
                            drain(directory.name)
                except Exception as e:
                    with LOCK:
                        if (ROOT / 'projeler' / directory.name).is_dir():
                            d = read_state(directory.name)
                            d.update(hata=str(e))
                            save(directory.name, d)
        time.sleep(1)


def trust(approve=False):
    key = hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()
    p = STORE / ('trust-' + key)
    if approve:
        STORE.mkdir(parents=True, exist_ok=True)
        p.write_text(time.strftime('%Y-%m-%d %H:%M:%S'), encoding='utf-8')
    return p.exists()


def start(name, prompt, approved=False, format='ana'):
    directory = project(name)
    if format not in ('ana', 'reels', 'tiktok', 'shorts', 'story'):
        raise ValueError('Geçersiz kurgu biçimi.')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 40000:
        raise ValueError('Mesaj 1–40000 karakter olmalı')
    from kurgu_plan import REQUIRED, durum as plan_durum, oner
    directory = Path(directory)
    planning = ""
    if name != '_profil' and (directory / REQUIRED).exists() and not plan_durum(directory)['onayli']:
        suggestions = ', '.join(item['ad'] for item in oner(prompt)) or 'Doğal montaj'
        planning = ('\n\nBu tur sadece planlama ve revizyon. Üretim, kesim ve render yapma. '
                   'Storyboard’u yazıp panel onayında dur. Stil önerileri: ' + suggestions)
    with LOCK:
        if name in JOBS and (JOBS[name]['p'].poll() is None or JOBS[name]['thread'].is_alive()):
            raise ValueError('Orkestratör çalışıyor. Yanıtını bekle veya üretimi durdur.')
        if not trust(approved):
            return {'ok': False, 'guven_gerekli': True, 'kok': str(ROOT)}
        cfg = config().coz(None if name == '_profil' else name).get('orkestrator', {})
        kind = cfg.get('calisma_ortami', 'claude-code')
        d = read_state(name)
        if d.get('ortam') != kind or d.get('model') != cfg.get('model'):
            d['session'] = None
        d.update(durum='calisiyor', izin=None, hata='', ortam=kind, model=cfg.get('model'))
        d['mesajlar'].append({'rol': 'user', 'metin': prompt})
        save(name, d)
        jobfile = STORE / (name + '.job.json')
        jobfile.write_text(json.dumps({'proje': name, 'prompt': prompt, 'cfg': cfg, 'session': d.get('session'),
                                       'history': d['mesajlar'][-40:], 'format': format, 'planlama': planning}, ensure_ascii=False), encoding='utf-8')
        import yol
        py = ROOT / 'sistem/ortam/venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not py.exists():
            py = Path(sys.executable).with_name('python.exe') if os.name == 'nt' else Path(sys.executable)
        kw = {'creationflags': NW} if os.name == 'nt' else {'start_new_session': True}
        try:
            p = subprocess.Popen([str(py), '-u', str(Path(__file__)), 'worker', str(jobfile)], cwd=str(ROOT),
                                 env={**os.environ, **yol.kapsama()}, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **kw)
        except OSError as e:
            d.update(durum='hata', hata=str(e)); save(name, d)
            raise RuntimeError(str(e)) from e
        t = threading.Thread(target=collect, args=(name, p), daemon=True)
        JOBS[name] = {'p': p, 'thread': t}
        t.start()
        return {'ok': True, 'proje': name, 'panel': True}


def collect(name, p):
    for line in p.stdout:
        try:
            e = json.loads(line)
        except ValueError:
            e = {'type': 'log', 'text': line.strip()[-2000:]}
        with LOCK:
            d = read_state(name)
            if d['durum'] == 'iptal':
                continue
            typ = e.get('type')
            if typ == 'permission':
                d.update(durum='izin', izin=e)
            elif typ == 'session':
                d['session'] = e['id']
            elif typ == 'error':
                d.update(durum='hata', hata=e.get('text', 'İşlem başarısız'))
            if e.get('text'):
                d['mesajlar'].append({'rol': 'assistant' if typ == 'text' else 'system', 'metin': e['text']})
            save(name, d)
    rc = p.wait()
    with LOCK:
        d = read_state(name)
        if d['durum'] not in ('iptal', 'hata'):
            d.update(durum='bitti' if rc == 0 else 'hata', hata='' if rc == 0 else f'Orkestratör çıkış kodu: {rc}')
        d['izin'] = None
        save(name, d)


def permission(name, ident, allow, answers=None):
    with LOCK:
        d = read_state(name)
        if not d.get('izin') or d['izin']['id'] != ident or name not in JOBS:
            raise ValueError('Bu izin isteği artık geçerli değil')
        p = JOBS[name]['p']
        p.stdin.write(json.dumps({'id': ident, 'allow': allow is True, 'answers': answers or {}}, ensure_ascii=False) + '\n')
        p.stdin.flush()
        d.update(izin=None, durum='calisiyor'); save(name, d)
    return {'ok': True}


def stop(name):
    project(name)
    with LOCK:
        for pending in (STORE / 'queue' / name).glob('*.json'):
            pending.replace(pending.with_suffix('.done'))
        d = read_state(name)
        d.update(durum='iptal', izin=None); save(name, d)
        p = (JOBS.get(name) or {}).get('p')
    if p and p.poll() is None:
        if os.name == 'nt':
            r = subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True, creationflags=NW, timeout=30)
            if r.returncode and p.poll() is None:
                raise RuntimeError('Üretim süreci durdurulamadı; proje silinmedi.')
        else:
            import signal
            os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=30)
    t = (JOBS.get(name) or {}).get('thread')
    if t:
        t.join(timeout=10)
        if t.is_alive():
            raise RuntimeError('Orkestratör kapanışı sürüyor; tekrar deneyin')
    return {'ok': True}


def emit(typ, **kw):
    print(json.dumps({'type': typ, **kw}, ensure_ascii=False), flush=True)


def ask(tool, args):
    ident = uuid.uuid4().hex
    emit('permission', id=ident, tool=tool, input=args)
    while True:
        ln = sys.stdin.readline()
        if not ln:
            raise RuntimeError('Panel bağlantısı kapandı')
        d = json.loads(ln)
        if d.get('id') == ident:
            return d


async def claude(job):
    try:
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, PermissionResultAllow, PermissionResultDeny
    except ImportError:
        raise RuntimeError('Panel ajan bağlantısı eksik: kurulum sihirbazında bağımlılıkları onar (claude-agent-sdk).') from None
    async def approve(tool, args, context):
        r = await asyncio.to_thread(ask, tool, args)
        if r['allow']:
            if tool == 'AskUserQuestion':
                args = {**args, 'answers': r.get('answers', {})}
            return PermissionResultAllow(updated_input=args)
        return PermissionResultDeny(message='Kullanıcı panelden reddetti')
    cfg = job['cfg']
    opts = ClaudeAgentOptions(cwd=str(ROOT), setting_sources=['user', 'project', 'local'],
                             permission_mode='default', can_use_tool=approve, resume=job.get('session'),
                             model=cfg.get('model') or None,
                             system_prompt={'type': 'preset', 'preset': 'claude_code', 'append': 'Kullanıcıyla yalnızca panelde konuş. Terminal penceresi açma. Proje: ' + job['proje']})
    configure_mcp(opts, job['proje'], job.get('format', 'ana'))
    if job['proje'] != '_profil':
        opts.allowed_tools = ['mcp__yerel_medya__gorevlendir']
        opts.env = {**getattr(opts, 'env', {}), 'MCP_TOOL_TIMEOUT': '7500000'}
        opts.system_prompt['append'] += ' Teknik planın her görevi için ilgili becerileri seç. python sistem/araclar/kurgu_becerileri.py liste komutu uygun yerel dosya yollarını verir. ' + ' Üretim yapma: görevi planla, ilgili alt ajana ver, teslimi kontrol et. Proje tercihi yerel veya API ise medya için sahne etiketi ve kısa görevle yerel_medya / gorevlendir aracını kullan; uzman uygulamayı üstlenir.'
    cli = shutil.which('claude')
    if cli and not cli.lower().endswith(('.cmd', '.bat')):
        opts.cli_path = cli
    async with ClaudeSDKClient(options=opts) as client:
        await client.query(job['prompt'] + job.get('planlama', ''))
        async for msg in client.receive_response():
            sid = getattr(msg, 'session_id', None)
            if sid:
                emit('session', id=sid)
            for block in getattr(msg, 'content', []) or []:
                if getattr(block, 'text', None):
                    emit('text', text=block.text)
                elif getattr(block, 'name', None):
                    emit('log', text='Araç: ' + block.name)
            if getattr(msg, 'is_error', False):
                raise RuntimeError(getattr(msg, 'result', None) or 'Claude isteği başarısız')


def configure_mcp(opts, project_name, format='ana'):
    # Use subscription login of the installed CLI when available, SDK bundle otherwise.
    # The existing MCP configuration includes project-selected connectors and scoped secrets.
    sys.path.insert(0, str(ROOT / 'sistem/baglayici'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('yst_studio_mcp', ROOT / 'sistem/baglayici/mcp.py')
    studio_mcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(studio_mcp)
    mcp_path = studio_mcp.olustur()
    if mcp_path:
        opts.mcp_servers = str(mcp_path)
        for item in studio_mcp.liste().values():
            key = item.get("anahtar_adi")
            if item.get("etkin") and key:
                value = studio_mcp.ortak.anahtar_oku(key)
                if value:
                    os.environ[key] = value

    if project_name != '_profil':
        from claude_agent_sdk import create_sdk_mcp_server, tool
        import medya_gorevi

        @tool('gorevlendir', medya_gorevi.DESCRIPTION, {'tur': str, 'istem': str, 'sahne': str, 'oran': str})
        async def produce(args):
            try:
                result = await asyncio.to_thread(
                    lambda: medya_gorevi.gorevlendir(
                        project_name, args['tur'], args['istem'], args.get('sahne', ''),
                        args.get('oran', ''), format=format,
                    ),
                )
                return {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}]}
            except Exception as exc:
                return {'isError': True, 'content': [{'type': 'text', 'text': str(exc)}]}

        servers = json.loads(Path(mcp_path).read_text(encoding='utf-8')).get('mcpServers', {}) if mcp_path else {}
        servers['yerel_medya'] = create_sdk_mcp_server(name='yerel_medya', tools=[produce])
        opts.mcp_servers = servers


def safe_path(value, write=False, name=None):
    p = (ROOT / value).resolve()
    if (p != ROOT.resolve() and ROOT.resolve() not in p.parents) or any(x in p.parts for x in ('.git', '.aws')):
        raise ValueError('Yol stüdyo dışında veya korunan bir konumda')
    if write and (project(name).resolve() not in p.parents or 'kaynak' in p.relative_to(project(name)).parts):
        raise ValueError('Yazma yalnızca etkin projenin üretilen dosyalarına yapılabilir')
    return p


TOOLS = [{'type': 'function', 'function': {'name': n, 'description': desc,
          'parameters': {'type': 'object', 'properties': props, 'required': list(props)}}} for n, desc, props in [
    ('read', 'Read a UTF-8 studio file', {'path': {'type': 'string'}}),
    ('list', 'List a studio directory', {'path': {'type': 'string'}}),
    ('write', 'Write a generated project file, after panel approval', {'path': {'type': 'string'}, 'text': {'type': 'string'}}),
    ('run', 'Run a program with argv after explicit panel approval; no shell', {'argv': {'type': 'array', 'items': {'type': 'string'}}}),
    ('local_media', 'Assign a media task to the project specialist using the configured project engine. Pass a short brief. Scene: storyboard label or empty. Aspect ratio: images only, or empty. Returns a verified asset record.', {
        'tur': {'type': 'string', 'enum': ['image', 'video', 'music']},
        'istem': {'type': 'string'}, 'sahne': {'type': 'string'}, 'oran': {'type': 'string'},
    }),
    ('skills', 'List installed skill IDs and local reference paths before delegating', {}),
    ('delegate', 'Delegate to a configured agent role with relevant skill IDs in beceriler', {'agent': {'type': 'string'}, 'task': {'type': 'string'}, 'beceriler': {'type': 'array', 'items': {'type':'string'}}})
]]


def local(job, role=None, depth=0, approval=None):
    kind, cfg = job['cfg'].get('calisma_ortami'), job['cfg']
    model = cfg.get('model')
    if not model:
        raise ValueError('Ayarlar → Orkestratör bölümünden kurulu bir yerel model seç.')
    instructions = (ROOT / '.claude/CLAUDE.md').read_text(encoding='utf-8')
    if role:
        instructions += '\n' + (ROOT / '.claude/agents' / (role + '.md')).read_text(encoding='utf-8')
    direction = ('Execute only the assigned specialist task.' if role else
                 'Plan, delegate production to specialists, verify the result. For media dispatch use local_media; for judgment and editing use delegate.')
    messages = [{'role': 'system', 'content': instructions + '\n' + direction + job.get('planlama', '') +
                 ' Do not claim work without a verified result. Active project: ' + job['proje']}]
    messages += [{'role': m['rol'], 'content': m['metin']} for m in job['history'] if m['rol'] in ('user', 'assistant')]
    u = endpoint(kind, cfg) + ('/api/chat' if kind == 'ollama' else '/chat/completions')
    for _ in range(60):
        data = request(u, {'model': model, 'messages': messages, 'tools': TOOLS, 'stream': False}, timeout=900)
        msg = data['message'] if kind == 'ollama' else data['choices'][0]['message']
        messages.append(msg)
        if msg.get('content'):
            emit('text', text=msg['content'])
        if not msg.get('tool_calls'):
            return msg.get('content', '')
        for call in msg['tool_calls']:
            f = call['function']; n = f['name']; a = f['arguments']
            if isinstance(a, str):
                a = json.loads(a)
            emit('log', text=('Alt ajan: ' + a.get('agent', '') if n == 'delegate' else 'Araç: ' + n))
            try:
                if n == 'read':
                    result = safe_path(a['path']).read_text(encoding='utf-8')[:60000]
                elif n == 'list':
                    result = '\n'.join(p.name for p in safe_path(a['path']).iterdir())[:12000]
                elif n == 'local_media':
                    from medya_gorevi import gorevlendir
                    result = json.dumps(gorevlendir(
                        job['proje'], a['tur'], a['istem'], a.get('sahne', ''), a.get('oran', ''),
                        format=job.get('format', 'ana'),
                    ), ensure_ascii=False)
                elif n == 'skills':
                    from kurgu_plan import beceriler
                    result = json.dumps({key: value['yol'] for key, value in beceriler().items()
                                         if value['kurulu']}, ensure_ascii=False)
                elif n == 'delegate':
                    if depth >= 2 or not re.fullmatch(r'[a-z][a-z-]{0,50}', a['agent']):
                        raise ValueError('Alt ajan sınırı veya geçersiz rol')
                    from kurgu_plan import beceriler
                    known = beceriler()
                    selected = a.get('beceriler') or []
                    paths = [known[key]['yol'] for key in selected if key in known and known[key]['kurulu']]
                    if paths:
                        a['task'] += '\nUygulanacak beceriler: ' + ', '.join(paths)
                    ac = config().ajan(a['agent'], None if job['proje'] == '_profil' else job['proje'])
                    ak = ac['etkin_ortam']
                    if ak in LOCAL:
                        result = local({**job, 'cfg': {**cfg, 'calisma_ortami': ak, 'model': ac.get('model') or model},
                                        'history': [{'rol': 'user', 'metin': a['task']}]}, a['agent'], depth + 1, approval)
                    else:
                        if not (approval or ask)('delegate', {**a, 'runtime': ak})['allow']:
                            raise ValueError('Alt ajan çağrısı reddedildi')
                        import ajan_cagir
                        task = STORE / ('task-' + uuid.uuid4().hex + '.md')
                        task.write_text(a['task'], encoding='utf-8')
                        result = ajan_cagir.calistir(a['agent'], str(task), None if job['proje'] == '_profil' else job['proje'], ortam=ak)
                elif n in ('write', 'run'):
                    if not (approval or ask)(n, a)['allow']:
                        raise ValueError('Kullanıcı reddetti')
                    if n == 'write':
                        p = safe_path(a['path'], True, job['proje']); p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(a['text'], encoding='utf-8'); result = 'Dosya yazıldı'
                    else:
                        argv = a['argv']
                        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                            raise ValueError('argv dizisi gerekli')
                        r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=NW, timeout=7200, stdin=subprocess.DEVNULL)
                        result = json.dumps({'code': r.returncode, 'output': (r.stdout + r.stderr)[-24000:]})
                else:
                    raise ValueError('Bilinmeyen araç')
            except Exception as e:
                result = 'HATA: ' + str(e)
            item = {'role': 'tool', 'content': str(result)}
            if kind == 'ollama':
                item['tool_name'] = n
            else:
                item['tool_call_id'] = call['id']
            messages.append(item)
    raise RuntimeError('Araç döngüsü sınırına ulaşıldı; panelden devam edebilirsiniz.')


def worker(path):
    if os.name == 'nt':
        # Includes SDK/asyncio children: a hidden worker must not spawn visible consoles.
        original = subprocess.Popen
        class HiddenProcess(original):
            def __init__(self, *args, **kwargs):
                kwargs['creationflags'] = kwargs.get('creationflags', 0) | NW
                super().__init__(*args, **kwargs)
        subprocess.Popen = HiddenProcess
    job = json.loads(Path(path).read_text(encoding='utf-8'))
    kind = job['cfg'].get('calisma_ortami', 'claude-code')
    try:
        import yerel_medya
        direct = yerel_medya.komut(job['prompt'])
        if direct:
            from medya_gorevi import ROLLER, gorevlendir
            emit('log', text='Medya görevi: ' + ROLLER[direct['tur']])
            result = gorevlendir(job['proje'], **direct, format=job.get('format', 'ana'))
            emit('text', text='Hazır: ' + result['dosya'])
        elif kind == 'claude-code':
            asyncio.run(claude(job))
        elif kind in LOCAL:
            local(job)
        else:
            # Existing CLI adapters run noninteractively and retain their sandbox.
            import ajan_cagir
            out = Path(path).with_suffix('.output.txt')
            conversation = '\n\n'.join(m['rol'] + ': ' + m['metin'] for m in job['history'] if m['rol'] in ('user', 'assistant'))[-60000:]
            context = Path(path).with_suffix('.conversation.md')
            context.write_text(conversation + job.get('planlama', ''), encoding='utf-8')
            prompt = 'Read .claude/CLAUDE.md and ' + context.relative_to(ROOT).as_posix() + '. Continue the conversation from the last user message. Respond through this session; never open a terminal window.'
            cmd = ajan_cagir.komut_kur(kind, prompt, False, out, job['cfg'].get('model') or '')
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=NW, stdin=subprocess.DEVNULL, timeout=7200)
            emit('text', text=(out.read_text(encoding='utf-8') if out.exists() else r.stdout)[-60000:])
            if r.returncode:
                raise RuntimeError(r.stderr[-3000:] or 'CLI işlemi başarısız')
    except Exception as e:
        emit('error', text=str(e)); return 1
    return 0


if __name__ == '__main__':
    if sys.argv[1] == 'enqueue':
        enqueue(sys.argv[2], sys.argv[3])
    else:
        sys.exit(worker(sys.argv[2]))
