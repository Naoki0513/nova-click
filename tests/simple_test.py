import os
import time
import sys
import base64
from PIL import Image
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser

os.makedirs('test_evidence', exist_ok=True)

def run_test():
    print('Starting CAPTCHA avoidance test...')
    
    initialize_browser()
    time.sleep(2)
    
    print('Testing UserAgent...')
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.userAgent'
        }
    })
    
    user_agent_result = _res_queue.get(timeout=10)
    print(f'UserAgent: {user_agent_result}')
    
    print('Testing WebDriver property...')
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.webdriver === undefined'
        }
    })
    
    webdriver_result = _res_queue.get(timeout=10)
    print(f'WebDriver undefined: {webdriver_result}')
    
    print('Testing Google access...')
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
    print(f'CAPTCHA detected: {captcha_check_result}')
    
    if screenshot_result.get('status') == 'success':
        image_data = base64.b64decode(screenshot_result.get('data'))
        with open('test_evidence/google_screenshot.png', 'wb') as f:
            f.write(image_data)
        print('Screenshot saved to test_evidence/google_screenshot.png')
    
    print('Testing click functionality...')
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'document.querySelector("input[type=\'text\']").click()'
        }
    })
    
    click_result = _res_queue.get(timeout=10)
    print(f'Click result: {click_result}')
    
    _cmd_queue.put({
        'command': 'screenshot',
        'params': {}
    })
    
    click_screenshot_result = _res_queue.get(timeout=10)
    
    if click_screenshot_result.get('status') == 'success':
        image_data = base64.b64decode(click_screenshot_result.get('data'))
        with open('test_evidence/click_test.png', 'wb') as f:
            f.write(image_data)
        print('Click test screenshot saved to test_evidence/click_test.png')
    
    shutdown_browser()
    
    print('\nTest Summary:')
    print(f'UserAgent Test: {user_agent_result.get("status") if user_agent_result else "Failed"}')
    print(f'WebDriver Test: {webdriver_result.get("status") if webdriver_result else "Failed"}')
    print(f'Google CAPTCHA Test: {captcha_check_result.get("status") if captcha_check_result else "Failed"}')
    print(f'Click Test: {click_result.get("status") if click_result else "Failed"}')
    
    return {
        'user_agent': user_agent_result,
        'webdriver': webdriver_result,
        'captcha_check': captcha_check_result,
        'click': click_result
    }

if __name__ == "__main__":
    run_test()
