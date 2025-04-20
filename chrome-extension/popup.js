document.addEventListener('DOMContentLoaded', function() {
  // 要素の取得
  const changeColorBtn = document.getElementById('changeColor');
  const captureTabBtn = document.getElementById('captureTab');
  const resetPageBtn = document.getElementById('resetPage');
  const colorPicker = document.getElementById('bgColor');
  const statusDiv = document.getElementById('status');

  // 背景色を変更する関数
  changeColorBtn.addEventListener('click', function() {
    const color = colorPicker.value;
    
    // 現在のタブに対してコンテンツスクリプトを実行
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      chrome.tabs.sendMessage(tabs[0].id, {
        action: 'changeBackgroundColor',
        color: color
      }, function(response) {
        showStatus('背景色を ' + color + ' に変更しました', 'success');
      });
    });
  });

  // 現在のタブをキャプチャする関数
  captureTabBtn.addEventListener('click', function() {
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      chrome.tabs.captureVisibleTab(function(dataUrl) {
        // キャプチャしたデータをローカルストレージに保存
        chrome.storage.local.set({
          'lastCapture': {
            url: tabs[0].url,
            title: tabs[0].title,
            image: dataUrl,
            timestamp: new Date().toISOString()
          }
        }, function() {
          showStatus('ページをキャプチャしました', 'success');
        });
      });
    });
  });

  // ページをリセットする関数
  resetPageBtn.addEventListener('click', function() {
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      chrome.tabs.sendMessage(tabs[0].id, {
        action: 'resetPage'
      }, function(response) {
        showStatus('ページをリセットしました', 'success');
      });
    });
  });

  // ステータスメッセージを表示する関数
  function showStatus(message, type) {
    statusDiv.textContent = message;
    statusDiv.className = type;
    statusDiv.style.display = 'block';
    
    // 3秒後にメッセージを非表示にする
    setTimeout(function() {
      statusDiv.style.display = 'none';
    }, 3000);
  }
});
