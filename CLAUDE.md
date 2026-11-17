# 引き継ぎメモ（Claude Code 用）

オーナー：山本 勉（GitHub: tsutomu2 ※旧メモの yamamototsu は誤り）。Excel VBAに詳しい。

**応答・説明・進捗報告はすべて日本語で行うこと（オーナーの指定。途中で英語に切り替えない）。**

## 目的
Excelで手作業管理していた3種類の需給データを自動取得し、表（マトリックス計算）とグラフで見るHTMLアプリにする。GitHub Actionsで取得し、GitHub Pages（/docs）で公開する。

## 構成
- `scripts/fetch.py`：取得と推計。平日 17:35 / 21:35 JST に Actions から実行（`.github/workflows/update-data.yml`）
- `docs/index.html`：アプリ（Chart.js、タブはシグナル・信用残・テクニカル・日経理論値・投資主体別）
- `docs/data/*.json`：データ。初期値はオーナーのExcel画面から転記したもの（src: "sheet"）
- `docs/data/manual_eval.csv`：信用評価損益率の実績値（手入力）
- `debug/`：取得失敗時のExcelダンプと `last_run.log`

## データ元（確認済み）
- 信用残：JPX `margin/04.html` から `YYYYMMDD_mtcurrent.xlsx` を取得。二市場合計、単位は百万円。前週比の列と前週の値を突き合わせて合計行を特定する
- 投資主体別：JPX `investor-type/index.html` から `stock_1_w_開始_終了.xlsx` を取得。二市場の金額差引き（千円）÷1000。項目は海外投資家・個人・投資信託・信託銀行・自己計・事業法人
  - 実ファイルは横持ち形式（2026-11 確認）：主体が列方向に「売/買/差引/合計」の4列ずつ並び、見出しは3〜6行目（結合セル）、7行目が「売/買/差引/合計」、行は市場×株数/金額
  - 自己＝現金＋信用、個人＝現金＋信用、海外投資家＝法人＋個人 の差引きを合算（シートの値と10/9〜11/6の5週すべて一致）
  - `parse_investor_wide()` が見出し名で列を探す。同名の見出し（海外投資家の下の「個人」など）は、より上の見出し行にあるものを優先する。旧来の行方向パーサーは予備として残している
- 日経PER/EPS/PBR（加重平均・指数ベース）：stock-marketdata.com/kabukashihyo.html。日経公式サイトとトレーダーズ・ウェブは自動取得を拒否しているため使わない
- 日経平均終値：FRED NIKKEI225。未反映の日は PER×EPS で仮置きし、後日FREDの値で上書き
- 信用評価損益率：公開データがないため推計。買い残金額（約定代金＝取得原価）を日経平均の騰落で時価に引き直す。新規の買い建ては時価で加算、返済は時価比率で減算し、直近の実績値を起点にする。7〜10月で検証した1週先の誤差は平均で約1.1ポイント

## 投資手法の参考（シグナル・テクニカル画面）
オーナーの依頼で YouTube「Sho's投資情報局」（@SHO1112、テクニカル分析中心）の手法を参考にした。
動画本編・概要欄は YouTube の自動アクセス制限で読めず、チャンネル説明と動画タイトル約100本から、繰り返し出てくる指標を拾った：
信用倍率・信用買い残の激減（投げ）・空売り激減/爆増（騙し上げ・踏み上げ）・海外勢の売り越し・ボリンジャー・MACD・RSI・VIX・ドル円・ナスダック。
- しきい値は動画から取ったものではなく、一般的な目安（評価損益率-10%/倍率9.5倍は元のシートの値）。`index.html` 冒頭の `TH` で変更できる
- 一目均衡表・パラボリック・ストキャスティクスも動画で扱われているが、高値・安値データが無い（FREDは終値のみ）ため未対応
- 画面上部の相場の帯：TradingView の ticker-tape ウィジェット（`index.html` の `TAPE`）。無料ウィジェットで表示できない銘柄（TVC:NI225・TOPIX指数・COMEX:GC1!・NYMEX:CL1!）があるため、日経225＝OANDA:JP225USD（CFD）、日経先物＝OSE:NK2251!（20分遅れ）、TOPIX先物＝OSE:TOPIX1!（20分遅れ）、ドル円＝FX:USDJPY、金＝TVC:GOLD、WTI＝TVC:USOIL。INDEX:NKY は前日終値しか出ないので不採用（2026-11-17 に実表示で確認）
- 追加データ：`docs/data/short.json`（JPX空売り集計PDF、日次）、`docs/data/daily.json`（日経・VIX・ドル円・ナスダックの日次終値3年分、FRED）

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
   - 数分後に `https://tsutomu2.github.io/market-dashboard/` で見られるようになる
