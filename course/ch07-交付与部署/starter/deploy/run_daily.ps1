<#
    每日任务包装器（Windows 任务计划程序调它，不直接调 python）。

    为什么需要这层壳：
      - 统一设置工作目录与环境变量（计划程序的默认目录不是项目目录）
      - 把「业务失败」和「检查失败」合成一个退出码
      - 失败时自动发告警（默认 dry-run，加 -Send 才真发）
      - 所有输出重定向到日志文件，便于事后排查

    用法：
      .\run_daily.ps1                          # 跑昨天
      .\run_daily.ps1 -Date 2026-11-18         # 指定日期（回补）
      .\run_daily.ps1 -Date 2026-11-18 -Send   # 真发告警
#>
[CmdletBinding()]
param(
    [string]$ProjectDir,
    [string]$DataDir,
    [string]$Python = "python",
    [string]$Date = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd"),
    [switch]$Send,
    [switch]$CheckReconcile
)

$ErrorActionPreference = "Stop"
$ErrorActionPreference = "Continue"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
# $here 是 .../starter/deploy，往上三层才是 course/
if (-not $ProjectDir) { $ProjectDir = (Resolve-Path (Join-Path $here "..\..\..\ch04-Python数据管道\solution")).Path }
if (-not $DataDir)    { $DataDir    = (Resolve-Path (Join-Path $here "..\..\..\ch03-数据接入与对账\data\raw")).Path }

if (-not (Test-Path (Join-Path $ProjectDir "run.py"))) {
    Write-Host "项目目录里没有 run.py：$ProjectDir" -ForegroundColor Red
    exit 2
}

$outDir  = Join-Path $ProjectDir "output"
$logDir  = Join-Path $ProjectDir "logs"
$logFile = Join-Path $logDir ("daily-{0}.log" -f (Get-Date -Format "yyyyMMdd"))
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log([string]$msg) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

Write-Log "=== 开始 date=$Date project=$ProjectDir ==="

# ---- 1. 跑管道
Push-Location $ProjectDir
& $Python "run.py" --start $Date --end $Date 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
$runCode = $LASTEXITCODE
Pop-Location
Write-Log "管道退出码 = $runCode"

# ---- 2. 健康检查
$healthJson = & $Python -m ops.healthcheck --data-dir $DataDir --out-dir $outDir --date $Date --json $(if ($CheckReconcile) { "" } else { "--skip-reconcile" })
$healthCode = $LASTEXITCODE
Write-Log "健康检查退出码 = $healthCode"
Write-Log $healthJson

# ---- 3. 合并退出码：只要有一个非 0，就按更严重的算
if (-not $runCode) { $runCode = 0 }
if (-not $healthCode) { $healthCode = 0 }
$finalCode = [Math]::Max([int]$runCode, [int]$healthCode)

# ---- 4. 异常时告警（默认 dry-run）
if ($finalCode -ne 0) {
    Write-Log "检测到异常，准备告警（Send=$Send）"
    $payloadFile = Join-Path $logDir "alert-payload.json"
    $healthJson | Set-Content -Path $payloadFile -Encoding UTF8
    $sendFlag = @()
    if ($Send) { $sendFlag = @("--send") }
    & $Python -m ops.notify --title "日报任务异常" --severity error --task "daily-report" `
        --line "日期：$Date" --line "管道退出码：$runCode" --line "健康检查退出码：$healthCode" @sendFlag |
        Tee-Object -FilePath $logFile -Append
}

Write-Log "=== 结束 exit=$finalCode ==="
exit $finalCode
