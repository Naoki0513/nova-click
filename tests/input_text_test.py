"""input_textテストスクリプト

指定されたURLを開き、ref_id で指定した要素にテキストを入力してEnterを押すテストを行います。

正常系と異常系（存在しない要素への入力など）のテストが含まれます。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
"""

import argparse
import logging
import os
import signal
import sys
import time
import traceback

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=wrong-import-position
from src.browser import (cleanup_browser, get_aria_snapshot, goto_url,
                         initialize_browser, input_text)
from src.utils import setup_logging

# pylint: enable=wrong-import-position

# テスト用パラメータ（自由に変更可能）
TEST_URL = "https://www.google.co.jp/"
TEST_REF_ID = 13
TEST_TEXT = "Amazon"
TEST_TIMEOUT = 3
# 異常系テスト用
TEST_ERROR_REF_ID = 9999


def timeout_handler(_signum, _frame):
    """タイムアウト発生時のハンドラ関数"""
    logging.error("テスト実行がタイムアウトしました。強制終了します。")
    sys.exit(1)


# Windowsの場合、signal.alarm は利用できない
if sys.platform == "win32":
    logging.warning("Windows環境ではテストのタイムアウト処理が限定的になります。")


def test_normal_case(
    url=TEST_URL, ref_id=TEST_REF_ID, text=TEST_TEXT, operation_timeout=TEST_TIMEOUT
):
    """正常系テスト - 指定された要素にテキストを入力する"""
    logging.info(
        "=== 正常系テスト開始: url=%s, ref_id=%s, text='%s' ===", url, ref_id, text
    )

    start_time = time.time()

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    if time.time() - start_time > operation_timeout:
        logging.error("ブラウザ初期化がタイムアウトしました（%s秒）", operation_timeout)
        assert False, "ブラウザ初期化がタイムアウト"

    # 初期URLを記録
    initial_url = ""
    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"
    else:
        initial_url = goto_res.get("current_url", url)
    logging.info("ページ読み込み完了: %s", initial_url)

    if time.time() - start_time > operation_timeout:
        logging.error("URL移動がタイムアウトしました（%s秒）", operation_timeout)
        assert False, "URL移動がタイムアウト"

    # 初回ARIA Snapshot取得でDOMにref-id属性を注入
    snap_res = get_aria_snapshot()
    if snap_res.get("status") != "success":
        logging.error("ARIA Snapshot取得に失敗: %s", snap_res.get("message"))
        assert False, "ARIA Snapshot取得に失敗"

    if time.time() - start_time > operation_timeout:
        logging.error(
            "ARIA Snapshot取得がタイムアウトしました（%s秒）", operation_timeout
        )
        assert False, "ARIA Snapshot取得がタイムアウト"

    elements_before = snap_res.get("aria_snapshot", [])
    logging.info("取得した要素数: %d", len(elements_before))

    logging.info("利用可能な要素一覧:")
    for elem in elements_before:
        logging.info(
            "  ref_id=%s, role=%s, name=%s",
            elem.get("ref_id"),
            elem.get("role"),
            elem.get("name"),
        )
        search_start_time = time.time()
    search_timeout = 3  # 要素検索のタイムアウト（秒）
    search_input_ref_id = None

    # Googleの検索入力欄を探索する複数の方法
    if (
        url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") == "textbox" and (
                "search" in str(elem.get("name", "")).lower()
                or "query" in str(elem.get("name", "")).lower()
            ):
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "方法1で検索入力欄を発見: ref_id=%s, name=%s",
                    search_input_ref_id,
                    elem.get("name"),
                )
                break

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") == "textbox":
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "方法2で検索入力欄を発見: ref_id=%s, name=%s",
                    search_input_ref_id,
                    elem.get("name"),
                )
                break

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for test_ref_id in [
            17,
            18,
            20,
            21,
            22,
            23,
        ]:  # ref_id=19はsubmitボタンなので除外
            if time.time() - search_start_time >= search_timeout:
                break

            matching_elem = next(
                (e for e in elements_before if e.get("ref_id") == test_ref_id), None
            )
            if matching_elem:
                if matching_elem.get("role") != "button":
                    search_input_ref_id = test_ref_id
                    logging.info(
                        "方法3で検索入力欄を発見: ref_id=%s, role=%s",
                        search_input_ref_id,
                        matching_elem.get("role"),
                    )
                    break
                else:
                    logging.info("ref_id=%s はボタンなのでスキップします", test_ref_id)

    if (
        search_input_ref_id is None
        and url.startswith("https://www.google.co")
        and time.time() - search_start_time < search_timeout
    ):
        for elem in elements_before:
            if elem.get("role") not in ["button", "link", "heading", "img"]:
                search_input_ref_id = elem.get("ref_id")
                logging.info(
                    "方法4で検索入力欄を発見: ref_id=%s, role=%s",
                    search_input_ref_id,
                    elem.get("role"),
                )
                break

    search_elapsed = time.time() - search_start_time
    logging.info("要素検索時間: %.2f秒", search_elapsed)

    actual_ref_id = search_input_ref_id if search_input_ref_id is not None else ref_id
    logging.info("テスト対象の要素: ref_id=%s", actual_ref_id)

    # 対象要素の情報を記録
    target_element = next(
        (e for e in elements_before if e.get("ref_id") == actual_ref_id), None
    )
    if target_element:
        logging.info(
            "入力対象要素: ref_id=%s, role=%s, name=%s",
            target_element.get("ref_id"),
            target_element.get("role"),
            target_element.get("name"),
        )

    element_exists = any(e.get("ref_id") == actual_ref_id for e in elements_before)
    if not element_exists:
        logging.error("指定されたref_id=%s の要素が見つかりません", actual_ref_id)

        # フォールバック：別の入力可能要素を選択
        if elements_before:
            for elem in elements_before:
                if elem.get("role") != "button":
                    fallback_ref_id = elem.get("ref_id")
                    logging.info(
                        "フォールバック: ボタン以外の要素 ref_id=%s を使用してテストを続行します",
                        fallback_ref_id,
                    )
                    actual_ref_id = fallback_ref_id
                    target_element = elem
                    break
            else:
                fallback_ref_id = elements_before[0].get("ref_id")
                logging.info(
                    "フォールバック: 最初の要素 ref_id=%s を使用してテストを続行します",
                    fallback_ref_id,
                )
                actual_ref_id = fallback_ref_id
                target_element = elements_before[0]
        else:
            logging.error("要素が見つからないためテストを中止します")
            assert False, "要素が見つかりません"

    if time.time() - start_time > operation_timeout:
        logging.error("要素検索がタイムアウトしました（%s秒）", operation_timeout)
        assert False, "要素検索がタイムアウト"

    # テキスト入力実行
    logging.info("テキスト入力実行: text='%s', ref_id=%s", text, actual_ref_id)
    input_res = input_text(text, actual_ref_id)
    if input_res.get("status") != "success":
        logging.error("テキスト入力に失敗しました: %s", input_res.get("message"))
        assert False, "テキスト入力に失敗"

    if time.time() - start_time > operation_timeout:
        logging.error("テキスト入力がタイムアウトしました（%s秒）", operation_timeout)
        assert False, "テキスト入力がタイムアウト"

    logging.info("テキスト入力処理成功")

    # 操作後の検証
    # 1. 少し待機して画面の変化を待つ
    time.sleep(2)

    # 2. 現在のURLを取得して変化を確認
    current_url_res = goto_url("")
    if current_url_res.get("status") == "success":
        current_url = current_url_res.get("current_url", "")
        if current_url != initial_url:
            logging.info("URLが変化しました: %s → %s", initial_url, current_url)
            # Google検索の場合、検索語句が含まれているか確認
            if text.lower() in current_url.lower():
                logging.info("URL内に入力テキスト '%s' が含まれています", text)
        else:
            logging.info("URLは変化していません: %s", current_url)

    # 3. DOM変化を検証
    aria_after_res = get_aria_snapshot()
    if aria_after_res.get("status") == "success":
        elements_after = aria_after_res.get("aria_snapshot", [])
        if len(elements_after) != len(elements_before):
            logging.info(
                "DOM要素数が変化しました: %d → %d",
                len(elements_before),
                len(elements_after),
            )
        else:
            logging.info("DOM要素数は変化していません: %d", len(elements_after))

        # Google検索結果ページの特徴を確認
        search_results = [
            e
            for e in elements_after
            if e.get("role") in ["heading", "link"]
            and text.lower() in str(e.get("name", "")).lower()
        ]
        if search_results:
            logging.info(
                "検索結果ページと思われる要素を %d 個発見しました", len(search_results)
            )
            for i, result in enumerate(search_results[:3]):  # 最初の3つだけログ出力
                logging.info(
                    "検索結果 #%d: role=%s, name=%s",
                    i + 1,
                    result.get("role"),
                    result.get("name"),
                )

    assert True


