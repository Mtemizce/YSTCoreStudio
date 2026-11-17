"""Hermetic regression tests: IPC, permissions, model downloads and panel lifecycle.

No sockets, real installers, model downloads or GPU work are started.
"""
import asyncio
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock, AsyncMock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sistem/araclar'))
sys.path.insert(0, str(ROOT / 'sistem/panel'))
import orkestrator as O
import indirme as D
import panel as P
import ek_api as E
import yerel_video as V


class Response(io.BytesIO):
    def __init__(self, data, status=200, **headers):
        super().__init__(data)
        self.status = status
        self.headers = {'Content-Length': str(len(data)), **headers}


class Downloads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'model.gguf'

    def test_resume_hash_and_receipt(self):
        self.file.with_suffix('.gguf.part').write_bytes(b'abc')
        digest = hashlib.sha256(b'abcdef').hexdigest()
        with patch.object(D.urllib.request, 'urlopen', return_value=Response(b'def', 206, **{'Content-Range':'bytes 3-5/6'})) as req:
            D.download('https://example.test/model', self.file, 6, digest)
        self.assertEqual(req.call_args.args[0].get_header('Range'), 'bytes=3-')
        self.assertEqual(self.file.read_bytes(), b'abcdef')
        self.assertTrue(D.valid(self.file, 6, digest))

    def test_server_ignoring_range_restarts(self):
        self.file.with_suffix('.gguf.part').write_bytes(b'old')
        with patch.object(D.urllib.request, 'urlopen', return_value=Response(b'abcdef')):
            D.download('https://example.test/model', self.file, 6)
        self.assertEqual(self.file.read_bytes(), b'abcdef')

    def test_invalid_range_is_not_appended(self):
        part = self.file.with_suffix('.gguf.part'); part.write_bytes(b'abc')
        with patch.object(D.urllib.request, 'urlopen', return_value=Response(b'def', 206, **{'Content-Range':'bytes 0-2/6'})):
            with self.assertRaises(RuntimeError): D.download('https://example.test/model', self.file, 6)
        self.assertEqual(part.read_bytes(), b'abc')

    def test_truncated_download_never_becomes_installed(self):
        with patch.object(D.urllib.request, 'urlopen', return_value=Response(b'abc', **{'Content-Length':'6'})):
            with self.assertRaises(RuntimeError): D.download('https://example.test/model', self.file, 6)
        self.assertFalse(self.file.exists())
        self.assertEqual(self.file.with_suffix('.gguf.part').read_bytes(), b'abc')

    def test_hash_mismatch_discards_partial(self):
        with patch.object(D.urllib.request, 'urlopen', return_value=Response(b'bad')):
            with self.assertRaises(RuntimeError): D.download('https://example.test/model', self.file, 3, '0'*64)
        self.assertFalse(self.file.exists())
        self.assertFalse(self.file.with_suffix('.gguf.part').exists())

    def test_same_size_corruption_invalidates_receipt(self):
        self.file.write_bytes(b'good'); digest=hashlib.sha256(b'good').hexdigest()
        self.assertTrue(D.valid(self.file, 4, digest))
        self.file.write_bytes(b'evil'); os.utime(self.file, (1,1))
        self.assertFalse(D.valid(self.file, 4, digest))

    def test_zip_traversal_rejected_before_extraction(self):
        z = self.file.with_suffix('.zip')
        with zipfile.ZipFile(z, 'w') as out:
            out.writestr('normal.txt','yes'); out.writestr('../escape.txt','no')
        with self.assertRaises(ValueError): D.unzip(z, self.file.parent/'out')
        self.assertFalse((self.file.parent/'out/normal.txt').exists())


