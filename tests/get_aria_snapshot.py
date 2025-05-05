#!/usr/bin/env python3
"""ARIA Snapshot取得用テストスクリプト

ブラウザワーカーを起動し、指定(またはデフォルト)のURLに移動してから
最新のARIA Snapshotを取得してコンソールに出力します。

Usage:
    python tests/get_aria_snapshot.py --url "https://example.com" [--debug]
"""
import sys
import os
import json
import logging

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import setup_logging
from src.browser import initialize_browser, goto_url, get_aria_snapshot

# テスト用パラメータ (ここを編集してください)
URL = "https://www.google.com/"
DEBUG_MODE = False

def main():
    # テストスクリプトでは直接定義したパラメータを使用します
    setup_logging(debug=DEBUG_MODE)
    # テストパラメータを出力
    logging.info(f"Test parameters: url={URL}")

    # ブラウザ起動
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return 1

    # URLに移動
    goto_res = goto_url(URL)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return 1
    logging.info(f"ページに移動しました: {URL}")

    # ARIA Snapshot取得
    snap_res = get_aria_snapshot()
    if snap_res.get("status") != "success":
        logging.error(f"ARIA Snapshot取得に失敗: {snap_res.get('message')}")
        return 1

    snapshot = snap_res.get("aria_snapshot", [])
    logging.info(f"取得した要素数: {len(snapshot)}")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main()) 