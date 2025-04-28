import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..', '..')))
import streamlit as st
import time
import base64
from PIL import Image
from io import BytesIO

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser
import atexit

st.set_page_config(page_title="CAPTCHA回避テスト", layout="wide")

if 'browser_initialized' not in st.session_state:
    st.session_state.browser_initialized = False
if 'user_agent_result' not in st.session_state:
    st.session_state.user_agent_result = None
if 'webdriver_result' not in st.session_state:
    st.session_state.webdriver_result = None
if 'google_result' not in st.session_state:
    st.session_state.google_result = None
if 'click_result' not in st.session_state:
    st.session_state.click_result = None
if 'input_result' not in st.session_state:
    st.session_state.input_result = None
if 'google_screenshot' not in st.session_state:
    st.session_state.google_screenshot = None
if 'click_screenshot' not in st.session_state:
    st.session_state.click_screenshot = None
if 'input_screenshot' not in st.session_state:
    st.session_state.input_screenshot = None

atexit.register(shutdown_browser)

os.makedirs('streamlit_evidence', exist_ok=True)

def save_screenshot(data, filename):
    """スクリーンショットを保存"""
    try:
        image_data = base64.b64decode(data)
        with open(f'streamlit_evidence/{filename}', 'wb') as f:
            f.write(image_data)
        return f'streamlit_evidence/{filename}'
    except Exception as e:
        st.error(f"スクリーンショット保存エラー: {e}")
        return None

