from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "CLI_example.py"


class TestCLIExample(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_help_message(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("简单的个人健康助理 CLI 示例", result.stdout)
        self.assertIn("--weight", result.stdout)

    def test_bmi_output(self) -> None:
        result = self.run_script("--name", "小明", "--weight", "60", "--height", "170")
        self.assertIn("你好, 小明!", result.stdout)
        self.assertIn("你的 BMI 指数是: 20.76", result.stdout)
        self.assertIn("身材保持得真棒！", result.stdout)

    def test_missing_values(self) -> None:
        result = self.run_script("--name", "小明")
        self.assertIn("如果你提供体重和身高，我可以帮你计算 BMI。", result.stdout)


if __name__ == "__main__":
    unittest.main()
