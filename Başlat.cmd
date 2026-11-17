@echo off
rem YSTCoreStudio baslatici: cift tikla. Bu pencere hemen kapanir; studyo arka planda ayaga kalkar.
rem   Baslat.cmd           paneli sessizce ac (ilk seferde kurulum sihirbazi tarayicida acilir)
rem   Baslat.cmd claude    Claude Code'u bu klasorde ac
rem   Baslat.cmd varlik    inmeyen muzik/ses efektlerini tamamla
rem   Baslat.cmd durdur    arka plandaki paneli kapat
rem   Baslat.cmd kontrol   sistem analizi (hicbir sey degistirmez)
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "NoDefaultCurrentDirectoryInExePath=1"
set "PYTHONUTF8=1"

:bul
call :pybul
if defined PY goto :var
rem Python yok: pencerede kopyalanabilir kurulum bilgisi goster; "Devam et" ile tekrar tara
powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0sistem\kurulum\python_yok.ps1"
if errorlevel 1 exit /b 1
goto :bul

:var
if not "%~1"=="" goto :arg
start "" %PYW% "%~dp0sistem\kurulum\baslat.py"
exit /b 0

:arg
%PY% "%~dp0sistem\kurulum\baslat.py" %*
set "KOD=%errorlevel%"
if /i "%~1"=="kontrol" pause
exit /b %KOD%

:pybul
set "PY="
set "PYW="
for %%V in (3.12 3.13 3.11 3.10) do if not defined PY py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V" && set "PYW=pyw -%%V"
if defined PY exit /b 0
python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python" && set "PYW=pythonw"
if defined PY exit /b 0
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3" && set "PYW=pyw -3"
exit /b 0