def main():
    st.title('CAPTCHA回避機能テスト')
    st.markdown("このアプリはブラウザの自動化検出回避機能をテストします。")

    st.header("1. ブラウザ起動")
    if st.button('ブラウザ起動', key='init'):
        if not st.session_state.browser_initialized:
            with st.spinner('ブラウザを初期化中...'):
                try:
                    initialize_browser()
                    st.session_state.browser_initialized = True
                    st.success("ブラウザの初期化に成功しました")
                except Exception as e:
                    st.error(f"ブラウザの初期化に失敗しました: {e}")
        else:
            st.info("ブラウザは既に起動しています。")

    st.header("2. UserAgentテスト")
    st.markdown("ブラウザのUserAgentが標準的なブラウザと同様であることを確認します。")
    
    if st.button('UserAgentテスト実行', disabled=not st.session_state.browser_initialized):
        with st.spinner("UserAgent取得中..."):
            _cmd_queue.put({
                'command': 'execute_javascript',
                'params': {
                    'script': 'navigator.userAgent'
                }
            })
            
            st.session_state.user_agent_result = _res_queue.get(timeout=10)
    
    if st.session_state.user_agent_result:
        if st.session_state.user_agent_result.get('status') == 'success':
            st.success("UserAgentの取得に成功しました")
            st.code(st.session_state.user_agent_result.get('result'), language="text")
        else:
            st.error("UserAgentの取得に失敗しました")
        st.json(st.session_state.user_agent_result)

    st.header("3. WebDriverプロパティテスト")
    st.markdown("navigator.webdriverがundefinedであることを確認します。")
    
    if st.button('WebDriverテスト実行', disabled=not st.session_state.browser_initialized):
        with st.spinner("WebDriverプロパティ確認中..."):
            _cmd_queue.put({
                'command': 'execute_javascript',
                'params': {
                    'script': 'navigator.webdriver === undefined'
                }
            })
            
            st.session_state.webdriver_result = _res_queue.get(timeout=10)
    
    if st.session_state.webdriver_result:
        if st.session_state.webdriver_result.get('status') == 'success':
            is_undefined = st.session_state.webdriver_result.get('result')
            if is_undefined:
                st.success("navigator.webdriverはundefinedです（検出回避成功）")
            else:
                st.warning("navigator.webdriverはundefinedではありません（検出回避失敗）")
        else:
            st.error("WebDriverプロパティの確認に失敗しました")
        st.json(st.session_state.webdriver_result)

    st.header("4. Google CAPTCHA回避テスト")
    st.markdown("Googleにアクセスしてキャプチャが表示されないことを確認します。")
    
    if st.button('Googleテスト実行', disabled=not st.session_state.browser_initialized):
        with st.spinner("Googleにアクセス中..."):
            _cmd_queue.put({
                'command': 'navigate',
                'params': {
                    'url': 'https://www.google.com'
                }
            })
            
            time.sleep(5)  # ページが読み込まれるのを待つ
            
            _cmd_queue.put({
                'command': 'screenshot',
                'params': {}
            })
            
            screenshot_result = _res_queue.get(timeout=10)
            st.session_state.google_screenshot = screenshot_result
            
            _cmd_queue.put({
                'command': 'execute_javascript',
                'params': {
                    'script': 'document.body.innerText.includes("CAPTCHA") || document.body.innerText.includes("ロボットではありません") || document.body.innerText.includes("I\'m not a robot")'
                }
            })
            
            captcha_check_result = _res_queue.get(timeout=10)
            st.session_state.google_result = captcha_check_result
    
    if st.session_state.google_screenshot:
        if st.session_state.google_screenshot.get('status') == 'success':
            try:
                image_data = base64.b64decode(st.session_state.google_screenshot.get('data'))
                image_path = save_screenshot(st.session_state.google_screenshot.get('data'), "google_screenshot.png")
                if image_path:
                    st.image(image_path, caption="Googleアクセス結果")
            except Exception as e:
                st.error(f"スクリーンショット表示エラー: {e}")
    
    if st.session_state.google_result:
        if st.session_state.google_result.get('status') == 'success':
            has_captcha = st.session_state.google_result.get('result')
            if has_captcha:
                st.warning("CAPTCHAが検出されました（回避失敗）")
            else:
                st.success("CAPTCHAは検出されませんでした（回避成功）")
        else:
            st.error("CAPTCHA検出確認に失敗しました")
        st.json(st.session_state.google_result)

    st.header("5. クリック機能テスト")
    st.markdown("クリック機能が正常に動作することを確認します。")
    
    if st.button('クリックテスト実行', disabled=not st.session_state.browser_initialized):
        with st.spinner("検索ボックスをクリック中..."):
            _cmd_queue.put({
                'command': 'execute_javascript',
                'params': {
                    'script': 'const input = document.querySelector("input[type=\'text\']"); if(input) { input.click(); true; } else { false; }'
                }
            })
            
            click_result = _res_queue.get(timeout=10)
            st.session_state.click_result = click_result
            
            time.sleep(2)
            
            _cmd_queue.put({
                'command': 'screenshot',
                'params': {}
            })
            
            screenshot_result = _res_queue.get(timeout=10)
            st.session_state.click_screenshot = screenshot_result
    
    if st.session_state.click_result:
        if st.session_state.click_result.get('status') == 'success':
            if st.session_state.click_result.get('result'):
                st.success("検索ボックスのクリックに成功しました")
            else:
                st.warning("検索ボックスが見つかりませんでした")
        else:
            st.error("クリック操作に失敗しました")
        st.json(st.session_state.click_result)
    
    if st.session_state.click_screenshot:
        if st.session_state.click_screenshot.get('status') == 'success':
            try:
                image_path = save_screenshot(st.session_state.click_screenshot.get('data'), "click_test.png")
                if image_path:
                    st.image(image_path, caption="クリック後の状態")
            except Exception as e:
                st.error(f"スクリーンショット表示エラー: {e}")

    st.header("6. テキスト入力機能テスト")
    st.markdown("テキスト入力機能が正常に動作することを確認します。")
    
    if st.button('テキスト入力テスト実行', disabled=not st.session_state.browser_initialized):
        with st.spinner("テキスト入力中..."):
            _cmd_queue.put({
                'command': 'execute_javascript',
                'params': {
                    'script': 'const input = document.querySelector("input[type=\'text\']"); if(input) { input.value = "test automation"; input.dispatchEvent(new Event("input", { bubbles: true })); true; } else { false; }'
                }
            })
            
            input_result = _res_queue.get(timeout=10)
            st.session_state.input_result = input_result
            
            time.sleep(2)
            
            _cmd_queue.put({
                'command': 'screenshot',
                'params': {}
            })
            
            screenshot_result = _res_queue.get(timeout=10)
            st.session_state.input_screenshot = screenshot_result
    
    if st.session_state.input_result:
        if st.session_state.input_result.get('status') == 'success':
            if st.session_state.input_result.get('result'):
                st.success("テキスト入力に成功しました")
            else:
                st.warning("検索ボックスが見つかりませんでした")
        else:
            st.error("テキスト入力に失敗しました")
        st.json(st.session_state.input_result)
    
    if st.session_state.input_screenshot:
        if st.session_state.input_screenshot.get('status') == 'success':
            try:
                image_path = save_screenshot(st.session_state.input_screenshot.get('data'), "input_test.png")
                if image_path:
                    st.image(image_path, caption="テキスト入力後の状態")
            except Exception as e:
                st.error(f"スクリーンショット表示エラー: {e}")

    st.header("7. ブラウザ終了")
    if st.button('ブラウザ終了', disabled=not st.session_state.browser_initialized):
        with st.spinner('ブラウザを終了中...'):
            shutdown_browser()
            st.session_state.browser_initialized = False
            st.session_state.user_agent_result = None
            st.session_state.webdriver_result = None
            st.session_state.google_result = None
            st.session_state.click_result = None
            st.session_state.input_result = None
            st.session_state.google_screenshot = None
            st.session_state.click_screenshot = None
            st.session_state.input_screenshot = None
            st.success("ブラウザを終了しました")
            st.rerun()  # 状態リセット後に再描画

if __name__ == '__main__':
    main()
