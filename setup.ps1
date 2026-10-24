param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Invoke-PythonStep {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python step failed: $($Arguments -join ' ')" }
}
Invoke-PythonStep $Python @('-c', 'import sys; assert (3,10) <= sys.version_info[:2] < (3,14), "Use Python 3.10-3.13 via -Python path/to/python.exe"')
if (!(Test-Path .venv/Scripts/python.exe)) {
    Invoke-PythonStep $Python @('-m', 'venv', '.venv')
}
$VenvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
Invoke-PythonStep $VenvPython @('-m', 'pip', 'install', '-r', 'requirements.txt')
Invoke-PythonStep $VenvPython @('scripts/setup_env.py')
Invoke-PythonStep $VenvPython @('-m', 'pytest', '-q')
Invoke-PythonStep $VenvPython @('scripts/print_addresses.py')
Write-Host ""
Write-Host "Next: put ASI1_API_KEY in .env, then:  .\.venv\Scripts\Activate.ps1 ; python run_all.py"
