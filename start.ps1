param([int]$Port=8000)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) { throw '请先安装 Python 3.12，并将 python 加入 PATH。详细步骤见 README.md。' }
    & $PythonCommand.Source -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败。' }
}
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath '.venv\.dependencies-ready')) {
    & $PythonExe -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。请检查网络。' }
    New-Item -ItemType File -Path '.venv\.dependencies-ready' -Force | Out-Null
}
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw '缺少前端构建。请执行 README 中的 pnpm build 步骤。' }
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
Write-Host "工作台：http://127.0.0.1:$Port （Ctrl+C 停止；请勿使用多 worker）"
& $PythonExe -m uvicorn econworkbench.api:app --host 127.0.0.1 --port $Port --workers 1
