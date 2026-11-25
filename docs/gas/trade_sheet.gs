/**
 * 短期トレードの記録を Google スプレッドシートに保存するプログラム（Google Apps Script）
 *
 * 使い方（くわしくはアプリの「損益履歴」タブの「スプレッドシートに保存」）
 *  1. 新しいスプレッドシートを作り、メニュー「拡張機能 → Apps Script」を開く
 *  2. 最初からある中身を全部消して、このファイルの中身を貼り付ける
 *  3. 下の KEY の '' の中に、自分だけの合言葉（10文字以上の英数字がおすすめ）を入れて保存
 *  4. 「デプロイ → 新しいデプロイ」→ 種類「ウェブアプリ」→ 次のユーザーとして実行「自分」、
 *     アクセスできるユーザー「全員」→ デプロイ → 許可を求められたら自分のアカウントで許可
 *  5. 表示された「ウェブアプリのURL」（https://script.google.com/macros/s/…/exec）と合言葉を、アプリに入力する
 *
 * 合言葉が合わないと読み書きできません。URL と合言葉は人に教えないでください。
 * プログラムを書き直したときは「デプロイ → デプロイを管理 → 編集（鉛筆）→ バージョン：新バージョン → デプロイ」で反映します。
 *
 * 2026-11-25 版（v2）：記録を「取引（根拠と損益）」「今日の合計」「気づき」の3種類に分けた。シート「記録」に1件1行で入る。
 * 以前の版のシート「損益記録」は使わなくなる（消さずに残る。アプリの記録はつないだときに新しいシートへ送り直す）。
 * 2026-11-25 追加：Google ドライブの trade_summary.json（Claude が毎朝作る振り返り）を読んで、一覧と一緒に返す。
 *   初めてデプロイし直すとき、ドライブを読む許可を求められるので許可する。
 */
const KEY = '';            // ← ここに合言葉を入れる
const SHEET = '記録';
const COLS = ['id', '日付', '時刻', '種類', '損益（円）', '方向', '根拠', 'メモ', '更新', '削除'];
const KIND = {trade: '取引', day: '今日の合計', note: '気づき', old: '合計（旧形式）'};
const KIND_R = Object.fromEntries(Object.entries(KIND).map(([k, v]) => [v, k]));
const SUMMARY_FILE = 'trade_summary.json';   // 振り返り（Claude が毎朝ドライブに書く）

function summary_() {
  try {
    const it = DriveApp.getFilesByName(SUMMARY_FILE); let f = null;
    while (it.hasNext()) { const x = it.next(); if (!x.isTrashed() && (!f || x.getLastUpdated() > f.getLastUpdated())) f = x; }
    return f ? JSON.parse(f.getBlob().getDataAsString('UTF-8')) : null;
  } catch (err) { return null; }
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let s = ss.getSheetByName(SHEET);
  if (!s) {
    s = ss.insertSheet(SHEET);
    s.getRange('A:C').setNumberFormat('@');   // id・日付・時刻は文字のまま（日付や時刻に変換させない）
    s.getRange('I:I').setNumberFormat('0');
    s.getRange(1, 1, 1, COLS.length).setValues([COLS]).setFontWeight('bold');
    s.setFrozenRows(1);
  }
  return s;
}
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function txt_(v, fmt) {   // シートが日付・時刻に変えたセルも YYYY-MM-DD・HH:mm の文字で返す（instanceof Date が効かないことがあるため型名で見る）
  return Object.prototype.toString.call(v) === '[object Date]' ? Utilities.formatDate(v, Session.getScriptTimeZone(), fmt) : String(v);
}

function doGet() { return out_({ok: true, v: 2, app: 'trade-sheet', note: 'POST で使います'}); }

function doPost(e) {
  let q;
  try { q = JSON.parse(e.postData.contents); } catch (err) { return out_({ok: false, error: '送られた内容を読めません'}); }
  if (!KEY) return out_({ok: false, error: 'プログラムの KEY（合言葉）が空です'});
  if (q.key !== KEY) return out_({ok: false, error: '合言葉が違います'});
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const s = sheet_();
    if (q.op === 'put' && (q.rows || []).length) {
      const vals = s.getDataRange().getValues(), idx = {};
      for (let i = 1; i < vals.length; i++) idx[String(vals[i][0])] = i + 1;
      q.rows.forEach(r => {
        const row = [String(r.id), r.date, r.t, KIND[r.k] || KIND.trade, r.k === 'note' ? '' : Number(r.amt) || 0,
          r.dir === 'buy' ? '買い' : r.dir === 'sell' ? '売り' : '', (r.reasons || []).join('／'), r.memo || '', Number(r.u || r.id), r.del ? 1 : ''];
        const n = idx[String(r.id)];
        if (!n) { s.appendRow(['']); n = s.getLastRow(); idx[String(r.id)] = n; }
        s.getRange(n, 1, 1, 3).setNumberFormat('@');   // id・日付・時刻は文字のまま（日付や時刻に変換させない）
        s.getRange(n, 1, 1, row.length).setValues([row]);
      });
      const last = s.getLastRow();   // 日付・時刻順に並べ直す
      if (last > 2) s.getRange(2, 1, last - 1, COLS.length).sort([{column: 2, ascending: true}, {column: 3, ascending: true}]);
    }
    const rows = s.getDataRange().getValues().slice(1).filter(v => v[0] !== '').map(v => ({
      id: Number(v[0]), date: txt_(v[1], 'yyyy-MM-dd'), t: txt_(v[2], 'HH:mm'), k: KIND_R[v[3]] || 'trade', amt: Number(v[4]) || 0,
      dir: v[5] === '買い' ? 'buy' : v[5] === '売り' ? 'sell' : null, reasons: v[6] ? String(v[6]).split('／') : [],
      memo: String(v[7] || ''), u: Number(v[8]) || Number(v[0]), del: !!v[9]}));
    const res = {ok: true, v: 2, rows: rows};
    if (q.op === 'list') res.summary = summary_();   // 振り返りは一覧のときだけ返す
    return out_(res);
  } finally {
    lock.releaseLock();
  }
}
