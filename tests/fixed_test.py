import os
import time
import sys
import base64
from PIL import Image
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser

os.makedirs('test_evidence', exist_ok=True)

def test_captcha_avoidance():
    """CAPTCHA回避機能のテスト"""
    print("Starting CAPTCHA avoidance tests...")
    
    print("\n1. Testing UserAgent...")
    initialize_browser()
    time.sleep(2)
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.userAgent'
        }
    })
    
    user_agent_result = _res_queue.get(timeout=10)
    print(f"UserAgent result: {user_agent_result}")
    
    print("\n2. Testing WebDriver property...")
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.webdriver === undefined'
        }
    })
    
    webdriver_result = _res_queue.get(timeout=10)
    print(f"WebDriver undefined: {webdriver_result}")
    
    print("\n3. Testing Google access for CAPTCHA...")
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
    print(f"CAPTCHA detected: {captcha_check_result}")
    
    if screenshot_result and screenshot_result.get('status') == 'success' and screenshot_result.get('data'):
        try:
            image_data = base64.b64decode(screenshot_result.get('data'))
            with open('test_evidence/google_screenshot.png', 'wb') as f:
                f.write(image_data)
            print("Screenshot saved to test_evidence/google_screenshot.png")
            
            img = Image.open(BytesIO(image_data))
            img.save('test_evidence/google_screenshot.png')
        except Exception as e:
            print(f"Error saving screenshot: {e}")
    
    print("\n4. Testing click functionality...")
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'const input = document.querySelector("input[type=\'text\']"); if(input) { input.click(); true; } else { false; }'
        }
    })
    
    click_result = _res_queue.get(timeout=10)
    print(f"Click result: {click_result}")
    
    print("\n5. Testing input text functionality...")
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'const input = document.querySelector("input[type=\'text\']"); if(input) { input.value = "test automation"; input.dispatchEvent(new Event("input", { bubbles: true })); true; } else { false; }'
        }
    })
    
    input_result = _res_queue.get(timeout=10)
    print(f"Input text result: {input_result}")
    
    _cmd_queue.put({
        'command': 'screenshot',
        'params': {}
    })
    
    final_screenshot_result = _res_queue.get(timeout=10)
    
    if final_screenshot_result and final_screenshot_result.get('status') == 'success' and final_screenshot_result.get('data'):
        try:
            image_data = base64.b64decode(final_screenshot_result.get('data'))
            with open('test_evidence/final_screenshot.png', 'wb') as f:
                f.write(image_data)
            print("Final screenshot saved to test_evidence/final_screenshot.png")
        except Exception as e:
            print(f"Error saving final screenshot: {e}")
    
    shutdown_browser()
    
    print("\nTest Summary:")
    print(f"UserAgent Test: {user_agent_result.get('status') if user_agent_result else 'Failed'}")
    print(f"WebDriver Test: {webdriver_result.get('status') if webdriver_result else 'Failed'}")
    print(f"Google CAPTCHA Test: {captcha_check_result.get('status') if captcha_check_result else 'Failed'}")
    print(f"Click Test: {click_result.get('status') if click_result else 'Failed'}")
    print(f"Input Text Test: {input_result.get('status') if input_result else 'Failed'}")
    
    with open('test_evidence/test_results.txt', 'w') as f:
        f.write("CAPTCHA回避機能テスト結果\n\n")
        f.write(f"UserAgent Test: {user_agent_result.get('status') if user_agent_result else 'Failed'}\n")
        f.write(f"UserAgent Value: {user_agent_result.get('result') if user_agent_result else 'N/A'}\n\n")
        f.write(f"WebDriver Test: {webdriver_result.get('status') if webdriver_result else 'Failed'}\n")
        f.write(f"WebDriver undefined: {webdriver_result.get('result') if webdriver_result else 'N/A'}\n\n")
        f.write(f"Google CAPTCHA Test: {captcha_check_result.get('status') if captcha_check_result else 'Failed'}\n")
        f.write(f"CAPTCHA detected: {captcha_check_result.get('result') if captcha_check_result else 'N/A'}\n\n")
        f.write(f"Click Test: {click_result.get('status') if click_result else 'Failed'}\n\n")
        f.write(f"Input Text Test: {input_result.get('status') if input_result else 'Failed'}\n")
    
    return {
        'user_agent': user_agent_result,
        'webdriver': webdriver_result,
        'captcha_check': captcha_check_result,
        'click': click_result,
        'input_text': input_result
    }

if __name__ == "__main__":
    test_captcha_avoidance()
