import streamlit as st
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser
from agent.utils import add_debug_log, display_debug_logs, clear_conversation_history

def test_user_agent():
    """UserAgentが標準的なブラウザと同様であることを確認"""
    initialize_browser()
    time.sleep(2)  # ブラウザの初期化を待つ
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.userAgent'
        }
    })
    
    result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    return result

def test_webdriver_property():
    """navigator.webdriverがundefinedであることを確認"""
    initialize_browser()
    time.sleep(2)  # ブラウザの初期化を待つ
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.webdriver === undefined'
        }
    })
    
    result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    return result

def test_google_access():
    """Googleにアクセスしてキャプチャが表示されないことを確認"""
    initialize_browser()
    time.sleep(2)  # ブラウザの初期化を待つ
    
    _cmd_queue.put({
        'command': 'navigate',
        'params': {
            'url': 'https://www.google.com'
        }
    })
    
    time.sleep(5)
    
    _cmd_queue.put({
        'command': 'screenshot',
        'params': {}
    })
    
    screenshot_result = _res_queue.get(timeout=10)
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'document.body.innerText.includes("CAPTCHA") || document.body.innerText.includes("ロボットではありません") || document.body.innerText.includes("I\'m not a robot")'
        }
    })
    
    captcha_check_result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    return {
        'screenshot': screenshot_result,
        'has_captcha': captcha_check_result
    }

def run_tests():
    st.title("CAPTCHA回避機能テスト")
    
    if st.button("UserAgentテスト実行"):
        with st.spinner("テスト実行中..."):
            result = test_user_agent()
            st.success("テスト完了")
            st.json(result)
    
    if st.button("WebDriverプロパティテスト実行"):
        with st.spinner("テスト実行中..."):
            result = test_webdriver_property()
            st.success("テスト完了")
            st.json(result)
    
    if st.button("Google CAPTCHA回避テスト実行"):
        with st.spinner("テスト実行中..."):
            result = test_google_access()
            st.success("テスト完了")
            if 'screenshot' in result and result['screenshot'].get('status') == 'success':
                import base64
                from io import BytesIO
                from PIL import Image
                
                image_data = base64.b64decode(result['screenshot'].get('data'))
                image = Image.open(BytesIO(image_data))
                st.image(image)
            st.write(f"CAPTCHA検出: {result.get('has_captcha', {}).get('result', 'unknown')}")
    
    display_debug_logs()

if __name__ == "__main__":
    run_tests()
