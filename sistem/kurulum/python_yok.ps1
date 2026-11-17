# YSTCoreStudio: Python yoksa resmi yukleyiciyi bu pencereden kurar.
param([switch]$Deneme)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

function PythonVarMi {
  $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
  if (Test-Path -LiteralPath $localPython) {
    & $localPython -c "import sys;sys.exit(0 if (3,10)<=sys.version_info<(3,14) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return $true }
  }
  $launcher = Get-Command py -ErrorAction SilentlyContinue
  if ($launcher) {
    foreach ($v in '3.12','3.13','3.11','3.10') {
      & $launcher.Source "-$v" -c "import sys" 2>$null
      if ($LASTEXITCODE -eq 0) { return $true }
    }
  }
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCommand) { return $false }
  & $pythonCommand.Source -c "import sys;sys.exit(0 if (3,10)<=sys.version_info<(3,14) else 1)" 2>$null
  return ($LASTEXITCODE -eq 0)
}
# winget/yukleyici PATH'e yeni ekleme yaptiysa bu surec gormez: kayit defterinden yenile
function YolYenile {
  $m = [Environment]::GetEnvironmentVariable('Path','Machine'); $u = [Environment]::GetEnvironmentVariable('Path','User')
  $env:Path = "$m;$u"
}

$f = New-Object System.Windows.Forms.Form
$f.Text = 'YSTCoreStudio - Python gerekli'
$f.Size = New-Object System.Drawing.Size(640,430)
$f.StartPosition = 'CenterScreen'
$f.TopMost = $false
$f.Font = New-Object System.Drawing.Font('Segoe UI',10)

$l = New-Object System.Windows.Forms.Label
$l.Location = New-Object System.Drawing.Point(16,12); $l.Size = New-Object System.Drawing.Size(600,60)
$l.Text = "Stüdyoyu açmak için bu bilgisayarda Python 3.10 - 3.13 kurulu olmalı (şu an bulunamadı). 'Python kur' düğmesine bas. İndirme ve kurulum burada otomatik yapılır; gerekirse aşağıdaki elle kurulum seçeneklerini kullanabilirsin."
$f.Controls.Add($l)

$t = New-Object System.Windows.Forms.TextBox
$t.Multiline = $true; $t.ReadOnly = $true; $t.ScrollBars = 'Vertical'
$t.Location = New-Object System.Drawing.Point(16,80); $t.Size = New-Object System.Drawing.Size(600,190)
$t.Font = New-Object System.Drawing.Font('Consolas',10)
$t.Text = "1) winget ile (önerilen, Windows 10/11):`r`n`r`n   winget install --id Python.Python.3.12 -e --source winget`r`n`r`n2) Elle indir:`r`n`r`n   https://www.python.org/downloads/windows/`r`n   (kurarken 'Add python.exe to PATH' kutusunu işaretle)"
$f.Controls.Add($t)

$k1 = New-Object System.Windows.Forms.Button; $k1.Text = 'Python kur'; $k1.Location = New-Object System.Drawing.Point(16,285); $k1.Size = New-Object System.Drawing.Size(190,32)
$script:installJob = $null
$k1.Add_Click({
  $k1.Enabled = $false
  $s.Text = 'Python indiriliyor ve kuruluyor... Bu pencereyi kapatmayin.'
  $script:installJob = Start-Job -ScriptBlock {
    param($scriptPath)
    $outputFile = [IO.Path]::GetTempFileName()
    $errorFile = [IO.Path]::GetTempFileName()
    try {
      $proc = Start-Process powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$scriptPath+'"'),'-Bilesen','python') -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile
      Get-Content -LiteralPath $outputFile
      Get-Content -LiteralPath $errorFile
      if ($proc.ExitCode -ne 0) { throw 'Python kurulumu basarisiz' }
    } finally {
      Remove-Item -LiteralPath $outputFile, $errorFile -ErrorAction SilentlyContinue
    }
  } -ArgumentList (Join-Path $PSScriptRoot 'on_kur.ps1')
})
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({
  if ($script:installJob -and $script:installJob.State -in @('Completed','Failed','Stopped')) {
    $output = Receive-Job $script:installJob 2>&1 | Out-String
    Remove-Job $script:installJob; $script:installJob = $null
    YolYenile
    if (PythonVarMi) { $f.DialogResult = [System.Windows.Forms.DialogResult]::OK; $f.Close() }
    else { $s.Text = 'Kurulum dogrulanamadi. ' + $output; $k1.Enabled = $true }
  }
})
$timer.Start()
$f.Controls.Add($k1)
$k2 = New-Object System.Windows.Forms.Button; $k2.Text = 'indirme adresini aç'; $k2.Location = New-Object System.Drawing.Point(216,285); $k2.Size = New-Object System.Drawing.Size(170,32)
$k2.Add_Click({ Start-Process 'https://www.python.org/downloads/windows/' })
$f.Controls.Add($k2)

$d = New-Object System.Windows.Forms.Button; $d.Text = 'Devam et'; $d.Location = New-Object System.Drawing.Point(396,285); $d.Size = New-Object System.Drawing.Size(110,32)
$d.Add_Click({
  YolYenile
  if (PythonVarMi) { $f.DialogResult = [System.Windows.Forms.DialogResult]::OK; $f.Close() }
  else { $s.Text = 'Python hâlâ bulunamadı. Kurulum bittiyse yeni bir pencerede dene ya da bilgisayarı yeniden başlat.'; $s.ForeColor = 'Firebrick' }
})
$f.Controls.Add($d)
$c = New-Object System.Windows.Forms.Button; $c.Text = 'Kapat'; $c.Location = New-Object System.Drawing.Point(516,285); $c.Size = New-Object System.Drawing.Size(100,32)
$c.Add_Click({ $f.DialogResult = [System.Windows.Forms.DialogResult]::Cancel; $f.Close() })
$f.Controls.Add($c)

$s = New-Object System.Windows.Forms.Label
$s.Location = New-Object System.Drawing.Point(16,330); $s.Size = New-Object System.Drawing.Size(600,50); $s.ForeColor = 'DimGray'
$s.Text = 'Sonraki adımlar (Git, Node.js, Claude Code vb.) için tarayıcıda bir kurulum sihirbazı açılacak; eksikleri orada görürsün.'
$f.Controls.Add($s)

if ($Deneme) { $f.Dispose(); exit 0 }
$r = $f.ShowDialog()
if ($r -eq [System.Windows.Forms.DialogResult]::OK) { exit 0 } else { exit 1 }
