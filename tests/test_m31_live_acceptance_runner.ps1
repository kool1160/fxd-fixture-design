$runner = Join-Path $PSScriptRoot "..\scripts\run_m31_live_acceptance.ps1"
. $runner

Describe "M31 live acceptance runner summaries" {
    It "parses focused test totals without needing test output details" {
        $summary = Get-M31UnittestSummary -OutputLines @(
            "Ran 24 tests in 1.234s",
            "OK (skipped=1)"
        ) -ExitCode 0

        $summary.Total | Should Be 24
        $summary.Skipped | Should Be 1
        $summary.Status | Should Be "skipped"
    }

    It "accepts only the allowlisted sanitized provider failure marker" {
        $category = Get-M31SanitizedProviderFailureCategory -OutputLines @(
            "FXD_M31_SANITIZED_PROVIDER_FAILURE=unknown governed identity"
        )

        $category | Should Be "unknown governed identity"
    }

    It "does not surface an untrusted provider failure marker" {
        $category = Get-M31SanitizedProviderFailureCategory -OutputLines @(
            "FXD_M31_SANITIZED_PROVIDER_FAILURE=untrusted provider detail"
        )

        $category | Should Be "unavailable"
    }

    It "checks only for API-key presence and dispatches one live smoke test" {
        $content = Get-Content -LiteralPath $runner -Raw

        $content.Contains('$env:OPENAI_API_KEY') | Should Be $false
        $content.Contains('Test-Path -LiteralPath "Env:OPENAI_API_KEY"') | Should Be $true
        ([regex]::Matches(
            $content,
            'test_opt_in_openai_live_smoke_uses_one_bounded_request'
        )).Count | Should Be 1
    }

    It "stops before focused checks when the live smoke does not pass" {
        $content = Get-Content -LiteralPath $runner -Raw
        $liveFailureGate = $content.IndexOf('if ($liveSummary.Status -ne "passed")')
        $focusedInvocation = $content.IndexOf('$focusedResult = Invoke-M31Unittest')

        ($liveFailureGate -ge 0) | Should Be $true
        ($focusedInvocation -ge 0) | Should Be $true
        ($liveFailureGate -lt $focusedInvocation) | Should Be $true
    }

    It "captures unittest stderr and preserves a started failure result" {
        $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
        $result = Invoke-M31Unittest -Python $python -TestArguments @(
            "tests.test_m31_runner_capture_fixture",
            "-v"
        ) -EnvironmentOverrides @{
            "FXD_M31_RUNNER_CAPTURE_TEST" = "1"
        }

        $summary = Get-M31UnittestSummary -OutputLines $result.OutputLines -ExitCode $result.ExitCode
        $category = Get-M31SanitizedProviderFailureCategory -OutputLines $result.OutputLines
        $result.ExitCode | Should Be 1
        ($result.OutputLines -join "`n") | Should Match "FAIL"
        $summary.Status | Should Be "failed"
        $category | Should Be "top-level schema mismatch"
    }

    It "removes provider configuration from the focused child without changing the parent" {
        $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
        $beforePresence = @{}
        foreach ($name in $script:FocusedProviderEnvironmentNames) {
            $beforePresence[$name] = Test-Path -LiteralPath ("Env:" + $name)
        }
        $result = Invoke-M31Unittest -Python $python -DisableLiveSmoke -TestArguments @(
            "tests.test_m31_runner_environment_fixture",
            "-v"
        ) -EnvironmentOverrides @{
            "FXD_M31_RUNNER_ENV_CAPTURE_TEST" = "1"
            "FXD_M31_RUNNER_ENV_EXPECTATION" = "focused"
            "OPENAI_API_KEY" = "test-configured"
            "FXD_OPENAI_MODEL" = "test-configured"
            "FXD_AI_MODEL" = "test-configured"
            "FXD_AI_PROVIDER" = "test-configured"
            "FXD_AI_ENDPOINT" = "test-configured"
            "FXD_AI_API_KEY" = "test-configured"
            "FXD_OPENAI_LIVE_SMOKE" = "1"
        }

        $result.ExitCode | Should Be 0
        ($result.OutputLines -join "`n") | Should Match "FXD_M31_FOCUSED_PROVIDER_CONFIGURATION_ABSENT"
        foreach ($name in $script:FocusedProviderEnvironmentNames) {
            (Test-Path -LiteralPath ("Env:" + $name)) | Should Be $beforePresence[$name]
        }
    }

    It "preserves configured provider state for the live child" {
        $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
        $result = Invoke-M31Unittest -Python $python -TestArguments @(
            "tests.test_m31_runner_environment_fixture",
            "-v"
        ) -EnvironmentOverrides @{
            "FXD_M31_RUNNER_ENV_CAPTURE_TEST" = "1"
            "FXD_M31_RUNNER_ENV_EXPECTATION" = "live"
            "OPENAI_API_KEY" = "test-configured"
            "FXD_OPENAI_MODEL" = "test-configured"
            "FXD_AI_MODEL" = "test-configured"
            "FXD_AI_PROVIDER" = "test-configured"
            "FXD_AI_ENDPOINT" = "test-configured"
            "FXD_AI_API_KEY" = "test-configured"
            "FXD_OPENAI_LIVE_SMOKE" = "1"
        }

        $result.ExitCode | Should Be 0
        ($result.OutputLines -join "`n") | Should Match "FXD_M31_LIVE_PROVIDER_CONFIGURATION_PRESERVED"
    }

    It "runs the focused AI fixture suite in a child that cannot select a network provider" {
        $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
        $result = Invoke-M31Unittest -Python $python -DisableLiveSmoke -TestArguments @(
            "tests.test_ai_fixture_engineer",
            "-v"
        )

        $summary = Get-M31UnittestSummary -OutputLines $result.OutputLines -ExitCode $result.ExitCode
        $result.ExitCode | Should Be 0
        $summary.Total | Should BeGreaterThan 0
        $summary.Skipped | Should BeGreaterThan 0
        $summary.Status | Should Be "skipped"
    }
}
