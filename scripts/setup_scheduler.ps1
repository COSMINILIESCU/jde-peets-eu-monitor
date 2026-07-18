# Registers the weekly (Monday 07:00) and monthly (first Monday 08:00) scheduled tasks.
# Run once, as the current user:  powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source

# Weekly pipeline — Monday 07:00; if the PC is off, runs as soon as possible after start-up
$weeklyAction = New-ScheduledTaskAction -Execute $python -Argument "`"$root\scripts\run_weekly.py`"" -WorkingDirectory $root
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 07:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "JDE Monitor - Weekly Run" -Action $weeklyAction -Trigger $weeklyTrigger -Settings $settings -Force | Out-Null
Write-Host "OK  registered: JDE Monitor - Weekly Run (Monday 07:00)"

# Monthly source scout — first Monday of the month, 08:00
$scoutAction = New-ScheduledTaskAction -Execute $python -Argument "`"$root\scripts\run_monthly_scout.py`"" -WorkingDirectory $root
$scoutTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:00
Register-ScheduledTask -TaskName "JDE Monitor - Monthly Source Scout" -Action $scoutAction -Trigger $scoutTrigger -Settings $settings -Force | Out-Null
Write-Host "OK  registered: JDE Monitor - Monthly Source Scout (Mondays 08:00; the script itself exits unless it is the first Monday of the month)"

Get-ScheduledTask -TaskName "JDE Monitor*" | Format-Table TaskName, State
