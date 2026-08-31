param(
    [string]$TargetUri = "http://127.0.0.1:8000/health",
    [int]$TimeoutSeconds = 5
)

$projectRoot = Split-Path $PSScriptRoot -Parent
$logDirectory = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDirectory "health.log"

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


$healthy = Test-ServiceHealth `
    -Uri $TargetUri `
    -TimeoutSeconds $TimeoutSeconds `
    -LogFile $logFile


if ($healthy) {
    exit 0
}

exit 1