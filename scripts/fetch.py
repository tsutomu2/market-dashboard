"""市場データの自動取得スクリプト（GitHub Actions から毎日実行）

取得元
- 信用残        : JPX「信用取引現在高」(毎週火曜 16:00 公表, 単位 百万円)
- 投資主体別    : JPX「投資部門別売買状況」二市場・金額の差引き (毎週木曜公表, 千円→百万円)
- 日経PER/EPS/PBR: stock-marketdata.com（日経平均プロフィルの公表値を掲載）
- 日経平均終値  : FRED (NIKKEI225)
- 信用評価損益率: 公開データでは取得できないため推計（docs/data/manual_eval.csv の実績値を起点）

取得に失敗しても既存データは壊さず、原因を debug/ に書き出す。
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sys
import traceback
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
DEBUG = ROOT / "debug"
JPX = "https://www.jpx.co.jp"
UA = {"User-Agent": "Mozilla/5.0 (personal market-dashboard; weekly fetch)"}
LOG: list[str] = []


def log(msg: str) -> None:
    print(msg)
    LOG.append(msg)


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r


def load_json(name: str) -> list:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_json(name: str, rows: list) -> None:
    (DATA / name).write_text(json.dumps(rows, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def dump_sheet(content: bytes, name: str) -> None:
    """解析に失敗したExcelの中身を debug/ にテキストで残す（次の修正用）"""
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f"=== sheet: {ws.title} ===")
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i > 150:
                    break
                cells = [repr(v) for v in row if v is not None]
                if cells:
                    out.append(f"{i + 1}: " + " | ".join(cells))
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / f"{name}.txt").write_text("\n".join(out), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log(f"dump failed {name}: {e}")


def jp_only(text: str) -> str:
    return re.sub(r"[^぀-ヿ一-鿿]", "", text or "")


def nums(row) -> list:
    return [v for v in row if isinstance(v, (int, float)) and not isinstance(v, bool)]


# ---------------------------------------------------------------- 信用残
def parse_margin(content: bytes, prev: dict | None) -> dict | None:
    """信用取引残高合計（二市場）の売残・買残（金額・株数）を取り出す。
    前週比の列で前週の値と突き合わせて、正しい行を確実に選ぶ。"""
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    quads = []  # (row_index, sell, sell_chg, buy, buy_chg, text)
    for i, r in enumerate(rows):
        n = nums(r)
        text = " ".join(str(v) for v in r if isinstance(v, str))
        for k in range(len(n) - 3):
            s, ds, b, db = n[k:k + 4]
            if s > 0 and b > 0:
                quads.append((i, s, ds, b, db, text, k))
    amount = None
    if prev:
        for q in quads:
            i, s, ds, b, db, _, _ = q
            if abs((s - ds) - prev["sell"]) <= 2 and abs((b - db) - prev["buy"]) <= 2:
                amount = q
                break
    if amount is None:
        # 前週の値がない場合：「金額/Val」と書かれた行のうち買残が最大のもの（=合計）
        cands = [q for q in quads if q[6] == 0 and ("金額" in q[5] or "Val" in q[5])]
        if cands:
            amount = max(cands, key=lambda q: q[3])
    if amount is None:
        return None
    i, s, ds, b, db, _, k = amount
    res = {"sell": int(round(s)), "buy": int(round(b)), "sell_shares": None, "buy_shares": None}
    for j in (i - 1, i + 1):  # 株数は隣の行
        if 0 <= j < len(rows):
            n = nums(rows[j])
            if len(n) >= k + 4:
                res["sell_shares"], res["buy_shares"] = int(round(n[k])), int(round(n[k + 2]))
                break
    return res


def update_margin() -> None:
    rows = load_json("margin.json")
    by_date = {r["date"]: r for r in rows}
    html = get(f"{JPX}/markets/statistics-equities/margin/04.html").text
    links = sorted(set(re.findall(r'href="([^"]*?(\d{8})_mtcurrent\.xlsx)"', html)), key=lambda x: x[1])
    for href, ymd in links:
        d = iso(ymd)
        if d in by_date and by_date[d].get("src") == "jpx":
            continue
        url = href if href.startswith("http") else JPX + href
        try:
            content = get(url).content
            prev_dates = sorted(x for x in by_date if x < d)
            prev = by_date[prev_dates[-1]] if prev_dates else None
            res = parse_margin(content, prev)
            if not res:
                log(f"margin parse failed {d}")
                dump_sheet(content, f"margin_{ymd}")
                continue
            old = by_date.get(d)
            if old and (old["sell"] != res["sell"] or old["buy"] != res["buy"]):
                log(f"margin {d}: sheet値と差異 {old['sell']}/{old['buy']} -> {res['sell']}/{res['buy']}")
            by_date[d] = {"date": d, **res, "src": "jpx"}
            log(f"margin {d}: sell={res['sell']} buy={res['buy']}")
        except Exception as e:  # noqa: BLE001
            log(f"margin error {d}: {e}")
    save_json("margin.json", [by_date[k] for k in sorted(by_date)])


# ---------------------------------------------------------------- 投資主体別
INVESTOR_LABELS = {
    "海外投資家": "foreign",
    "個人": "individual",
    "投資信託": "inv_trust",
    "信託銀行": "trust_bank",
    "自己計": "proprietary",
    "事業法人": "business",
}


def best_balance(n: list) -> tuple | None:
    """行の数値から 売り・買い・差引き・合計 の組（買い−売り=差引き, 売り+買い=合計）を探す。
    金額（千円）は株数より大きいので、合計が最大の組を採用する。"""
    ints = [int(v) for v in n if isinstance(v, int) or (isinstance(v, float) and v.is_integer())]
    best = None
    setv = set(ints)
    for a in range(len(ints)):
        for b in range(a + 1, len(ints)):
            s, buy = ints[a], ints[b]
            if s <= 0 or buy <= 0:
                continue
            if (buy - s) in setv and (s + buy) in setv:
                if best is None or s + buy > best[3]:
                    best = (s, buy, buy - s, s + buy)
    return best


# 横持ち形式（2026年時点のJPXの実ファイル）での見出し名。
# 「自己」「個人」「海外投資家」は 現金/信用・法人/個人 の小計列に分かれているので合算する。
WIDE_LABELS = {
    "foreign": ("海外投資家",),
    "individual": ("個人",),
    "inv_trust": ("投資信託",),
    "trust_bank": ("信託銀行",),
    "proprietary": ("自己計", "自己"),
    "business": ("事業法人",),
}


def parse_investor_wide(ws) -> dict | None:
    """投資主体が列方向に並ぶ形式。
    見出し行（売/買/差引/合計 が並ぶ行）より上の行を、結合セルを展開して列ごとの見出しにする。
    各主体は「その名前が最初に現れる見出し行」で範囲を決める
    （例：海外投資家の下にある『個人』ではなく、委託の下の『個人』を使う）。
    値は「二市場」の「金額」行の差引き（千円）。"""
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    if not grid:
        return None
    width = max(len(r) for r in grid)
    for r in grid:
        r.extend([None] * (width - len(r)))
    for mr in ws.merged_cells.ranges:  # 結合セルの値を範囲全体に広げる
        v = grid[mr.min_row - 1][mr.min_col - 1]
        for rr in range(mr.min_row - 1, mr.max_row):
            for cc in range(mr.min_col - 1, mr.max_col):
                grid[rr][cc] = v
    head = next((i for i, r in enumerate(grid) if sum(jp_only(str(v)) == "差引" for v in r if isinstance(v, str)) >= 3), None)
    if head is None:
        return None
    bal_cols = [c for c in range(width) if isinstance(grid[head][c], str) and jp_only(grid[head][c]) == "差引"]
    labels = [[jp_only(v) if isinstance(v, str) else "" for v in grid[i]] for i in range(head)]
    target = None
    for r in grid[head + 1:]:
        text = [jp_only(v) for v in r if isinstance(v, str)]
        if any("二市場" in t for t in text) and any(t.startswith("金額") for t in text):
            target = r
            break
    if target is None:
        return None
    res = {}
    for key, names in WIDE_LABELS.items():
        cols = None
        for name in names:
            for lv in range(head):
                hit = [c for c in bal_cols if labels[lv][c] == name]
                if hit:
                    cols = hit
                    break
            if cols:
                break
        if not cols:
            res[key] = None
            continue
        total = 0
        for c in cols:
            s, b, d = target[c - 2], target[c - 1], target[c]
            if not all(isinstance(x, (int, float)) for x in (s, b, d)) or abs((b - s) - d) > 2:
                raise ValueError(f"{key}: 列{c + 1}の 売/買/差引 が合わない ({s}, {b}, {d})")
            total += d
        res[key] = int(round(total / 1000))
    if res.get("foreign") is None or res.get("individual") is None:
        return None
    return res


def parse_investor(content: bytes) -> dict | None:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    for ws in wb.worksheets:
        res = parse_investor_wide(ws)
        if res:
            return res
    # 以下は主体が行方向に並ぶ形式（旧形式）向けの予備
    found: dict[str, tuple] = {}
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            labels = [jp_only(v) for v in r if isinstance(v, str)]
            key = next((INVESTOR_LABELS[l] for l in labels if l in INVESTOR_LABELS), None)
            if not key:
                continue
            bal = best_balance(nums(r))
            if bal and (key not in found or bal[3] > found[key][3]):
                found[key] = bal  # 合計が最大＝二市場（全市場の合計）
    if "foreign" not in found or "individual" not in found:
        return None
    return {k: int(round(found[k][2] / 1000)) if k in found else None for k in INVESTOR_LABELS.values()}


def update_investor() -> None:
    rows = load_json("investor.json")
    by_week = {r["week_end"]: r for r in rows}
    html = get(f"{JPX}/markets/statistics-equities/investor-type/index.html").text
    links = sorted(set(re.findall(r'href="([^"]*?stock_1_w_(\d{8})_(\d{8})\.xlsx)"', html)), key=lambda x: x[2])
    for href, start, end in links:
        d = iso(end)
        if d in by_week and by_week[d].get("src") == "jpx":
            continue
        url = href if href.startswith("http") else JPX + href
        try:
            content = get(url).content
            res = parse_investor(content)
            if not res:
                log(f"investor parse failed {d}（未公表の可能性）")
                dump_sheet(content, f"investor_{end}")
                continue
            old = by_week.get(d)
            if old and old.get("foreign") != res["foreign"]:
                log(f"investor {d}: sheet値と差異 foreign {old.get('foreign')} -> {res['foreign']}")
            by_week[d] = {"week_end": d, "week_start": iso(start), **res, "src": "jpx"}
            log(f"investor {d}: {res}")
        except Exception as e:  # noqa: BLE001
            log(f"investor error {d}: {e}")
    save_json("investor.json", [by_week[k] for k in sorted(by_week)])


# ---------------------------------------------------------------- 日経平均
def fred_closes() -> dict[str, float]:
    text = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=NIKKEI225").text
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) == 2 and re.match(r"\d{4}-\d{2}-\d{2}", row[0]) and row[1] not in (".", ""):
            out[row[0]] = float(row[1])
    return out


def to_num(s: str) -> float | None:
    s = (s or "").replace(",", "").replace("%", "").replace("倍", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def update_nikkei(closes: dict[str, float]) -> None:
    rows = load_json("nikkei.json")
    by_date = {r["date"]: r for r in rows}
    html = get("https://stock-marketdata.com/kabukashihyo.html").text
    soup = BeautifulSoup(html, "lxml")
    table = None
    for t in soup.find_all("table"):
        head = t.get_text(" ")
        if "PER" in head and "EPS" in head and "指数" in head and "日付" in head:
            table = t
            break
    if table is None:
        log("nikkei: table not found")
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / "nikkei_page.html").write_text(html[:200000], encoding="utf-8")
        return
    trs = table.find_all("tr")
    headers = [re.sub(r"\s", "", th.get_text()).replace("（", "(").replace("）", ")") for th in trs[0].find_all(["th", "td"])]
    colmap = {"PER": "per_w", "EPS": "eps_w", "PBR": "pbr_w", "PER(指数)": "per_i", "EPS(指数)": "eps_i", "PBR(指数)": "pbr_i"}
    added = 0
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) != len(headers):
            continue
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cells[0])
        if not m:
            continue
        d = f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
        rec = {"date": d}
        for h, v in zip(headers, cells):
            if h in colmap:
                rec[colmap[h]] = to_num(v)
        if rec.get("per_w") is None or rec.get("eps_w") is None:
            continue
        old = by_date.get(d, {})
        if old.get("close_src") in ("fred", "sheet") and old.get("per_w") == rec["per_w"]:
            continue
        by_date[d] = {**old, **rec}
        added += 1
    # 終値：FRED を優先、まだ無い日は PER×EPS で仮置き（後日 FRED で上書き）
    for d, r in by_date.items():
        if r.get("close_src") == "sheet":
            continue
        if d in closes:
            r["close"], r["close_src"] = closes[d], "fred"
        elif r.get("close") is None or r.get("close_src") == "calc":
            r["close"], r["close_src"] = round(r["per_w"] * r["eps_w"], 2), "calc"
    log(f"nikkei: {added} rows updated")
    save_json("nikkei.json", [by_date[k] for k in sorted(by_date)])


# ---------------------------------------------------------------- 評価損益率（推計）
def close_on_or_before(closes: dict[str, float], d: str) -> float | None:
    day = dt.date.fromisoformat(d)
    for _ in range(10):
        k = day.isoformat()
        if k in closes:
            return closes[k]
        day -= dt.timedelta(days=1)
    return None


def estimate_eval(closes: dict[str, float]) -> None:
    """買い残金額＝約定代金（取得原価）を、日経平均の値動きで時価に引き直して評価損益率を推計。
    新規の買い増しは時価で、返済は保有の時価比率で減ると仮定。実績値がある週はそこを起点に戻す。"""
    manual = {}
    p = DATA / "manual_eval.csv"
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8")):
            v = to_num(r.get("eval", ""))
            if r.get("date") and v is not None:
                manual[r["date"].strip()] = v
    rows = load_json("margin.json")
    cost = mv = None
    prev_close = None
    for r in rows:
        c = close_on_or_before(closes, r["date"])
        if r["date"] in manual:
            r["eval"], r["eval_type"] = manual[r["date"]], "actual"
            cost, mv = r["buy"], r["buy"] * (1 + manual[r["date"]] / 100)
        elif cost and mv and c and prev_close:
            mv *= c / prev_close
            diff = r["buy"] - cost
            mv += diff if diff > 0 else diff * mv / cost
            cost = r["buy"]
            r["eval"], r["eval_type"] = round((mv / cost - 1) * 100, 2), "est"
        else:
            r["eval"], r["eval_type"] = None, None
        r["nikkei"] = c
        prev_close = c
    save_json("margin.json", rows)


def main() -> int:
    errors = 0
    closes: dict[str, float] = {}
    for name, fn in (("fred", None), ("margin", update_margin), ("investor", update_investor)):
        try:
            if name == "fred":
                closes = fred_closes()
                log(f"fred: {len(closes)} closes")
            else:
                fn()
        except Exception:  # noqa: BLE001
            errors += 1
            log(f"{name} failed:\n{traceback.format_exc()}")
    for name, fn in (("nikkei", update_nikkei), ("eval", estimate_eval)):
        try:
            fn(closes)
        except Exception:  # noqa: BLE001
            errors += 1
            log(f"{name} failed:\n{traceback.format_exc()}")
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    (DATA / "meta.json").write_text(json.dumps({"updated": now, "errors": errors}, ensure_ascii=False) + "\n", encoding="utf-8")
    DEBUG.mkdir(exist_ok=True)
    (DEBUG / "last_run.log").write_text(f"{now} JST\n" + "\n".join(LOG) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
