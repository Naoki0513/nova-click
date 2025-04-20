// オリジナルの背景色を保存する変数
let originalBackgroundColor = null;
let originalBodyStyle = null;

// メッセージリスナーを設定
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  // 背景色を変更するアクション
  if (request.action === 'changeBackgroundColor') {
    // 初回実行時にオリジナルの背景色を保存
    if (originalBackgroundColor === null) {
      originalBackgroundColor = document.body.style.backgroundColor;
      originalBodyStyle = document.body.getAttribute('style');
    }
    
    // 背景色を変更
    document.body.style.backgroundColor = request.color;
    
    // 応答を返す
    sendResponse({success: true});
    return true;
  }
  
  // ページをリセットするアクション
  if (request.action === 'resetPage') {
    if (originalBodyStyle !== null) {
      // 保存したスタイルを復元
      document.body.setAttribute('style', originalBodyStyle || '');
    } else {
      // 背景色のみリセット
      document.body.style.backgroundColor = originalBackgroundColor || '';
    }
    
    // 応答を返す
    sendResponse({success: true});
    return true;
  }
});

// ページ読み込み時に実行される処理
console.log('Browser Agent: コンテンツスクリプトが読み込まれました');

// ページ情報をバックグラウンドスクリプトに送信
chrome.runtime.sendMessage({
  action: 'pageLoaded',
  url: window.location.href,
  title: document.title
});
