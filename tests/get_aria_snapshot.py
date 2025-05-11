#!/usr/bin/env python3
"""ARIA Snapshot取得用テストスクリプト

ブラウザワーカーを起動し、指定(またはデフォルト)のURLに移動してから
最新のARIA Snapshotを取得してコンソールに出力します。

環境変数:
    HEADLESS - 'true'の場合、ブラウザをヘッドレスモードで実行します
"""
import json
import logging
import os
import sys
import traceback

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.browser import (cleanup_browser, get_aria_snapshot, goto_url,
                         initialize_browser)
from src.utils import setup_logging


# テスト用パラメータ（ここを変更することでテスト条件を設定できます）
TEST_URL = "https://www.google.co.jp/maps/"


def main():
    """
    メイン実行関数 - ARIAスナップショットの取得テストを実行します。
    """
    # 設定を適用
    url = TEST_URL

    setup_logging()
    # ログレベルを常にDEBUGに設定
    logging.getLogger().setLevel(logging.DEBUG)

    # テストパラメータを出力
    logging.info(
        "Test parameters: url=%s, headless=%s",
        url,
        os.environ.get("HEADLESS", "false"),
    )

    try:
        # ブラウザ起動
        init_res = initialize_browser()
        if init_res.get("status") != "success":
            logging.error("ブラウザ初期化に失敗: %s", init_res.get("message"))
            return 1

        # URLに移動
        goto_res = goto_url(url)
        if goto_res.get("status") != "success":
            logging.error("URL移動に失敗: %s", goto_res.get("message"))
            return 1

        current_url = goto_res.get("current_url", url)
        logging.info("ページに移動しました: %s", current_url)

        # 検証: 正しいURLに移動できたか
        if current_url != url and not current_url.startswith(url):
            logging.warning(
                "移動先URLが指定URLと異なります: 指定=%s, 実際=%s",
                url,
                current_url,
            )

        # ARIA Snapshot取得
        aria_res = get_aria_snapshot()
        if aria_res.get("status") != "success":
            logging.error("ARIA Snapshot取得に失敗: %s", aria_res.get("message"))
            return 1

        snapshot = aria_res.get("aria_snapshot", [])
        logging.info("取得した要素数: %d", len(snapshot))

        # 検証: スナップショットの基本的な有効性チェック
        if not snapshot:
            logging.error("ARIAスナップショットが空です")
            return 1

        # スナップショットの基本的な構造を検証
        valid_structure = all(isinstance(e, dict) for e in snapshot)
        if not valid_structure:
            logging.error("ARIAスナップショットの構造が無効です")
            return 1

        # 基本的な要素の存在確認
        key_roles = ["document", "heading", "link"]
        found_roles = {role: False for role in key_roles}

        for element in snapshot:
            role = element.get("role")
            if role in key_roles:
                found_roles[role] = True
                logging.info(
                    "基本要素を発見: role=%s, name=%s",
                    role,
                    element.get("name", "(名前なし)"),
                )

        for role, found in found_roles.items():
            if found:
                logging.info("基本要素 '%s' が存在します", role)
            else:
                logging.warning("基本要素 '%s' が見つかりません", role)

        # 結果出力（最初の10要素だけ詳細表示）
        logging.info("スナップショットの最初の10要素:")
        for i, elem in enumerate(snapshot[:10]):
            logging.info(
                "要素 #%d: ref_id=%s, role=%s, name=%s",
                i + 1,
                elem.get("ref_id"),
                elem.get("role"),
                elem.get("name"),
            )

        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, IOError) as e:
        # より具体的な例外タイプを指定
        logging.error("テスト実行中にエラーが発生しました: %s", e)
        traceback.print_exc()
        return 1
    finally:
        # 必ずブラウザをクリーンアップ
        try:
            cleanup_browser()
            logging.info("ブラウザのクリーンアップが完了しました")
        except Exception as e:
            logging.error("ブラウザのクリーンアップ中にエラーが発生しました: %s", e)


if __name__ == "__main__":
    sys.exit(main())
