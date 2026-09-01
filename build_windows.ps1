param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$Version = $Version.TrimStart("v")
if ($Version -notmatch '^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$') {
    throw "Version must be semantic, for example 2.11.0"
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root "build\windows-x64"
$Resources = Join-Path $Build "app"
$PythonDir = Join-Path $Resources "python"
$Dist = Join-Path $Root "dist"
$Archive = Join-Path $Build "python.tar.gz"
$PythonTag = "20260602"
$PythonFile = "cpython-3.12.13%2B20260602-x86_64-pc-windows-msvc-install_only.tar.gz"
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PythonTag/$PythonFile"
$PythonExe = Join-Path $PythonDir "python.exe"
$Output = Join-Path $Dist "RealtimeSubtitle-$Version-windows-x64-setup.exe"

Write-Host "Building Realtime Subtitle $Version for Windows x64"
Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
New-Item $Resources -ItemType Directory -Force | Out-Null
New-Item $Dist -ItemType Directory -Force | Out-Null

Write-Host "[1/7] Portable Python"
Invoke-WebRequest -Uri $PythonUrl -OutFile $Archive
New-Item $PythonDir -ItemType Directory -Force | Out-Null
tar -xzf $Archive -C $PythonDir --strip-components=1
if (-not (Test-Path $PythonExe)) { throw "Portable Python is incomplete" }
& $PythonExe -m pip install --disable-pip-version-check --quiet "PyQt6>=6.5,<6.12" "huggingface-hub>=0.20,<2"

Write-Host "[2/7] Application sources"
$ExcludedDirectories = @(".git", ".github", ".venv", ".python_cache", ".pytest_cache", "build", "dist", "docs", "tests", "tools", "benchmarks", "demo", "wheelhouse", "__pycache__")
$ExcludedFiles = @("*.dmg", "*.pyc", ".DS_Store")
Get-ChildItem $Root -Force | ForEach-Object {
    $Entry = $_
    $Excluded = $Entry.Name -in $ExcludedDirectories
    foreach ($Pattern in $ExcludedFiles) {
        if ($Entry.Name -like $Pattern) { $Excluded = $true }
    }
    if (-not $Excluded) {
        Copy-Item $Entry.FullName -Destination $Resources -Recurse -Force
    }
}
Remove-Item (Join-Path $Resources "build_windows.ps1") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Resources "build_dmg.sh") -Force -ErrorAction SilentlyContinue

$Commit = (git -C $Root rev-parse --short=10 HEAD 2>$null)
if (-not $Commit) { $Commit = "unknown" }
$BuildTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
@"
BUILD_VERSION = "$Version"
BUILD_COMMIT = "$Commit"
BUILD_TIME = "$BuildTime"
BUILD_ARCH = "x86_64"
BUILD_PLATFORM = "windows"
"@ | Set-Content (Join-Path $Resources "version.py") -Encoding UTF8

Write-Host "[3/7] Offline wheelhouse"
$Wheelhouse = Join-Path $Resources "wheelhouse"
New-Item $Wheelhouse -ItemType Directory -Force | Out-Null
& $PythonExe -m pip download --dest $Wheelhouse --only-binary=:all: -r (Join-Path $Resources "requirements-core.txt")
$WheelCount = @(Get-ChildItem $Wheelhouse -Filter "*.whl").Count
if ($WheelCount -lt 8) { throw "Wheelhouse is incomplete ($WheelCount wheels)" }
$TestVenv = Join-Path $Build "verify-venv"
& $PythonExe -m venv $TestVenv
$TestPython = Join-Path $TestVenv "Scripts\python.exe"
& $TestPython -m pip install --no-index --find-links $Wheelhouse -r (Join-Path $Resources "requirements-core.txt")
& $TestPython -c "import PyQt6,numpy,soundcard,httpx,openai,faster_whisper,sentencepiece"
Remove-Item $TestVenv -Recurse -Force

Write-Host "[4/7] Bundled recognition and translation models"
& $PythonExe (Join-Path $Root "tools\bundle_release_models.py") $Resources

