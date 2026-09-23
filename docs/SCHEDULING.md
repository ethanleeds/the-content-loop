# Scheduling the weekly loop

The loop only compounds if it runs every week without you remembering.

## Mac / Linux (cron)
```
crontab -e
0 7 * * 1 /full/path/to/repo/scripts/weekly.sh
```

## Windows (PowerShell, once)
```
$a = New-ScheduledTaskAction -Execute 'C:\full\path\to\repo\scripts\weekly.cmd'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 7am
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName 'Content-Loop-Weekly' -Action $a -Trigger $t -Settings $s
```

The machine has to be on. With StartWhenAvailable, a missed run fires the next time it is.

## Metrics
With a Metricool MCP server connected to Claude Code, the agent pulls numbers itself. Without it, paste each week's numbers into `vault/Metrics/YYYY-MM-DD.md` (post, views, saves, shares) before the run.
