import streamlit as st
from playwright.sync_api import sync_playwright
from .utils import add_debug_log

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def initialize_browser():
    """Playwrightを使って通常のChromeブラウザを起動します"""
    # ログ: ブラウザ初期化開始
    add_debug_log("ブラウザ初期化開始")
    if st.session_state.get('browser') is None:
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(channel='chrome', headless=False)
            page = browser.new_page()

            # Google を開く
            page.goto("https://www.google.com")
            add_debug_log('Google を開きました')

            st.session_state['playwright'] = playwright
            st.session_state['browser'] = browser
            st.session_state['page'] = page

            add_debug_log('ブラウザを初期化しました')
            return {'status': 'success', 'message': 'ブラウザを初期化しました'}
        except Exception as e:
            # ログ: 例外発生
            add_debug_log(f'ブラウザ初期化エラー: {str(e)}')
            return {'status': 'error', 'message': f'ブラウザ初期化エラー: {str(e)}'}
    # 既に初期化済み
    add_debug_log('ブラウザは既に初期化されています')
    return {'status': 'success', 'message': 'ブラウザは既に初期化されています'}

def get_dom_info():
    """現在のページのDOM情報を取得します"""
    # ログ: DOM取得開始
    add_debug_log("DOM取得開始")
    page = st.session_state.get('page')
    if page is None:
        add_debug_log('ブラウザが初期化されていません')
        return {'status': 'error', 'message': 'ブラウザが初期化されていません'}
    try:
        dom = page.content()
        add_debug_log('DOM情報を取得しました')
        return {'status': 'success', 'dom': dom}
    except Exception as e:
        add_debug_log(f'DOM取得エラー: {str(e)}')
        return {'status': 'error', 'message': f'DOM取得エラー: {str(e)}'}

def dispatch_browser_tool(tool_name, params=None):
    """ツール名に基づいて initialize_browser を呼び出します"""
    # ログ: ツール呼び出し
    add_debug_log(f'ツール呼び出し: {tool_name}, params: {params}')
    if tool_name == 'initialize_browser':
        return initialize_browser()
    elif tool_name == 'get_dom_info':
        return get_dom_info()
    return {'error': f'不明なツール: {tool_name}'} 