<#
.SYNOPSIS
  Idempotent, user-scope installer for the central runbook. Never elevates.
.DESCRIPTION
  Creates the per-install token, the Startup-folder launcher for the service,
  the hourly "Runbook\Processor" scheduled task, the CLI shims, and the
  `.runbook/` git excludes. Each step checks current state first and prints
  "exists:", "created:" or "updated:". -WhatIf prints every action and changes
  nothing. The token value is never printed.

  Paths are derived, never hard-coded: the tool's root is the folder holding this
  script, and its WSL spelling comes from `wslpath` (override with -WslRoot).
  The projects root the service scans is set by RUNBOOK_PROJECTS_ROOT or
  "projects_root" in config.json (default: the parent of this folder).
#>
param([switch]$WhatIf, [string]$WslRoot = '')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root      = $PSScriptRoot
$ServerPy  = Join-Path $Root 'server.py'
$ProcessPy = Join-Path $Root 'process.py'
$TokenPath = Join-Path $Root '.token'
$TaskName  = 'Runbook\Processor'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Counts    = @{ exists = 0; created = 0; updated = 0; skipped = 0 }

function Say([string]$Tag, [string]$Msg) {
    $key = $Tag
    if ($WhatIf -and $Tag -in 'created', 'updated') { $Msg = "(WhatIf, not done) $Msg"; $Tag = "would-$Tag" }
    Write-Host ("{0}: {1}" -f $Tag, $Msg)
    $Counts[$key]++
}

if ($WhatIf) { Write-Host 'WhatIf: printing actions only; nothing is changed.' }

# --- pythonw -----------------------------------------------------------------
$cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $cmd) { throw 'pythonw.exe not found on PATH. Install Python 3.12 for Windows and re-run.' }
$Pythonw = $cmd.Source
Write-Host "pythonw: $Pythonw"

# --- 1. token ----------------------------------------------------------------
if (Test-Path -LiteralPath $TokenPath) {
    Say 'exists' "token file $TokenPath (value not shown)"
} else {
    if (-not $WhatIf) {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $hex = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        [System.IO.File]::WriteAllText($TokenPath, $hex, $Utf8NoBom)
    }
    Say 'created' "token file $TokenPath (64 hex chars, value not shown)"
}

# --- 2. Startup launcher -----------------------------------------------------
$StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$StartupCmd = Join-Path $StartupDir 'runbook-server.cmd'
$want = "@echo off`r`nstart `"`" `"$Pythonw`" `"$ServerPy`"`r`n"
if (Test-Path -LiteralPath $StartupCmd) {
    if ([System.IO.File]::ReadAllText($StartupCmd) -ceq $want) {
        Say 'exists' "Startup launcher $StartupCmd"
    } else {
        if (-not $WhatIf) { [System.IO.File]::WriteAllText($StartupCmd, $want, $Utf8NoBom) }
        Say 'updated' "Startup launcher $StartupCmd"
    }
} else {
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
        [System.IO.File]::WriteAllText($StartupCmd, $want, $Utf8NoBom)
    }
    Say 'created' "Startup launcher $StartupCmd"
}

# --- 3. hourly scheduled task ------------------------------------------------
$wantArgs = "`"$ProcessPy`" --reason hourly"
$tr       = "`"$Pythonw`" $wantArgs"
$task = Get-ScheduledTask -TaskPath '\Runbook\' -TaskName 'Processor' -ErrorAction SilentlyContinue
$taskState = 'missing'
if ($task) {
    $a = @($task.Actions)[0]
    $haveExe  = ([string]$a.Execute).Trim('"')
    $haveArgs = ([string]$a.Arguments).Trim()
    if ($haveExe -ieq $Pythonw -and $haveArgs -ceq $wantArgs) { $taskState = 'same' } else { $taskState = 'differs' }
}
if ($taskState -eq 'same') {
    Say 'exists' "scheduled task $TaskName"
} else {
    if (-not $WhatIf) {
        & schtasks.exe /create /tn $TaskName /sc hourly /mo 1 /st 00:00 /tr $tr /f | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "schtasks /create failed (exit $LASTEXITCODE)" }
    }
    $tag = 'updated'
    if ($taskState -eq 'missing') { $tag = 'created' }
    Say $tag "scheduled task $TaskName -> $tr"
}

