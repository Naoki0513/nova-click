#!/usr/bin/env python3
"""ARIA Snapshot取得用テストスクリプト

ブラウザワーカーを起動し、指定(またはデフォルト)のURLに移動してから
最新のARIA Snapshotを取得してコンソールに出力します。

Usage:
    python tests/get_aria_snapshot.py [--debug] [--url URL]
    
環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
"""
import sys
import os
import json
import logging
import argparse
import traceback

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import setup_logging
from src.browser import initialize_browser, goto_url, get_aria_snapshot

# テスト用パラメータ
URL = "https://www.google.com/"
DEBUG_MODE = False

def main():
    parser = argparse.ArgumentParser(description='ARIAスナップショットのテスト')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--url', type=str, default=URL, help='テスト対象のURL')
    args = parser.parse_args()

    setup_logging(debug=args.debug or DEBUG_MODE)
    
    # テストパラメータを出力
    logging.info(f"Test parameters: url={args.url}, headless={os.environ.get('HEADLESS', 'false')}")

    try:
        # ブラウザ起動
        init_res = initialize_browser()
        if init_res.get("status") != "success":
            logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
            return 1

        # URLに移動
        goto_res = goto_url(args.url)
        if goto_res.get("status") != "success":
            logging.error(f"URL移動に失敗: {goto_res.get('message')}")
            return 1
        logging.info(f"ページに移動しました: {args.url}")

        # ARIA Snapshot取得
        snap_res = get_aria_snapshot()
        if snap_res.get("status") != "success":
            logging.error(f"ARIA Snapshot取得に失敗: {snap_res.get('message')}")
            return 1

        snapshot = snap_res.get("aria_snapshot", [])
        logging.info(f"取得した要素数: {len(snapshot)}")
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        logging.error(f"テスト実行中にエラーが発生しました: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 