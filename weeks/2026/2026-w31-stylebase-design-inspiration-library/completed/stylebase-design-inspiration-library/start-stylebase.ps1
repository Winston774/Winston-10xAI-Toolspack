$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "找不到 Node.js。Stylebase 需要 Node.js 24 或更新版本。"
}

Write-Host ""
Write-Host "STYLEBASE / LOCAL VISUAL ARCHIVE" -ForegroundColor Cyan
Write-Host "瀏覽器網址：http://127.0.0.1:4177" -ForegroundColor White
Write-Host "圖片資料夾：$PSScriptRoot\library\inbox" -ForegroundColor DarkGray
Write-Host ""

npm.cmd start
