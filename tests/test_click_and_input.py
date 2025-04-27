import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..', '..')))
import streamlit as st
from agent.browser.worker import initialize_browser, shutdown_browser
from agent.browser.tools import click_element, input_text
import atexit


def main():
    st.title('Playwright クリック＆入力 テスト')

    # セッションステートの初期化
    if 'init_result' not in st.session_state:
        st.session_state.init_result = None
    if 'input_result' not in st.session_state:
        st.session_state.input_result = None
    if 'click_result' not in st.session_state:
        st.session_state.click_result = None

    # 終了処理の登録
    atexit.register(shutdown_browser)

    # ブラウザ初期化
    if st.button('ブラウザ初期化', key='init'):
        with st.spinner('ブラウザを初期化中...'):
            st.session_state.init_result = initialize_browser()
    if st.session_state.init_result:
        st.json(st.session_state.init_result)

    st.markdown('---')

    # comboboxにテキストを入力
    if st.button('検索ボックスに "amazon" を入力', key='input'):
        with st.spinner('テキストを入力中...'):
            st.session_state.input_result = input_text('combobox', '検索', 'amazon')
    if st.session_state.input_result:
        st.json(st.session_state.input_result)

    st.markdown('---')

    # 検索ボタンをクリック
    if st.button('検索ボタンをクリック', key='click'):
        with st.spinner('ボタンをクリック中...'):
            st.session_state.click_result = click_element('button', 'Google 検索')
    if st.session_state.click_result:
        st.json(st.session_state.click_result)

if __name__ == '__main__':
    main() 