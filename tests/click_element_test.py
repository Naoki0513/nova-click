#!/usr/bin/env python3
"""click_elementテストスクリプト

指定されたURLを開き、ARIA Snapshotを取得して
ref_id で指定した要素をクリックするテストを行います。
"""
import sys
import os
import argparse
import json
import logging

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.tools import initialize_browser, goto_url, get_aria_snapshot, click_element
from agent.utils import setup_logging


def main():
    parser = argparse.ArgumentParser(description="click_element テスト")
    parser.add_argument("--url", type=str, required=True, help="対象ページURL")
    parser.add_argument("--ref-id", type=int, required=True, help="クリックする要素のref_id (数値)")
    parser.add_argument("--debug", action="store_true", help="デバッグモード (常に有効)")
    args = parser.parse_args()

    # デバッグモードを強制的に有効化
    setup_logging(debug=True)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return 1

    goto_res = goto_url(args.url)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return 1
    logging.info("ページ読み込み完了")

    # クリック実行
    click_res = click_element(args.ref_id)
    print(json.dumps(click_res, ensure_ascii=False, indent=2))
    if click_res.get("status") != "success":
        logging.error("クリックに失敗しました")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 