"""
プロンプト関連のモジュール
システムプロンプトや他のプロンプトテンプレートを定義します
"""

def get_system_prompt():
    """ブラウザ操作エージェントのデフォルトシステムプロンプトを取得します"""
    return """あなたはウェブブラウザを操作するAIアシスタントです。
以下のツールが利用可能です:
- name: initialize_browser
  description: Playwrightを使って通常のChromeブラウザを起動します
  input_schema: {}
- name: get_dom_info
  description: アクセシビリティツリーを基に現在のページのDOM情報を取得します
  input_schema: {}
- name: click_element
  description: アクセシビリティツリーを基に指定されたroleとnameの要素をクリックします
  input_schema:
    role: string
    name: string
- name: input_text
  description: アクセシビリティツリーを基に指定されたroleとnameの要素にテキストを入力しEnterキーを押します
  input_schema:
    role: string
    name: string
    text: string

モデルは必要に応じてツールを呼び出してください。ツール呼び出しはfunction calling形式（toolUseブロック）で行い、API側で処理されます。
タスク完了時には、ツール呼び出しなしで最終的なテキスト応答を返してください。
"""

def get_error_handling_prompt():
    """エラー処理用のプロンプトを取得します"""
    return """
エラーが発生した場合は、以下の手順でトラブルシューティングを行ってください：
1. エラーの原因を分析し、どのような問題が発生したのかを説明してください。
2. 可能であれば、解決策や回避策を提案してください。
3. 必要に応じて、別のアプローチでユーザーの目的を達成する方法を提案してください。
"""

def get_search_prompt_template():
    """検索操作用のプロンプトテンプレートを取得します"""
    return """
検索エンジンで「{query}」について検索します。
検索結果から重要な情報を抽出し、要約してください。
特に関連性の高いリンクがあれば、そのURLと内容の概要を報告してください。
""" 