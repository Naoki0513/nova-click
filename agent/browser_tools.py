import streamlit as st
import time
import base64
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .utils import add_debug_log

def initialize_browser():
    """Playwrightブラウザを初期化します"""
    if st.session_state.get("browser") is None:
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            
            st.session_state["playwright"] = playwright
            st.session_state["browser"] = browser
            st.session_state["page"] = page
            
            add_debug_log("ブラウザを初期化しました", "ブラウザ")
            return True
        except Exception as e:
            add_debug_log(f"ブラウザ初期化エラー: {str(e)}", "エラー")
            return False
    return True

def close_browser():
    """ブラウザを閉じます"""
    if st.session_state.get("browser") is not None:
        try:
            st.session_state["browser"].close()
            st.session_state["playwright"].stop()
            
            st.session_state["browser"] = None
            st.session_state["page"] = None
            st.session_state["playwright"] = None
            
            add_debug_log("ブラウザを閉じました", "ブラウザ")
        except Exception as e:
            add_debug_log(f"ブラウザ終了エラー: {str(e)}", "エラー")

def navigate_to_url_tool(url=None):
    """指定されたURLに移動するツール"""
    if url is None:
        return {"error": "URLが指定されていません"}
    
    try:
        if not initialize_browser():
            return {"error": "ブラウザの初期化に失敗しました"}
        
        page = st.session_state["page"]
        page.goto(url)
        add_debug_log(f"URL {url} に移動しました", "ブラウザ")
        
        # 少し待ってからDOM取得
        time.sleep(1)
        content = get_page_content()
        
        return {
            "status": "success",
            "message": f"URL {url} に移動しました",
            "current_url": page.url,
            "page_title": page.title(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content
        }
    except Exception as e:
        add_debug_log(f"URL移動エラー: {str(e)}", "エラー")
        return {"error": f"URL移動エラー: {str(e)}"}

def get_page_content():
    """現在のページのHTML内容を取得します"""
    if st.session_state.get("page") is None:
        return "ブラウザが初期化されていません"
    
    try:
        content = st.session_state["page"].content()
        return content
    except Exception as e:
        add_debug_log(f"ページ内容取得エラー: {str(e)}", "エラー")
        return f"ページ内容取得エラー: {str(e)}"

def get_dom_tool(selector=None, extract_text_only=False):
    """指定されたセレクタのDOM要素または全体のDOMを取得するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        if selector:
            try:
                if extract_text_only:
                    # テキストのみを抽出
                    text_content = page.text_content(selector)
                    return {
                        "status": "success",
                        "text_content": text_content
                    }
                else:
                    # HTML要素を取得
                    html = page.inner_html(selector)
                    return {
                        "status": "success",
                        "html": html,
                        "element_exists": True
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"セレクタ '{selector}' の要素が見つかりませんでした",
                    "element_exists": False
                }
        else:
            # 全体のDOMを取得
            full_html = page.content()
            # サイズ削減のためにBeautifulSoupで整形
            soup = BeautifulSoup(full_html, 'html.parser')
            return {
                "status": "success",
                "url": page.url,
                "title": page.title(),
                "html": str(soup)
            }
    except Exception as e:
        add_debug_log(f"DOM取得エラー: {str(e)}", "エラー")
        return {"error": f"DOM取得エラー: {str(e)}"}

def click_element_tool(selector=None):
    """指定されたセレクタの要素をクリックするツール"""
    if selector is None:
        return {"error": "セレクタが指定されていません"}
    
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # 要素が表示されるまで少し待つ
        try:
            page.wait_for_selector(selector, timeout=5000)
        except:
            return {
                "status": "error",
                "message": f"セレクタ '{selector}' の要素が見つかりませんでした"
            }
        
        # クリック
        page.click(selector)
        add_debug_log(f"要素 '{selector}' をクリックしました", "ブラウザ")
        
        # 少し待ってからDOM取得
        time.sleep(1)
        
        return {
            "status": "success",
            "message": f"要素 '{selector}' をクリックしました",
            "current_url": page.url,
            "page_title": page.title()
        }
    except Exception as e:
        add_debug_log(f"クリックエラー: {str(e)}", "エラー")
        return {"error": f"クリックエラー: {str(e)}"}

def input_text_tool(selector=None, text=None):
    """指定されたセレクタの入力フィールドにテキストを入力するツール"""
    if selector is None or text is None:
        return {"error": "セレクタまたはテキストが指定されていません"}
    
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # 要素が表示されるまで少し待つ
        try:
            page.wait_for_selector(selector, timeout=5000)
        except:
            return {
                "status": "error",
                "message": f"セレクタ '{selector}' の入力フィールドが見つかりませんでした"
            }
        
        # テキスト入力前にフィールドをクリア
        page.fill(selector, "")
        
        # テキスト入力
        page.fill(selector, text)
        add_debug_log(f"要素 '{selector}' にテキスト '{text}' を入力しました", "ブラウザ")
        
        return {
            "status": "success",
            "message": f"要素 '{selector}' にテキスト '{text}' を入力しました"
        }
    except Exception as e:
        add_debug_log(f"テキスト入力エラー: {str(e)}", "エラー")
        return {"error": f"テキスト入力エラー: {str(e)}"}

def take_screenshot_tool():
    """現在のページのスクリーンショットを取得するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        screenshot_path = f"screenshot_{int(time.time())}.png"
        
        # スクリーンショット撮影
        page.screenshot(path=screenshot_path)
        add_debug_log(f"スクリーンショットを保存しました: {screenshot_path}", "ブラウザ")
        
        # 画像をbase64エンコード
        with open(screenshot_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        return {
            "status": "success",
            "message": f"スクリーンショットを取得しました",
            "file_path": screenshot_path,
            "base64_image": encoded_string
        }
    except Exception as e:
        add_debug_log(f"スクリーンショットエラー: {str(e)}", "エラー")
        return {"error": f"スクリーンショットエラー: {str(e)}"}

def extract_links_tool():
    """現在のページからすべてのリンクを抽出するツール"""
    if st.session_state.get("page") is None:
        return {"error": "ブラウザが初期化されていません"}
    
    try:
        page = st.session_state["page"]
        
        # ページ上のすべてのaタグを抽出
        links = page.evaluate("""
            () => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors.map(anchor => {
                    return {
                        text: anchor.textContent.trim(),
                        href: anchor.href,
                        id: anchor.id || null,
                        class: anchor.className || null,
                        selector: 'a[href="' + anchor.getAttribute('href') + '"]'
                    };
                });
            }
        """)
        
        add_debug_log(f"{len(links)}個のリンクを抽出しました", "ブラウザ")
        
        return {
            "status": "success",
            "links_count": len(links),
            "links": links
        }
    except Exception as e:
        add_debug_log(f"リンク抽出エラー: {str(e)}", "エラー")
        return {"error": f"リンク抽出エラー: {str(e)}"}

# ブラウザツールをディスパッチする関数
def dispatch_browser_tool(tool_name, params=None):
    """ツール名に基づいて適切なブラウザツールを呼び出します"""
    if params is None:
        params = {}
        
    # ツールに応じた処理
    if tool_name == "initialize_browser":
        return {"status": "success", "message": "ブラウザを初期化しました"} if initialize_browser() else {"error": "ブラウザの初期化に失敗しました"}
    elif tool_name == "close_browser":
        close_browser()
        return {"status": "success", "message": "ブラウザを閉じました"}
    elif tool_name == "navigate_to_url":
        return navigate_to_url_tool(params.get("url"))
    elif tool_name == "get_dom":
        return get_dom_tool(
            params.get("selector"), 
            params.get("extract_text_only", False)
        )
    elif tool_name == "click_element":
        return click_element_tool(params.get("selector"))
    elif tool_name == "input_text":
        return input_text_tool(
            params.get("selector"),
            params.get("text")
        )
    elif tool_name == "take_screenshot":
        result = take_screenshot_tool()
        
        # スクリーンショットをセッションに保存
        if "status" in result and result["status"] == "success":
            # base64エンコードされた画像データをデコード
            image_data = base64.b64decode(result["base64_image"])
            st.session_state["screenshot_data"] = image_data
        return result
            
    elif tool_name == "extract_links":
        return extract_links_tool()
    else:
        return {"error": f"不明なツール: {tool_name}"} 