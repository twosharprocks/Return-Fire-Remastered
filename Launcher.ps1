[CmdletBinding()]
param(
    [ValidateSet('1080p','720p','Original')] [string]$ProfileName = '1080p',
    [ValidateSet('Smooth','Sharp','xBR')] [string]$Filter = 'Smooth',
    [string]$Source,
    [string]$WrapperZip,
    [switch]$MovieFix,
    [switch]$BuildCinematics,
    [switch]$HDCinematics,
    [switch]$WidescreenTrial,
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
    if ($BuildCinematics) {
        if (!$Source -and !(Test-Path "$runtime/Title/rf.stm")) {
            $picker = New-Object System.Windows.Forms.FolderBrowserDialog
            $picker.Description = 'Choose the mounted or extracted English Return Fire ISO folder'
            if ($picker.ShowDialog() -ne 'OK') { return }
            $Source = $picker.SelectedPath
        }
        $mediaSource = if ($Source) { $Source } else { $runtime }
        & python (Join-Path $PSScriptRoot 'build_cinematics.py') $mediaSource (Join-Path $PSScriptRoot 'HD-Cinematics')
        if ($LASTEXITCODE) { throw 'Cinematic conversion failed.' }
        return
    }
    if ($HDCinematics) {
        foreach ($film in 'rf','win','win1','win2','win3') {
            if (!(Test-Path "$PSScriptRoot/HD-Cinematics/$film.mp4")) { throw 'Run Play.cmd -BuildCinematics first.' }
        }
        & python -c 'import cv2, psutil'
        if ($LASTEXITCODE) { throw 'HD playback requires opencv-python and psutil in your Python environment.' }
    }
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
    if (Get-Process -Name ReturnFireGame,ReturnFireMovieFix,ReturnFireWide -ErrorAction SilentlyContinue) { throw 'Close the running Return Fire game before launching this edition.' }
    $gameName = 'ReturnFireGame.exe'
    if ($MovieFix -or $WidescreenTrial -or $HDCinematics) {
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
            if ($WidescreenTrial) {
                # The trial expands the presentation surface and the logical battlefield together.
                foreach ($offset in 0x49c08,0x1957,0x2e728,0x2f5ea,0x2fdd9,0x31344,0x3145f,0x314a9) {
                    [BitConverter]::GetBytes([uint16]856).CopyTo($original, $offset)
                }
                foreach ($offset in 0xc6b0,0x2f4df,0x312d0,0x313b2,0x313f5,0x2e7e3,0xf5f2,0xf623,0x30314,0x304ba) {
                    [BitConverter]::GetBytes([uint16]428).CopyTo($original, $offset)
                }
                [BitConverter]::GetBytes([uint16]396).CopyTo($original, 0xf643)
                $original[0x3037f] = 214
                $wideHash = [BitConverter]::ToString($sha.ComputeHash($original)).Replace('-','')
                if ($wideHash -ne 'DE123BDB21262A2C0FF4F33C7FBC8D11FFDE5C813BACE83CFEDF1E63F056F0B0') {
                    throw 'Widescreen trial verification failed.'
                }
                $gameName = 'ReturnFireWide.exe'
            }
            [IO.File]::WriteAllBytes((Join-Path $runtime $gameName), $original)
        } finally { $sha.Dispose() }
    }
    $desktop = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $target = @{ '1080p' = 1080; '720p' = 720; 'Original' = 480 }[$ProfileName]
    $height = [int][Math]::Min($target, $desktop.Height)
    $width = [int][Math]::Min([Math]::Floor($height * 16 / 9), $desktop.Width)
    if ($ProfileName -eq 'Original' -and !$WidescreenTrial) { $width = [Math]::Min(640,$desktop.Width) }
    $sampling = if ($Filter -eq 'Sharp') { 0 } else { 2 }
    $graphics = @('renderer=direct3d9',"d3d9_filter=$sampling")
    if ($Filter -eq 'xBR') {
        $shader = 'xbr-lv2-noblend.glsl'
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $shader) -Destination $runtime -Force
        $graphics = @('renderer=opengl',"shader=$shader")
    }
    $aspect = if ($WidescreenTrial) { '16:9' } else { '4:3' }
    $mode = if ($WidescreenTrial) { '856x480x8' } else { '640x480x8' }
    $display = @('[ddraw]',"width=$width","height=$height",'windowed=true','fullscreen=false','border=false','maintas=true',"aspect_ratio=$aspect",'boxing=false')
    ($display + $graphics + @("fake_mode=$mode",'savesettings=0','resizable=false','adjmouse=true','posX=-32000','posY=-32000')) | Set-Content -LiteralPath (Join-Path $runtime 'ddraw.ini') -Encoding ASCII
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
        $p = Start-Process ($drive + '\' + $gameName) -WorkingDirectory ($drive + '\') -PassThru
        try {
            if ($HDCinematics) {
                $timer = [Diagnostics.Stopwatch]::StartNew()
                while (!$p.HasExited -and !$p.MainWindowHandle -and $timer.Elapsed.TotalSeconds -lt 30) {
                    Start-Sleep -Milliseconds 100
                    $p.Refresh()
                }
                if ($p.MainWindowHandle) {
                    & python (Join-Path $PSScriptRoot 'hd_player.py') $p.Id $p.MainModule.BaseAddress.ToInt64() $runtime
                    if ($LASTEXITCODE) { Write-Warning 'HD playback ended. Native playback is available.' }
                }
            }
        } finally { $p.WaitForExit() }
        if ($p.ExitCode -ne 0) { throw "Return Fire exited with code $($p.ExitCode)." }
    } finally { & subst.exe $drive /d | Out-Null }
} finally { $mutex.Dispose() }
