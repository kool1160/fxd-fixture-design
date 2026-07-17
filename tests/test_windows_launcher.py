"""Portable contract checks for the Windows Explorer launcher."""
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPOSITORY_ROOT / "launch-fxd.bat"


class WindowsLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.launcher = LAUNCHER.read_text(encoding="utf-8")

    def test_double_click_launcher_uses_repository_venv_and_entrypoint(self) -> None:
        self.assertIn("@echo off", self.launcher)
        self.assertIn('set "FXD_ROOT=%~dp0"', self.launcher)
        self.assertIn('set "FXD_PYTHON=%FXD_ROOT%.venv\\Scripts\\python.exe"', self.launcher)
        self.assertIn('set "FXD_APP=%FXD_ROOT%scripts\\fxd-app.py"', self.launcher)
        self.assertIn('"%FXD_PYTHON%" "%FXD_APP%"', self.launcher)

    def test_launcher_fails_readably_when_required_files_are_missing(self) -> None:
        self.assertIn('if not exist "%FXD_PYTHON%"', self.launcher)
        self.assertIn('ERROR: FXD virtual environment is missing.', self.launcher)
        self.assertIn('if not exist "%FXD_APP%"', self.launcher)
        self.assertIn('ERROR: FXD application entry point is missing.', self.launcher)
        self.assertIn("pause", self.launcher)
        self.assertIn("exit /b 1", self.launcher)

    def test_launcher_forwards_a_step_file_through_the_standard_app_path(self) -> None:
        self.assertIn('if not exist "%~f1"', self.launcher)
        self.assertIn('ERROR: STEP file was not found.', self.launcher)
        self.assertIn('"%FXD_PYTHON%" "%FXD_APP%" --step "%~f1"', self.launcher)


if __name__ == "__main__":
    unittest.main()