# --- WSL helper --------------------------------------------------------------
# Scripts go to bash on stdin (avoids Windows-to-WSL quoting); the exit code is the answer.
$WslOk = $false
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    & wsl.exe bash -lc 'true' *> $null
    $WslOk = ($LASTEXITCODE -eq 0)
}
function ConvertTo-WslPath([string]$WinPath) {
    # Ask WSL itself; fall back to the default automount spelling.
    $p = (& wsl.exe wslpath -a ($WinPath.Replace('\', '/')) 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -eq 0 -and $p) { return ([string]$p).Trim() }
    return '/mnt/' + $WinPath.Substring(0, 1).ToLower() + $WinPath.Substring(2).Replace('\', '/')
}
function Invoke-Wsl([string]$Script) {
    # Never pipe strings to wsl.exe: pwsh appends CRLF and bash then sees a name ending in CR.
    # Write an LF-only temp script (UTF-8, no BOM) and run it by its /mnt path.
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('runbook-wsl-' + [guid]::NewGuid().ToString('N') + '.sh')
    [System.IO.File]::WriteAllText($tmp, $Script.Replace("`r", '').TrimEnd("`n") + "`n", $Utf8NoBom)
    try {
        $wslPath = ConvertTo-WslPath $tmp
        & wsl.exe bash -l $wslPath *> $null
        return $LASTEXITCODE
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

# --- 4. WSL shim -------------------------------------------------------------
if ($WslOk -and -not $WslRoot) { $WslRoot = ConvertTo-WslPath $Root }
# An executable on PATH, not a ~/.bashrc alias: aliases exist only in interactive
# shells, so `wsl.exe bash -lc 'runbook ...'` and agent shells never saw one.
$wslShimBody = @'
#!/bin/sh
exec python3 __PY__ "$@"
'@
# One single-quoted shell word, so a path with spaces stays one argument.
$wslShimBody = $wslShimBody.Replace('__PY__', "'" + "$WslRoot/runbook.py".Replace("'", "'\''") + "'")
$wslShimHeredoc = "<<'RUNBOOK_SHIM'`n$wslShimBody`nRUNBOOK_SHIM"
if (-not $WslOk) {
    Say 'skipped' 'wsl (not available): ~/.local/bin/runbook shim'
} else {
    $check = "want=`$(mktemp)`ncat > `"`$want`" $wslShimHeredoc`ncmp -s `"`$want`" ~/.local/bin/runbook && [ -x ~/.local/bin/runbook ]; rc=`$?; rm -f `"`$want`"; exit `$rc"
    $have = (Invoke-Wsl $check) -eq 0
    if ($have) {
        Say 'exists' 'WSL shim ~/.local/bin/runbook'
    } else {
        $existed = (Invoke-Wsl 'test -e ~/.local/bin/runbook') -eq 0
        if (-not $WhatIf) {
            # set -e: a failed step stops before mv, so a working shim is never
            # replaced by a partial one. A mktemp name per run, so two installers
            # never share one temp file; the trap removes it either way.
            $s = "set -e`nmkdir -p ~/.local/bin`ntmp=`$(mktemp ~/.local/bin/.runbook.XXXXXX)`ntrap 'rm -f `"`$tmp`"' EXIT`ncat > `"`$tmp`" $wslShimHeredoc`nchmod +x `"`$tmp`"`nmv -f `"`$tmp`" ~/.local/bin/runbook"
            if ((Invoke-Wsl $s) -ne 0) { throw 'failed to write WSL ~/.local/bin/runbook' }
        }
        $tag = 'created'
        if ($existed) { $tag = 'updated' }
        Say $tag 'WSL shim ~/.local/bin/runbook'
    }
    if ((Invoke-Wsl 'case ":$PATH:" in *":$HOME/.local/bin:"*) exit 0;; esac; exit 1') -ne 0) {
        Write-Host 'WARNING: ~/.local/bin is not on the WSL login-shell PATH; add it in ~/.profile (PATH not modified).'
    }
}

# --- 5. Windows shim ---------------------------------------------------------
$BinDir  = Join-Path $env:USERPROFILE '.local\bin'
$Shim    = Join-Path $BinDir 'runbook.cmd'
$shimTxt = "@python `"$Root\runbook.py`" %*`r`n"
if (Test-Path -LiteralPath $Shim) {
    if ([System.IO.File]::ReadAllText($Shim) -ceq $shimTxt) {
        Say 'exists' "shim $Shim"
    } else {
        if (-not $WhatIf) { [System.IO.File]::WriteAllText($Shim, $shimTxt, $Utf8NoBom) }
        Say 'updated' "shim $Shim"
    }
} else {
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
        [System.IO.File]::WriteAllText($Shim, $shimTxt, $Utf8NoBom)
    }
    Say 'created' "shim $Shim"
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$onPath = $false
if ($userPath) {
    foreach ($p in $userPath.Split(';')) {
        if ($p.Trim().TrimEnd('\') -ieq $BinDir.TrimEnd('\')) { $onPath = $true }
    }
}
if (-not $onPath) {
    Write-Host "WARNING: $BinDir is not on your user PATH; add it to run 'runbook' from any prompt (PATH not modified)."
}

# --- 6. git excludes ---------------------------------------------------------
$Pattern   = '.runbook/'
$WinIgnore = Join-Path $env:USERPROFILE '.config\git\ignore'
$haveLine  = $false
if (Test-Path -LiteralPath $WinIgnore) {
    foreach ($l in [System.IO.File]::ReadAllText($WinIgnore).Split("`n")) {
        if ($l.TrimEnd("`r") -ceq $Pattern) { $haveLine = $true }
    }
}
if ($haveLine) {
    Say 'exists' "git exclude $Pattern in $WinIgnore"
} else {
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path (Split-Path $WinIgnore) | Out-Null
        $prefix = ''
        if (Test-Path -LiteralPath $WinIgnore) {
            $cur = [System.IO.File]::ReadAllText($WinIgnore)
            if ($cur.Length -gt 0 -and -not $cur.EndsWith("`n")) { $prefix = "`n" }
        }
        [System.IO.File]::AppendAllText($WinIgnore, "$prefix$Pattern`n", $Utf8NoBom)
    }
    Say 'created' "git exclude $Pattern in $WinIgnore"
}
if (-not $WslOk) {
    Say 'skipped' "wsl (not available): git exclude $Pattern in ~/.config/git/ignore"
} else {
    if ((Invoke-Wsl 'grep -qxF ".runbook/" ~/.config/git/ignore 2>/dev/null') -eq 0) {
        Say 'exists' "git exclude $Pattern in WSL ~/.config/git/ignore"
    } else {
        if (-not $WhatIf) {
            $s = @'
mkdir -p ~/.config/git
touch ~/.config/git/ignore
if [ -n "$(tail -c1 ~/.config/git/ignore)" ]; then echo >> ~/.config/git/ignore; fi
echo ".runbook/" >> ~/.config/git/ignore
'@
            if ((Invoke-Wsl $s) -ne 0) { throw 'failed to update WSL git ignore' }
        }
        Say 'created' "git exclude $Pattern in WSL ~/.config/git/ignore"
    }
}

# --- 7. runbook.json tracked -------------------------------------------------
# Only when this folder is its own git repo and runbook.json is not ignored: inside
# another repo (for example a public config mirror) the state must stay local.
$top = (& git -C $Root rev-parse --show-toplevel 2>$null)
$ownRepo = $false
if ($LASTEXITCODE -eq 0 -and $top) {
    $ownRepo = ([System.IO.Path]::GetFullPath(([string]$top).Trim()).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($Root).TrimEnd('\'))
}
$ignored = $false
if ($ownRepo) { & git -C $Root check-ignore -q runbook.json *> $null; $ignored = ($LASTEXITCODE -eq 0) }
& git -C $Root ls-files --error-unmatch runbook.json *> $null
$tracked = ($LASTEXITCODE -eq 0)
if (-not $ownRepo -or $ignored) {
    Say 'skipped' 'runbook.json stays untracked (not its own git repo, or git-ignored)'
} elseif ($tracked) {
    Say 'exists' 'runbook.json is tracked'
} elseif (Test-Path -LiteralPath (Join-Path $Root 'runbook.json')) {
    if (-not $WhatIf) {
        $msg  = Join-Path ([System.IO.Path]::GetTempPath()) ('runbook-commit-' + [guid]::NewGuid().ToString('N') + '.txt')
        $text = "chore: track runbook.json`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`nAI-Model: claude-opus-5-5`n"
        [System.IO.File]::WriteAllText($msg, $text, $Utf8NoBom)
        try {
            & git -C $Root add -- runbook.json
            & git -C $Root commit -F $msg -- runbook.json | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'git commit of runbook.json failed' }
        } finally { Remove-Item -LiteralPath $msg -Force -ErrorAction SilentlyContinue }
    }
    Say 'created' 'runbook.json tracked (committed)'
} else {
    Say 'skipped' 'runbook.json does not exist yet'
}

# --- summary -----------------------------------------------------------------
$note = ''
if ($WhatIf) { $note = ' (WhatIf: nothing changed)' }
Write-Host ''
Write-Host ("Summary: {0} created, {1} updated, {2} already present, {3} skipped{4}" -f $Counts.created, $Counts.updated, $Counts.exists, $Counts.skipped, $note)
Write-Host 'Next step: start the service now (it also starts at login via the Startup folder):'
Write-Host "  Start-Process -FilePath '$Pythonw' -ArgumentList '`"$ServerPy`"' -WindowStyle Hidden"
