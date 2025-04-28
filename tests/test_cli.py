import unittest
import subprocess
import os
import sys
import json
from pathlib import Path

class TestCLIMode(unittest.TestCase):
    """CLIモードのE2Eテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        self.project_root = Path(__file__).parent.parent.absolute()
        self.credentials_path = self.project_root / "credentials" / "aws_credentials.json"
        if not self.credentials_path.exists():
            self.skipTest("認証情報ファイルが見つかりません")
    
    def test_cli_help(self):
        """CLIのヘルプが正しく表示されるか"""
        result = subprocess.run(
            [sys.executable, str(self.project_root / "main.py"), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)
        self.assertIn("cli", result.stdout)
        self.assertIn("ui", result.stdout)
    
    def test_cli_mode_simple_query(self):
        """簡単なクエリをCLIモードで実行"""
        query = "こんにちは"
        
        result = subprocess.run(
            [
                sys.executable, 
                str(self.project_root / "main.py"),
                "cli",
                query,
                "--debug"
            ],
            capture_output=True,
            text=True,
            timeout=30  # タイムアウト設定
        )
        
        self.assertEqual(result.returncode, 0, f"エラー出力: {result.stderr}")
        
        self.assertIn("こんにちは", result.stdout, "応答が見つかりません")
        
        self.assertIn("[DEBUG]", result.stderr, "デバッグログが見つかりません")

if __name__ == "__main__":
    unittest.main()
