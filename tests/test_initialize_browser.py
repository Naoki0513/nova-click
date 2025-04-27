import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(__file__, "..", "..")))
import streamlit as st
from agent.browser.worker import initialize_browser

def main():
    st.title("Playwright ブラウザ初期化テスト")
    if st.button("ブラウザ初期化"):
        result = initialize_browser()
        st.json(result)

if __name__ == "__main__":
    main() 