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

# pylint: disable=wrong-import-position
from src.utils import setup_logging
from src.browser import initialize_browser, goto_url, get_aria_snapshot
from src import constants
# pylint: enable=wrong-import-position

# テスト用パラメータ
# URL = "https://www.google.com/" # constantsから参照
DEBUG_MODE = False


def main():
    """
    メイン実行関数 - ARIAスナップショットの取得テストを実行します。
    コマンドライン引数でURLやデバッグモードを制御できます。
    """
    parser = argparse.ArgumentParser(description='ARIAスナップショットのテスト')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument(
        '--url',
        type=str,
        default=constants.TEST_DEFAULT_URL,
        help='テスト対象のURL'
    )
    args = parser.parse_args()

    setup_logging(debug=args.debug or DEBUG_MODE)

    # テストパラメータを出力
    logging.info("Test parameters: url=%s, headless=%s",
                 args.url, os.environ.get('HEADLESS', 'false'))

    try:
        # ブラウザ起動
        init_res = initialize_browser()
        if init_res.get("status") != "success":
            logging.error("ブラウザ初期化に失敗: %s", init_res.get('message'))
            return 1

        # URLに移動
        goto_res = goto_url(args.url)
        if goto_res.get("status") != "success":
            logging.error("URL移動に失敗: %s", goto_res.get('message'))
            return 1
        logging.info("ページに移動しました: %s", args.url)

        # ARIA Snapshot取得
        snap_res = get_aria_snapshot()
        if snap_res.get("status") != "success":
            logging.error("ARIA Snapshot取得に失敗: %s", snap_res.get('message'))
            return 1

        snapshot = snap_res.get("aria_snapshot", [])
        logging.info("取得した要素数: %d", len(snapshot))
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, IOError) as e:
        # より具体的な例外タイプを指定
        logging.error("テスト実行中にエラーが発生しました: %s", e)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
