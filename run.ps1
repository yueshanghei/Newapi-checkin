# 运行入口（Jasonliu-0/Newapi-checkin 方案）：
#   .\run.ps1              执行签到（全部站点）
#   .\run.ps1 -Only hkkkj  只跑某个站点
#   .\run.ps1 --verbose    打印调试信息
#
# 作用：设置 UTF-8（避免 Windows 控制台 GBK 让中文/emoji 报 UnicodeEncodeError），
#       并补齐 Turnstile 需要的浏览器路径。
param(
    [string]$Only = "",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"   # 不能用 Stop：python 往 stderr 写日志会被当成致命错误

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) { $root = (Get-Location).Path }
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "未找到虚拟环境: $py" -ForegroundColor Red
    Write-Host "请先执行: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
# 本机没装 Chrome，用 Edge 过 Turnstile（.env 里也写了这个变量，这里再兜一层）
if (-not $env:TURNSTILE_CHROME_PATH) {
    $edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (Test-Path $edge) { $env:TURNSTILE_CHROME_PATH = $edge }
}
try { chcp 65001 > $null } catch {}

$argv = @()
if ($Only) { $argv += @("--only", $Only) }
if ($Verbose) { $argv += "--verbose" }

Push-Location $root
$code = 1
try {
    & $py -W ignore "run_checkin.py" @argv
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

Write-Host ""
if ($code -eq 0) { Write-Host "退出码 0：至少一个站点签到成功" -ForegroundColor Green }
else { Write-Host "退出码 $code：全部站点失败，请查看上面的日志" -ForegroundColor Yellow }
exit $code

