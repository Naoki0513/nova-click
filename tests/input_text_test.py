#!/usr/bin/env python3
"""input_textテストスクリプト

指定されたURLを開き、ref_id で指定した要素にテキストを入力してEnterを押すテストを行います。
"""
import sys
import os
import json
import logging

# テスト用パラメータ (ここを編集してください)
URL = "https://www.google.co.jp/"
REF_ID = 8
TEXT = "Amazon"
DEBUG_MODE = True

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.browser import initialize_browser, goto_url, input_text, get_aria_snapshot
from src.utils import setup_logging


def main():
    setup_logging(debug=DEBUG_MODE)
    # テストパラメータを出力
    logging.info(f"Test parameters: url={URL}, ref_id={REF_ID}, text='{TEXT}'")

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}\n")
        return 1

    goto_res = goto_url(URL)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}\n")
        return 1
    logging.info("ページ読み込み完了")

    # 初回ARIA Snapshot取得でDOMにref-id属性を注入
    snap_res = get_aria_snapshot()
    logging.info(f"Injected ARIA snapshot elements: {len(snap_res.get('aria_snapshot', []))}")
    print(json.dumps(snap_res, ensure_ascii=False, indent=2))

    # テキスト入力実行
    input_res = input_text(TEXT, REF_ID)
    print(json.dumps(input_res, ensure_ascii=False, indent=2))
    if input_res.get("status") != "success":
        logging.error("テキスト入力に失敗しました")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 