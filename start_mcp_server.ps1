# ============================================================================
# Simplified MCP Server Management Script (PowerShell Version)
# Description: Manages MCP servers, supporting local and FRP modes.
# Author: Gemini
# Version: 1.5 (Updated FRP JSON path to base_dir/.useit/)
# ============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('start', 'start-frp', 'stop', 'restart', 'status', 'logs', 'list', 'single', 'help')]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$Arg1, # Used for vm_id or server_name

    [Parameter(Position=2)]
    [string]$Arg2, # Used for session_id

    [Parameter(Position=3)]
    [string]$Arg3  # Used for base_dir
)

# --- Script Configuration ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = $ScriptDir
$LogDir = Join-Path -Path $ProjectDir -ChildPath "logs"
$ServerLog = Join-Path -Path $LogDir -ChildPath "mcp_servers.log"
$PidFile = Join-Path -Path $ProjectDir -ChildPath "mcp_servers.pid"
$McpServerDir = Join-Path -Path $ProjectDir -ChildPath "mcp-server"
# Note: FRP JSON file path is now dynamic based on base_dir/.useit/
# We'll calculate it in functions that need it

# --- Helper Functions ---

function Get-FrpJsonPath {
    param(
        [string]$BaseDir
    )
    
    if ($BaseDir) {
        $useitDir = Join-Path -Path $BaseDir -ChildPath ".useit"
        return Join-Path -Path $useitDir -ChildPath "mcp_server_frp.json"
    } else {
        $defaultWorkspace = Join-Path -Path $ProjectDir -ChildPath "mcp_workspace"
        $useitDir = Join-Path -Path $defaultWorkspace -ChildPath ".useit"
        return Join-Path -Path $useitDir -ChildPath "mcp_server_frp.json"
    }
}

function Check-Dependencies {
    Write-Host "[INFO] Checking dependencies..." -ForegroundColor Cyan
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] Python not found. Please ensure Python is installed and in your system's PATH." -ForegroundColor Red
        exit 1
    }

    $modulesCheck = & python -c "import yaml, requests, httpx" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Missing Python dependencies. Attempting to install..." -ForegroundColor Yellow
        & python -m pip install pyyaml requests httpx
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Dependency installation failed. Please run manually: python -m pip install pyyaml requests httpx" -ForegroundColor Red
            exit 1
        }
    }
}