Write-Host "[5/7] Windows icon"
$IconDir = Join-Path $Resources "assets\icon"
$Icon = Join-Path $IconDir "AppIcon.ico"
$Png = Join-Path $IconDir "realtime-subtitle-icon.png"
Add-Type -AssemblyName System.Drawing
$SourceImage = [System.Drawing.Image]::FromFile($Png)
$Sizes = @(256, 128, 64, 48, 32, 16)
$Payloads = @()
foreach ($Size in $Sizes) {
    $Bitmap = New-Object System.Drawing.Bitmap($Size, $Size)
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $Graphics.DrawImage($SourceImage, 0, 0, $Size, $Size)
    $Stream = New-Object System.IO.MemoryStream
    $Bitmap.Save($Stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $Payloads += ,$Stream.ToArray()
    $Graphics.Dispose()
    $Bitmap.Dispose()
    $Stream.Dispose()
}
$SourceImage.Dispose()
$File = [System.IO.File]::Open($Icon, [System.IO.FileMode]::Create)
$Writer = New-Object System.IO.BinaryWriter($File)
$Writer.Write([UInt16]0); $Writer.Write([UInt16]1); $Writer.Write([UInt16]$Sizes.Count)
$Offset = 6 + (16 * $Sizes.Count)
for ($Index = 0; $Index -lt $Sizes.Count; $Index++) {
    $Size = $Sizes[$Index]
    $Writer.Write([Byte]$(if ($Size -eq 256) { 0 } else { $Size }))
    $Writer.Write([Byte]$(if ($Size -eq 256) { 0 } else { $Size }))
    $Writer.Write([Byte]0); $Writer.Write([Byte]0)
    $Writer.Write([UInt16]1); $Writer.Write([UInt16]32)
    $Writer.Write([UInt32]$Payloads[$Index].Length)
    $Writer.Write([UInt32]$Offset)
    $Offset += $Payloads[$Index].Length
}
foreach ($Payload in $Payloads) { $Writer.Write($Payload) }
$Writer.Dispose(); $File.Dispose()
if (-not (Test-Path $Icon)) { throw "Windows icon generation failed" }

Write-Host "[6/7] Inno Setup installer"
$Iss = Join-Path $Build "RealtimeSubtitle.iss"
$EscResources = $Resources
$EscOutput = $Output
$EscIcon = $Icon
@"
[Setup]
AppId={{AA8B9D69-AB57-4EF1-B827-4D9E23E53F35}
AppName=Realtime Subtitle
AppVersion=$Version
AppPublisher=Dreaminmaster
AppPublisherURL=https://github.com/Dreaminmaster/realtime-subtitle-product
DefaultDirName={localappdata}\Programs\Realtime Subtitle
DefaultGroupName=Realtime Subtitle
UninstallDisplayIcon={app}\assets\icon\AppIcon.ico
OutputDir=$([IO.Path]::GetDirectoryName($EscOutput))
OutputBaseFilename=$([IO.Path]::GetFileNameWithoutExtension($EscOutput))
SetupIconFile=$EscIcon
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=$Version
VersionInfoDescription=Realtime Subtitle for Windows

[Files]
Source: "$EscResources\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Realtime Subtitle"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon\AppIcon.ico"
Name: "{autodesktop}\Realtime Subtitle"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon\AppIcon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launcher.py"""; WorkingDir: "{app}"; Description: "Launch Realtime Subtitle"; Flags: nowait postinstall skipifsilent
"@ | Set-Content $Iss -Encoding UTF8

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) { throw "Inno Setup 6 was not found" }
& $Iscc $Iss
if (-not (Test-Path $Output)) { throw "Installer was not created: $Output" }

Write-Host "[7/7] Verify installer"
if ((Get-Item $Output).Length -lt 100MB) { throw "Installer is unexpectedly small" }
$Hash = (Get-FileHash $Output -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "SHA256 $Hash  $([IO.Path]::GetFileName($Output))"
Write-Host "Built $Output"
