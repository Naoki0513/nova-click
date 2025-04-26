import streamlit as st
from playwright.sync_api import sync_playwright
from .utils import add_debug_log

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def initialize_browser():
    """Playwrightを使って通常のChromeブラウザを起動します"""
    if st.session_state.get('browser') is None:
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(channel='chrome', headless=False)
            page = browser.new_page()

            # Google を開く
            page.goto("https://www.google.com")
            add_debug_log('Google を開きました', 'ブラウザ')

            st.session_state['playwright'] = playwright
            st.session_state['browser'] = browser
            st.session_state['page'] = page

            add_debug_log('ブラウザを初期化しました', 'ブラウザ')
            return {'status': 'success', 'message': 'ブラウザを初期化しました'}
        except Exception as e:
            add_debug_log(f'ブラウザ初期化エラー: {str(e)}', 'エラー')
            return {'status': 'error', 'message': f'ブラウザ初期化エラー: {str(e)}'}
    return {'status': 'success', 'message': 'ブラウザは既に初期化されています'}

def dispatch_browser_tool(tool_name, params=None):
    """ツール名に基づいて initialize_browser を呼び出します"""
    if tool_name == 'initialize_browser':
        return initialize_browser()
    return {'error': f'不明なツール: {tool_name}'} 