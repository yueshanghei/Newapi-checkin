# 一键部署到 GitHub（建私有仓库 + 推代码 + 配 Secrets + 触发首次运行）
#
# 用法：
#   .\deploy_github.ps1 -Token ghp_xxxxxxxx
#   或先 set GH_TOKEN 再 .\deploy_github.ps1
#
# token 需要 classic PAT，勾选 repo + workflow
param(
    [string]$Token = $env:GH_TOKEN,
    [string]$Repo = "newapi-checkin",
    [string]$Only = ""
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) { $root = (Get-Location).Path }

if (-not $Token) {
    Write-Host "缺少 token：.\deploy_github.ps1 -Token ghp_xxx" -ForegroundColor Red
    exit 2
}

# 把 .env 里的配置读进环境变量（NEWAPI_ACCOUNTS / EMAIL_* 等）
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $i = $line.IndexOf("=")
            $k = $line.Substring(0, $i).Trim()
            $v = $line.Substring($i + 1).Trim()
            if ($k -and $v) { Set-Item -Path "env:$k" -Value $v }
        }
    }
    Write-Host "已从 .env 载入配置（NEWAPI_ACCOUNTS / EMAIL_*）" -ForegroundColor DarkGray
}

$env:GH_TOKEN = $Token
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$argsList = @((Join-Path $root "setup_github.py"), "--repo", $Repo)
if ($Only) { $argsList += @("--only", $Only) }

& (Join-Path $root ".venv\Scripts\python.exe") -W ignore @argsList
exit $LASTEXITCODE

