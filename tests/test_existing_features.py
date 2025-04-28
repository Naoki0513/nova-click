import streamlit as st
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser
from agent.utils import add_debug_log, display_debug_logs, clear_conversation_history

def test_click_element():
    """クリック機能が正常に動作することを確認"""
    initialize_browser()
    time.sleep(2)  # ブラウザの初期化を待つ
    
    _cmd_queue.put({
        'command': 'navigate',
        'params': {
            'url': 'https://www.google.com'
        }
    })
    
    time.sleep(3)
    
    _cmd_queue.put({
        'command': 'click_element',
        'params': {
            'role': 'textbox',
            'name': 'Search'
        }
    })
    
    result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    return result

def test_input_text():
    """テキスト入力機能が正常に動作することを確認"""
    initialize_browser()
    time.sleep(2)  # ブラウザの初期化を待つ
    
    _cmd_queue.put({
        'command': 'navigate',
        'params': {
            'url': 'https://www.google.com'
        }
    })
    
    time.sleep(3)
    
    _cmd_queue.put({
        'command': 'input_text',
        'params': {
            'role': 'textbox',
            'name': 'Search',
            'text': 'test automation'
        }
    })
    
    result = _res_queue.get(timeout=10)
    
    _cmd_queue.put({
        'command': 'screenshot',
        'params': {}
    })
    
    screenshot_result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    return {
        'input_result': result,
        'screenshot': screenshot_result
    }

def run_tests():
    st.title("既存機能テスト")
    
    if st.button("クリック機能テスト実行"):
        with st.spinner("テスト実行中..."):
            result = test_click_element()
            st.success("テスト完了")
            st.json(result)
    
    if st.button("テキスト入力機能テスト実行"):
        with st.spinner("テスト実行中..."):
            result = test_input_text()
            st.success("テスト完了")
            st.json(result.get('input_result'))
            if 'screenshot' in result and result['screenshot'].get('status') == 'success':
                st.image(result['screenshot'].get('data'))
    
    display_debug_logs()

if __name__ == "__main__":
    run_tests()
