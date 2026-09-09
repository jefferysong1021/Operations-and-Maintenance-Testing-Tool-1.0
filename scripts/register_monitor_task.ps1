param(
    [string]$TaskName = "OpsTestLab-Monitor",

    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 5
)

$projectRoot = Split-Path $PSScriptRoot -Parent
$healthScript = Join-Path $PSScriptRoot "health_check.ps1"

if (-not (Test-Path -LiteralPath $healthScript)) {
    throw "Health check script not found: $healthScript"
}

$actionArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$healthScript`""
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $actionArguments `
    -WorkingDirectory $projectRoot `
    -ErrorAction Stop

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650) `
    -ErrorAction Stop

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited `
    -ErrorAction Stop

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -ErrorAction Stop

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Run Ops Test Lab multi-target health checks" `
    -Force `
    -ErrorAction Stop | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop

Write-Host "Registered task: $($task.TaskName)"
Write-Host "Interval: every $IntervalMinutes minute(s)"
Write-Host "Next run: $($info.NextRunTime)"
