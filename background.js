// 拡張機能がインストールされたときに実行される処理
chrome.runtime.onInstalled.addListener(function(details) {
  console.log('Browser Agent: 拡張機能がインストールされました', details.reason);
  
  // 初期設定をストレージに保存
  chrome.storage.local.set({
    'settings': {
      'defaultBackgroundColor': '#ffffff',
      'captureEnabled': true,
      'installDate': new Date().toISOString()
    },
    'stats': {
      'pagesVisited': 0,
      'colorChanges': 0,
      'capturesTaken': 0
    }
  }, function() {
    console.log('Browser Agent: 初期設定が保存されました');
  });
});

// コンテンツスクリプトからのメッセージを処理
chrome.runtime.onMessage.addListener(function(message, sender, sendResponse) {
  // ページ読み込み時のメッセージ
  if (message.action === 'pageLoaded') {
    console.log('ページが読み込まれました:', message.url, message.title);
    
    // 訪問したページのカウントを更新
    chrome.storage.local.get('stats', function(data) {
      const stats = data.stats || {};
      stats.pagesVisited = (stats.pagesVisited || 0) + 1;
      
      chrome.storage.local.set({ 'stats': stats }, function() {
        console.log('統計情報が更新されました');
      });
    });
    
    // 最後に訪問したページの情報を保存
    chrome.storage.local.set({
      'lastVisited': {
        url: message.url,
        title: message.title,
        timestamp: new Date().toISOString()
      }
    });
    
    return true;
  }
});

// ブラウザのタブが更新されたときのイベント
chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
  // タブの読み込みが完了したとき
  if (changeInfo.status === 'complete' && tab.url) {
    // URLがhttpまたはhttpsで始まる場合のみ処理
    if (tab.url.startsWith('http')) {
      console.log('タブが更新されました:', tab.url);
    }
  }
});

// ブラウザのタブがアクティブになったときのイベント
chrome.tabs.onActivated.addListener(function(activeInfo) {
  chrome.tabs.get(activeInfo.tabId, function(tab) {
    if (tab.url && tab.url.startsWith('http')) {
      console.log('タブがアクティブになりました:', tab.url);
    }
  });
});

console.log('Browser Agent: バックグラウンドスクリプトが読み込まれました');
