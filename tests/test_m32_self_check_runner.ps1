$runner = Join-Path $PSScriptRoot "..\scripts\run_m32_self_check.ps1"
. $runner

Describe "M32 autonomous self-check runner" {
    It "reports unittest failures, errors, skips, and totals without replaying output" {
        $summary = Get-M32UnittestSummary -OutputLines @(
            "Ran 17 tests in 1.234s",
            "FAILED (failures=2, errors=1, skipped=3)"
        ) -ExitCode 1

        $summary.Total | Should Be 17
        $summary.Failures | Should Be 2
        $summary.Errors | Should Be 1
        $summary.Skipped | Should Be 3
        $summary.Status | Should Be "failed"
    }

    It "removes live and generic provider settings only from every child process" {
        $parentPresence = @{}
        foreach ($name in $script:ProviderEnvironmentNames) {
            $parentPresence[$name] = Test-Path -LiteralPath ("Env:" + $name)
        }
        $child = New-M32ChildStartInfo -Python "python.exe" -Arguments @("-m", "unittest") `
            -EnvironmentOverrides @{
                "OPENAI_API_KEY" = "configured"
                "FXD_OPENAI_MODEL" = "configured"
                "FXD_AI_MODEL" = "configured"
                "FXD_AI_PROVIDER" = "configured"
                "FXD_AI_ENDPOINT" = "configured"
                "FXD_AI_API_KEY" = "configured"
                "FXD_OPENAI_LIVE_SMOKE" = "1"
        }

        foreach ($name in $script:ProviderEnvironmentNames) {
            $child.EnvironmentVariables.ContainsKey($name) | Should Be $false
        }
        $child.EnvironmentVariables["FXD_OPENAI_LIVE_SMOKE"] | Should Be "0"
        foreach ($name in $script:ProviderEnvironmentNames) {
            (Test-Path -LiteralPath ("Env:" + $name)) | Should Be $parentPresence[$name]
        }
    }

    It "keeps the runner offline and does not launch the GUI" {
        $content = Get-Content -LiteralPath $runner -Raw

        $content.Contains("scripts.m32_self_check") | Should Be $true
        $content.Contains("network_provider_used") | Should Be $true
        $content.Contains("fxd_qt_app.py") | Should Be $false
    }

    It "requires a passed redacted report before running its focused suite" {
        $content = Get-Content -LiteralPath $runner -Raw
        $reportGate = $content.IndexOf('Get-M32SelfCheckReport -Path $reportPath')
        $focusedInvocation = $content.IndexOf('$focusedResult = Invoke-M32Python')

        ($reportGate -ge 0) | Should Be $true
        ($focusedInvocation -ge 0) | Should Be $true
        ($reportGate -lt $focusedInvocation) | Should Be $true
    }

    It "maps only an allowlisted self-check failure category from a redacted report" {
        $report = Join-Path $TestDrive "failed-m32-report.json"
        '{"schema":"fxd-m32-self-check-v1","status":"failed","network_provider_used":false,"failure_category":"synthetic source detail"}' |
            Set-Content -LiteralPath $report -Encoding UTF8

        (Get-M32SelfCheckFailureCategory -Path $report) | Should Be "unexpected_internal_failure"
    }

    It "uses a supplied Git for Windows Bash fallback when Bash is absent from PATH" {
        $fallback = Join-Path $TestDrive "bash.exe"
        New-Item -ItemType File -Path $fallback | Out-Null

        (Resolve-M32BashExecutable -OnPath "" -GitForWindowsPath $fallback) | Should Be $fallback
    }
}
