"""Storyboard approval, timing and local measurements."""
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'araclar'))
import arka_indirme as downloads
import kurgu_plan as plan
import montaj_olcum as edit


class Montaj(unittest.TestCase):
    def test_explicit_style_name_is_recommended(self):
        candidates = plan.oner('Kısa bir tanıtımı Modüler vitrin şablonundan esinlenerek yap.')
        self.assertEqual(candidates[0]['id'], 'moduler-vitrin')
        self.assertNotIn('moduler-vitrin', {item['id'] for item in plan.oner('Modüler vitrin', 'moduler-vitrin')})

    def test_approval_belongs_to_displayed_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / plan.REQUIRED).touch()
            with self.assertRaises(ValueError):
                plan.kontrol(root)
            (root / 'hikaye_tahtasi.md').write_text('İlk sahne', encoding='utf-8')
            first = plan.durum(root)
            plan.onayla(root, first['revizyon'])
            plan.kontrol(root)
            (root / 'kesim_oneri.json').write_text('{"korunan":[[0,2]]}', encoding='utf-8')
            with self.assertRaises(ValueError):
                plan.kontrol(root)
            with self.assertRaises(ValueError):
                plan.onayla(root, first['revizyon'])

    def test_cut_keeps_word_times_in_output_coordinates(self):
        words = [{'baslangic': 0.1, 'bitis': 0.3, 'kelime': 'bir'},
                 {'baslangic': 1.1, 'bitis': 1.3, 'kelime': 'çıkar'},
                 {'baslangic': 2.2, 'bitis': 2.7, 'kelime': 'iki'}]
        result = edit.yeniden_zamanla(words, [[0, 1], [2, 3]])
        self.assertEqual([w['kelime'] for w in result['kelimeler']], ['bir', 'iki'])
        self.assertEqual(result['kelimeler'][1]['baslangic'], 1.2)
        self.assertEqual(result['sure'], 2)

    def test_missing_flag_parent_created_at_real_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sound = root / 'new-a' / 'sound'
            gpu = root / 'new-b' / 'gpu'
            with (
                patch.object(downloads, 'YEREL', root / 'unrelated'),
                patch.object(downloads, 'SES_ISTEMIYOR', sound),
                patch.object(downloads, 'GPU_ISTEMIYOR', gpu),
                patch.object(downloads, 'durum', return_value={}),
            ):
                downloads.ses_istemiyor()
                downloads.gpu_istemiyor()
                self.assertTrue(sound.exists() and gpu.exists())
                downloads.ses_istemiyor(False)
                self.assertFalse(sound.exists())

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg gerekli')
    def test_approved_silence_cut_exports_video_and_transcript(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            original = root / 'clip.mp4'
            edit.ff(['-f', 'lavfi', '-i', 'color=blue:s=80x80:d=3',
                     '-f', 'lavfi', '-i', 'sine=frequency=500:sample_rate=16000:duration=3',
                     '-af', "volume=enable='between(t,0.8,2.2)':volume=0",
                     '-c:v', 'libx264', '-c:a', 'aac', str(original)], capture_output=True)
            board = root / 'hikaye_tahtasi.md'
            board.write_text('Konuşma klibi', encoding='utf-8')
            proposal = edit.kesim_oner(root, original)
            self.assertEqual(len(proposal['korunan']), 2)
            (root / 'kesim_oneri.json').write_text(json.dumps(proposal), encoding='utf-8')
            transcript = root / 'transcript.json'
            words = [{'baslangic': 0.2, 'bitis': 0.4, 'kelime': 'ilk'},
                     {'baslangic': 2.5, 'bitis': 2.7, 'kelime': 'son'}]
            transcript.write_text(json.dumps({'kelimeler': words}), encoding='utf-8')
            result = root / 'hazir' / 'cut.mp4'
            with self.assertRaises(ValueError):
                edit.kesim_uygula(root, result, transcript)
            self.assertFalse(result.exists())
            plan.onayla(root, plan.durum(root)['revizyon'])
            edit.kesim_uygula(root, result, transcript)
            self.assertGreater(result.stat().st_size, 0)
            retimed = json.loads(result.with_suffix('.kelimeler.json').read_text(encoding='utf-8'))
            self.assertEqual(retimed['kelimeler'][1]['kelime'], 'son')
            self.assertLess(retimed['kelimeler'][1]['baslangic'], 2.5)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg gerekli')
    def test_real_first_frame_and_audio_peaks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / 'black.mp4'
            edit.ff(['-f', 'lavfi', '-i', 'color=black:s=80x80:d=0.1',
                     '-c:v', 'libx264', str(draft)], capture_output=True)
            frame = edit.ilk_kare(draft, root / 'first.png')
            self.assertTrue(frame['incelenmeli'])
            self.assertEqual(frame['karanlik_orani'], 1.0)
            source = root / 'beats.wav'
            values = bytearray(16000 * 5 * 2)
            for point in range(1, 9):
                for i in range(80):
                    struct.pack_into('<h', values, (point * 8000 + i) * 2, 23000 if i % 2 else -23000)
            with wave.open(str(source), 'wb') as output:
                output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                output.writeframes(values)
            result = edit.vuruslar(source)
            self.assertGreaterEqual(len(result['vuruslar']), 7)
            self.assertAlmostEqual(result['bpm_tahmin'], 120, delta=4)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Montaj))
    print(f'{result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)} başarılı, '
          f'{len(result.failures) + len(result.errors)} başarısız')
    sys.exit(0 if result.wasSuccessful() else 1)
