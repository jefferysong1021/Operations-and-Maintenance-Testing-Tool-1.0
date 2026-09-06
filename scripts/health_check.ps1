param(
    [string[]]$TargetUri = @(
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/ready"
    ),
    [int]$TimeoutSeconds = 5
)

$projectRoot = Split-Path $PSScriptRoot -Parent
$logDirectory = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDirectory "health.log"
$alertFile = Join-Path $logDirectory "alerts.log"
$statusFile = Join-Path $logDirectory "monitor_status.json"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $logDirectory | Out-Null


function Write-Log {
    param(
        [ValidateSet("INFO", "ERROR")]
        [string]$Level,

        [string]$Message,

        [string]$Path
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp [$Level] $Message"

    Add-Content -LiteralPath $Path -Value $line
    Write-Host $line
}


function Test-ServiceHealth {
    param(
        [string]$Uri,

        [int]$TimeoutSeconds = 5,

        [string]$LogFile
    )

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -TimeoutSec $TimeoutSeconds `
            -UseBasicParsing

        if ($response.StatusCode -eq 200) {
            Write-Log `
                -Level "INFO" `
                -Message "Service check passed: $Uri" `
                -Path $LogFile

            return $true
        }

        Write-Log `
            -Level "ERROR" `
            -Message "Unexpected status code: $($response.StatusCode)" `
            -Path $LogFile

        return $false
    }
    catch {
        Write-Log `
            -Level "ERROR" `
            -Message "Cannot reach service: $($_.Exception.Message)" `
            -Path $LogFile

        return $false
    }
}


function Write-MonitorStatus {
    param(
        [string]$Status,

        [string[]]$FailedUris,

        [string]$Path
    )

    $payload = [ordered]@{
        status = $Status
        checked_at = (Get-Date).ToUniversalTime().ToString("o")
        failed_targets = @($FailedUris)
    }

    $payload | ConvertTo-Json | Set-Content -LiteralPath $Path -Encoding utf8
}


$allHealthy = $true
$failedUris = @()

foreach ($uri in $TargetUri) {
    $healthy = Test-ServiceHealth `
        -Uri $uri `
        -TimeoutSeconds $TimeoutSeconds `
        -LogFile $logFile

    if (-not $healthy) {
        $allHealthy = $false
        $failedUris += $uri
    }
}


if ($allHealthy) {
    Write-MonitorStatus `
        -Status "healthy" `
        -FailedUris @() `
        -Path $statusFile

    exit 0
}

function Write-Alert {
    param(
        [string]$Message,

        [string]$Path
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp [ALERT] $Message"

    Add-Content -LiteralPath $Path -Value $line
    Write-Warning $line
}

Write-Alert `
    -Message "Health check failed for: $($failedUris -join ', ')" `
    -Path $alertFile

Write-MonitorStatus `
    -Status "unhealthy" `
    -FailedUris $failedUris `
    -Path $statusFile

exit 1
