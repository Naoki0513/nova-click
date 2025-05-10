"""exceptions

ブラウザ操作エージェントで使用する共通例外クラス群。

共通の基底例外 ``BrowserAgentError`` を定義し、
機能領域ごとにサブクラスを用意することで
例外ハンドリングの一貫性を保ちます。
"""

from __future__ import annotations

class BrowserAgentError(Exception):
    """ライブラリ全体の基底例外。"""


class BedrockAPIError(BrowserAgentError):
    """Bedrock API 呼び出しに関する例外。"""


class BrowserWorkerError(BrowserAgentError):
    """ブラウザワーカースレッド関連の例外。""" 