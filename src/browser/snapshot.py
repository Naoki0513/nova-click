from __future__ import annotations

"""browser.snapshot

Playwright の ``page`` オブジェクトを用いて ARIA Snapshot を取得する
ユーティリティ関数を集めたモジュールです。JavaScript/Evaluate を
1 箇所に集約することで、ブラウザワーカースレッド以外でも再利用
しやすくしています。
"""

from typing import Any, Dict, List, Tuple

import main as constants
from ..utils import add_debug_log

__all__ = [
    "take_aria_snapshot",
    "get_snapshot_with_stats",
]

_JS_GET_SNAPSHOT = r"""() => {
    const snapshotResult = [];
    let refIdCounter = 1;
    let errorCount = 0; // エラーカウント用

    try {
        // ドキュメント内の対話可能な要素を取得
        const interactiveElements = document.querySelectorAll(
            'button, a, input, select, textarea, ' +
            '[role="button"], [role="link"], [role="checkbox"], [role="radio"], ' +
            '[role="tab"], [role="combobox"], [role="textbox"], [role="searchbox"]'
        );

        interactiveElements.forEach(element => {
            try {
                // role を決定
                let role = element.getAttribute('role');
                if (!role) {
                    switch (element.tagName.toLowerCase()) {
                        case 'button': role = 'button'; break;
                        case 'a': role = 'link'; break;
                        case 'input':
                            switch (element.type) {
                                case 'text': role = 'textbox'; break;
                                case 'checkbox': role = 'checkbox'; break;
                                case 'radio': role = 'radio'; break;
                                case 'search': role = 'searchbox'; break;
                                default: role = element.type; break;
                            }
                            break;
                        case 'select': role = 'combobox'; break;
                        case 'textarea': role = 'textbox'; break;
                        default: role = 'unknown'; break;
                    }
                }

                // 要素名 (name/label) を取得
                let name = '';
                if (element.hasAttribute('aria-label')) {
                    name = element.getAttribute('aria-label');
                } else if (element.hasAttribute('aria-labelledby')) {
                    const labelledById = element.getAttribute('aria-labelledby');
                    const labelEl = document.getElementById(labelledById);
                    if (labelEl) {
                        name = labelEl.textContent.trim();
                    }
                } else if (element.hasAttribute('placeholder')) {
                    name = element.getAttribute('placeholder');
                } else if (element.hasAttribute('name')) {
                    name = element.getAttribute('name');
                } else if (element.hasAttribute('title')) {
                    name = element.getAttribute('title');
                } else if (element.hasAttribute('alt')) {
                    name = element.getAttribute('alt');
                } else {
                    name = (element.textContent || '').trim();
                    if (element.tagName.toLowerCase() === 'input' && element.id) {
                        const labels = document.querySelectorAll(`label[for="${element.id}"]`);
                        if (labels.length > 0) {
                            name = labels[0].textContent.trim();
                        }
                    }
                }

                // ref-id を付与
                const refIdValue = refIdCounter++;
                element.setAttribute('data-ref-id', `ref-${refIdValue}`);

                // 可視性チェック
                const rect = element.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 &&
                                  window.getComputedStyle(element).visibility !== 'hidden' &&
                                  window.getComputedStyle(element).display !== 'none';

                const isDisabled = element.disabled === true || element.hasAttribute('disabled');
                const isReadOnly = element.readOnly === true || element.hasAttribute('readonly');

                if (!isDisabled && !isReadOnly && isVisible && role !== 'unknown') {
                    snapshotResult.push({
                        role: role,
                        name: name || 'Unnamed Element',
                        ref_id: refIdValue
                    });
                }
            } catch (elError) {
                console.error('Error processing element:', element, elError);
                errorCount++;
            }
        });
    } catch (mainError) {
        console.error('Snapshot process error:', mainError);
        return { error: `Snapshot process error: ${mainError.message}`, errorCount: errorCount, snapshot: snapshotResult };
    }

    return { snapshot: snapshotResult, errorCount: errorCount };
}"""

async def get_snapshot_with_stats(page: Any) -> Dict[str, Any]:
    """Playwright ``page`` からスナップショットを取得し統計情報を付与して返します。"""

    add_debug_log("snapshot.get_snapshot_with_stats: JavaScript でスナップショットを取得")
    result = await page.evaluate(_JS_GET_SNAPSHOT)

    # 期待する型チェック
    if not isinstance(result, dict):
        add_debug_log("snapshot.get_snapshot_with_stats: JS から期待しない型が返却されました", level="WARNING")
        return {"snapshot": [], "errorCount": 1, "error": "Unexpected return from JS"}

    return result  # type: ignore[return-value]


async def take_aria_snapshot(page: Any) -> List[Dict[str, Any]]:
    """``page`` から要素のフラットリスト(スナップショット)のみを取得して返します。"""

    data = await get_snapshot_with_stats(page)
    snapshot_list = data.get("snapshot", [])

    # ALLOWED_ROLES でフィルタリング
    filtered = [e for e in snapshot_list if e.get("role") in constants.ALLOWED_ROLES]

    add_debug_log(f"snapshot.take_aria_snapshot: {len(filtered)} 要素を取得")
    return filtered 