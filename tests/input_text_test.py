#!/usr/bin/env python3
"""input_textテストスクリプト

指定されたURLを開き、ref_id で指定した要素にテキストを入力してEnterを押すテストを行います。

正常系と異常系（存在しない要素への入力など）のテストが含まれます。

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

from src.browser import initialize_browser, goto_url, input_text, get_aria_snapshot
from src.utils import setup_logging


def test_normal_case(url, ref_id, text):
    """正常系テスト - 指定された要素にテキストを入力する"""
    logging.info(f"=== 正常系テスト開始: url={url}, ref_id={ref_id}, text='{text}' ===")
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    logging.info("ページ読み込み完了")

    # 初回ARIA Snapshot取得でDOMにref-id属性を注入
    snap_res = get_aria_snapshot()
    if snap_res.get("status") != "success":
        logging.error(f"ARIA Snapshot取得に失敗: {snap_res.get('message')}")
        return False
    
    elements = snap_res.get('aria_snapshot', [])
    logging.info(f"取得した要素数: {len(elements)}")
    
    search_input_ref_id = None
    if url.startswith("https://www.google.co"):
        for elem in elements:
            if elem.get('role') == 'textbox' and 'search' in str(elem.get('name', '')).lower():
                search_input_ref_id = elem.get('ref_id')
                logging.info(f"検索入力欄を発見: ref_id={search_input_ref_id}, name={elem.get('name')}")
                break
    
    actual_ref_id = search_input_ref_id if search_input_ref_id is not None else ref_id
    logging.info(f"テスト対象の要素: ref_id={actual_ref_id}")
    
    element_exists = any(e.get('ref_id') == actual_ref_id for e in elements)
    if not element_exists:
        logging.error(f"指定されたref_id={actual_ref_id}の要素が見つかりません")
        return False

    # テキスト入力実行
    input_res = input_text(text, actual_ref_id)
    if input_res.get("status") != "success":
        logging.error(f"テキスト入力に失敗しました: {input_res.get('message')}")
        return False
    
    logging.info("テキスト入力処理成功")
    return True


def test_error_case(url, ref_id, text):
    """異常系テスト - 存在しない要素にテキストを入力する"""
    logging.info(f"=== 異常系テスト開始: url={url}, 存在しないref_id={ref_id}, text='{text}' ===")
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    logging.info("ページ読み込み完了")

    # テキスト入力実行（存在しない要素）
    logging.info(f"存在しない要素へのテキスト入力処理開始: ref_id={ref_id}, text='{text}'")
    input_res = input_text(text, ref_id)
    
    if input_res.get("status") == "error":
        logging.info(f"想定通りエラーが返されました: {input_res.get('message')}")
        return True
    else:
        logging.error("存在しない要素へのテキスト入力がエラーを返しませんでした")
        return False


def main():
    parser = argparse.ArgumentParser(description='input_textのテスト')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    parser.add_argument('--url', type=str, default="https://www.google.co.jp/", 
                        help='テスト対象のURL')
    parser.add_argument('--ref-id', type=int, default=13, help='テキストを入力する要素のref_id')
    parser.add_argument('--text', type=str, default="Amazon", help='入力するテキスト')
    args = parser.parse_args()

    setup_logging(debug=args.debug or True)
    
    # テストパラメータを出力
    logging.info(f"Test parameters: url={args.url}, ref_id={args.ref_id}, text='{args.text}', headless={os.environ.get('HEADLESS', 'false')}")

    try:
        normal_success = test_normal_case(args.url, args.ref_id, args.text)
        
        non_existent_ref_id = 9999  # 存在しないref_id
        error_success = test_error_case(args.url, non_existent_ref_id, args.text)
        
        if normal_success and error_success:
            logging.info("すべてのテストが成功しました")
            return 0
        else:
            logging.error("一部のテストが失敗しました")
            return 1
    except Exception as e:
        logging.error(f"テスト実行中にエラーが発生しました: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())       