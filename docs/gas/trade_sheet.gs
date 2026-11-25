/**
 * 短期トレードの損益記録を Google スプレッドシートに保存するプログラム（Google Apps Script）
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
 */
const KEY = '';            // ← ここに合言葉を入れる
const SHEET = '損益記録';
const COLS = ['id', '日付', '時刻', 'その時点の合計', 'この回の損益', '方向', '根拠', 'メモ', '更新', '削除'];

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
function txt_(v, fmt) { return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), fmt) : String(v); }

function doGet() { return out_({ok: true, app: 'trade-sheet', note: 'POST で使います'}); }

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
        const row = [String(r.id), r.date, r.t, Number(r.cum), '', r.dir === 'buy' ? '買い' : r.dir === 'sell' ? '売り' : '',
          (r.reasons || []).join('／'), r.memo || '', Number(r.u || r.id), r.del ? 1 : ''];
        const n = idx[String(r.id)];
        if (n) s.getRange(n, 1, 1, row.length).setValues([row]);
        else { s.appendRow(row); idx[String(r.id)] = s.getLastRow(); }
      });
      // 日付・時刻順に並べ直し、「この回の損益」（同じ日の前回の合計との差）を計算し直す
      const last = s.getLastRow();
      if (last > 2) s.getRange(2, 1, last - 1, COLS.length).sort([{column: 2, ascending: true}, {column: 3, ascending: true}]);
      const v2 = s.getDataRange().getValues(), prev = {}, diff = [];
      for (let i = 1; i < v2.length; i++) {
        if (v2[i][9]) { diff.push(['']); continue; }
        const d = txt_(v2[i][1], 'yyyy-MM-dd'), c = Number(v2[i][3]);
        diff.push([d in prev ? c - prev[d] : c]); prev[d] = c;
      }
      if (diff.length) s.getRange(2, 5, diff.length, 1).setValues(diff);
    }
    const rows = s.getDataRange().getValues().slice(1).filter(v => v[0] !== '').map(v => ({
      id: Number(v[0]), date: txt_(v[1], 'yyyy-MM-dd'), t: txt_(v[2], 'HH:mm'), cum: Number(v[3]),
      dir: v[5] === '買い' ? 'buy' : v[5] === '売り' ? 'sell' : null, reasons: v[6] ? String(v[6]).split('／') : [],
      memo: String(v[7] || ''), u: Number(v[8]) || Number(v[0]), del: !!v[9]}));
    return out_({ok: true, rows: rows});
  } finally {
    lock.releaseLock();
  }
}
