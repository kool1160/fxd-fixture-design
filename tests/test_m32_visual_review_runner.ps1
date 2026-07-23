$runner = Join-Path $PSScriptRoot "..\scripts\run_m32_visual_review.ps1"
. $runner

Describe "M32 Windows visual-review launcher" {
    It "strips provider configuration only from visual-review children" {
        $parentPresence = @{}
        foreach ($name in $script:M32VisualProviderEnvironmentNames) {
            $parentPresence[$name] = Test-Path -LiteralPath ("Env:" + $name)
        }
        $child = New-M32VisualChildStartInfo -Executable "python.exe" -WorkingDirectory $TestDrive `
            -Arguments @("-m", "scripts.m32_visual_review")
        foreach ($name in $script:M32VisualProviderEnvironmentNames) {
            if ($name -eq "FXD_OPENAI_LIVE_SMOKE") {
                $child.EnvironmentVariables[$name] | Should Be "0"
            }
            else {
                $child.EnvironmentVariables.ContainsKey($name) | Should Be $false
            }
            (Test-Path -LiteralPath ("Env:" + $name)) | Should Be $parentPresence[$name]
        }
        $child.EnvironmentVariables["FXD_M32_VISUAL_REVIEW_SESSION"] | Should Be "1"
    }

    It "issues the actual FXD project launch and never auto-closes the GUI" {
        $content = Get-Content -LiteralPath $runner -Raw
        $content.Contains('.\fxd_qt_app.py') | Should Be $true
        $content.Contains('"--project"') | Should Be $true
        $content.Contains('"--require-m32-visual-review"') | Should Be $true
        $content.Contains('$Process.WaitForExit()') | Should Be $true
        $content.Contains('.Kill(') | Should Be $false
        $content.Contains('CloseMainWindow') | Should Be $false
    }

    It "turns a failed application process into a launcher failure" {
        $failure = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile", "-Command", "exit 7"
        ) -PassThru -WindowStyle Hidden
        { Wait-M32VisualApplicationProcess -Process $failure `
            -ScreenshotPath (Join-Path $TestDrive "missing.png") } | Should Throw
    }

    It "requires a real application screenshot after successful close" {
        $success = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile", "-Command", "exit 0"
        ) -PassThru -WindowStyle Hidden
        { Wait-M32VisualApplicationProcess -Process $success `
            -ScreenshotPath (Join-Path $TestDrive "missing.png") } | Should Throw
    }

    It "keeps persistent bundle paths outside the repository and reports approval boundaries" {
        $content = Get-Content -LiteralPath $runner -Raw
        $content.Contains('[System.IO.Path]::GetTempPath()') | Should Be $true
        $content.Contains('Software acceptance is not engineering approval.') | Should Be $true
        $content.Contains('remain open until you close it manually') | Should Be $true
    }

    It "fits the native camera after the complete review assembly is displayed" {
        $worker = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\fxd_geometry\vtk_worker.py") -Raw
        $review = $worker.IndexOf("scene.set_review_geometry(tuple(raw_items))")
        $fit = $worker.IndexOf("scene.fit()", $review)
        ($review -ge 0) | Should Be $true
        ($fit -gt $review) | Should Be $true
    }
}
