<#
.SYNOPSIS
    ReqTrace v0.2.0: Docker Launch Helper Script (Windows PowerShell)
.DESCRIPTION
    Builds and launches the air-gapped ReqTrace container with a local directory volume mount.
.PARAMETER Workspace
    Path to project workspace directory. Defaults to current working directory.
.PARAMETER Port
    Host and container port to expose. Defaults to 8765.
.PARAMETER Detach
    Run the container in the background (detached mode) and open the browser.
.PARAMETER NoBrowser
    Do not automatically open the browser when launched in detached mode.
.PARAMETER BuildOnly
    Build the Docker image without starting the container.
.PARAMETER Rebuild
    Force rebuild of the Docker image before running.
.EXAMPLE
    .\docker-run.ps1
.EXAMPLE
    .\docker-run.ps1 -Detach
.EXAMPLE
    .\docker-run.ps1 -Workspace "C:\Projects\FlightControls" -Port 8766 -Detach
#>

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [string]$Workspace = (Get-Location).Path,

    [Parameter(Position = 1)]
    [int]$Port = 8765,

    [Alias("d")]
    [switch]$Detach,

    [switch]$NoBrowser,

    [switch]$BuildOnly,

    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$ImageName = "reqtrace:0.2.0"

# 1. Verify Docker CLI and Daemon Availability
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker is not installed or not available in PATH." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

$ErrorActionPreference = "Continue"
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker daemon does not appear to be running." -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
$ErrorActionPreference = "Stop"

# 2. Verify Target Workspace Directory Exists (Option B Policy)
if (-not (Test-Path $Workspace -PathType Container)) {
    Write-Host "[ERROR] Target workspace directory does not exist: $Workspace" -ForegroundColor Red
    Write-Host "ReqTrace enforces Option B: directories must exist prior to launch." -ForegroundColor Yellow
    exit 1
}

$WorkspaceAbs = (Resolve-Path $Workspace).Path

# Convert Windows path for Docker volume mounting (forward slashes)
$DockerMountPath = $WorkspaceAbs -replace '\\', '/'

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  ReqTrace Docker Cockpit (v0.2.0)" -ForegroundColor Green
Write-Host "  Status:    Zero-Egress Air-Gapped Local Web Application" -ForegroundColor DarkGray
Write-Host "  Image:     $ImageName" -ForegroundColor White
Write-Host "  Workspace: $WorkspaceAbs" -ForegroundColor White
Write-Host "  Port:      http://localhost:$Port" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 3. Build Docker Image If Missing or Rebuild Requested
$imageExists = docker images -q $ImageName 2>$null
if ($Rebuild -or -not $imageExists) {
    Write-Host "[BUILD] Building Docker image '$ImageName'..." -ForegroundColor Yellow
    docker build -t $ImageName .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to build Docker image." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Image '$ImageName' built successfully.`n" -ForegroundColor Green
}

if ($BuildOnly) {
    Write-Host "Build complete (-BuildOnly specified). Exiting." -ForegroundColor Green
    exit 0
}

# 4. Remove any stale container instance from previous runs
$ErrorActionPreference = "Continue"
$null = docker rm -f reqtrace-cockpit 2>&1
$ErrorActionPreference = "Stop"

# 5. Run the Container
if ($Detach) {
    Write-Host "[START] Launching ReqTrace container in the background..." -ForegroundColor Green

    $dockerArgs = @(
        "run",
        "-d",
        "--name", "reqtrace-cockpit",
        "-p", "127.0.0.1:${Port}:${Port}",
        "-v", "${DockerMountPath}:/workspace",
        $ImageName,
        "ui",
        "--workspace", "/workspace",
        "--host", "0.0.0.0",
        "--port", "$Port",
        "--ticket-timeout", "1800",
        "--no-browser"
    )

    $containerId = & docker $dockerArgs

    $launchUrl = $null
    $ErrorActionPreference = "Continue"
    for ($i = 0; $i -lt 8; $i++) {
        Start-Sleep -Seconds 1
        $logs = ((docker logs reqtrace-cockpit 2>&1) | ForEach-Object { $_.ToString() }) -join "`n"
        if ($logs -match '(http://localhost:\d+/login\?ticket=[A-Za-z0-9_\-]+)') {
            $launchUrl = $matches[1]
            break
        }
    }
    $ErrorActionPreference = "Stop"

    Write-Host "[OK] Container 'reqtrace-cockpit' is active in Docker Desktop!" -ForegroundColor Green
    Write-Host "   Container ID:  $containerId" -ForegroundColor DarkGray
    Write-Host "   Stop Command:  docker stop reqtrace-cockpit" -ForegroundColor Yellow
    Write-Host "   View Logs:     docker logs -f reqtrace-cockpit" -ForegroundColor Cyan
    Write-Host "   New Ticket:    docker exec reqtrace-cockpit reqtrace ticket -p $Port`n" -ForegroundColor Cyan

    # Extract and display the single-use launch URL and ticket from container startup logs
    if ($launchUrl) {
        $ticketOnly = ($launchUrl -split 'ticket=', 2)[1]
        Write-Host "[OPEN] Launch URL:  $launchUrl" -ForegroundColor Green
        Write-Host "[KEY]  Ticket Only: $ticketOnly`n" -ForegroundColor Green
        if (-not $NoBrowser) {
            Start-Process $launchUrl
        }
    } else {
        Write-Host "Access Cockpit:   http://localhost:$Port" -ForegroundColor Green
        Write-Host "Run 'docker logs reqtrace-cockpit' or 'docker exec reqtrace-cockpit reqtrace ticket' for a ticket.`n" -ForegroundColor Yellow
    }
} else {
    Write-Host "[START] Starting ReqTrace container on http://localhost:$Port ..." -ForegroundColor Green
    Write-Host "   (Press Ctrl+C to stop the container)`n" -ForegroundColor DarkGray

    $dockerArgs = @(
        "run",
        "--rm",
        "-it",
        "--name", "reqtrace-cockpit",
        "-p", "127.0.0.1:${Port}:${Port}",
        "-v", "${DockerMountPath}:/workspace",
        $ImageName,
        "ui",
        "--workspace", "/workspace",
        "--host", "0.0.0.0",
        "--port", "$Port",
        "--ticket-timeout", "1800",
        "--no-browser"
    )

    & docker $dockerArgs
}
