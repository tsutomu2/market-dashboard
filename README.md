# マーケット需給ダッシュボード

信用残・日経平均の理論値（PER/EPS）・投資主体別売買動向を自動で集めて、表とグラフで見るWebアプリです。

- アプリ本体：`docs/index.html`（GitHub Pagesで公開）
- データ：`docs/data/*.json`（GitHub Actionsが平日17:35・21:35 JSTに自動更新）
- 取得プログラム：`scripts/fetch.py`

## データの出どころ

| 項目 | 取得元 | 公表 |
|---|---|---|
| 信用残（売り残・買い残） | JPX「信用取引現在高」二市場合計（百万円） | 毎週火曜 16:00 |
| 投資主体別 | JPX「投資部門別売買状況」二市場・金額差引き（千円→百万円） | 毎週木曜 |
| 日経PER/EPS/PBR | 日経平均プロフィル公表値（stock-marketdata.com 経由） | 毎営業日 |
| 日経平均終値 | FRED（NIKKEI225） | 毎営業日 |
| 信用評価損益率 | 公開データなし → 実績は手入力、それ以外は推計 | — |

## 信用評価損益率の入力（実績値）

`docs/data/manual_eval.csv` に `日付,評価損益率` を1行追加してください（GitHubのスマホアプリやWebから直接編集できます）。保存するとデータ更新が自動で走り、その値を起点に以降の推計が計算し直されます。

## 初回セットアップ

1. Settings → Pages → Source を「Deploy from a branch」、Branch を `main` / `/docs` にして保存
2. Actions タブ → `update-data` → 「Run workflow」で初回取得
3. `https://<ユーザー名>.github.io/market-dashboard/` を開く

取得に失敗した場合は `debug/last_run.log` と `debug/*.txt` に原因が書き出されます。
