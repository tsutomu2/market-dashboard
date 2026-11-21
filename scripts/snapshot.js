// アプリ（docs/index.html）を裏で開き、画面が計算したシグナル・判断を JSON で書き出す。
// AI がコメントを書くための材料にする（計算方法はアプリと完全に同じ）。
// 使い方：node scripts/snapshot.js > debug/snapshot.json
// 必要：Playwright（クラウドの作業環境には入っている）。外部の CDN・TradingView は読み込まない（計算に不要）。
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', 'docs');
const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.csv': 'text/csv', '.js': 'application/javascript' };

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\/$/, '/index.html'));
  if (!p.startsWith(ROOT) || !fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

server.listen(0, async () => {
  const port = server.address().port;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route(/^https?:\/\/(?!localhost)/, r => r.abort());   // 外部の読み込みは止める
  await page.goto(`http://localhost:${port}/#signal`);   // 最初に開くタブはSHO手法なので、シグナル画面を開く
  await page.waitForFunction(() => document.querySelector('#s-judge .concl'), null, { timeout: 30000 });
  const snap = await page.evaluate(() => {
    const txt = el => (el ? el.innerText.replace(/\s+\n/g, '\n').trim() : '');
    const list = id => [...document.querySelectorAll(id + ' .sig')].map(e => ({
      stars: (e.querySelector('.stars') || {}).textContent || '',
      name: [...e.querySelector('.n').childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim(),
      status: (e.querySelector('.pill') || {}).textContent || '',
      value: txt(e.querySelector('.val')),
      note: txt(e.querySelector('.snote')),
      detail: txt(e.querySelector('.c')),
    }));
    const H = histCtx(), t = H.t, i = t.c.length - 1;
    return {
      updated: (D.meta || {}).updated,
      nikkei: { date: t.dates[i], close: t.c[i], prev: t.c[i - 1] },
      rule_conclusion: document.querySelector('#s-judge .rulec') ? txt(document.querySelector('#s-judge .rulec')).replace(/^ルールによる結論：/, '') : txt(document.querySelector('#s-judge .concl')),
      previous_ai: D.ai || null,
      steps: [...document.querySelectorAll('#s-judge .step')].map(e => ({ head: txt(e.querySelector('.sh')), result: txt(e.querySelector('.sr')), detail: txt(e.querySelector('.c')) })),
      summary: txt(document.querySelector('#s-summary')),
      crash: list('#s-crash'), rebound: list('#s-rebound'), caution: list('#s-caution'), verify: list('#s-verify'),
      video: txt(document.querySelector('#s-sho')),
    };
  });
  snap.page_errors = errors;
  process.stdout.write(JSON.stringify(snap, null, 1) + '\n');
  await browser.close();
  server.close();
});
