from __future__ import annotations

"""pytest ラッパーテスト

既存のスクリプトベース E2E テスト (`tests/*.py`) を pytest から呼び出せる
ようにするための薄いラッパーです。各スクリプトの `main()` が 0 を返せば
成功と見なします。
"""

import os
import importlib

# 全テストスクリプトと期待される戻り値
_TEST_SCRIPTS: list[str] = [
    "tests.get_aria_snapshot",
    "tests.click_element_test",
    "tests.input_text_test",
    "tests.main_e2e_test",
]

# すべてのテストで共通の環境変数を設定
os.environ.setdefault("HEADLESS", "true")


@staticmethod  # noqa: D401
def _run_module_main(module_name: str) -> int:
    """指定モジュールを import し、``main()`` を実行して戻り値を返す。"""

    module = importlib.import_module(module_name)
    return int(module.main())  # type: ignore[attr-defined]


def test_e2e_scripts() -> None:
    """各スクリプトの `main()` が 0 を返すことを確認する。"""

    failures: list[str] = []
    for mod_name in _TEST_SCRIPTS:
        exit_code = _run_module_main(mod_name)
        if exit_code != 0:
            failures.append(f"{mod_name} exited with {exit_code}")

    assert not failures, "\n".join(failures) 