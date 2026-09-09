param(
    [string[]]$TargetUri,
    [int]$TimeoutSeconds = 5,
    [string]$ConfigPath = "config\targets.json"
)

$projectRoot = Split-Path $PSScriptRoot -Parent
$logDirectory = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDirectory "health.log"
$alertFile = Join-Path $logDirectory "alerts.log"
$statusFile = Join-Path $logDirectory "monitor_status.json"
$resolvedConfigPath = if ([IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $projectRoot $ConfigPath
}

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
        [string]$Name,

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
                -Message "Service check passed: $Name ($Uri)" `
                -Path $LogFile

            return $true
        }

        Write-Log `
            -Level "ERROR" `
            -Message "Unexpected status code for $Name ($Uri): $($response.StatusCode)" `
            -Path $LogFile

        return $false
    }
    catch {
        Write-Log `
            -Level "ERROR" `
            -Message "Cannot reach $Name ($Uri): $($_.Exception.Message)" `
            -Path $LogFile

        return $false
    }
}


function Get-TargetDefinitions {
    param(
        [string[]]$OverrideUris,

        [string]$Path,

        [int]$DefaultTimeout
    )

    if ($OverrideUris -and $OverrideUris.Count -gt 0) {
        return @(
            $OverrideUris | ForEach-Object {
                [pscustomobject]@{
                    name = $_
                    uri = $_
                    timeout_seconds = $DefaultTimeout
                }
            }
        )
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Target configuration file not found: $Path"
    }

    try {
        $config = Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
    }
    catch {
        throw "Unable to parse target configuration file: $Path. $($_.Exception.Message)"
    }

    if (-not $config.targets) {
        throw "Target configuration must contain a non-empty targets array: $Path"
    }

    $targets = @(
        $config.targets | ForEach-Object {
            if ([string]::IsNullOrWhiteSpace($_.url)) {
                throw "Each target must contain a url: $Path"
            }

            $targetName = if ([string]::IsNullOrWhiteSpace($_.name)) {
                $_.url
            } else {
                $_.name
            }

            $targetTimeout = if ($_.timeout_seconds) {
                [int]$_.timeout_seconds
            } else {
                $DefaultTimeout
            }

            [pscustomobject]@{
                name = $targetName
                uri = $_.url
                timeout_seconds = $targetTimeout
            }
        }
    )

    return $targets
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


$targets = Get-TargetDefinitions `
    -OverrideUris $TargetUri `
    -Path $resolvedConfigPath `
    -DefaultTimeout $TimeoutSeconds

$allHealthy = $true
$failedUris = @()

foreach ($target in $targets) {
    $healthy = Test-ServiceHealth `
        -Name $target.name `
        -Uri $target.uri `
        -TimeoutSeconds $target.timeout_seconds `
        -LogFile $logFile

    if (-not $healthy) {
        $allHealthy = $false
        $failedUris += $target.uri
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
