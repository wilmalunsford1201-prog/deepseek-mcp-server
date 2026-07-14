# DeepSeek MCP Server - One-Click Installer for Claude Desktop (Windows)
# Run: Right-click -> "Run with PowerShell"

$ErrorActionPreference = "Stop"
Write-Host "`n===== DeepSeek MCP Server Installer =====" -ForegroundColor Cyan

# 0. Get API key (env var, or prompt — never hard-coded)
$apiKey = $env:DEEPSEEK_API_KEY
if (-not $apiKey) {
    $apiKey = Read-Host "Enter your DeepSeek API key (get one at https://platform.deepseek.com/api_keys)"
}
if (-not $apiKey) { Write-Host "No API key provided. Aborting." -ForegroundColor Red; exit 1 }

# 1. Create server directory
$serverDir = "$env:USERPROFILE\.deepseek-mcp"
if (!(Test-Path $serverDir)) { New-Item -ItemType Directory -Path $serverDir -Force | Out-Null }
Write-Host "[1/4] Created directory: $serverDir" -ForegroundColor Green

# 2. Copy server files
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Copy-Item "$scriptDir\deepseek_mcp.py" "$serverDir\deepseek_mcp.py" -Force
Copy-Item "$scriptDir\requirements.txt" "$serverDir\requirements.txt" -Force
Write-Host "[2/4] Copied server files" -ForegroundColor Green

# 3. Install Python dependencies
Write-Host "[3/4] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r "$serverDir\requirements.txt" 2>&1 | Out-Null
Write-Host "[3/4] Dependencies installed" -ForegroundColor Green

# 4. Update Claude Desktop config
$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$dsEntry = @{
    command = "python"
    args    = @("$serverDir\deepseek_mcp.py")
    env     = @{ DEEPSEEK_API_KEY = $apiKey }
}

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
} else {
    $configDir = Split-Path $configPath
    if (!(Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir -Force | Out-Null }
    $config = [PSCustomObject]@{ mcpServers = [PSCustomObject]@{} }
}
if ($null -eq $config.mcpServers) {
    $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([PSCustomObject]@{})
}
$config.mcpServers | Add-Member -NotePropertyName "deepseek" -NotePropertyValue ([PSCustomObject]$dsEntry) -Force
$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
Write-Host "[4/4] Updated Claude Desktop config at: $configPath" -ForegroundColor Green

Write-Host "`n===== Done! =====" -ForegroundColor Cyan
Write-Host "Restart Claude Desktop to activate the 4 DeepSeek tools:"
Write-Host "  deepseek_generate / deepseek_chat / deepseek_reason / deepseek_list_models"
Read-Host "Press Enter to exit"
