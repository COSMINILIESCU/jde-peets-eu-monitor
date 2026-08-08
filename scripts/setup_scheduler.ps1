# Registers the scheduled tasks for the JDE monitor.
# Run once (re-run any time to apply changes):
#   powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler.ps1
#
# Robustness settings that matter (learned the hard way on 2026-08-03, when a run
# was killed 18 minutes in, at source 140/169, and nothing got published):
#   -AllowStartIfOnBatteries / -DontStopIfGoingOnBatteries : Windows' DEFAULT is to
#     refuse to start and to KILL a running task when a laptop switches to battery.
#   -StartWhenAvailable : run as soon as possible if the PC was off at the trigger time.
#   Catch-up task       : after logon, if no successful weekly run in 6 days, run one.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15)

# --- Weekly pipeline: Monday 07:00 -------------------------------------------------
$weeklyAction = New-ScheduledTaskAction -Execute $python -Argument "`"$root\scripts\run_weekly.py`"" -WorkingDirectory $root
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 07:00
Register-ScheduledTask -TaskName "JDE Monitor - Weekly Run" -Action $weeklyAction -Trigger $weeklyTrigger -Settings $settings -Force | Out-Null
Write-Host "OK  JDE Monitor - Weekly Run (Monday 07:00)"

# --- Monthly source scout: Mondays 08:00, script exits unless first Monday ----------
$scoutAction = New-ScheduledTaskAction -Execute $python -Argument "`"$root\scripts\run_monthly_scout.py`"" -WorkingDirectory $root
$scoutTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:00
Register-ScheduledTask -TaskName "JDE Monitor - Monthly Source Scout" -Action $scoutAction -Trigger $scoutTrigger -Settings $settings -Force | Out-Null
Write-Host "OK  JDE Monitor - Monthly Source Scout (first Monday of the month)"

# --- Catch-up safety net: daily check, launches a run only if the last one is stale --
# (a daily trigger needs no elevation, unlike AtLogOn, and also catches the case where
#  the PC simply stays logged in all week)
$catchAction = New-ScheduledTaskAction -Execute $python -Argument "`"$root\scripts\catchup.py`"" -WorkingDirectory $root
$catchTrigger = New-ScheduledTaskTrigger -Daily -At 12:30
Register-ScheduledTask -TaskName "JDE Monitor - Catch-up" -Action $catchAction -Trigger $catchTrigger -Settings $settings -Force | Out-Null
Write-Host "OK  JDE Monitor - Catch-up (daily 12:30; runs only if no successful run in 6 days)"

Get-ScheduledTask -TaskName "JDE Monitor*" | Format-Table TaskName, State
