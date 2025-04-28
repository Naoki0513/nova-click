import os
import time
import sys
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.browser.worker import initialize_browser, _cmd_queue, _res_queue, shutdown_browser

os.makedirs('test_evidence', exist_ok=True)

def create_evidence_image(title, result, filename):
    """Create an image with test results"""
    img = Image.new('RGB', (800, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    d.text((10, 10), title, fill=(0, 0, 0))
    
    y_pos = 40
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, dict):
                d.text((10, y_pos), f"{key}:", fill=(0, 0, 0))
                y_pos += 30
                for k, v in value.items():
                    d.text((30, y_pos), f"{k}: {v}", fill=(0, 0, 0))
                    y_pos += 30
            else:
                d.text((10, y_pos), f"{key}: {value}", fill=(0, 0, 0))
                y_pos += 30
    else:
        d.text((10, y_pos), str(result), fill=(0, 0, 0))
    
    img.save(f'test_evidence/{filename}')
    print(f"Evidence saved to test_evidence/{filename}")

def test_with_evidence():
    """Run tests and generate evidence"""
    print("Starting CAPTCHA avoidance tests with evidence generation...")
    
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
    create_evidence_image("UserAgent Test", user_agent_result, "user_agent_test.png")
    
    print("\n2. Testing WebDriver property...")
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'navigator.webdriver === undefined'
        }
    })
    
    webdriver_result = _res_queue.get(timeout=10)
    create_evidence_image("WebDriver Property Test", webdriver_result, "webdriver_test.png")
    
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
    create_evidence_image("CAPTCHA Detection Test", captcha_check_result, "captcha_test.png")
    
    if screenshot_result and screenshot_result.get('status') == 'success' and screenshot_result.get('data'):
        try:
            image_data = base64.b64decode(screenshot_result.get('data'))
            with open('test_evidence/google_screenshot.png', 'wb') as f:
                f.write(image_data)
            print("Screenshot saved to test_evidence/google_screenshot.png")
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
    create_evidence_image("Click Functionality Test", click_result, "click_test.png")
    
    print("\n5. Testing input text functionality...")
    _cmd_queue.put({
        'command': 'execute_javascript',
        'params': {
            'script': 'const input = document.querySelector("input[type=\'text\']"); if(input) { input.value = "test automation"; input.dispatchEvent(new Event("input", { bubbles: true })); true; } else { false; }'
        }
    })
    
    input_result = _res_queue.get(timeout=10)
    create_evidence_image("Input Text Functionality Test", input_result, "input_test.png")
    
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
    
    summary = {
        "UserAgent Test": user_agent_result.get('status') if user_agent_result else 'Failed',
        "WebDriver Test": webdriver_result.get('status') if webdriver_result else 'Failed',
        "Google CAPTCHA Test": captcha_check_result.get('status') if captcha_check_result else 'Failed',
        "Click Test": click_result.get('status') if click_result else 'Failed',
        "Input Text Test": input_result.get('status') if input_result else 'Failed'
    }
    create_evidence_image("Test Summary", summary, "test_summary.png")
    
    print("\nTest Summary:")
    for test, status in summary.items():
        print(f"{test}: {status}")
    
    return {
        'user_agent': user_agent_result,
        'webdriver': webdriver_result,
        'captcha_check': captcha_check_result,
        'click': click_result,
        'input_text': input_result
    }

if __name__ == "__main__":
    test_with_evidence()
