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
            "FXD_M31_SANITIZED_PROVIDER_FAILURE=AI proposal failed or was quarantined: OpenAI response reached the output-token limit."
        )

        $category | Should Be "AI proposal failed or was quarantined: OpenAI response reached the output-token limit."
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
}
