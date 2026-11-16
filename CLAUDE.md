# 引き継ぎメモ（Claude Code 用）

オーナー：山本 勉（GitHub: yamamototsu）。日本語で会話。Excel VBAに詳しい。

## 目的
Excelで手作業管理していた3種類の需給データを自動取得し、表（マトリックス計算）とグラフで見るHTMLアプリにする。GitHub Actionsで取得し、GitHub Pages（/docs）で公開する。

## 構成
- `scripts/fetch.py`：取得と推計。平日 17:35 / 21:35 JST に Actions から実行（`.github/workflows/update-data.yml`）
- `docs/index.html`：アプリ（Chart.js、タブは信用残・日経理論値・投資主体別）
- `docs/data/*.json`：データ。初期値はオーナーのExcel画面から転記したもの（src: "sheet"）
- `docs/data/manual_eval.csv`：信用評価損益率の実績値（手入力）
- `debug/`：取得失敗時のExcelダンプと `last_run.log`

## データ元（確認済み）
- 信用残：JPX `margin/04.html` から `YYYYMMDD_mtcurrent.xlsx` を取得。二市場合計、単位は百万円。前週比の列と前週の値を突き合わせて合計行を特定する
- 投資主体別：JPX `investor-type/index.html` から `stock_1_w_開始_終了.xlsx` を取得。二市場の金額差引き（千円）÷1000。「買い−売り＝差引き」「売り＋買い＝合計」が成り立つ組のうち合計が最大のもの（＝二市場）を採用。項目は海外投資家・個人・投資信託・信託銀行・自己計・事業法人
- 日経PER/EPS/PBR（加重平均・指数ベース）：stock-marketdata.com/kabukashihyo.html。日経公式サイトとトレーダーズ・ウェブは自動取得を拒否しているため使わない
- 日経平均終値：FRED NIKKEI225。未反映の日は PER×EPS で仮置きし、後日FREDの値で上書き
- 信用評価損益率：公開データがないため推計。買い残金額（約定代金＝取得原価）を日経平均の騰落で時価に引き直す。新規の買い建ては時価で加算、返済は時価比率で減算し、直近の実績値を起点にする。7〜10月で検証した1週先の誤差は平均で約1.1ポイント

## 設定手順：GitHub と Claude Code（Web版）を PC・スマホの両方から使う

ファイルは GitHub に置き、作業は Claude Code の Web版（claude.ai/code）で行う。こうすると、どのPCのブラウザからでもスマホの Claude アプリからでも、同じリポジトリと同じ作業の続きにアクセスできる。端末側に何かをインストールする必要はない。

### 1. GitHub にリポジトリを作る（PCで行う）
1. github.com/new を開き、Repository name を `market-dashboard`、公開範囲を Public にして作成する（README などは追加しない）
2. zip を解凍し、`market-dashboard` フォルダの中身をすべてアップロードする
   - 作成直後の画面の「uploading an existing file」、または「Add file → Upload files」を使う
   - フォルダの中身（`.github`、`docs`、`scripts`、`debug`、`CLAUDE.md`、`README.md` など）をまとめてドラッグし、「Commit changes」を押す
3. アップロード後、`.github/workflows/update-data.yml` があるか確認する
   - Mac では `.github` が隠しフォルダになり、アップロードから漏れやすい
   - 無い場合は「Add file → Create new file」を開き、名前欄に `.github/workflows/update-data.yml` と入力して、zip 内の同じファイルの中身を貼り付ける

### 2. 公開と自動取得を有効にする（PC・スマホどちらでも可）
1. Settings → Pages で、Source を「Deploy from a branch」、Branch を `main` / `/docs` にして Save する
   - 数分後に `https://yamamototsu.github.io/market-dashboard/` で見られるようになる
2. Actions タブを開く。有効化を求められたら有効にする
3. `update-data` → 「Run workflow」で初回取得を実行する
4. 実行後にデータがコミットされない場合は、Settings → Actions → General → Workflow permissions を「Read and write permissions」にする

### 3. Claude Code の Web版をつなぐ
1. PC のブラウザで claude.ai/code を開き、GitHub 連携を行う（Claude の GitHub App をインストールし、`market-dashboard` へのアクセスを許可する）
2. リポジトリに `yamamototsu/market-dashboard` を選んでセッションを始め、最初に「CLAUDE.md を読んで、未完了の作業を続けて」と頼む
3. スマホからは Claude アプリのコード（Claude Code）画面を開く。同じアカウントなら、同じリポジトリやセッションをそのまま選べる
4. 注意：クラウドの作業環境は、既定ではアクセスできるサイトが限られている
   - JPX・stock-marketdata.com・FRED に接続できず、`fetch.py` をその場で試せないことがある
   - Claude Code の環境設定でネットワークアクセスに `www.jpx.co.jp`、`stock-marketdata.com`、`fred.stlouisfed.org` を追加するとその場で試せる
   - 追加しない場合は、GitHub Actions で実行し、その結果（`debug/`）を読んで直す

### 4. 自分のPCのターミナルでも使いたい場合（任意）
1. Claude Code をインストールし、`git clone https://github.com/yamamototsu/market-dashboard.git` を実行して、そのフォルダで `claude` を起動する
2. Web版で進めていたセッションを手元に取り込むには `claude --teleport` を使う（未コミットの変更が無い状態で行う）

### 5. 日常の使い方
- 見る：スマホやPCで `https://yamamototsu.github.io/market-dashboard/` を開く（ホーム画面に追加するとアプリのように使える）
- 評価損益率の実績を入れる：GitHub アプリまたはブラウザで `docs/data/manual_eval.csv` を開き、鉛筆マークで `2026-11-13,-9.85` のような1行を追加してコミットする。データ更新が自動で走る
- 直したいとき：claude.ai/code（PC）または Claude アプリ（スマホ）で、このリポジトリのセッションに頼む

## 未完了
1. リポジトリ `yamamototsu/market-dashboard`（Public）を作成して push する
2. Pages を main /docs で有効化し、`workflow_dispatch` で初回取得を実行する
3. 実際のJPX Excelでパーサーを検証する（ここまでは模擬ファイルでしか試せていない）。失敗した場合は `debug/*.txt` を見て修正する
4. 既知のシート側の入力ミス：日経10/21の終値（正しくは64,621.24）、10/28のEPS（正しくは3,813.61）、信用残の7/27（正しくは7/24）。データ側は修正済み
