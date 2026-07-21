param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:RunnerPath = $PSCommandPath
$script:ExpectedBranch = "milestone-32-multi-station-weld-fixture-synthesis"
$script:ProviderEnvironmentNames = @(
    "OPENAI_API_KEY",
    "FXD_OPENAI_MODEL",
    "FXD_AI_MODEL",
    "FXD_AI_PROVIDER",
    "FXD_AI_ENDPOINT",
    "FXD_AI_API_KEY"
)

function Get-M32UnittestSummary {
    param(
        [string[]]$OutputLines,
        [int]$ExitCode
    )

    $output = $OutputLines -join "`n"
    $runMatch = [regex]::Match($output, "Ran (?<count>\d+) tests? in")
    $total = if ($runMatch.Success) { [int]$runMatch.Groups["count"].Value } else { 0 }
    $counts = @{ failures = 0; errors = 0; skipped = 0 }
    foreach ($match in [regex]::Matches($output, "(?<name>failures|errors|skipped)=(?<count>\d+)")) {
        $counts[$match.Groups["name"].Value] = [int]$match.Groups["count"].Value
    }
    $status = if ($ExitCode -eq 0) { "passed" } else { "failed" }
    return [pscustomobject]@{
        Total = $total
        Failures = $counts.failures
        Errors = $counts.errors
        Skipped = $counts.skipped
        Status = $status
    }
}

