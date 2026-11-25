"""docs/index.html から、短期トレードだけの単独ページ docs/trade.html を作る。

中身（画面とプログラム）は index.html と同じで、ページの名前・ホーム画面のアイコン・manifest だけを差し替える。
trade.html で開くと、index.html の中の判定（body に app-trade）で「短期トレード」「損益履歴」のタブだけが出る。
index.html を直したら、このスクリプトを実行して trade.html を作り直すこと（GitHub Actions でも毎回実行する）。
"""
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
REPL = [
    ('<link rel="apple-touch-icon" href="apple-touch-icon.png">', '<link rel="apple-touch-icon" href="apple-touch-icon-trade.png">'),
    ('<meta name="apple-mobile-web-app-title" content="Sho\'s投資法">', '<meta name="apple-mobile-web-app-title" content="短期トレード">'),
    ('<link rel="manifest" href="manifest.webmanifest">', '<link rel="manifest" href="manifest-trade.webmanifest">'),
    ('<title>マーケット需給ダッシュボード</title>', '<title>短期トレード</title>'),
]


def main():
    s = (DOCS / "index.html").read_text(encoding="utf-8")
    for a, b in REPL:
        if s.count(a) != 1:
            raise SystemExit(f"index.html に置き換え元が1つだけ見つかりません: {a}")
        s = s.replace(a, b)
    s = s.replace("<head>\n", "<head>\n<!-- このファイルは scripts/build_trade.py が index.html から自動で作る。直接編集しないこと -->\n", 1)
    out = DOCS / "trade.html"
    old = out.read_text(encoding="utf-8") if out.exists() else ""
    if old != s:
        out.write_text(s, encoding="utf-8")
        print("trade.html を更新しました")
    else:
        print("trade.html は最新です")


if __name__ == "__main__":
    main()
