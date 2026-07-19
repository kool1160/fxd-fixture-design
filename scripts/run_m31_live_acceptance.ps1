param(
    [switch]$LaunchGui
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:RunnerPath = $PSCommandPath

$script:KnownM31ProviderFailureCategories = @(
    "AI proposal failed or was quarantined: OpenAI authentication is unavailable.",
    "AI proposal failed or was quarantined: OpenAI structured-output request was rejected.",
    "AI proposal failed or was quarantined: OpenAI model or endpoint is unavailable.",
    "AI proposal failed or was quarantined: OpenAI request limit prevented proposal generation.",
    "AI proposal failed or was quarantined: OpenAI Responses request failed.",
    "AI proposal failed or was quarantined: OpenAI Responses request was unavailable.",
    "AI proposal failed or was quarantined: OpenAI proposal context exceeds the configured safe limit.",
    "AI proposal failed or was quarantined: OpenAI response exceeded the configured safe limit.",
    "AI proposal failed or was quarantined: OpenAI response was malformed.",
    "AI proposal failed or was quarantined: OpenAI response was incomplete.",
    "AI proposal failed or was quarantined: OpenAI response reached the output-token limit.",
    "AI proposal failed or was quarantined: OpenAI response was stopped by content filtering.",
    "AI proposal failed or was quarantined: OpenAI response was refused.",
    "AI proposal failed or was quarantined: OpenAI response did not contain a JSON proposal.",
    "AI proposal failed or was quarantined: OpenAI JSON proposal was not an object.",
    "AI proposal failed or was quarantined: OpenAI response contained no structured output.",
    "AI proposal failed or was quarantined: OpenAI response contained no JSON proposal.",
    "AI proposal failed or was quarantined: OpenAI provider failed safely."
)

function Get-M31UnittestSummary {
    param(
        [string[]]$OutputLines,
        [int]$ExitCode
    )

    $output = $OutputLines -join "`n"
    $runMatch = [regex]::Match($output, "Ran (?<count>\d+) tests? in")
    $skipMatch = [regex]::Match($output, "skipped=(?<count>\d+)")
    $total = if ($runMatch.Success) { [int]$runMatch.Groups["count"].Value } else { 0 }
    $skipped = if ($skipMatch.Success) { [int]$skipMatch.Groups["count"].Value } else { 0 }
    $status = if ($ExitCode -ne 0) {
        "failed"
    }
    elseif ($skipped -gt 0) {
        "skipped"
    }
    else {
        "passed"
    }
    return [pscustomobject]@{
        Total = $total
        Skipped = $skipped
        Status = $status
    }
}

function Get-M31SanitizedProviderFailureCategory {
    param([string[]]$OutputLines)

    foreach ($category in $script:KnownM31ProviderFailureCategories) {
        $marker = "FXD_M31_SANITIZED_PROVIDER_FAILURE=$category"
        if ($OutputLines -contains $marker) {
            return $category
        }
    }
    return "unavailable"
}

function Invoke-M31Unittest {
    param(
        [string]$Python,
        [string[]]$TestArguments,
        [switch]$DisableLiveSmoke
    )

    $originalSmokeFlag = [Environment]::GetEnvironmentVariable("FXD_OPENAI_LIVE_SMOKE")
    try {
        if ($DisableLiveSmoke) {
            $env:FXD_OPENAI_LIVE_SMOKE = "0"
        }
        $output = @(& $Python -m unittest @TestArguments 2>&1 | ForEach-Object {
            [string]$_
        })
        return [pscustomobject]@{
            OutputLines = $output
            ExitCode = $LASTEXITCODE
        }
    }
    finally {
        if ($DisableLiveSmoke) {
            if ($null -eq $originalSmokeFlag) {
                Remove-Item -LiteralPath "Env:FXD_OPENAI_LIVE_SMOKE" -ErrorAction SilentlyContinue
            }
            else {
                $env:FXD_OPENAI_LIVE_SMOKE = $originalSmokeFlag
            }
        }
    }
}

function Write-M31Summary {
    param(
        [string]$Branch,
        [string]$Sha,
        [string]$LiveSmokeStatus,
        [string]$FocusedTestTotals,
        [string]$ProviderFailureCategory
    )

    Write-Host ""
    Write-Host "M31 live-provider acceptance summary"
    Write-Host "Branch: $Branch"
    Write-Host "SHA: $Sha"
    Write-Host "Live smoke: $LiveSmokeStatus"
    Write-Host "Focused tests: $FocusedTestTotals"
    Write-Host "Sanitized provider failure category: $ProviderFailureCategory"
}

function Invoke-M31LiveAcceptance {
    $branch = "unavailable"
    $sha = "unavailable"
    $liveSmokeStatus = "not run"
    $focusedTestTotals = "not run"
    $providerFailureCategory = "unavailable"
    $exitCode = 0
    $checksPassed = $false
    $python = $null

    try {
        $scriptPath = [System.IO.Path]::GetFullPath($script:RunnerPath)
        $root = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $scriptPath -Parent) ".."))
        $repositoryRoot = (& git -C $root rev-parse --show-toplevel 2>$null).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
            throw "This runner must be located inside an FXD Git repository."
        }
        if (-not [string]::Equals(
                [System.IO.Path]::GetFullPath($repositoryRoot), $root,
                [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "This runner must be executed from its FXD repository root."
        }
        Set-Location -LiteralPath $root

        $branch = (& git branch --show-current).Trim()
        $sha = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $branch -or -not $sha) {
            throw "Unable to determine the FXD branch and HEAD SHA."
        }
        Write-Host "Branch: $branch"
        Write-Host "SHA: $sha"

        $dirtyWorktree = @(& git status --porcelain --untracked-files=all)
        if ($dirtyWorktree.Count -gt 0) {
            throw "FXD worktree is dirty; commit or remove local changes before live acceptance."
        }

        # Test only whether the key variable exists; do not read its value.
        $apiKeyConfigured = Test-Path -LiteralPath "Env:OPENAI_API_KEY"
        $model = [Environment]::GetEnvironmentVariable("FXD_OPENAI_MODEL")
        $smokeFlag = [Environment]::GetEnvironmentVariable("FXD_OPENAI_LIVE_SMOKE")
        $displayModel = if ([string]::IsNullOrWhiteSpace($model)) { "<not configured>" } else { $model.Trim() }
        $displaySmokeFlag = if ($null -eq $smokeFlag) { "<not configured>" } else { $smokeFlag }
        Write-Host "OPENAI_API_KEY configured: $apiKeyConfigured"
        Write-Host "FXD_OPENAI_MODEL: $displayModel"
        Write-Host "FXD_OPENAI_LIVE_SMOKE: $displaySmokeFlag"
        if (-not $apiKeyConfigured -or [string]::IsNullOrWhiteSpace($model) -or $smokeFlag -ne "1") {
            throw "Required live-provider environment configuration is not available."
        }

        $python = Join-Path $root ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "FXD repository virtual-environment Python was not found."
        }

        $liveResult = Invoke-M31Unittest -Python $python -TestArguments @(
            "tests.test_ai_fixture_engineer.AiFixtureEngineerTests.test_opt_in_openai_live_smoke_uses_one_bounded_request",
            "-v"
        )
        $liveSummary = Get-M31UnittestSummary -OutputLines $liveResult.OutputLines -ExitCode $liveResult.ExitCode
        $liveSmokeStatus = $liveSummary.Status
        $providerFailureCategory = Get-M31SanitizedProviderFailureCategory -OutputLines $liveResult.OutputLines

        # The provider suite is intentionally run with the opt-in smoke disabled so
        # this runner makes no second live request.
        $focusedResult = Invoke-M31Unittest -Python $python -DisableLiveSmoke -TestArguments @(
            "tests.test_ai_fixture_engineer",
            "-v"
        )
        $focusedSummary = Get-M31UnittestSummary -OutputLines $focusedResult.OutputLines -ExitCode $focusedResult.ExitCode
        $focusedTestTotals = "{0} run, {1} skipped ({2})" -f `
            $focusedSummary.Total, $focusedSummary.Skipped, $focusedSummary.Status

        if ($liveSummary.Status -ne "passed") {
            throw "The opt-in live OpenAI smoke test did not pass."
        }
        if ($focusedSummary.Status -eq "failed") {
            throw "Focused AI fixture provider tests failed."
        }
        $checksPassed = $true
    }
    catch {
        $exitCode = 1
        [Console]::Error.WriteLine("M31 live acceptance failed: $($_.Exception.Message)")
    }
    finally {
        Write-M31Summary -Branch $branch -Sha $sha -LiveSmokeStatus $liveSmokeStatus `
            -FocusedTestTotals $focusedTestTotals -ProviderFailureCategory $providerFailureCategory
    }

    if ($LaunchGui -and $checksPassed) {
        Write-Host "Launching FXD GUI after successful automated checks."
        & $python .\fxd_qt_app.py
        if ($LASTEXITCODE -ne 0) {
            return 1
        }
    }
    if ($LaunchGui -and -not $checksPassed) {
        Write-Host "FXD GUI was not launched because automated checks did not pass."
    }
    return $exitCode
}

# Dot-sourcing exposes the pure summary helpers to the focused PowerShell tests
# without invoking a provider request or launching the desktop application.
if ($MyInvocation.InvocationName -eq ".") {
    return
}

exit (Invoke-M31LiveAcceptance)