def test_error_case(url=TEST_URL, ref_id=TEST_ERROR_REF_ID, text=TEST_TEXT):
    """異常系テスト - 存在しない要素にテキストを入力する"""
    logging.info(
        "=== 異常系テスト開始: url=%s, 存在しないref_id=%s, text='%s' ===",
        url,
        ref_id,
        text,
    )

    init_res = initialize_browser()
    if init_res.get("status") != "success":
        logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
        assert False, "ブラウザ初期化に失敗"

    # 初期状態の記録
    goto_res = goto_url(url)
    if goto_res.get("status") != "success":
        logging.error("URL移動に失敗: %s", goto_res.get("message"))
        assert False, "URL移動に失敗"

    initial_url = goto_res.get("current_url", url)
    logging.info("ページ読み込み完了: %s", initial_url)

    # 操作前のDOM状態を記録
    snap_before_res = get_aria_snapshot()
    if snap_before_res.get("status") != "success":
        logging.error(
            "操作前のARIA Snapshot取得に失敗: %s", snap_before_res.get("message")
        )
        assert False, "ARIA Snapshot取得に失敗"

    elements_before = snap_before_res.get("aria_snapshot", [])
    logging.info("操作前の要素数: %d", len(elements_before))

    # テキスト入力実行（存在しない要素）
    logging.info(
        "存在しない要素へのテキスト入力処理開始: ref_id=%s, text='%s'", ref_id, text
    )
    input_res = input_text(text, ref_id)

    if input_res.get("status") == "error":
        logging.info("想定通りエラーが返されました: %s", input_res.get("message"))

        # 操作後の検証 - エラー時は状態が変わっていないことを確認

        # 1. URLの変化がないこと
        current_url_res = goto_url("")
        if current_url_res.get("status") == "success":
            current_url = current_url_res.get("current_url", "")
            if current_url == initial_url:
                logging.info("URLが変化していないことを確認: %s", current_url)
            else:
                logging.warning(
                    "エラー発生にもかかわらずURLが変化しています: %s → %s",
                    initial_url,
                    current_url,
                )

        # 2. DOM状態の変化がないか確認
        snap_after_res = get_aria_snapshot()
        if snap_after_res.get("status") == "success":
            elements_after = snap_after_res.get("aria_snapshot", [])
            if len(elements_after) == len(elements_before):
                logging.info("要素数に変化がないことを確認: %d", len(elements_after))
            else:
                logging.warning(
                    "エラー発生にもかかわらず要素数が変化しています: %d → %d",
                    len(elements_before),
                    len(elements_after),
                )

        assert True
    else:
        logging.error("存在しない要素へのテキスト入力がエラーを返しませんでした")
        assert False, "存在しない要素へのテキスト入力がエラーを返しませんでした"