2. Actions タブを開く。有効化を求められたら有効にする
3. `update-data` → 「Run workflow」で初回取得を実行する
4. 実行後にデータがコミットされない場合は、Settings → Actions → General → Workflow permissions を「Read and write permissions」にする

### 3. Claude Code の Web版をつなぐ
1. PC のブラウザで claude.ai/code を開き、GitHub 連携を行う（Claude の GitHub App をインストールし、`market-dashboard` へのアクセスを許可する）
2. リポジトリに `tsutomu2/market-dashboard` を選んでセッションを始め、最初に「CLAUDE.md を読んで、未完了の作業を続けて」と頼む
3. スマホからは Claude アプリのコード（Claude Code）画面を開く。同じアカウントなら、同じリポジトリやセッションをそのまま選べる
4. 注意：クラウドの作業環境は、既定ではアクセスできるサイトが限られている
   - JPX・stock-marketdata.com・FRED に接続できず、`fetch.py` をその場で試せないことがある
   - Claude Code の環境設定でネットワークアクセスに `www.jpx.co.jp`、`stock-marketdata.com`、`fred.stlouisfed.org` を追加するとその場で試せる
   - 追加しない場合は、GitHub Actions で実行し、その結果（`debug/`）を読んで直す

### 4. 自分のPCのターミナルでも使いたい場合（任意）
1. Claude Code をインストールし、`git clone https://github.com/tsutomu2/market-dashboard.git` を実行して、そのフォルダで `claude` を起動する
2. Web版で進めていたセッションを手元に取り込むには `claude --teleport` を使う（未コミットの変更が無い状態で行う）

### 5. 日常の使い方
- 見る：スマホやPCで `https://tsutomu2.github.io/market-dashboard/` を開く（ホーム画面に追加するとアプリのように使える）
- 評価損益率の実績を入れる：GitHub アプリまたはブラウザで `docs/data/manual_eval.csv` を開き、鉛筆マークで `2026-11-13,-9.85` のような1行を追加してコミットする。データ更新が自動で走る
- 直したいとき：claude.ai/code（PC）または Claude アプリ（スマホ）で、このリポジトリのセッションに頼む

## 未完了
1. ~~リポジトリ `tsutomu2/market-dashboard`（Public）を作成して push する~~ → 2026-11-17 完了。リポジトリ作成直後の最初の push では Actions が起動しなかったため、ワークフロー修正の push で起動させた
2. Pages を main /docs で有効化する（オーナーの手作業。Claude からは設定できない）
3. ~~実際のJPX Excelでパーサーを検証する~~ → 2026-11-17 完了。信用残・日経PER/EPS・FREDはそのまま動作し、シートの値と一致。投資主体別は実ファイルが横持ち形式だったためパーサーを書き直し、シートの値と一致を確認。`docs/data/*.json` は実データで更新済み（信用残・投資主体別は 10/9〜11/6 が src: "jpx"、日経は 11/16 まで）
4. 既知のシート側の入力ミス：日経10/21の終値（正しくは64,621.24）、10/28のEPS（正しくは3,813.61）、信用残の7/27（正しくは7/24）。データ側は修正済み
5. stock-marketdata.com は短時間に何度もアクセスすると接続を切られる（`get()` に3回の再試行を入れた）。Actionsでは1日2回なので通常は問題ない
