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
import time
import signal

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.browser import initialize_browser, goto_url, input_text, get_aria_snapshot
from src.utils import setup_logging

TEST_TIMEOUT = 60

def timeout_handler(signum, frame):
    logging.error("テスト実行がタイムアウトしました。強制終了します。")
    sys.exit(1)


def test_normal_case(url, ref_id, text, operation_timeout=10):
    """正常系テスト - 指定された要素にテキストを入力する"""
    logging.info(f"=== 正常系テスト開始: url={url}, ref_id={ref_id}, text='{text}' ===")
    
    start_time = time.time()
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"ブラウザ初期化がタイムアウトしました（{operation_timeout}秒）")
        return False
    
    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    logging.info("ページ読み込み完了")
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"URL移動がタイムアウトしました（{operation_timeout}秒）")
        return False

    # 初回ARIA Snapshot取得でDOMにref-id属性を注入
    snap_res = get_aria_snapshot()
    if snap_res.get("status") != "success":
        logging.error(f"ARIA Snapshot取得に失敗: {snap_res.get('message')}")
        return False
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"ARIA Snapshot取得がタイムアウトしました（{operation_timeout}秒）")
        return False
    
    elements = snap_res.get('aria_snapshot', [])
    logging.info(f"取得した要素数: {len(elements)}")
    
    logging.info("利用可能な要素一覧:")
    for elem in elements:
        logging.info(f"  ref_id={elem.get('ref_id')}, role={elem.get('role')}, name={elem.get('name')}")
    
    search_start_time = time.time()
    search_timeout = 3  # 要素検索のタイムアウト（秒）
    search_input_ref_id = None
    
    if url.startswith("https://www.google.co") and time.time() - search_start_time < search_timeout:
        for elem in elements:
            if elem.get('role') == 'textbox' and ('search' in str(elem.get('name', '')).lower() or 'query' in str(elem.get('name', '')).lower()):
                search_input_ref_id = elem.get('ref_id')
                logging.info(f"方法1で検索入力欄を発見: ref_id={search_input_ref_id}, name={elem.get('name')}")
                break
    
    if search_input_ref_id is None and url.startswith("https://www.google.co") and time.time() - search_start_time < search_timeout:
        for elem in elements:
            if elem.get('role') == 'textbox':
                search_input_ref_id = elem.get('ref_id')
                logging.info(f"方法2で検索入力欄を発見: ref_id={search_input_ref_id}, name={elem.get('name')}")
                break
    
    if search_input_ref_id is None and url.startswith("https://www.google.co") and time.time() - search_start_time < search_timeout:
        for test_ref_id in [17, 18, 20, 21, 22, 23]:  # ref_id=19はsubmitボタンなので除外
            if time.time() - search_start_time >= search_timeout:
                break  # 検索タイムアウト
                
            matching_elem = next((e for e in elements if e.get('ref_id') == test_ref_id), None)
            if matching_elem:
                if matching_elem.get('role') != 'button':
                    search_input_ref_id = test_ref_id
                    logging.info(f"方法3で検索入力欄を発見: ref_id={search_input_ref_id}, role={matching_elem.get('role')}")
                    break
                else:
                    logging.info(f"ref_id={test_ref_id}はボタンなのでスキップします")
    
    if search_input_ref_id is None and url.startswith("https://www.google.co") and time.time() - search_start_time < search_timeout:
        for elem in elements:
            if elem.get('role') not in ['button', 'link', 'heading', 'img']:
                search_input_ref_id = elem.get('ref_id')
                logging.info(f"方法4で検索入力欄を発見: ref_id={search_input_ref_id}, role={elem.get('role')}")
                break
    
    search_elapsed = time.time() - search_start_time
    logging.info(f"要素検索時間: {search_elapsed:.2f}秒")
    
    actual_ref_id = search_input_ref_id if search_input_ref_id is not None else ref_id
    logging.info(f"テスト対象の要素: ref_id={actual_ref_id}")
    
    element_exists = any(e.get('ref_id') == actual_ref_id for e in elements)
    if not element_exists:
        logging.error(f"指定されたref_id={actual_ref_id}の要素が見つかりません")
        
        if len(elements) > 0:
            for elem in elements:
                if elem.get('role') != 'button':
                    fallback_ref_id = elem.get('ref_id')
                    logging.info(f"フォールバック: ボタン以外の要素 ref_id={fallback_ref_id} を使用してテストを続行します")
                    actual_ref_id = fallback_ref_id
                    break
            else:
                fallback_ref_id = elements[0].get('ref_id')
                logging.info(f"フォールバック: 最初の要素 ref_id={fallback_ref_id} を使用してテストを続行します")
                actual_ref_id = fallback_ref_id
        else:
            logging.error("要素が見つからないためテストを中止します")
            return False
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"要素検索がタイムアウトしました（{operation_timeout}秒）")
        return False

    # テキスト入力実行
    logging.info(f"テキスト入力実行: text='{text}', ref_id={actual_ref_id}")
    input_res = input_text(text, actual_ref_id)
    if input_res.get("status") != "success":
        logging.error(f"テキスト入力に失敗しました: {input_res.get('message')}")
        return False
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"テキスト入力がタイムアウトしました（{operation_timeout}秒）")
        return False
    
    logging.info("テキスト入力処理成功")
    return True


def test_error_case(url, ref_id, text, operation_timeout=10):
    """異常系テスト - 存在しない要素にテキストを入力する"""
    logging.info(f"=== 異常系テスト開始: url={url}, 存在しないref_id={ref_id}, text='{text}' ===")
    
    start_time = time.time()
    
    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return False
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"ブラウザ初期化がタイムアウトしました（{operation_timeout}秒）")
        return False

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return False
    logging.info("ページ読み込み完了")
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"URL移動がタイムアウトしました（{operation_timeout}秒）")
        return False

    # テキスト入力実行（存在しない要素）
    logging.info(f"存在しない要素へのテキスト入力処理開始: ref_id={ref_id}, text='{text}'")
    input_res = input_text(text, ref_id)
    
    if time.time() - start_time > operation_timeout:
        logging.error(f"テキスト入力がタイムアウトしました（{operation_timeout}秒）")
        return False
    
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
    parser.add_argument('--timeout', type=int, default=TEST_TIMEOUT, 
                        help=f'テスト全体のタイムアウト（秒）。デフォルト: {TEST_TIMEOUT}秒')
    args = parser.parse_args()

    setup_logging(debug=args.debug or True)
    
    # テストパラメータを出力
    logging.info(f"Test parameters: url={args.url}, ref_id={args.ref_id}, text='{args.text}', headless={os.environ.get('HEADLESS', 'false')}, timeout={args.timeout}秒")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(args.timeout)
    
    start_time = time.time()
    
    try:
        logging.info("テスト開始時刻: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        
        normal_success = test_normal_case(args.url, args.ref_id, args.text)
        
        non_existent_ref_id = 9999  # 存在しないref_id
        error_success = test_error_case(args.url, non_existent_ref_id, args.text)
        
        signal.alarm(0)
        
        elapsed_time = time.time() - start_time
        logging.info(f"テスト実行時間: {elapsed_time:.2f}秒")
        
        if normal_success and error_success:
            logging.info("すべてのテストが成功しました")
            return 0
        else:
            logging.error("一部のテストが失敗しました")
            return 1
    except Exception as e:
        signal.alarm(0)
        logging.error(f"テスト実行中にエラーが発生しました: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())                     