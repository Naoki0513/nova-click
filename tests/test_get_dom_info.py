import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..', '..')))
import streamlit as st
from agent.browser_tools import initialize_browser, get_raw_html, get_structured_dom, get_ax_tree, shutdown_browser
import atexit

def main():
    st.title('Playwright DOM情報取得テスト')

    # --- Session State の初期化 ---
    if 'init_result' not in st.session_state:
        st.session_state.init_result = None
    if 'raw_html_result' not in st.session_state:
        st.session_state.raw_html_result = None
    if 'structured_dom_result' not in st.session_state:
        st.session_state.structured_dom_result = None
    if 'ax_tree_result' not in st.session_state:
        st.session_state.ax_tree_result = None

    # --- 終了処理登録 ---
    # アプリケーション終了時にブラウザを閉じる処理を登録
    # Streamlit のセッション終了時に呼ばれる保証はないため注意
    atexit.register(shutdown_browser)

    # --- 操作ボタン --- (初期化は独立して配置)
    if st.button('ブラウザ初期化', key='init'):
        with st.spinner('ブラウザを初期化中...'):
            st.session_state.init_result = initialize_browser()

    # 初期化結果表示 (オプション)
    if st.session_state.init_result:
        st.json(st.session_state.init_result)

    st.markdown("--- ### データ取得 ---")
    # ボタンは横並びのままにする
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button('Raw HTML取得', key='raw'):
            with st.spinner('Raw HTML を取得中...'):
                st.session_state.raw_html_result = get_raw_html()

    with col_btn2:
        if st.button('構造化DOM取得', key='structured'):
            st.info("`agent/js/buildDomTree.js` が存在しない場合、この処理は失敗します。")
            with st.spinner('構造化DOM情報を取得中...'):
                st.session_state.structured_dom_result = get_structured_dom()

    with col_btn3:
        if st.button('AxTree取得', key='ax'):
            with st.spinner('AxTree情報を取得中...'):
                st.session_state.ax_tree_result = get_ax_tree()

    st.markdown("--- ### 取得結果表示 (縦並び) ---")
    # --- 結果表示エリア (縦並び) ---

    # Raw HTML 表示
    st.subheader("Raw HTML")
    if st.session_state.raw_html_result:
        result = st.session_state.raw_html_result
        if result['status'] == 'success':
            st.text_area("Raw HTML Content", result.get('html', ''), height=300, key='raw_html_area_v') # keyを変更
        else:
            st.error(f"エラー: {result.get('message', '不明なエラー')}")
    else:
        st.write("Raw HTML はまだ取得されていません。")

    st.markdown("---") # 区切り線

    # 構造化DOM 表示
    st.subheader("構造化DOM")
    if st.session_state.structured_dom_result:
        result = st.session_state.structured_dom_result
        st.json(result)
    else:
        st.write("構造化DOMはまだ取得されていません。")

    st.markdown("---") # 区切り線

    # AxTree 表示
    st.subheader("AxTree")
    if st.session_state.ax_tree_result:
        result = st.session_state.ax_tree_result
        st.json(result)
    else:
        st.write("AxTreeはまだ取得されていません。")

    # --- デバッグログ (オプション) ---
    # st.markdown("---")
    # st.subheader("デバッグログ")
    # from agent.utils import get_debug_logs # 必要に応じて utils にログ取得関数を作成
    # st.text_area("Logs", "\n".join(get_debug_logs()), height=200)

if __name__ == '__main__':
    main() 