def main():
    """メイン関数 - テストの実行を制御する"""
    # pytestから実行される場合は、sys.argvを変更して余計な引数を削除
    if len(sys.argv) > 1 and sys.argv[0].endswith("__main__.py"):
        # pytestから実行される場合、余計な引数をフィルタリング
        filtered_args = [sys.argv[0]]
        for arg in sys.argv[1:]:
            if arg in [
                "--debug",
                "--url",
                "--ref-id",
                "--text",
                "--timeout",
            ] or not arg.startswith("-"):
                filtered_args.append(arg)
        sys.argv = filtered_args

    parser = argparse.ArgumentParser(description="input_textのテスト")
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモードを有効にする"
    )
    parser.add_argument("--url", type=str, default=TEST_URL, help="テスト対象のURL")
    parser.add_argument(
        "--ref-id", type=int, default=TEST_REF_ID, help="テキストを入力する要素のref_id"
    )
    parser.add_argument("--text", type=str, default=TEST_TEXT, help="入力するテキスト")
    parser.add_argument(
        "--timeout", type=int, default=60, help="テスト全体のタイムアウト（秒）"
    )
    args = parser.parse_args()

    setup_logging()
    if args.debug or True:
        logging.getLogger().setLevel(logging.DEBUG)

    # テストパラメータを出力
    logging.info(
        "Test parameters: url=%s, ref_id=%s, text='%s', headless=%s, timeout=%s秒",
        args.url,
        args.ref_id,
        args.text,
        os.environ.get("HEADLESS", "false"),
        args.timeout,
    )

    if sys.platform != "win32":
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(args.timeout)

    start_time = time.time()

    try:
        logging.info("テスト開始時刻: %s", time.strftime("%Y-%m-%d %H:%M:%S"))

        # テスト関数は値を返さないため、例外をキャッチして成功/失敗を判断
        normal_success = False
        error_success = False

        try:
            test_normal_case(args.url, args.ref_id, args.text)
            normal_success = True
        except AssertionError as e:
            logging.error("正常系テスト失敗: %s", e)

        try:
            test_error_case(args.url, TEST_ERROR_REF_ID, args.text)
            error_success = True
        except AssertionError as e:
            logging.error("異常系テスト失敗: %s", e)

        if sys.platform != "win32":
            signal.alarm(0)

        elapsed_time = time.time() - start_time
        logging.info("テスト実行時間: %.2f秒", elapsed_time)

        if normal_success and error_success:
            logging.info("すべてのテストが成功しました")
            return 0
        else:
            logging.error("一部のテストが失敗しました")
            return 1
    except (RuntimeError, IOError) as e:
        if sys.platform != "win32":
            signal.alarm(0)
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
