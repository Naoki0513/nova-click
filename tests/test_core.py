import unittest
import os
import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from agent.core import get_inference_config, get_browser_tools_config, update_token_usage

class TestCoreModule(unittest.TestCase):
    """コアモジュールのユニットテスト"""
    
    def test_get_inference_config(self):
        """推論設定が正しく取得できるか"""
        nova_config = get_inference_config("us.amazon.nova-pro-v1:0")
        self.assertEqual(nova_config["maxTokens"], 3000)
        self.assertEqual(nova_config["topP"], 1)
        self.assertEqual(nova_config["temperature"], 1)
        
        claude_config = get_inference_config("us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        self.assertEqual(claude_config["maxTokens"], 3000)
        self.assertEqual(claude_config["temperature"], 0)
    
    def test_get_browser_tools_config(self):
        """ブラウザツール設定が正しく取得できるか"""
        tools = get_browser_tools_config()
        self.assertEqual(len(tools), 3)
        
        tool_names = [t["toolSpec"]["name"] for t in tools]
        self.assertIn("get_ax_tree", tool_names)
        self.assertIn("click_element", tool_names)
        self.assertIn("input_text", tool_names)
        
        click_tool = next(t for t in tools if t["toolSpec"]["name"] == "click_element")
        self.assertIn("role", click_tool["toolSpec"]["inputSchema"]["json"]["properties"])
        self.assertIn("name", click_tool["toolSpec"]["inputSchema"]["json"]["properties"])
    
    def test_update_token_usage(self):
        """トークン使用量が正しく更新されるか"""
        token_usage = {
            "inputTokens": 100,
            "outputTokens": 200,
            "totalTokens": 300
        }
        
        response = {
            "usage": {
                "inputTokens": 50,
                "outputTokens": 75
            }
        }
        
        updated = update_token_usage(response, token_usage)
        
        self.assertEqual(updated["inputTokens"], 150)
        self.assertEqual(updated["outputTokens"], 275)
        self.assertEqual(updated["totalTokens"], 425)

if __name__ == "__main__":
    unittest.main()
