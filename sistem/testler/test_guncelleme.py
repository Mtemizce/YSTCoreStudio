"""Hermetic update tests: no network, installs or real user data."""
import sys, unittest, tempfile, io, json, zipfile, hashlib
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'araclar'))
import guncelleme as G

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name,rel in [('ROOT','.'),('SISTEM','sistem'),('ORTAM','sistem/ortam'),('CONF','sistem/ortam/config.json'),('DURUM','sistem/ortam/durum.json'),('RAPOR','sistem/ortam/rapor.json'),('YEDEK','sistem/ortam/yedek'),('REVIZYON','sistem/ortam/rev.json')]:
            p=patch.object(G,name,self.root/rel);p.start();self.addCleanup(p.stop)
        for name,value in [('MESGUL',lambda:[]),('CALISIYOR',dict(var=False,bitti=False,log=[],hata='',adim=''))]:
            p=patch.object(G,name,value);p.start();self.addCleanup(p.stop)
    def package(self,extra=None):
        p=self.root/'update.zip'
        with zipfile.ZipFile(p,'w') as z:
            for n,b in {'sistem/surum.json':'{"uygulama":"2.0.0"}','sistem/panel/panel.py':'new',**(extra or {})}.items():
                info=zipfile.ZipInfo();info.filename='release/'+n;z.writestr(info,b)
        return p
    def test_public_default(self):
        self.assertTrue(G.ayar_oku()['etkin']);self.assertFalse(G.ayar_oku()['jeton_var'])
    def test_tokenless_check(self):
        with patch.object(G,'_api_json',return_value={'id':7,'tag_name':'v2.0.0'}) as api:
            self.assertTrue(G.kontrol()['var']);self.assertEqual(api.call_args.args[1],'')
    def test_check_does_not_install(self):
        with patch.object(G,'_api_json',return_value={'id':7,'tag_name':'v2.0.0'}),patch.object(G,'_yerlestir') as put:
            G.kontrol();put.assert_not_called()
    def test_repo_change_drops_token(self):
        G.ayar_yaz('owner/one','a'*30);G.ayar_yaz('owner/two');self.assertFalse(G.ayar_oku()['jeton_var'])
    def test_disabled(self):
        G.ayar_yaz('');self.assertFalse(G.ayar_oku()['etkin'])
    def test_no_auth_to_assets(self):
        with patch.object(G.urllib.request,'build_opener') as op:
            G._istek('https://assets.example/file','secret');self.assertIsNone(op.return_value.open.call_args.args[0].get_header('Authorization'))
    def test_anonymous_headers(self):
        with patch.object(G.urllib.request,'build_opener') as op:
            G._istek('/repos/a/b','');self.assertIsNone(op.return_value.open.call_args.args[0].get_header('Authorization'))
    def test_missing_checksum(self):
        with patch.object(G,'_api_json',return_value={'assets':[{'name':'YSTCoreStudio-2.0.0.zip','url':'/asset'}]}):
            with self.assertRaises(ValueError):G._surum_paketi(G.config(),{'release_id':7})
    def test_checksum_mismatch(self):
        with patch.object(G,'_istek',return_value=io.BytesIO(b'bad')):
            with self.assertRaises(ValueError):G._indir('/file','',self.root/'file.zip','0'*64)
        self.assertFalse((self.root/'file.zip').exists())
    def test_protected_case(self):
        G._yerlestir(self.package({'KIMLIK/secret':'replace','PROJELER/a/file':'replace','sistem/ayar/kullanici.json':'replace'}))
        self.assertFalse((self.root/'KIMLIK').exists());self.assertFalse((self.root/'PROJELER').exists())
    def test_traversal_rejected_before_write(self):
        with self.assertRaises(ValueError):G._yerlestir(self.package({'../escape':'bad'}))
        self.assertFalse((self.root/'sistem/panel/panel.py').exists())
    def test_windows_backslash_rejected(self):
        with self.assertRaises(ValueError):G._yerlestir(self.package({'dir'+chr(92)+'bad':'bad'}))
    def test_case_collision(self):
        with self.assertRaises(ValueError):G._yerlestir(self.package({'x':'a','X':'b'}))
    def test_rollback(self):
        old=self.root/'sistem/panel/panel.py';old.parent.mkdir(parents=True);old.write_text('old')
        backup=G.yedekle();G._yerlestir(self.package(),backup);G._geri_al(backup)
        self.assertEqual(old.read_text(),'old');self.assertFalse((self.root/'sistem/surum.json').exists())
    def test_active_work_blocks(self):
        with patch.object(G,'MESGUL',return_value=['render']),patch.object(G.threading,'Thread') as thread:
            self.assertFalse(G.guncelle_baslat()['ok']);thread.assert_not_called()
    def test_double_click(self):
        with patch.object(G.threading,'Thread') as thread:
            self.assertTrue(G.guncelle_baslat()['ok']);self.assertFalse(G.guncelle_baslat()['ok']);self.assertEqual(thread.call_count,1)
    def test_dirty_clone(self):
        with patch.object(G,'_git',return_value=Mock(returncode=0,stdout=' M file')) as git:
            with self.assertRaises(ValueError):G._git_kur(G.config(),{'sha':'a'*40})
            self.assertEqual(git.call_count,1)
    def test_failed_dependencies_not_success(self):
        pkg=self.package()
        with patch.object(G,'kontrol',return_value={'var':True,'hata':'','yeni':'2','release_id':7}),patch.object(G,'_surum_paketi',return_value=pkg),patch.object(G,'_sonrasi',side_effect=RuntimeError('pip failed')):
            G._is()
        r=json.loads(G.RAPOR.read_text(encoding='utf-8'));self.assertFalse(r['ok']);self.assertTrue(r['onarim_gerekli']);self.assertFalse((self.root/'sistem/panel/panel.py').exists())
    def test_success_requires_manual_restart(self):
        pkg=self.package()
        with patch.object(G,'kontrol',return_value={'var':True,'hata':'','yeni':'2','release_id':7}),patch.object(G,'_surum_paketi',return_value=pkg),patch.object(G,'_sonrasi',return_value=[]),patch.object(G,'yeniden_baslat') as restart:
            G._is();restart.assert_not_called()
        self.assertTrue(G.CALISIYOR['yeniden_baslat']);self.assertTrue(json.loads(G.RAPOR.read_text(encoding='utf-8'))['ok'])
    def test_restart_blocked_during_work(self):
        with patch.object(G,'MESGUL',return_value=['render']),patch.object(G.subprocess,'Popen') as spawn:
            with self.assertRaises(ValueError):G.yeniden_baslat()
            spawn.assert_not_called()

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(f'{r.testsRun-len(r.failures)-len(r.errors)} başarılı, {len(r.failures)+len(r.errors)} başarısız')
    sys.exit(0 if r.wasSuccessful() else 1)