class Orchestration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'projeler/demo/ana/.kurgu').mkdir(parents=True)
        (self.root/'projeler/demo/kaynak').mkdir()
        (self.root/'.claude').mkdir(); (self.root/'.claude/CLAUDE.md').write_text('Test rules')
        for obj, attr, value in [(O,'ROOT',self.root),(O,'STORE',self.root/'state'),(O,'JOBS',{})]:
            p=patch.object(obj,attr,value);p.start();self.addCleanup(p.stop)

    def test_untrusted_start_does_not_spawn(self):
        with patch.object(O.subprocess,'Popen') as spawn:
            r=O.start('demo','hello')
        self.assertTrue(r['guven_gerekli']); spawn.assert_not_called()

    def test_folder_trust_is_specific_to_root(self):
        O.trust(True); self.assertTrue(O.trust())
        with patch.object(O,'ROOT',self.root/'different'):
            self.assertFalse(O.trust())

    def test_path_bounds_and_source_protection(self):
        self.assertEqual(O.safe_path('.'),self.root)
        self.assertEqual(O.safe_path('projeler/demo/output.txt',True,'demo').name,'output.txt')
        for value in ['../escape','.git/config']:
            with self.assertRaises(ValueError): O.safe_path(value)
        with self.assertRaises(ValueError): O.safe_path('projeler/demo/kaynak/input.jpg',True,'demo')
        with self.assertRaises(ValueError): O.project('../demo')

    def test_local_endpoint_and_discovery(self):
        for address in ['https://example.com','http://example.com','http://user:pass@localhost','http://localhost/?key=x']:
            with self.assertRaises(ValueError): O.endpoint('ollama',{'yerel_adresler':{'ollama':address}})
        with patch.object(O,'request',return_value={'models':[{'name':'qwen3:8b'}]}) as req:
            self.assertEqual(O.models('ollama',{})[0]['id'],'qwen3:8b')
        self.assertEqual(req.call_args.args[0],'http://127.0.0.1:11434/api/tags')
        with patch.object(O,'request',return_value={'data':[{'id':'local-model'}]}):
            self.assertEqual(O.models('lmstudio',{})[0]['id'],'local-model')

    def test_worker_hidden_and_history_persisted(self):
        process=Mock(stdout=io.StringIO(''),stdin=io.StringIO());process.poll.return_value=None
        thread=Mock();thread.is_alive.return_value=False
        with patch.object(O,'config',return_value=Mock(coz=lambda _: {'orkestrator':{'calisma_ortami':'ollama','model':'qwen'}})), patch.object(O.subprocess,'Popen',return_value=process) as spawn, patch.object(O.threading,'Thread',return_value=thread):
            self.assertTrue(O.start('demo','hello',True)['ok'])
        kw=spawn.call_args.kwargs
        self.assertEqual(kw['stdin'],O.subprocess.PIPE)
        if os.name=='nt': self.assertTrue(kw['creationflags'] & O.NW)
        self.assertEqual(O.read_state('demo')['mesajlar'][-1]['metin'],'hello')
        with self.assertRaises(ValueError): O.start('demo','duplicate')

    def test_permission_id_and_deny(self):
        O.save('demo',{'durum':'izin','mesajlar':[],'izin':{'id':'one'}})
        stdin=io.StringIO();O.JOBS['demo']={'p':types.SimpleNamespace(stdin=stdin)}
        with self.assertRaises(ValueError):O.permission('demo','stale',True)
        O.permission('demo','one',False)
        self.assertFalse(json.loads(stdin.getvalue())['allow'])
        self.assertIsNone(O.read_state('demo')['izin'])

    def test_restart_clears_stale_permission(self):
        O.save('demo',{'durum':'izin','mesajlar':[],'izin':{'id':'old'}})
        self.assertEqual(O.state('demo')['durum'],'kesildi')
        self.assertIsNone(O.state('demo')['izin'])

    def test_collect_keeps_session_output_and_failure(self):
        rows=[{'type':'session','id':'session-id'},{'type':'text','text':'answer'},{'type':'error','text':'quota'}]
        p=Mock(stdout=io.StringIO('\n'.join(json.dumps(x) for x in rows)));p.wait.return_value=1
        O.collect('demo',p)
        d=O.read_state('demo');self.assertEqual(d['session'],'session-id');self.assertEqual(d['durum'],'hata')
        self.assertEqual(d['mesajlar'][0]['metin'],'answer')

    def test_kurgu_delivery_queued_once_and_trust_required(self):
        directory=self.root/'projeler/demo/ana'
        entry={'seq':1,'notes':[{'text':'cut this','timecode':'00:02'}]}
        (directory/'.kurgu/inbox.jsonl').write_text(json.dumps(entry)+'\n')
        O.enqueue(directory,1);O.enqueue(directory,1)
        self.assertEqual(O.state('demo')['bekleyen_not'],1)
        self.assertTrue(O.drain('demo')['guven_gerekli'])
        with patch.object(O,'start',return_value={'ok':True}) as start:
            self.assertTrue(O.drain('demo',True)['ok'])
            self.assertIn('00:02 cut this', start.call_args.args[1])
        O.enqueue(directory,1);self.assertEqual(O.state('demo')['bekleyen_not'],0)

    def test_cancel_discards_pending_notes_and_preserves_files(self):
        queue=O.STORE/'queue/demo';queue.mkdir(parents=True);(queue/'note.json').write_text('{}')
        source=self.root/'projeler/demo/kaynak/source.txt';source.write_text('original')
        O.stop('demo');self.assertEqual(O.state('demo')['bekleyen_not'],0)
        self.assertEqual(source.read_text(),'original')

    def test_kurgu_old_completed_notes_are_not_replayed(self):
        directory=self.root/'projeler/demo/ana'
        (directory/'project.json').write_text(json.dumps({'notes':[{'id':'old','done':True},{'id':'new'}]}))
        entries=[{'seq':1,'notes':[{'id':'old','text':'old task'}]},{'seq':2,'notes':[{'id':'new','text':'new task'}]}]
        (directory/'.kurgu/inbox.jsonl').write_text('\n'.join(json.dumps(e) for e in entries))
        O.enqueue(directory,2)
        self.assertEqual(O.state('demo')['bekleyen_not'],1)

    def test_local_tool_roundtrip_no_unapproved_write(self):
        job={'proje':'demo','cfg':{'calisma_ortami':'ollama','model':'qwen'},'history':[{'rol':'user','metin':'write'}]}
        data=[{'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'write','arguments':{'path':'projeler/demo/generated.txt','text':'x'}}}]}}, {'message':{'role':'assistant','content':'denied'}}]
        captured=[]
        def call(url, body, **kw):captured.append(copy.deepcopy(body));return data.pop(0)
        with patch.object(O,'request',side_effect=call), patch.object(O,'ask',return_value={'allow':False}), patch.object(O,'emit'):
            self.assertEqual(O.local(job),'denied')
        self.assertFalse((self.root/'projeler/demo/generated.txt').exists())
        self.assertEqual(captured[-1]['messages'][-1]['role'],'tool')

    def call_panel(self, path, data):
        h=object.__new__(P.H);h.path=path;h.headers={'X-Panel':'1'};h._host_ok=lambda:True;h._govde_json=lambda:data
        h._json=lambda data,code=200:(code,data)
        with patch.object(P.ek(), 'guncelleme_m', return_value=__import__('guncelleme')):
            return h.do_POST()

    def test_panel_cancel_and_draft_route_preserve_project(self):
        fake=Mock();fake.guncelleme_m.return_value=__import__('guncelleme');fake.yerel_video_m.return_value.iptal.return_value={'ok':True}
        with patch.object(P,'ork',return_value=O),patch.object(P,'ek',return_value=fake):
            for action in ('iptal','taslak'):
                code, result=self.call_panel('/api/proje/'+action,{'proje':'demo'})
                self.assertEqual(code,200);self.assertTrue(result['ok'])
                fake.durum.return_value.yaz.assert_called_with('demo',action,'Kullanıcı panelden durdurdu; dosyalar korundu.')
        self.assertTrue((self.root/'projeler/demo').is_dir())

    def test_panel_delete_moves_only_project_to_trash(self):
        fake=Mock();source=self.root/'archive';source.mkdir();(source/'original.txt').write_text('original')
        with patch.object(P,'ork',return_value=O),patch.object(P,'ek',return_value=fake),patch.object(P,'ORTAM',self.root/'runtime'):
            code,result=self.call_panel('/api/proje/sil',{'proje':'demo'})
        self.assertEqual(code,200);self.assertTrue(result['ok'])
        self.assertFalse((self.root/'projeler/demo').exists())
        self.assertEqual(len(list((self.root/'runtime/cop').glob('demo-*'))),1)
        self.assertEqual((source/'original.txt').read_text(),'original')


class Transcription(unittest.TestCase):
    def test_missing_model_does_not_start_process(self):
        with patch.object(E,'dikte_durum',return_value={'hazir':False,'mesaj':'missing'}),patch.object(E.subprocess,'run') as run:
            with self.assertRaises(ValueError):E.dikte_coz(b'x'*3000)
        run.assert_not_called()

    def test_uses_installed_model_cpu_and_local_cache(self):
        def transcribe(cmd,**kw):
            self.assertIn('--local-only',cmd);self.assertIn('--cpu',cmd)
            self.assertEqual(cmd[cmd.index('--model')+1],'tiny')
            self.assertIn('HF_HUB_CACHE',kw['env'])
            Path(cmd[cmd.index('-o')+1]).write_text(json.dumps({'cumleler':[{'metin':'Merhaba dünya'}],'kelimeler':[],'sure':3,'dil':'tr','cihaz':'cpu'}),encoding='utf-8')
            return types.SimpleNamespace(returncode=0)
        with patch.object(E,'dikte_durum',return_value={'hazir':True,'model':'tiny'}),patch.object(E,'ses_temizle_m',return_value=types.SimpleNamespace(NW=O.NW)),patch.object(E.subprocess,'run',side_effect=transcribe):
            self.assertEqual(E.dikte_coz(b'x'*3000)['metin'],'Merhaba dünya')


class Video(unittest.TestCase):
    def test_import_and_status_never_download(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(V,'DIR',Path(tmp)),patch.object(V,'download') as download:
            self.assertFalse(V.durum()['kurulu'])
        download.assert_not_called()

    def test_no_success_on_failed_install(self):
        with patch.object(V,'IS',dict(V.IS)),patch.object(V,'supported',return_value=(False,'unsupported')):
            V._install();self.assertEqual(V.IS['hata'],'unsupported');self.assertFalse(V.IS['var'])

    def test_video_worker_preserves_script_arguments(self):
        import subprocess
        import runpy
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake_recipe.py';out=Path(tmp)/'args.json'
            p.write_text('import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n')
            with patch.object(sys,'argv',[str(V.__file__),'worker',str(p),str(out),'--frames','17']),patch.object(subprocess,'Popen',subprocess.Popen):
                runpy.run_path(str(V.__file__),run_name='__main__')
            self.assertEqual(json.loads(out.read_text()),['--frames','17'])


class SDK(unittest.TestCase):
    def test_question_permission_and_session_roundtrip(self):
        sdk=types.ModuleType('claude_agent_sdk');captured={};events=[]
        sdk.ClaudeAgentOptions=types.SimpleNamespace
        sdk.PermissionResultAllow=lambda **kw:kw
        sdk.PermissionResultDeny=lambda **kw:kw
        class Client:
            def __init__(self,options):captured['options']=options
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def query(self,prompt):
                captured['prompt']=prompt
                captured['permission']=await captured['options'].can_use_tool('AskUserQuestion',{'questions':[{'question':'Continue?'}]},None)
            async def receive_response(self):
                yield types.SimpleNamespace(content=[types.SimpleNamespace(text='answer')],session_id='sid',is_error=False)
        sdk.ClaudeSDKClient=Client
        with patch.dict(sys.modules,{'claude_agent_sdk':sdk}),patch.object(O,'configure_mcp'),patch.object(O,'ask',return_value={'allow':True,'answers':{'Continue?':'yes'}}),patch.object(O,'emit',side_effect=lambda typ,**kw:events.append((typ,kw))),patch.object(O.shutil,'which',return_value=None),patch.object(O.asyncio,'to_thread',AsyncMock(side_effect=lambda fn,*args:fn(*args))):
            # All awaits here are mocked immediate operations. Avoid Windows event-loop
            # socketpair creation, which is unavailable in restricted test environments.
            coro=O.claude({'proje':'demo','prompt':'hello','session':'old','cfg':{'model':'sonnet'}})
            with self.assertRaises(StopIteration):coro.send(None)
        self.assertEqual(captured['options'].resume,'old')
        self.assertEqual(captured['permission']['updated_input']['answers'],{'Continue?':'yes'})
        self.assertIn(('session',{'id':'sid'}),events)
        self.assertIn(('text',{'text':'answer'}),events)


class Setup(unittest.TestCase):
    def test_prerequisite_failure_blocks_completion(self):
        sys.path.insert(0,str(ROOT/'sistem/kurulum'))
        import sihirbaz as S
        initial=copy.deepcopy(S.D)
        process=Mock(stdout=io.BytesIO(b'installer failed\n'));process.wait.return_value=1
        with patch.object(S,'D',initial),patch.object(S.onkosul,'tara',return_value={'engel':['node']}),patch.object(S,'log_ekle'),patch.object(S.subprocess,'Popen',return_value=process) as spawn:
            S.kurulum_calistir()
            self.assertFalse(S.D['kurulum']['bitti'])
            self.assertIsNotNone(S.D['kurulum']['hata'])
            if os.name=='nt':
                self.assertEqual(spawn.call_count,1)
                self.assertIn('node',spawn.call_args.args[0])
                self.assertTrue(spawn.call_args.kwargs['creationflags'] & O.NW)

    def test_successful_installer_is_rechecked(self):
        if os.name!='nt':self.skipTest('Windows installer')
        import sihirbaz as S
        process=Mock(stdout=io.BytesIO(b'ok\n'));process.wait.return_value=0
        with patch.object(S,'D',copy.deepcopy(S.D)),patch.object(S.onkosul,'tara',return_value={'engel':['node']}),patch.object(S,'tara_yenile',return_value={'engel':['node'],'tamam':False}),patch.object(S,'log_ekle'),patch.object(S.onkosul,'yol_yenile'),patch.object(S.onkosul,'bul',return_value=None),patch.object(S.subprocess,'Popen',return_value=process) as spawn:
            S.kurulum_calistir()
            self.assertEqual(spawn.call_count,1)
            self.assertFalse(S.D['kurulum']['bitti'])
            self.assertIn('doğrulanamadı',S.D['kurulum']['hata'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(f'{result.testsRun-len(result.failures)-len(result.errors)} başarılı, {len(result.failures)+len(result.errors)} başarısız')
    sys.exit(0 if result.wasSuccessful() else 1)
