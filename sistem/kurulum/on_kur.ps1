# Official prerequisite installers. Called by the panel; never opens a console.
param([ValidateSet('python','node','git','claude','vcredist')][string]$Bilesen)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$downloadDir = Join-Path $taskRoot 'sistem\ortam\kurulum-indirme'
New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
function Install-Signed($Url, $Name, $Arguments, $Msi = $false) {
    $file = Join-Path $downloadDir $Name
    Write-Output "Indiriliyor: $Name"
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $file
    $signature = Get-AuthenticodeSignature -LiteralPath $file
    if ($signature.Status -ne 'Valid') { throw "Yukleyici imzasi dogrulanamadi: $Name" }
    Write-Output "Kuruluyor: $Name"
    if ($Msi) {
        $proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', ('"' + $file + '"'), '/qn', '/norestart') -WindowStyle Hidden -PassThru -Wait
    } else {
        $proc = Start-Process -FilePath $file -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait
    }
    if ($proc.ExitCode -notin @(0,3010,1641)) { throw "Kurulum cikis kodu: $($proc.ExitCode)" }
}
try {
    $ids = @{python='Python.Python.3.12';node='OpenJS.NodeJS.LTS';git='Git.Git';claude='Anthropic.ClaudeCode';vcredist='Microsoft.VCRedist.2015+.x64'}
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    $done = $false
    if ($winget) {
        & $winget.Source install --id $ids[$Bilesen] -e --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        $done = $LASTEXITCODE -eq 0
    }
    if (-not $done) {
        switch ($Bilesen) {
            'python' { Install-Signed 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' 'python-3.12.10-amd64.exe' @('/quiet','InstallAllUsers=0','PrependPath=1','Include_test=0') }
            'node' {
                $versions = Invoke-RestMethod 'https://nodejs.org/dist/index.json'
                $version = $versions | Where-Object { $_.lts -and $_.files -contains 'win-x64-msi' } | Select-Object -First 1
                if (-not $version) { throw 'Node LTS paketi bulunamadi' }
                $name = "node-$($version.version)-x64.msi"
                Install-Signed "https://nodejs.org/dist/$($version.version)/$name" $name @() $true
            }
            'git' {
                $release = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'
                $asset = $release.assets | Where-Object { $_.name -match '^Git-.*-64-bit.exe$' } | Select-Object -First 1
                if (-not $asset) { throw 'Git Windows paketi bulunamadi' }
                Install-Signed $asset.browser_download_url $asset.name @('/VERYSILENT','/NORESTART','/NOCANCEL','/SP-')
            }
            'claude' { throw 'Claude kurulumu tamamlanamadi. Yerel model secilebilir; winget hatasi yukarida.' }
            'vcredist' { Install-Signed 'https://aka.ms/vs/17/release/vc_redist.x64.exe' 'vc_redist.x64.exe' @('/install','/quiet','/norestart') }
        }
    }
    Write-Output 'Kurulum tamamlandi; surum yeniden denetlenecek.'
    exit 0
} catch {
    Write-Output ('HATA: ' + $_.Exception.Message)
    exit 1
}
