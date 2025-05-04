#!/usr/bin/env python3
"""click_elementテストスクリプト

指定されたURLを開き、ARIA Snapshotを取得して
ref_id で指定した要素をクリックするテストを行います。
"""
import sys
import os
import json
import logging

# テスト用パラメータ (ここを編集してください)
URL = "https://www.amazon.co.jp/gp/cart/view.html?ref_=nav_cart"
REF_ID = 27
DEBUG_MODE = True

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.tools import initialize_browser, goto_url, get_aria_snapshot, click_element
from agent.utils import setup_logging


def main():
    # テストスクリプトでは直接定義したパラメータを使用します
    setup_logging(debug=DEBUG_MODE)
    # テストパラメータを出力
    logging.info(f"Test parameters: url={URL}, ref_id={REF_ID}")

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error(f"ブラウザ初期化に失敗: {init_res.get('message')}")
        return 1

    goto_res = goto_url(URL)
    if goto_res.get("status") != "success":
        logging.error(f"URL移動に失敗: {goto_res.get('message')}")
        return 1
    logging.info("ページ読み込み完了")

    # ARIA Snapshot取得・表示
    aria_res = get_aria_snapshot()
    logging.info("ARIA Snapshot取得結果:")
    print(json.dumps(aria_res, ensure_ascii=False, indent=2))
    # 各要素をデバッグログで出力
    for elem in aria_res.get('aria_snapshot', []):
        logging.debug(f"要素: ref_id={elem.get('ref_id')}, role={elem.get('role')}, name={elem.get('name')}")

    # クリック実行
    logging.info(f"クリック処理開始: ref_id={REF_ID}")
    click_res = click_element(REF_ID)
    logging.info("クリック処理結果:")
    print(json.dumps(click_res, ensure_ascii=False, indent=2))
    if click_res.get("status") != "success":
        logging.error(f"クリックに失敗しました: {click_res}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 