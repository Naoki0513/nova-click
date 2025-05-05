"""
Bedrock API向けのツール定義とディスパッチモジュール

LLMが利用可能なツールの定義と、ツール呼び出しをブラウザ操作関数に転送するディスパッチロジックを提供します。
"""

import json
import logging
from typing import Dict, Any, List, Optional

from .utils import add_debug_log
from .browser import click_element as browser_click_element
from .browser import input_text as browser_input_text
from .browser import get_aria_snapshot

logger = logging.getLogger(__name__)

def get_browser_tools_config() -> List[Dict[str, Any]]:
    """利用可能なブラウザ操作ツールの設定を取得します"""
    return [
        {
            "toolSpec": {
                "name": "click_element",
                "description": "ARIA Snapshotから要素の ref_id (数値) を特定してから使用してください。指定された参照IDを持つ要素をクリックします。実行後の最新のARIA Snapshotが自動的に結果に含まれます（成功時も失敗時も）。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "ref_id": {
                                "type": "integer",
                                "description": "クリックする要素の参照ID（数値、ARIA Snapshotで確認）"
                            }
                        },
                        "required": ["ref_id"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "input_text",
                "description": "ARIA Snapshotから要素の ref_id (数値) を特定してから使用してください。指定された参照IDを持つ要素にテキストを入力し、Enterキーを押します。実行後の最新のARIA Snapshotが自動的に結果に含まれます（成功時も失敗時も）。",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "入力するテキスト"
                            },
                            "ref_id": {
                                "type": "integer",
                                "description": "テキストを入力する要素の参照ID（数値、ARIA Snapshotで確認）"
                            }
                        },
                        "required": ["text", "ref_id"]
                    }
                }
            }
        }
    ]


def dispatch_browser_tool(tool_name: str, params=None) -> Dict[str, Any]:
    """LLMから呼び出されたツールを実行します

    Args:
        tool_name: ツール名 ("click_element" または "input_text")
        params: ツールのパラメータ (ref_id, textなど)

    Returns:
        ツール実行結果を含む辞書 (status, message, aria_snapshot)
    """
    add_debug_log(f"tools.dispatch_browser_tool: tool={tool_name}, params={params}")
    result = None
    
    if tool_name == 'click_element':
        if params is None or 'ref_id' not in params:
            result = {'status': 'error', 'message': 'パラメータ ref_id が指定されていません'}
        else:
            result = browser_click_element(params.get('ref_id'))
    elif tool_name == 'input_text':
        if params is None or 'ref_id' not in params or 'text' not in params:
            result = {'status': 'error', 'message': 'パラメータ text または ref_id が指定されていません'}
        else:
            result = browser_input_text(
                params.get('text'), 
                params.get('ref_id')
            )
    else:
        add_debug_log(f"tools.dispatch_browser_tool: 不明なツール {tool_name}")
        result = {'status': 'error', 'message': f'不明なツール: {tool_name}'}
    
    # ARIAスナップショットがすでに結果に含まれているはずなので、追加の取得は行わない
    
    return result 