import os
import time
import sys
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser

os.makedirs('test_evidence', exist_ok=True)

def test_user_agent():
    print('Testing UserAgent...')
    initialize_browser()
    time.sleep(2)
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.userAgent'
        }
    })
    
    result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    img = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), 'UserAgent Test Result:', fill=(0, 0, 0))
    d.text((10, 40), str(result), fill=(0, 0, 0))
    
    img.save('test_evidence/user_agent_test.png')
    print('UserAgent test completed and saved to test_evidence/user_agent_test.png')
    return result

def test_webdriver_property():
    print('Testing WebDriver property...')
    initialize_browser()
    time.sleep(2)
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.webdriver === undefined'
        }
    })
    
    result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    img = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), 'WebDriver Property Test Result:', fill=(0, 0, 0))
    d.text((10, 40), str(result), fill=(0, 0, 0))
    
    img.save('test_evidence/webdriver_test.png')
    print('WebDriver test completed and saved to test_evidence/webdriver_test.png')
    return result

def test_google_access():
    print('Testing Google access...')
    initialize_browser()
    time.sleep(2)
    
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
    
    if screenshot_result.get('status') == 'success':
        image_data = base64.b64decode(screenshot_result.get('data'))
        with open('test_evidence/google_screenshot.png', 'wb') as f:
            f.write(image_data)
    
    img = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), 'Google CAPTCHA Test Result:', fill=(0, 0, 0))
    d.text((10, 40), f'CAPTCHA detected: {captcha_check_result.get("result")}', fill=(0, 0, 0))
    
    img.save('test_evidence/captcha_test.png')
    print('Google access test completed and saved to test_evidence/google_screenshot.png and test_evidence/captcha_test.png')
    return {'screenshot': screenshot_result, 'has_captcha': captcha_check_result}

def test_click_element():
    print('Testing click element...')
    initialize_browser()
    time.sleep(2)
    
    _cmd_queue.put({
        'command': 'navigate',
        'params': {
            'url': 'https://www.google.com'
        }
    })
    
    time.sleep(3)
    
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'document.querySelector("input[type=\'text\']").click()'
        }
    })
    
    result = _res_queue.get(timeout=10)
    
    _cmd_queue.put({
        'command': 'screenshot',
        'params': {}
    })
    
    screenshot_result = _res_queue.get(timeout=10)
    shutdown_browser()
    
    if screenshot_result.get('status') == 'success':
        image_data = base64.b64decode(screenshot_result.get('data'))
        with open('test_evidence/click_test.png', 'wb') as f:
            f.write(image_data)
    
    print('Click element test completed and saved to test_evidence/click_test.png')
    return result

if __name__ == "__main__":
    user_agent_result = test_user_agent()
    webdriver_result = test_webdriver_property()
    google_result = test_google_access()
    click_result = test_click_element()

    print('\nTest Summary:')
    print(f'UserAgent Test: {user_agent_result.get("status") if user_agent_result else "Failed"}')
    print(f'WebDriver Test: {webdriver_result.get("status") if webdriver_result else "Failed"}')
    
    has_captcha = google_result.get("has_captcha") if google_result else None
    captcha_status = has_captcha.get("status") if has_captcha else "Failed"
    print(f'Google CAPTCHA Test: {captcha_status}')
    
    print(f'Click Element Test: {click_result.get("status") if click_result else "Failed"}')