function New-M32ChildStartInfo {
    param(
        [string]$Python,
        [string[]]$Arguments,
        [hashtable]$EnvironmentOverrides = @{}
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Python
    # Every supplied argument is fixed by this repository runner.  The script
    # path is relative to the verified root, and the report path is in TEMP.
    $startInfo.Arguments = ($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' '
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    # Windows PowerShell 5.1 initializes Environment lazily; obtaining the
    # legacy StringDictionary first is required before changing child state.
    # Initialize the lazy dictionary once, then retain it as one object instead
    # of letting PowerShell unwrap its initially empty enumeration to `$null`.
    $null = ,$startInfo.EnvironmentVariables
    [object]$childEnvironment = $startInfo.EnvironmentVariables
    foreach ($name in $EnvironmentOverrides.Keys) {
        $childEnvironment[[string]$name] = [string]$EnvironmentOverrides[$name]
    }
    # All Python children are offline.  Removing these only from StartInfo
    # avoids inspecting, printing, changing, or persisting caller credentials.
    foreach ($name in $script:ProviderEnvironmentNames) {
        $childEnvironment.Remove($name)
    }
    $childEnvironment["FXD_OPENAI_LIVE_SMOKE"] = "0"
    return $startInfo
}

function Invoke-M32Python {
    param(
        [string]$Python,
        [string[]]$Arguments,
        [hashtable]$EnvironmentOverrides = @{}
    )

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = New-M32ChildStartInfo -Python $Python -Arguments $Arguments `
        -EnvironmentOverrides $EnvironmentOverrides
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    return [pscustomobject]@{
        OutputLines = [string[]](@(($stdout -split "`r?`n"), ($stderr -split "`r?`n") | Where-Object { $_ -ne "" }))
        ExitCode = $process.ExitCode
    }
}

function Get-M32SelfCheckReport {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "M32 self-check did not create its redacted report."
    }
    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($report.schema -ne "fxd-m32-self-check-v1" -or $report.status -ne "passed") {
        throw "M32 self-check report did not attest a passed governed scenario."
    }
    if ($report.network_provider_used -ne $false) {
        throw "M32 self-check report indicates a network provider was used."
    }
    return $report
}

function Format-M32TestTotals {
    param($Summary)
    return "{0} run, {1} failures, {2} errors, {3} skipped ({4})" -f `
        $Summary.Total, $Summary.Failures, $Summary.Errors, $Summary.Skipped, $Summary.Status
}

function Write-M32Summary {
    param(
        [string]$Branch,
        [string]$Sha,
        [string]$SelfCheckStatus,
        [string]$FocusedTests,
        [string]$FullSuite,
        [string]$CompileAll,
        [string]$ReportPath
    )

    Write-Host ""
    Write-Host "M32 autonomous software self-check summary"
    Write-Host "Branch: $Branch"
    Write-Host "SHA: $Sha"
    Write-Host "Synthetic offline workflow: $SelfCheckStatus"
    Write-Host "Focused M32 and Qt tests: $FocusedTests"
    Write-Host "Full Python suite: $FullSuite"
    Write-Host "Compileall: $CompileAll"
    Write-Host "Redacted report: $ReportPath"
    Write-Host "Network provider requests: none"
    Write-Host "Human engineering review remains required for practicality, access, weld intent, clamps, manufacturability, structure, safety, and production approval."
}

function Invoke-M32SelfCheck {
    $branch = "unavailable"
    $sha = "unavailable"
    $selfCheckStatus = "not run"
    $focusedTests = "not run"
    $fullSuite = "not run"
    $compileAll = "not run"
    $reportPath = "not created"
    $exitCode = 0

    try {
        $scriptPath = [System.IO.Path]::GetFullPath($script:RunnerPath)
        $root = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $scriptPath -Parent) ".."))
        $repositoryRoot = (& git -C $root rev-parse --show-toplevel 2>$null).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot -or -not [string]::Equals(
                [System.IO.Path]::GetFullPath($repositoryRoot), $root,
                [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "This runner must be located inside the FXD repository root."
        }
        Set-Location -LiteralPath $root
        $branch = (& git branch --show-current).Trim()
        $sha = (& git rev-parse HEAD).Trim()
        if ($branch -ne $script:ExpectedBranch) {
            throw "M32 self-check must run from branch $script:ExpectedBranch."
        }
        if (@(& git status --porcelain --untracked-files=all).Count -gt 0) {
            throw "FXD worktree is dirty; commit or remove local changes before M32 self-check."
        }
        & git diff --check
        if ($LASTEXITCODE -ne 0) {
            throw "git diff --check failed before M32 self-check."
        }
        $python = Join-Path $root ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "FXD repository virtual-environment Python was not found."
        }

        $reportDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
            "fxd-m32-self-check-" + $sha + "-" + [guid]::NewGuid().ToString("N")
        )
        [System.IO.Directory]::CreateDirectory($reportDirectory) | Out-Null
        $reportPath = Join-Path $reportDirectory "m32-self-check.json"
        $selfResult = Invoke-M32Python -Python $python -Arguments @(
            "scripts/m32_self_check.py", "--report", $reportPath
        )
        if ($selfResult.ExitCode -ne 0) {
            throw "M32 synthetic offline workflow failed."
        }
        $null = Get-M32SelfCheckReport -Path $reportPath
        $selfCheckStatus = "passed"

        $focusedResult = Invoke-M32Python -Python $python -Arguments @(
            "-m", "unittest",
            "tests.test_m32_self_check",
            "tests.test_multi_station_fixture",
            "tests.test_qt_workbench.QtWorkbenchTests.test_m32_multi_station_controls_author_real_meshes_and_persist_station_intent",
            "tests.test_qt_workbench.QtWorkbenchTests.test_fixture_build_validation_source_is_independent_and_routes_to_visible_controls",
            "-v"
        )
        $focusedSummary = Get-M32UnittestSummary -OutputLines $focusedResult.OutputLines -ExitCode $focusedResult.ExitCode
        $focusedTests = Format-M32TestTotals -Summary $focusedSummary
        if ($focusedSummary.Status -ne "passed") {
            throw "Focused M32 and Qt validation failed."
        }

        $compileResult = Invoke-M32Python -Python $python -Arguments @(
            "-m", "compileall", "-q", "fxd_geometry", "scripts", "tests"
        )
        if ($compileResult.ExitCode -ne 0) {
            throw "compileall failed."
        }
        $compileAll = "passed"

        $fullResult = Invoke-M32Python -Python $python -Arguments @(
            "-m", "unittest", "discover", "-s", "tests"
        )
        $fullSummary = Get-M32UnittestSummary -OutputLines $fullResult.OutputLines -ExitCode $fullResult.ExitCode
        $fullSuite = Format-M32TestTotals -Summary $fullSummary
        if ($fullSummary.Status -ne "passed") {
            throw "Full Python suite failed."
        }
        & git diff --check
        if ($LASTEXITCODE -ne 0) {
            throw "git diff --check failed after M32 self-check."
        }
    }
    catch {
        $exitCode = 1
        [Console]::Error.WriteLine("M32 self-check failed: $($_.Exception.Message)")
    }
    finally {
        Write-M32Summary -Branch $branch -Sha $sha -SelfCheckStatus $selfCheckStatus `
            -FocusedTests $focusedTests -FullSuite $fullSuite -CompileAll $compileAll -ReportPath $reportPath
    }
    return $exitCode
}

# Dot-sourcing exposes pure helpers to Pester without starting a child process.
if ($MyInvocation.InvocationName -eq ".") {
    return
}

exit (Invoke-M32SelfCheck)