function Get-ServerStatus {
    param(
        [string]$BaseDir
    )
    
    if (-not (Test-Path $PidFile)) {
        Write-Host "[INFO] Server is not running (PID file not found)." -ForegroundColor Yellow
        return $null
    }

    try {
        $processId = Get-Content $PidFile
        if (-not $processId) {
             Write-Host "[WARN] PID file is empty. Cleaning up." -ForegroundColor Yellow
             Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
             return $null
        }
        $process = Get-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
    } catch {
        Write-Host "[WARN] PID file contains invalid data ('$processId'). Cleaning up." -ForegroundColor Yellow
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    if ($process) {
        Write-Host "[INFO] Server is running (PID: $($process.Id))." -ForegroundColor Green
        # FIX: Force Python to use UTF-8 to prevent encoding errors on status check
        $env:PYTHONUTF8 = 1
        Push-Location $McpServerDir
        & python simple_launcher.py --status 2>$null
        Pop-Location
        
        # Check for FRP configuration file in the new location
        $FrpJsonFile = Get-FrpJsonPath -BaseDir $BaseDir
        if (Test-Path $FrpJsonFile) {
            try {
                $frpData = Get-Content $FrpJsonFile | ConvertFrom-Json
                Write-Host "[INFO] FRP config file found: $FrpJsonFile" -ForegroundColor Cyan
                Write-Host "[INFO] Server count: $($frpData.servers.Count)" -ForegroundColor Cyan
            } catch { Write-Host "[WARN] Could not parse FRP JSON file." -ForegroundColor Yellow }
        }
        return $process
    } else {
        Write-Host "[WARN] PID file exists, but process (PID: $processId) is not running. Cleaning up." -ForegroundColor Yellow
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Stop-Server {
    param(
        [string]$BaseDir
    )
    
    Write-Host "[INFO] Stopping MCP servers..." -ForegroundColor Cyan
    $process = Get-ServerStatus -BaseDir $BaseDir
    if ($process) {
        Write-Host "[INFO] Sending termination signal to process $($process.Id)..."
        & taskkill /PID $process.Id /F /T | Out-Null
        Write-Host "[INFO] Server stopped successfully." -ForegroundColor Green
    }
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
    
    # Clean up FRP configuration files (both new and old locations)
    $NewFrpJsonFile = Get-FrpJsonPath -BaseDir $BaseDir
    if (Test-Path $NewFrpJsonFile) {
        Write-Host "[INFO] Cleaning up FRP configuration file: $NewFrpJsonFile" -ForegroundColor Cyan
        Remove-Item $NewFrpJsonFile -Force
    }
    
    # Also clean up old location for backward compatibility
    $OldFrpJsonFile = Join-Path -Path $ProjectDir -ChildPath "mcp_server_frp.json"
    if (Test-Path $OldFrpJsonFile) {
        Write-Host "[INFO] Cleaning up old FRP configuration file: $OldFrpJsonFile" -ForegroundColor Cyan
        Remove-Item $OldFrpJsonFile -Force
    }
}

function Start-Server {
    param(
        [bool]$EnableFrp = $false,
        [string]$VmId,
        [string]$SessionId,
        [string]$BaseDir
    )

    Write-Host "[INFO] Starting MCP servers..." -ForegroundColor Cyan
    if (Get-ServerStatus -BaseDir $BaseDir) {
        Write-Host "[WARN] Server is already running. Stopping it first..." -ForegroundColor Yellow
        Stop-Server -BaseDir $BaseDir
        Start-Sleep -Seconds 2
    }

    Check-Dependencies

    $argList = @("simple_launcher.py")
    if ($BaseDir) { $argList += "--base-dir", $BaseDir }

    if ($EnableFrp) {
        Write-Host "[INFO] Enabling FRP reverse proxy mode." -ForegroundColor Cyan
        $argList += "--enable-frp"
        if ($VmId) { $argList += "--vm-id", $VmId; Write-Host "[INFO] VM ID: $VmId" }
        if ($SessionId) { $argList += "--session-id", $SessionId; Write-Host "[INFO] Session ID: $SessionId" }
    } else {
        Write-Host "[INFO] Starting in local test mode."
    }
    
    if (-not $env:MCP_CLIENT_URL) { $env:MCP_CLIENT_URL = "http://localhost:8080" }
    Write-Host "[INFO] MCP client address: $env:MCP_CLIENT_URL"
    
    $quotedArgs = $argList | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }
    $commandString = "python.exe $($quotedArgs -join ' ')"
    Write-Host "[INFO] Executing: $commandString"
    Write-Host "[INFO] Log file: $ServerLog"

    try {
        if (-not (Test-Path $LogDir)) { New-Item -Path $LogDir -ItemType Directory -Force | Out-Null }
        
        # FIX: Set PYTHONUTF8=1 to force Python into UTF-8 mode.
        # This prevents UnicodeEncodeError on Windows for characters like emojis.
        $env:PYTHONUTF8 = 1

        $cmdArgs = "/C `"$commandString 1> `"$ServerLog`" 2>&1`""
        $wrapperProcess = Start-Process "cmd.exe" -ArgumentList $cmdArgs -WorkingDirectory $McpServerDir -WindowStyle Hidden -PassThru
        
        Start-Sleep -Seconds 2
        $pythonProcess = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $wrapperProcess.Id -and $_.Name -eq "python.exe" }

        if (-not $pythonProcess) {
            throw "Failed to find the python.exe child process. The script may have crashed instantly."
        }

        $pythonProcess.ProcessId | Out-File -FilePath $PidFile -Encoding ascii
        
        Write-Host "[SUCCESS] Server started successfully (PID: $($pythonProcess.ProcessId))." -ForegroundColor Green
        
        # 如果启用了FRP模式，等待配置文件生成
        if ($EnableFrp) {
            Write-Host "[INFO] FRP模式已启用，等待配置文件生成..." -ForegroundColor Cyan
            Start-Sleep -Seconds 2
            
            $FrpJsonFile = Get-FrpJsonPath -BaseDir $BaseDir
            if (Test-Path $FrpJsonFile) {
                Write-Host "[SUCCESS] FRP服务器配置文件已生成: $FrpJsonFile" -ForegroundColor Green
                Write-Host "[INFO] 可使用此文件配置注册到MCP客户端" -ForegroundColor Cyan
            } else {
                Write-Host "[WARN] FRP配置文件尚未生成，稍等片刻..." -ForegroundColor Yellow
                Start-Sleep -Seconds 3
                if (Test-Path $FrpJsonFile) {
                    Write-Host "[SUCCESS] FRP服务器配置文件: $FrpJsonFile" -ForegroundColor Green
                    Write-Host "[INFO] 可使用此文件配置注册到MCP客户端" -ForegroundColor Cyan
                } else {
                    Write-Host "[WARN] FRP配置文件未能及时生成，请检查日志" -ForegroundColor Yellow
                }
            }
        }
        
        Get-ServerStatus -BaseDir $BaseDir

    } catch {
        Write-Host "[ERROR] Failed to start server process." -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        Write-Host "[INFO] Check the latest entries in the log file for errors:" -ForegroundColor Yellow
        if(Test-Path $ServerLog) { Get-Content -Path $ServerLog -Tail 20 }
        if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
        exit 1
    }
}


# --- Main Logic ---

switch ($Command) {
    "start" { Start-Server -BaseDir $Arg1 }
    "start-frp" {
        if (-not $Arg1 -or -not $Arg2) {
            Write-Host "[ERROR] 'start-frp' requires a vm_id and a session_id." -ForegroundColor Red
            Write-Host "[INFO] Usage: .\start_mcp_server.ps1 start-frp <vm_id> <session_id> [base_dir]" -ForegroundColor Yellow
            exit 1
        }
        Start-Server -EnableFrp $true -VmId $Arg1 -SessionId $Arg2 -BaseDir $Arg3
    }
    "stop" { Stop-Server -BaseDir $Arg1 }
    "restart" {
        Write-Host "[INFO] Restarting servers..." -ForegroundColor Cyan
        Stop-Server -BaseDir $Arg1; Start-Sleep -Seconds 2; Start-Server -BaseDir $Arg1
    }
    "status" { Get-ServerStatus -BaseDir $Arg1 | Out-Null }
    "logs" {
        if (Test-Path $ServerLog) {
            Write-Host "--- Displaying last 30 lines of '$ServerLog' ---" -ForegroundColor Yellow
            Get-Content -Path $ServerLog -Tail 30
            Write-Host "--- End of log ---" -ForegroundColor Yellow
            Write-Host "To view logs in real-time, run: Get-Content -Path `"$ServerLog`" -Wait"
        } else { Write-Host "[WARN] Log file not found: $ServerLog" -ForegroundColor Yellow }
    }
    "list" {
        Check-Dependencies
        Write-Host "[INFO] Listing available servers..." -ForegroundColor Cyan
        # FIX: Force Python to use UTF-8 for this command too
        $env:PYTHONUTF8 = 1
        Push-Location $McpServerDir; & python simple_launcher.py --list; Pop-Location
    }
    "single" {
        if (-not $Arg1) {
            Write-Host "[ERROR] 'single' command requires a server name." -ForegroundColor Red
            Push-Location $McpServerDir; & python simple_launcher.py --list; Pop-Location
            exit 1
        }
        Check-Dependencies
        Write-Host "[INFO] Starting single server '$Arg1' in the foreground. Press Ctrl+C to stop." -ForegroundColor Cyan
        # FIX: Force Python to use UTF-8 for single-server mode
        $env:PYTHONUTF8 = 1
        $singleArgs = @("simple_launcher.py", "--single", $Arg1)
        Push-Location $McpServerDir; & python $singleArgs; Pop-Location
    }
    "help" {
        Write-Host "🚀 Simplified MCP Server Management Tool (PowerShell)" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Usage: .\start_mcp_server.ps1 [command] [options]" -ForegroundColor White
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Yellow
        Write-Host "  start [base_dir]           Start servers (local mode)" -ForegroundColor White
        Write-Host "  start-frp <vm_id> <session_id> [base_dir]  Start servers (FRP remote mode)" -ForegroundColor White
        Write-Host "  stop [base_dir]            Stop all servers" -ForegroundColor White
        Write-Host "  restart [base_dir]         Restart servers" -ForegroundColor White
        Write-Host "  status [base_dir]          Show server status" -ForegroundColor White
        Write-Host "  logs                       Show logs" -ForegroundColor White
        Write-Host "  list                       List available servers" -ForegroundColor White
        Write-Host "  single <name>              Start single server" -ForegroundColor White
        Write-Host "  help                       Show this help" -ForegroundColor White
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Yellow
        Write-Host "  .\start_mcp_server.ps1 start                        # Local mode start" -ForegroundColor Gray
        Write-Host "  .\start_mcp_server.ps1 start-frp vm123 sess456       # FRP mode with vm_id and session_id" -ForegroundColor Gray
        Write-Host "  .\start_mcp_server.ps1 start-frp vm123 sess456 C:\temp\workspace  # Specify base directory" -ForegroundColor Gray
        Write-Host "  .\start_mcp_server.ps1 single audio_slicer          # Start single server" -ForegroundColor Gray
        Write-Host "  .\start_mcp_server.ps1 status                       # Check status" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Note:" -ForegroundColor Yellow
        Write-Host "  - FRP mode generates mcp_server_frp.json config file in base_dir\.useit\ directory" -ForegroundColor Gray
        Write-Host "  - This file contains server connection info for MCP client registration" -ForegroundColor Gray
    }
    default {
        Write-Host "[ERROR] Unknown command: $Command" -ForegroundColor Red
        Write-Host "[INFO] Use 'help' to see available commands." -ForegroundColor Yellow
        exit 1
    }
}