[CmdletBinding()]
param(
    [ValidateSet('1080p','720p','Original')] [string]$ProfileName = '1080p',
    [ValidateSet('Smooth','Sharp','xBR')] [string]$Filter = 'Smooth',
    [string]$Source,
    [string]$WrapperZip,
    [switch]$MovieFix,
    [switch]$SetupOnly
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type 'using System.Runtime.InteropServices; public static class DisplayMode { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[void][DisplayMode]::SetProcessDPIAware()
$runtime = Join-Path $PSScriptRoot 'PrivateGame'
$cacheHash = '0B13AB89A64C9918189B1DADD449EF6ED3CB3B7B19CABD96D8ADBD95505BB908'
$release = 'https://github.com/FunkyFr3sh/cnc-ddraw/releases/download/v7.1.0.0/cnc-ddraw.zip'
$mutex = New-Object System.Threading.Mutex($false,'Local\ReturnFireHDLauncher')
try {
    if (!$mutex.WaitOne(0)) { throw 'Another launcher is already running.' }
    if (!(Test-Path -LiteralPath $runtime)) {
        if (!$Source) {
            $picker = New-Object System.Windows.Forms.FolderBrowserDialog
            $picker.Description = 'Choose your Windows Return Fire folder containing RFIRE.BIN'
            if ($picker.ShowDialog() -ne 'OK') { return }
            $Source = $picker.SelectedPath
        }
        $Source = (Resolve-Path -LiteralPath $Source).Path
        foreach ($name in 'RFIRE.BIN','ART\ART.CAR','SOUND','TITLE','WORLDS\1PLAYER') {
            if (!(Test-Path -LiteralPath (Join-Path $Source $name))) { throw "Missing $name in the selected PC game folder." }
        }
        $stage = Join-Path $PSScriptRoot ('.setup-' + [guid]::NewGuid())
        New-Item -ItemType Directory -Path $stage | Out-Null
        try {
            foreach ($name in 'ART','SOUND','TITLE','WORLDS','CONFIG.BIN','RFIRE.HLP','RFIRE.CNT') {
                $item = Join-Path $Source $name
                if (Test-Path -LiteralPath $item) { Copy-Item -LiteralPath $item -Destination $stage -Recurse }
            }
            Copy-Item -LiteralPath (Join-Path $Source 'RFIRE.BIN') -Destination (Join-Path $stage 'ReturnFireGame.exe')
            if (Test-Path -LiteralPath (Join-Path $Source 'Langs\RFireEng.dll')) {
                $englishFiles = @{
                    'RFireEng.dll' = 'Lang.dll'
                    'CnfgEng.bin' = 'Config.bin'
                    'RFireEng.hlp' = 'RFire.hlp'
                    'RFireEng.cnt' = 'RFire.cnt'
                }
                foreach ($name in $englishFiles.Keys) {
                    Copy-Item -LiteralPath (Join-Path $Source "Langs\$name") -Destination (Join-Path $stage $englishFiles[$name]) -Force
                }
            }
            if (!$WrapperZip) {
                $WrapperZip = Join-Path $stage 'wrapper.zip'
                Invoke-WebRequest -UseBasicParsing -Uri $release -OutFile $WrapperZip
            }
            $archivePath = (Resolve-Path -LiteralPath $WrapperZip).Path
            $stream = [IO.File]::OpenRead($archivePath)
            $sha = [Security.Cryptography.SHA256]::Create()
            try { $actualHash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
            finally { $stream.Dispose(); $sha.Dispose() }
            if ($actualHash -ne $cacheHash) { throw 'Unexpected cnc-ddraw archive checksum.' }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $WrapperZip).Path)
            try {
                [IO.Compression.ZipFileExtensions]::ExtractToFile($zip.GetEntry('ddraw.dll'), (Join-Path $stage 'ddraw.dll'))
            } finally { $zip.Dispose() }
            if (Test-Path -LiteralPath (Join-Path $stage 'wrapper.zip')) { Remove-Item -LiteralPath (Join-Path $stage 'wrapper.zip') }
            [IO.Directory]::Move($stage,$runtime)
        } finally {
            if (Test-Path -LiteralPath $stage) {
                $resolved = (Resolve-Path -LiteralPath $stage).Path
                if ((Split-Path $resolved) -eq $PSScriptRoot -and (Split-Path $resolved -Leaf) -match '^\.setup-[0-9a-f-]{36}$') { Remove-Item -LiteralPath $resolved -Recurse -Force }
            }
        }
    }
    if ($SetupOnly) { return }
    if (Get-Process -Name ReturnFireGame,ReturnFireMovieFix -ErrorAction SilentlyContinue) { throw 'Close the running Return Fire game before launching this edition.' }
    $gameName = 'ReturnFireGame.exe'
    if ($MovieFix) {
        $original = [IO.File]::ReadAllBytes((Join-Path $runtime $gameName))
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $sourceHash = [BitConverter]::ToString($sha.ComputeHash($original)).Replace('-','')
            if ($sourceHash -ne 'DC79163FC1C935CF3D4D8F7E68964F46990E439B41414960F2DA6C77EB1684E2') {
                throw 'The experimental movie fix requires the verified English ISO edition.'
            }
            # Use the existing native-size movie buffer and software copy path.
            # Signal frame completion after copying to the DirectDraw surface.
            $original[0x1da5f] = $original[0x1da60] = 0x90
            $original[0x1dbd7] = $original[0x1dbd8] = 0x90
            $original[0x1dc12] = 0x90
            $resultHash = [BitConverter]::ToString($sha.ComputeHash($original)).Replace('-','')
            if ($resultHash -ne '90CD971AFF6570AE508D3011C6A0A84B9F61B433F3FEF568BBF5854F14DE9DD8') {
                throw 'Movie fix verification failed.'
            }
            $gameName = 'ReturnFireMovieFix.exe'
            [IO.File]::WriteAllBytes((Join-Path $runtime $gameName), $original)
        } finally { $sha.Dispose() }
    }
    $desktop = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $target = @{ '1080p' = 1080; '720p' = 720; 'Original' = 480 }[$ProfileName]
    $height = [int][Math]::Min($target, $desktop.Height)
    $width = [int][Math]::Min([Math]::Floor($height * 16 / 9), $desktop.Width)
    if ($ProfileName -eq 'Original') { $width = [Math]::Min(640,$desktop.Width) }
    $sampling = if ($Filter -eq 'Sharp') { 0 } else { 2 }
    $graphics = @('renderer=direct3d9',"d3d9_filter=$sampling")
    if ($Filter -eq 'xBR') {
        $shader = 'xbr-lv2-noblend.glsl'
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $shader) -Destination $runtime -Force
        $graphics = @('renderer=opengl',"shader=$shader")
    }
    $display = @('[ddraw]',"width=$width","height=$height",'windowed=true','fullscreen=false','border=false','maintas=true','aspect_ratio=4:3','boxing=false')
    ($display + $graphics + @('fake_mode=640x480x8','savesettings=0','resizable=false','adjmouse=true','posX=-32000','posY=-32000')) | Set-Content -LiteralPath (Join-Path $runtime 'ddraw.ini') -Encoding ASCII
    $drive = $null
    foreach ($letter in 'S','T','U','V','W','X','Y','Z') {
        $candidate = $letter + ':'
        & subst.exe $candidate $runtime 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $drive = $candidate; break }
    }
    if (!$drive) { throw 'No temporary drive letter available between S and Z.' }
    try {
        $install = 'HKCU:\Software\Classes\VirtualStore\MACHINE\SOFTWARE\WOW6432Node\Silent Software, Inc.\Return Fire\1.0'
        $config = 'HKCU:\Software\Silent Software, Inc.\Return Fire\1.0\Configuration'
        foreach ($key in $install,$config) { if (!(Test-Path $key)) { New-Item $key -Force | Out-Null } }
        New-ItemProperty $install -Name 'Installed Path' -Value $runtime -PropertyType String -Force | Out-Null
        New-ItemProperty $install -Name 'Installation Complete' -Value 1 -PropertyType DWord -Force | Out-Null
        New-ItemProperty $config -Name 'Full Screen' -Value 1 -PropertyType DWord -Force | Out-Null
        $p = Start-Process ($drive + '\' + $gameName) -WorkingDirectory ($drive + '\') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Return Fire exited with code $($p.ExitCode)." }
    } finally { & subst.exe $drive /d | Out-Null }
} finally { $mutex.Dispose() }
