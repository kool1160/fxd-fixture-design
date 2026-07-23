param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:M32VisualRunnerPath = $PSCommandPath
$script:M32VisualExpectedBranch = "milestone-32-multi-station-weld-fixture-synthesis"
$script:M32VisualProviderEnvironmentNames = @(
    "OPENAI_API_KEY", "FXD_OPENAI_MODEL", "FXD_OPENAI_LIVE_SMOKE",
    "FXD_AI_MODEL", "FXD_AI_PROVIDER", "FXD_AI_ENDPOINT", "FXD_AI_API_KEY"
)

function ConvertTo-M32ProcessArguments {
    param([string[]]$Arguments)
    return ($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' '
}

function New-M32VisualChildStartInfo {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [switch]$RedirectOutput
    )
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = ConvertTo-M32ProcessArguments -Arguments $Arguments
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $false
    $startInfo.RedirectStandardOutput = [bool]$RedirectOutput
    $startInfo.RedirectStandardError = [bool]$RedirectOutput
    $null = ,$startInfo.EnvironmentVariables
    [object]$childEnvironment = $startInfo.EnvironmentVariables
    foreach ($name in $script:M32VisualProviderEnvironmentNames) {
        $childEnvironment.Remove($name)
    }
    $childEnvironment["FXD_OPENAI_LIVE_SMOKE"] = "0"
    # Keep the acceptance session from changing the engineer's ordinary window
    # layout or selected UI-only validation source.
    $childEnvironment["FXD_M32_VISUAL_REVIEW_SESSION"] = "1"
    return $startInfo
}

function Invoke-M32VisualBundlePreparation {
    param([string]$Python, [string]$Root, [string]$BundleDirectory)
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = New-M32VisualChildStartInfo -Executable $Python -WorkingDirectory $Root `
        -RedirectOutput -Arguments @(
            "-m", "scripts.m32_visual_review", "--bundle-directory", $BundleDirectory
        )
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $null = $stderrTask.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0 -or -not $stdout.Contains("FXD_M32_VISUAL_REVIEW_BUNDLE=prepared")) {
        throw "The governed M32 visual-review bundle could not be prepared."
    }
}

function Invoke-M32VisualApplication {
    param(
        [string]$Python,
        [string]$Root,
        [string]$ProjectPath,
        [string]$ScreenshotPath
    )
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = New-M32VisualChildStartInfo -Executable $Python -WorkingDirectory $Root `
        -Arguments @(
            ".\fxd_qt_app.py", "--project", $ProjectPath,
            "--require-m32-visual-review", "--screenshot", $ScreenshotPath
        )
    [void]$process.Start()
    Write-Host "Application launch status: launched; loading strict OCP/VTK visual review"
    Write-Host "The FXD application will remain open until you close it manually."
    Wait-M32VisualApplicationProcess -Process $process -ScreenshotPath $ScreenshotPath
}

function Wait-M32VisualApplicationProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$ScreenshotPath
    )
    $Process.WaitForExit()
    if ($Process.ExitCode -ne 0) {
        throw "The FXD M32 visual-review application failed or closed with an error."
    }
    if (-not (Test-Path -LiteralPath $ScreenshotPath -PathType Leaf)) {
        throw "The FXD application did not create its initial visual-review screenshot."
    }
}

function Read-M32VisualReport {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "The M32 visual-review report was not created."
    }
    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($report.schema -ne "fxd-m32-visual-review-v1" -or $report.status -ne "passed") {
        throw "The M32 visual-review report did not attest the governed scenario."
    }
    if ($report.network_provider_used -ne $false) {
        throw "The M32 visual-review report indicates a network provider was used."
    }
    return $report
}

function Invoke-M32VisualReview {
    $originalLocation = (Get-Location).Path
    try {
        $runner = [System.IO.Path]::GetFullPath($script:M32VisualRunnerPath)
        $root = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $runner -Parent) ".."))
        $repositoryRoot = (& git -C $root rev-parse --show-toplevel 2>$null).Trim()
        if ($LASTEXITCODE -ne 0 -or -not [string]::Equals(
                [System.IO.Path]::GetFullPath($repositoryRoot), $root,
                [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "This command must run from the FXD repository."
        }
        Set-Location -LiteralPath $root
        $branch = (& git branch --show-current).Trim()
        $sha = (& git rev-parse HEAD).Trim()
        if ($branch -ne $script:M32VisualExpectedBranch) {
            throw "M32 visual review must run from branch $script:M32VisualExpectedBranch."
        }
        if (@(& git status --porcelain --untracked-files=all).Count -gt 0) {
            throw "FXD worktree is dirty; preserve or commit local work before visual review."
        }
        $python = Join-Path $root ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "FXD repository virtual-environment Python was not found."
        }
        $bundle = Join-Path ([System.IO.Path]::GetTempPath()) (
            "fxd-m32-visual-review-" + (Get-Date -Format "yyyyMMdd-HHmmssfff") + "-" +
            [guid]::NewGuid().ToString("N")
        )
        if ([System.IO.Path]::GetFullPath($bundle).StartsWith(
                $root, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Visual-review artifacts must remain outside the repository."
        }

        Write-Host "Repository: $root"
        Write-Host "Branch: $branch"
        Write-Host "SHA: $sha"
        Write-Host "Bundle directory: $bundle"
        Invoke-M32VisualBundlePreparation -Python $python -Root $root -BundleDirectory $bundle

        $stepPath = Join-Path $bundle "m32_public_self_check_bracket.step"
        $projectPath = Join-Path $bundle "m32-visual-review.fxd.json"
        $reportPath = Join-Path $bundle "m32-visual-review-report.json"
        $screenshotPath = Join-Path $bundle "m32-application-initial-view.png"
        $report = Read-M32VisualReport -Path $reportPath
        foreach ($required in @($stepPath, $projectPath, (Join-Path $bundle "m32-human-engineering-review-checklist.md"))) {
            if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
                throw "The M32 visual-review bundle is incomplete."
            }
        }
        Write-Host "Synthetic STEP: $stepPath"
        Write-Host "Reloadable project: $projectPath"
        Write-Host "Redacted report: $reportPath"
        Write-Host "Application screenshot: $screenshotPath"
        Write-Host ("Scenario: {0} requested -> {1} feasible at {2:N1} mm pitch" -f `
            $report.fixture_build.requested_station_count,
            $report.fixture_build.accepted_feasible_station_count,
            $report.fixture_build.calculated_pitch_mm)
        Write-Host "Software acceptance is not engineering approval."
        Invoke-M32VisualApplication -Python $python -Root $root -ProjectPath $projectPath `
            -ScreenshotPath $screenshotPath
        Write-Host "Application launch status: completed after manual close"
        Write-Host "Persistent visual-review bundle retained at: $bundle"
        Write-Host "Qualified human fixture-engineering judgment remains required."
        return 0
    }
    catch {
        [Console]::Error.WriteLine("M32 visual review failed: $($_.Exception.Message)")
        return 1
    }
    finally {
        Set-Location -LiteralPath $originalLocation
    }
}

# Dot-sourcing exposes process and environment helpers to Pester without launch.
if ($MyInvocation.InvocationName -eq ".") {
    return
}

exit (Invoke-M32VisualReview)
