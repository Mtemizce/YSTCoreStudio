"""Panel launch routing regression: no terminal launch scripts."""
import sys, tempfile
from pathlib import Path
from unittest.mock import Mock, patch
R=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'sistem/panel'))
import panel as P
n=0
with tempfile.TemporaryDirectory() as tmp:
    project=Path(tmp)/'demo';project.mkdir();(project/'brief.md').write_text('brief')
    manager=Mock();manager.start.return_value={'ok':True,'panel':True}
    with patch.object(P,'proje_yolu',return_value=project),patch.object(P,'ork',return_value=manager),patch.object(P.subprocess,'Popen') as process:
        result=P.claude_baslat('demo',guven=True)
        assert result['panel'];n+=1
        args=manager.start.call_args.args
        assert args[0]=='demo' and '.claude/commands/video.md' in args[1] and args[2] is True;n+=1
        process.assert_not_called();n+=1
        try:P.claude_baslat('demo','final')
        except ValueError: n+=1
        else:raise AssertionError('Final must require approval')
        (project/'onay.json').write_text('{}')
        P.claude_baslat('demo','final')
        assert 'commands/final.md' in manager.start.call_args.args[1];n+=1
        P.claude_baslat(gorev='profil')
        assert manager.start.call_args.args[0]=='_profil';n+=1
print(f'{n} başarılı, 0 başarısız')
