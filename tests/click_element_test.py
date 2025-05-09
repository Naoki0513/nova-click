#!/usr/bin/env python3
"""click_elementテストスクリプト

指定されたURLを開き、ARIA Snapshotを取得して
ref_id で指定した要素をクリックするテストを行います。

正常系と異常系（存在しない要素へのクリックなど）のテストが含まれます。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
"""
import sys
import os
import logging
import argparse
import traceback

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# import json # 未使用のためコメントアウト

# リファクタリング後の新しいインポートパス
# pylint: disable=wrong-import-position
from src.browser import initialize_browser, goto_url, get_aria_snapshot, click_element
from src.utils import setup_logging


def test_normal_case(url, ref_id):
    """正常系テスト - 指定された要素をクリックする"""
    logging.info("=== 正常系テスト開始: url=%s, ref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get('message'))
        return False

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get('message'))
        return False
    logging.info("ページ読み込み完了")

    # ARIA Snapshot取得・表示
    aria_res = get_aria_snapshot()
    if aria_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get('message'))
        return False

    logging.info("取得した要素数: %s", len(aria_res.get('aria_snapshot', [])))

    elements = aria_res.get('aria_snapshot', [])
    element_exists = any(e.get('ref_id') == ref_id for e in elements)
    if not element_exists:
        logging.error("指定されたref_id=%s の要素が見つかりません", ref_id)
        return False

    # クリック実行
    logging.info("クリック処理開始: ref_id=%s", ref_id)
    click_res = click_element(ref_id)
    if click_res.get("status") != "success":
        logging.error("クリックに失敗しました: %s", click_res.get('message'))
        return False

    logging.info("クリック処理成功")
    return True


def test_error_case(url, ref_id):
    """異常系テスト - 存在しない要素をクリックする"""
    logging.info("=== 異常系テスト開始: url=%s, 存在しないref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get('message'))
        return False

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get('message'))
        return False
    logging.info("ページ読み込み完了")

    logging.info("存在しない要素のクリック処理開始: ref_id=%s", ref_id)
    click_res = click_element(ref_id)

    if click_res.get("status") == "error":
        logging.info("想定通りエラーが返されました: %s", click_res.get('message'))
        return True
    else:
        logging.error("存在しない要素へのクリックがエラーを返しませんでした")
        return False


def main():
    """メイン関数 - テストの実行と結果の処理を行う"""
    parser = argparse.ArgumentParser(description='click_elementのテスト')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--url', type=str, default="https://www.google.co.jp/",
                        help='テスト対象のURL')
    parser.add_argument('--ref-id', type=int, default=26, help='クリックする要素のref_id')
    args = parser.parse_args()

    setup_logging(debug=args.debug or True)

    # テストパラメータを出力
    logging.info("Test parameters: url=%s, ref_id=%s, headless=%s",
                 args.url, args.ref_id, os.environ.get('HEADLESS', 'false'))

    try:
        normal_success = test_normal_case(args.url, args.ref_id)

        non_existent_ref_id = 9999  # 存在しないref_id
        error_success = test_error_case(args.url, non_existent_ref_id)

        if normal_success and error_success:
            logging.info("すべてのテストが成功しました")
            return 0
        else:
            logging.error("一部のテストが失敗しました")
            return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("テスト実行中にエラーが発生しました: %s", e)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
