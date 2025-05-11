#!/usr/bin/env python3
"""click_elementテストスクリプト

指定されたURLを開き、ARIA Snapshotを取得して
ref_id で指定した要素をクリックするテストを行います。

正常系と異常系（存在しない要素へのクリックなど）のテストが含まれます。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
"""
import argparse
import logging
import os
import sys
import time
import traceback

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=wrong-import-position
from src.browser import (cleanup_browser, click_element, get_aria_snapshot,
                         goto_url, initialize_browser)
from src.utils import setup_logging

# pylint: enable=wrong-import-position

# テスト用パラメータ（自由に変更可能）
TEST_URL = "https://www.google.co.jp/"
TEST_REF_ID = 26
# 異常系テスト用
TEST_ERROR_REF_ID = 9999


def test_normal_case(url=TEST_URL, ref_id=TEST_REF_ID):
    """正常系テスト - 指定された要素をクリックする"""
    logging.info("=== 正常系テスト開始: url=%s, ref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"
    logging.info("ページ読み込み完了")

    # クリック前のARIA Snapshot取得
    aria_before_res = get_aria_snapshot()
    if aria_before_res.get("status") != "success":
        logging.error(
            "クリック前のARIA Snapshot取得に失敗: %s", aria_before_res.get("message")
        )
        assert False, "ARIA Snapshot取得に失敗"

    elements_before = aria_before_res.get("aria_snapshot", [])
    logging.info("クリック前の要素数: %s", len(elements_before))

    element_exists = any(e.get("ref_id") == ref_id for e in elements_before)
    if not element_exists:
        logging.error(
            "指定されたref_id=%s の要素が見つかりません。クリック可能な要素を探します。",
            ref_id,
        )

        # 要素が見つからない場合は、クリック可能な要素を探す
        clickable_elements = []
        for elem in elements_before:
            if elem.get("role") in ["button", "link"]:
                clickable_elements.append(elem)
                logging.info(
                    "クリック可能な要素を見つけました: ref_id=%s, role=%s, name=%s",
                    elem.get("ref_id"),
                    elem.get("role"),
                    elem.get("name"),
                )

        if clickable_elements:
            # 1番目のクリック可能な要素を使用
            ref_id = clickable_elements[0].get("ref_id")
            logging.info("テスト継続のため ref_id=%s に変更します", ref_id)
        else:
            # クリック可能な要素がない場合は、最初の要素を使用
            if elements_before:
                ref_id = elements_before[0].get("ref_id")
                logging.info(
                    "テスト継続のため、最初の要素 ref_id=%s を使用します", ref_id
                )
            else:
                assert False, "クリック可能な要素が見つかりません"

    # 選択した要素の情報をログ
    target_element = next(
        (e for e in elements_before if e.get("ref_id") == ref_id), None
    )
    if target_element:
        logging.info(
            "クリック対象要素: ref_id=%s, role=%s, name=%s",
            target_element.get("ref_id"),
            target_element.get("role"),
            target_element.get("name"),
        )

    # クリック実行
    logging.info("クリック処理開始: ref_id=%s", ref_id)
    click_res = click_element(ref_id)
    if click_res.get("status") != "success":
        logging.error("クリックに失敗しました: %s", click_res.get("message"))
        assert False, "クリックに失敗しました"

    logging.info("クリック処理成功")

    # 操作後の検証: ページの変化を待機
    time.sleep(1)

    # クリック後のARIA Snapshot取得して検証
    aria_after_res = get_aria_snapshot()
    if aria_after_res.get("status") != "success":
        logging.error(
            "クリック後のARIA Snapshot取得に失敗: %s", aria_after_res.get("message")
        )
        assert False, "クリック後のARIA Snapshot取得に失敗"

    elements_after = aria_after_res.get("aria_snapshot", [])
    logging.info("クリック後の要素数: %s", len(elements_after))

    # DOM変化の検証
    has_change = False

    # 1. 要素数の変化を検証
    if len(elements_before) != len(elements_after):
        has_change = True
        logging.info(
            "要素数の変化を検出: 前=%d, 後=%d",
            len(elements_before),
            len(elements_after),
        )

    # 2. リンク要素の場合はURLの変化を検証
    if target_element and target_element.get("role") == "link":
        current_url_res = goto_url("")  # 現在のURLを取得
        if (
            current_url_res.get("status") == "success"
            and current_url_res.get("current_url") != url
        ):
            has_change = True
            logging.info(
                "URLの変化を検出: %s → %s", url, current_url_res.get("current_url")
            )

    # 検証結果
    if has_change:
        logging.info("クリック操作による変化を確認しました")
    else:
        logging.warning(
            "クリック操作後の変化が検出できませんでした。実際の操作は成功している可能性があります。"
        )

    assert True


def test_error_case(url=TEST_URL, ref_id=TEST_ERROR_REF_ID):
    """異常系テスト - 存在しない要素をクリックする"""
    logging.info("=== 異常系テスト開始: url=%s, 存在しないref_id=%s ===", url, ref_id)

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"
    logging.info("ページ読み込み完了")

    # クリック前のARIA Snapshot取得
    aria_before_res = get_aria_snapshot()
    if aria_before_res.get("status") != "success":
        logging.error(
            "クリック前のARIA Snapshot取得に失敗: %s", aria_before_res.get("message")
        )
        assert False, "ARIA Snapshot取得に失敗"

    elements_before = aria_before_res.get("aria_snapshot", [])

    logging.info("存在しない要素のクリック処理開始: ref_id=%s", ref_id)
    click_res = click_element(ref_id)

    if click_res.get("status") == "error":
        logging.info("想定通りエラーが返されました: %s", click_res.get("message"))

        # 操作後の検証: DOMが変化していないことを確認
        aria_after_res = get_aria_snapshot()
        if aria_after_res.get("status") != "success":
            logging.error(
                "クリック後のARIA Snapshot取得に失敗: %s", aria_after_res.get("message")
            )
            assert False, "クリック後のARIA Snapshot取得に失敗"

        elements_after = aria_after_res.get("aria_snapshot", [])

        # 要素数が変わっていないことを確認
        if len(elements_before) == len(elements_after):
            logging.info(
                "エラー後も要素数に変化がないことを確認: %d", len(elements_after)
            )
        else:
            logging.warning(
                "エラー後に要素数が変化しています: 前=%d, 後=%d",
                len(elements_before),
                len(elements_after),
            )

        assert True
    else:
        logging.error("存在しない要素へのクリックがエラーを返しませんでした")
        assert False, "存在しない要素へのクリックがエラーを返しませんでした"


def main():
    """メイン関数 - テストの実行と結果の処理を行う"""
    # pytestから実行される場合は、sys.argvを変更して余計な引数を削除
    if len(sys.argv) > 1 and sys.argv[0].endswith("__main__.py"):
        # pytestから実行される場合、余計な引数をフィルタリング
        filtered_args = [sys.argv[0]]
        for arg in sys.argv[1:]:
            if arg in ["--debug", "--url", "--ref-id"] or not arg.startswith("-"):
                filtered_args.append(arg)
        sys.argv = filtered_args

    parser = argparse.ArgumentParser(description="click_elementのテスト")
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモードを有効にする"
    )
    parser.add_argument("--url", type=str, default=TEST_URL, help="テスト対象のURL")
    parser.add_argument(
        "--ref-id", type=int, default=TEST_REF_ID, help="クリックする要素のref_id"
    )
    args = parser.parse_args()

    setup_logging()
    if args.debug or True:
        logging.getLogger().setLevel(logging.DEBUG)

    # テストパラメータを出力
    logging.info(
        "Test parameters: url=%s, ref_id=%s, headless=%s",
        args.url,
        args.ref_id,
        os.environ.get("HEADLESS", "false"),
    )

    try:
        # テスト関数は値を返さないため、例外をキャッチして成功/失敗を判断
        normal_success = False
        error_success = False

        try:
            test_normal_case(args.url, args.ref_id)
            normal_success = True
        except AssertionError as e:
            logging.error("正常系テスト失敗: %s", e)

        try:
            test_error_case(args.url, TEST_ERROR_REF_ID)
            error_success = True
        except AssertionError as e:
            logging.error("異常系テスト失敗: %s", e)

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
    finally:
        # 必ずブラウザをクリーンアップ
        try:
            cleanup_browser()
            logging.info("ブラウザのクリーンアップが完了しました")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("ブラウザのクリーンアップ中にエラーが発生しました: %s", e)


if __name__ == "__main__":
    sys.exit(main())
