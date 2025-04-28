import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..', '..')))
import streamlit as st
from agent.browser.worker import initialize_browser, shutdown_browser
from agent.browser.tools import click_element, input_text, get_ax_tree
import atexit

# ★最初にページ設定を呼び出す
st.set_page_config(page_title="統合ブラウザテスト", layout="wide")

# --- Session State の初期化 ---
# 各操作の結果を保持
if 'init_result' not in st.session_state:
    st.session_state.init_result = None
if 'input_result' not in st.session_state:
    st.session_state.input_result = None
if 'click_result' not in st.session_state:
    st.session_state.click_result = None
if 'ax_tree_result' not in st.session_state:
    st.session_state.ax_tree_result = None
# ブラウザ初期化済みフラグ
if 'browser_initialized' not in st.session_state:
    st.session_state.browser_initialized = False

# --- 終了処理登録 ---
# アプリケーション終了時にブラウザを閉じる処理を登録
atexit.register(shutdown_browser)

def main():
    st.title('統合 Playwright ブラウザ操作テスト')

    # --- ブラウザ初期化 ---
    st.markdown("--- ### 1. ブラウザ起動 ---")
    if st.button('ブラウザ起動', key='init'):
        if not st.session_state.browser_initialized:
            with st.spinner('ブラウザを初期化中...'):
                st.session_state.init_result = initialize_browser()
                if st.session_state.init_result.get('status') == 'success':
                    st.session_state.browser_initialized = True
        else:
            st.info("ブラウザは既に起動しています。")

    if st.session_state.init_result:
        st.json(st.session_state.init_result)

    # --- テキスト入力 ---
    st.markdown("--- ### 2. テキスト入力 ---")
    col1, col2, col3 = st.columns(3)
    with col1:
        input_role = st.text_input("入力要素の Role", "combobox", key="input_role")
    with col2:
        input_name = st.text_input("入力要素の Name", "検索", key="input_name")
    with col3:
        input_value = st.text_input("入力するテキスト", "streamlit", key="input_value")

    if st.button('テキスト入力実行', key='input_exec', disabled=not st.session_state.browser_initialized):
        if st.session_state.browser_initialized:
            with st.spinner('テキストを入力中...'):
                st.session_state.input_result = input_text(input_role, input_name, input_value)
        else:
            st.error("ブラウザが起動していません。先に「ブラウザ起動」ボタンを押してください。")

    if st.session_state.input_result:
        st.json(st.session_state.input_result)

    # --- 要素クリック ---
    st.markdown("--- ### 3. 要素クリック ---")
    col1_click, col2_click = st.columns(2)
    with col1_click:
        click_role = st.text_input("クリック要素の Role", "button", key="click_role")
    with col2_click:
        click_name = st.text_input("クリック要素の Name", "Google 検索", key="click_name")

    if st.button('要素クリック実行', key='click_exec', disabled=not st.session_state.browser_initialized):
        if st.session_state.browser_initialized:
            with st.spinner('要素をクリック中...'):
                st.session_state.click_result = click_element(click_role, click_name)
        else:
            st.error("ブラウザが起動していません。先に「ブラウザ起動」ボタンを押してください。")

    if st.session_state.click_result:
        st.json(st.session_state.click_result)

    # --- AxTree 取得 ---
    st.markdown("--- ### 4. AxTree 取得 ---")
    if st.button('AxTree取得', key='ax_exec', disabled=not st.session_state.browser_initialized):
        if st.session_state.browser_initialized:
            with st.spinner('AxTree情報を取得中...'):
                st.session_state.ax_tree_result = get_ax_tree()
        else:
            st.error("ブラウザが起動していません。先に「ブラウザ起動」ボタンを押してください。")

    st.markdown("--- ### 取得結果表示 --- ")
    if st.session_state.ax_tree_result:
        st.subheader("AxTree")
        st.json(st.session_state.ax_tree_result)
    else:
        st.write("AxTreeはまだ取得されていません。")

    # --- ブラウザ終了 (手動) ---
    st.markdown("--- ### 5. ブラウザ終了 ---")
    if st.button('ブラウザ終了', key='shutdown', disabled=not st.session_state.browser_initialized):
        with st.spinner('ブラウザを終了中...'):
            result = shutdown_browser()
            st.json(result)
            # 状態をリセット
            st.session_state.browser_initialized = False
            st.session_state.init_result = None
            st.session_state.input_result = None
            st.session_state.click_result = None
            st.session_state.ax_tree_result = None
            st.rerun() # 状態リセット後に再描画


if __name__ == '__main__':
    main() 