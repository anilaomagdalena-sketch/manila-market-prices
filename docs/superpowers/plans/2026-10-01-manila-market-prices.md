# マニラの野菜・魚介価格 自動更新ページ 実装計画

> **実装者（Codex）へ：** この計画を上から順に、タスク単位で実装する。各タスクは「テストを書く → 落ちるのを確かめる → 実装する → 通るのを確かめる → コミット」の順で進める。手順はチェックボックス（`- [ ]`）で追跡する。設計書と食い違う点を見つけたら、勝手に埋めずに作業を止めて著者に報告する。

**Goal:** 農業省（DA）Bantay Presyo の日次PDFから首都圏の野菜・魚介の小売価格を毎週自動で集め、2020年11月からの推移をグラフにしてGitHub Pagesで公開する。

**Architecture:** 公開リポジトリ1つ。Pythonの部品（収集 → 集計 → 画面用JSON生成）がCSVファイルだけを介してつながり、静的なグラフページ（HTML＋Chart.js）がそのJSONを読む。GitHub Actionsが毎週動かし、取得済みのPDFは台帳（`data/sources.csv`）で管理して二度と取りに行かない。

**Tech Stack:** Python 3.11以上、pdfplumber、requests、openpyxl、pytest、Chart.js 4（リポジトリに同梱）、Playwright（画面テスト）、GitHub Actions、GitHub Pages。

**Spec:** `docs/superpowers/specs/2026-10-01-manila-market-prices-design.md`（末尾の12節「調査結果による更新」まで読むこと）

**検証済みの出発点:** `docs/reference/parser-prototype/` に、PDFの読み取り部分の試作とテストが入っている。2020-11〜2026-09の各月1本（71本）で動かし、画像だけのPDF 2本を除いて全部から行を取り出せた。テスト28件は実物のPDFから作った見本で通っている。**読み取り部分は書き直さず、これを土台にする。**

## Global Constraints

- 収集の開始日は `2020-11-01`。これより前の報告日のPDFは取得しない。
- 台帳（`data/sources.csv`）に `url` がある行は、`status` が何であれ再取得しない。例外は `collect --retry-failed` を付けたときの `failed` だけ。
- DAへのアクセスは、同時接続1本、PDF 1本ごとに3秒あける。User-Agentは `manila-market-prices/1.0 (+https://github.com/<owner>/manila-market-prices)`。
- テストはネットワークに出ない。DAへの実アクセスは `collect` の実行時だけ。
- CSVはすべてUTF-8、ヘッダーあり、改行はLF、日付は `YYYY-MM-DD`、決まった順に並べて書き出す。価格は小数第2位まで（末尾の0は付けない。`100`、`82.5`、`119.87`）。空は空文字。
- PDF本体はリポジトリに置かない。作業用のキャッシュは `.cache/pdf/`（gitignore）。
- 品目の対応は `data/commodities.csv` だけで管理する。コードに品目名を書かない。
- 産地・品種の違うものは別品目のまま扱う。勝手に平均しない。
- 画面の表記は日本語。品目名は「和名（タガログ名／英名）」。
- 画面はスマホ縦（幅360px）で横スクロールが出ないこと。iframeの高さは品目を変えても変わらないこと。
- 色だけに頼らず、線種と凡例で系列を区別する。
- 既存のWordPressページのURLは変えない。WordPressへは自動で書き込まない。
- コミットメッセージは英語、1行目は命令形。

## Review Focus

設計書が暗に求めているが、放っておくとテストされない入力。それぞれ担当タスクにテストを入れてある。

1. **よく似た名前のPDFを取り違える。** `Daily-Cigarette-Price-Monitoring-…` や `Weekly-Average-Prices-…` を価格PDFとして取り込んではいけない（計画を書く途中で実際に取り違えた）。→ Task 2
2. **ファイル名の日付が壊れている・本文と食い違う。** `Novermber-11-2020`、`September-1-2021-Final-Version`、アップロード月と報告月のずれ。日付が決まらないPDFは捨てずに `failed` にし、食い違いは台帳に残す。→ Task 2、Task 4
3. **PDFでないものが返ってくる・中身が空。** 画像だけのPDF、HTTP 200で返るHTMLのエラーページ、0バイト。落ちずに、取得失敗（台帳に載せない）か `failed` に振り分ける。→ Task 4
4. **途中で止まる。** 初回取り込みは数時間かかり、Actionsの制限や通信断で途中終了しうる。どこで止まっても台帳とデータが食い違わず、次回は続きから進むこと。→ Task 4
5. **データがまばらな品目を画面で開く。** 実測値の点しか無い品目、1点しか無い品目、選んだ期間にデータが無い品目、`?item=` に存在しないIDが来た場合。グラフが壊れず、「この期間のデータはありません」と出ること。→ Task 8

---

## ファイル構成

```
pyproject.toml
.gitignore
README.md
src/mmp/
  __init__.py
  names.py            品目名 → commodity_id          （試作から移す）
  parsers/
    geometry.py       単語の座標、数値のかたまり、行   （試作から移す）
    summary.py        首都圏まとめページ               （試作から移す）
    rowtable.py       行の表（2020〜21年、DPI）        （試作から移す）
    market.py         市場別の表                       （試作から移す）
    pdf.py            体裁の判定と振り分け             （試作から移す）
  links.py            一覧HTML → PDFリンクの分類
  ledger.py           data/sources.csv の読み書き
  store.py            daily / market_daily / unmapped / rejected の読み書き
  collect.py          収集のCLI
  import_own.py       Excel → data/own.csv のCLI
  aggregate.py        日次 → 週次のCLI
  build_site.py       CSV → site/data.json のCLI
  check_health.py     異常検知のCLI
data/
  commodities.csv     （試作の data/commodities.csv を移す）
  sources.csv daily.csv market_daily.csv weekly.csv own.csv unmapped.csv rejected.csv
site/
  index.html app.js style.css data.json
  vendor/chart.umd.min.js
tests/
  fixtures/*.json     （試作から移す）
  fixtures/index_sample.html
  test_parsers.py test_names.py   （試作から移す）
  test_links.py test_ledger.py test_store.py test_collect.py
  test_import_own.py test_aggregate.py test_build_site.py test_check_health.py
  e2e/test_site.py
tools/
  dump_fixture.py     PDF → 見本JSON（試作から移す）
.github/workflows/weekly.yml backfill.yml
docs/                 設計書、計画書、参考資料（既存）
```

---

### Task 0: リポジトリを用意する（著者の作業）

実装の前に、著者が次を済ませる。Codexはここは実行しない。

- [ ] GitHubに公開リポジトリ `manila-market-prices` を空で作る（README等は付けない）。
- [ ] 設計・計画・試作の入った作業フォルダ（Mac miniの `~/local-work/manila-market-prices/`）をMacBook Proへ持っていき、そのリポジトリへpushする。
- [ ] MacBook ProでCodexをそのリポジトリのフォルダで起動し、「`docs/superpowers/plans/2026-10-01-manila-market-prices.md` を Task 1 から実装して」と指示する。

---

### Task 1: 骨組みを作り、試作を取り込む

**Files:**
- Create: `pyproject.toml`、`.gitignore`、`src/mmp/__init__.py`
- Move: `docs/reference/parser-prototype/mmp/**` → `src/mmp/**`
- Move: `docs/reference/parser-prototype/tests/**` → `tests/**`
- Move: `docs/reference/parser-prototype/data/commodities.csv` → `data/commodities.csv`
- Move: `docs/reference/parser-prototype/dump_fixture.py` → `tools/dump_fixture.py`

**Interfaces:**
- Produces（後のタスクが使う。試作のまま、名前を変えない）:
  - `mmp.parsers.pdf.parse_pdf(data: bytes) -> ParseResult`
  - `ParseResult.report_date: datetime.date | None`、`.layouts: list[str]`、`.rows: list[dict]`、`.market_rows: list[dict]`
  - `rows` の各要素：`{"raw_name": str, "spec": str, "unit": str, "low": float|None, "high": float|None, "prevailing": float|None, "average": float|None}`
  - `market_rows` の各要素：`{"market": str, "raw_name": str, "low": float, "high": float, "price": float}`
  - `mmp.names.NameMap(path: Path)`、`NameMap.lookup(raw_name: str, spec: str = "") -> str | None`

- [x] **Step 1: `pyproject.toml` を書く**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mmp"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["pdfplumber>=0.11", "requests>=2.31", "openpyxl>=3.1"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-playwright>=0.5"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --ignore=tests/e2e"
```

- [x] **Step 2: `.gitignore` を書く**

```
.cache/
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
test-results/
```

- [x] **Step 3: 試作を `git mv` で移す**

```bash
mkdir -p src tools data
git mv docs/reference/parser-prototype/mmp src/mmp
git mv docs/reference/parser-prototype/tests tests
git mv docs/reference/parser-prototype/data/commodities.csv data/commodities.csv
git mv docs/reference/parser-prototype/dump_fixture.py tools/dump_fixture.py
```

`tests/test_names.py` は `Path(__file__).parent.parent / "data" / "commodities.csv"` を読むので、移したあともそのまま動く。

- [x] **Step 4: 環境を作り、テストが通ることを確かめる**

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Expected: `28 passed`

- [x] **Step 5: コミット**

```bash
git add -A && git commit -m "Set up package skeleton and adopt verified parser prototype"
```

---

### Task 2: 一覧ページからPDFリンクを分類する

**Files:**
- Create: `src/mmp/links.py`
- Create: `tests/fixtures/index_sample.html`
- Test: `tests/test_links.py`

**Interfaces:**
- Produces:
  - `START_DATE = datetime.date(2020, 11, 1)`
  - `@dataclass(frozen=True) class Link: url: str; kind: str; revised: bool; report_date: datetime.date | None`
    - `kind` は `"price_monitoring"` / `"daily_price_index"` / `"skip"`
  - `classify(url: str) -> Link`
  - `extract_links(html: str) -> list[Link]`（URLで重複を除き、出現順）

**ふるまい:**
- URLは `http://` を `https://` に直す。
- 種類はファイル名（最後の `/` より後ろ）の**先頭**で決める。大文字小文字は区別しない。
  - `Price-Monitoring-`、`Revised-Price-Monitoring-`、`Updated-Price-Monitoring-` → `price_monitoring`
  - `Daily-Price-Index-`、`Revised-Daily-Price-Index-` → `daily_price_index`
  - それ以外（`Daily-Cigarette-…`、`Weekly-Average-…`、`Price-Watch-…`、`Retail-Price-Monitoring-…`、`Price-Monitoring-Report-…` を含む）→ `skip`
- `revised` は、ファイル名が `Revised-` か `Updated-` で始まる、**または**ファイル名のどこかに `-Revised` か `-Final-Version` を含むとき真。
- `report_date` は、ファイル名の中の「月名-日-年」から読む。月名は先頭3文字で判定する（`Novermber` → 11月、`Sept` → 9月）。読めなければ `None`。
- `uploads/YYYY/MM/` はアップロード月なので、日付の判定に使わない。

- [x] **Step 1: 見本HTMLを書く**

`tests/fixtures/index_sample.html`：

```html
<html><body>
<a href="https://www.da.gov.ph/wp-content/uploads/2026/09/Price-Monitoring-August-28-2026.pdf">a</a>
<a href="https://www.da.gov.ph/wp-content/uploads/2026/09/Daily-Cigarette-Price-Monitoring-August-28-2026.pdf">b</a>
<a href="https://www.da.gov.ph/wp-content/uploads/2026/09/Daily-Price-Index-August-29-2026.pdf">c</a>
<a href="https://www.da.gov.ph/wp-content/uploads/2026/08/Weekly-Average-Prices-July-27-August-2-2026.pdf">d</a>
<a href="http://www.da.gov.ph/wp-content/uploads/2018/02/Price-Watch-February-6-2018.pdf">e</a>
<a href="https://www.da.gov.ph/wp-content/uploads/2026/09/Price-Monitoring-August-28-2026.pdf">dup</a>
<a href="https://www.da.gov.ph/about/">not a pdf</a>
</body></html>
```

- [x] **Step 2: 落ちるテストを書く**

`tests/test_links.py`：

```python
import datetime as dt
from pathlib import Path

import pytest

from mmp.links import classify, extract_links

BASE = "https://www.da.gov.ph/wp-content/uploads"


@pytest.mark.parametrize("path, kind, revised, date", [
    ("2020/11/Price-Monitoring-November-20-2020.pdf", "price_monitoring", False, dt.date(2020, 11, 20)),
    # アップロード月（2025/01）と報告月（2024年12月）がずれている
    ("2025/01/Price-Monitoring-December-24-2024.pdf", "price_monitoring", False, dt.date(2024, 12, 24)),
    # 月名の綴り違い
    ("2020/11/Price-Monitoring-Novermber-11-2020.pdf", "price_monitoring", False, dt.date(2020, 11, 11)),
    # 後ろに付く訂正の印
    ("2021/09/Price-Monitoring-September-1-2021-Final-Version.pdf", "price_monitoring", True, dt.date(2021, 9, 1)),
    ("2021/09/Price-Monitoring-September-10-2021-Revised.pdf", "price_monitoring", True, dt.date(2021, 9, 10)),
    ("2023/05/Revised-Price-Monitoring-May-3-2023.pdf", "price_monitoring", True, dt.date(2023, 5, 3)),
    ("2025/06/Daily-Price-Index-June-1-2025.pdf", "daily_price_index", False, dt.date(2025, 6, 1)),
    ("2026/01/Revised-Daily-Price-Index-January-5-2026.pdf", "daily_price_index", True, dt.date(2026, 1, 5)),
    # 取り違えてはいけないもの
    ("2026/09/Daily-Cigarette-Price-Monitoring-August-28-2026.pdf", "skip", False, dt.date(2026, 8, 28)),
    ("2026/08/Weekly-Average-Prices-July-27-August-2-2026.pdf", "skip", False, None),
    ("2019/03/Retail-Price-Monitoring-March-4-2019.pdf", "skip", False, dt.date(2019, 3, 4)),
    ("2020/04/Price-Monitoring-Report-April-2-2020.pdf", "skip", False, dt.date(2020, 4, 2)),
    ("2018/02/Price-Watch-February-6-2018.pdf", "skip", False, dt.date(2018, 2, 6)),
])
def test_classify(path, kind, revised, date):
    link = classify(f"{BASE}/{path}")
    assert (link.kind, link.revised) == (kind, revised)
    if kind != "skip":
        assert link.report_date == date


def test_classify_normalizes_http():
    link = classify("http://www.da.gov.ph/wp-content/uploads/2020/12/Price-Monitoring-December-1-2020.pdf")
    assert link.url.startswith("https://")


def test_classify_unreadable_date_is_none():
    assert classify(f"{BASE}/2022/01/Price-Monitoring-latest.pdf").report_date is None


def test_extract_links_dedupes_and_keeps_only_pdfs():
    html = (Path(__file__).parent / "fixtures" / "index_sample.html").read_text()
    links = extract_links(html)
    assert len(links) == 5
    assert [l.kind for l in links] == ["price_monitoring", "skip", "daily_price_index", "skip", "skip"]
    assert links[4].url.startswith("https://")
```

- [x] **Step 3: 落ちることを確かめる**

Run: `pytest tests/test_links.py`
Expected: FAIL（`ModuleNotFoundError: No module named 'mmp.links'`）

- [x] **Step 4: `src/mmp/links.py` を実装する**

リンクの抽出は正規表現 `href="([^"]+\.pdf)"`（大文字小文字を区別しない）で足りる。HTMLパーサーは入れない。

- [x] **Step 5: 通ることを確かめる**

Run: `pytest tests/test_links.py`
Expected: PASS（全件）

- [x] **Step 6: コミット**

```bash
git add src/mmp/links.py tests/test_links.py tests/fixtures/index_sample.html
git commit -m "Classify DA price PDF links by file name"
```

---

### Task 3: 台帳とデータファイルの読み書き

**Files:**
- Create: `src/mmp/ledger.py`、`src/mmp/store.py`
- Test: `tests/test_ledger.py`、`tests/test_store.py`

**Interfaces:**
- Produces（`ledger.py`）:
  - 列：`url, kind, revised, report_date, status, layout, rows, sha256, fetched_at, error`
  - `class Ledger: __init__(path: Path)`（無ければ空で始める）
  - `Ledger.has(url: str) -> bool`
  - `Ledger.get(url: str) -> dict | None`
  - `Ledger.put(entry: dict) -> None`（`url` で上書き）
  - `Ledger.entries() -> list[dict]`
  - `Ledger.save() -> None`（`report_date, url` の順に並べ、一時ファイルに書いてから置き換える）
  - `status` は `parsed` / `failed` / `skipped` / `superseded`
- Produces（`store.py`）:
  - `fmt(x: float | None) -> str`（`100.0 → "100"`、`82.5 → "82.5"`、`119.87 → "119.87"`、`None → ""`）
  - `class DailyStore: __init__(path: Path)`、列は `date, commodity_id, spec, unit, low, high, prevailing, average, source_url`
    - `replace_date(date: str, rows: list[dict]) -> None`（その日付の行を全部入れ替える）
    - `dates_with_source(url: str) -> set[str]`
    - `last_price(commodity_id: str, before: str) -> float | None`（その日より前の直近の代表値。代表値は `prevailing → average → (low+high)/2` の順）
    - `rows() -> list[dict]`、`save() -> None`（`date, commodity_id` の順）
  - `class MarketStore`：列は `date, market, commodity_id, low, high, price, source_url`。`replace_date`、`rows`、`save` は同じ形。並びは `date, market, commodity_id`。
  - `class UnmappedLog`：列は `raw_name, first_date, last_date, count, example_url`。`add(raw_name: str, date: str, url: str)`、`save()`（`count` の多い順、同数は `raw_name` 順）。
  - `class RejectedLog`：列は `date, commodity_id, value, previous, reason, source_url`。`add(...)`、`save()`（追記ではなく全体を並べ直して書く）。

- [x] **Step 1: 落ちるテストを書く**

`tests/test_ledger.py`：

```python
from mmp.ledger import Ledger


def entry(url, date="2020-11-20", status="parsed"):
    return {"url": url, "kind": "price_monitoring", "revised": "0", "report_date": date,
            "status": status, "layout": "rowtable", "rows": "45", "sha256": "ab",
            "fetched_at": "2026-10-05T00:00:00Z", "error": ""}


def test_roundtrip_and_sorted(tmp_path):
    p = tmp_path / "sources.csv"
    led = Ledger(p)
    led.put(entry("https://x/b.pdf", "2021-01-02"))
    led.put(entry("https://x/a.pdf", "2020-11-20"))
    led.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "url,kind,revised,report_date,status,layout,rows,sha256,fetched_at,error"
    assert lines[1].startswith("https://x/a.pdf,") and lines[2].startswith("https://x/b.pdf,")
    again = Ledger(p)
    assert again.has("https://x/a.pdf") and not again.has("https://x/c.pdf")
    assert again.get("https://x/b.pdf")["report_date"] == "2021-01-02"


def test_put_overwrites_by_url(tmp_path):
    led = Ledger(tmp_path / "s.csv")
    led.put(entry("https://x/a.pdf", status="failed"))
    led.put(entry("https://x/a.pdf", status="parsed"))
    assert len(led.entries()) == 1 and led.get("https://x/a.pdf")["status"] == "parsed"


def test_save_is_atomic(tmp_path):
    p = tmp_path / "s.csv"
    led = Ledger(p)
    led.put(entry("https://x/a.pdf"))
    led.save()
    assert not list(tmp_path.glob("*.tmp"))
```

`tests/test_store.py`：

```python
import pytest

from mmp.store import DailyStore, MarketStore, UnmappedLog, fmt


@pytest.mark.parametrize("x, s", [(100.0, "100"), (82.5, "82.5"), (119.87, "119.87"),
                                  (6.0, "6"), (None, ""), (57.499999, "57.5")])
def test_fmt(x, s):
    assert fmt(x) == s


def drow(cid, **kw):
    base = {"commodity_id": cid, "spec": "", "unit": "kg", "low": None, "high": None,
            "prevailing": None, "average": None, "source_url": "https://x/a.pdf"}
    base.update(kw)
    return base


def test_replace_date_swaps_all_rows_of_that_date(tmp_path):
    st = DailyStore(tmp_path / "daily.csv")
    st.replace_date("2020-11-20", [drow("tomato", prevailing=180.0), drow("cabbage_scorpio", prevailing=100.0)])
    st.replace_date("2020-11-21", [drow("tomato", prevailing=170.0)])
    st.replace_date("2020-11-20", [drow("tomato", prevailing=175.0, source_url="https://x/rev.pdf")])
    rows = st.rows()
    assert [(r["date"], r["commodity_id"]) for r in rows] == [("2020-11-20", "tomato"), ("2020-11-21", "tomato")]
    assert rows[0]["prevailing"] == "175" and rows[0]["source_url"] == "https://x/rev.pdf"


def test_save_sorted_and_reload(tmp_path):
    p = tmp_path / "daily.csv"
    st = DailyStore(p)
    st.replace_date("2021-01-02", [drow("tomato", low=24.0, high=50.0, prevailing=40.0)])
    st.replace_date("2020-11-20", [drow("tomato", prevailing=180.0), drow("bangus", prevailing=160.0)])
    st.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,commodity_id,spec,unit,low,high,prevailing,average,source_url"
    assert [l.split(",")[:2] for l in lines[1:]] == [
        ["2020-11-20", "bangus"], ["2020-11-20", "tomato"], ["2021-01-02", "tomato"]]
    assert DailyStore(p).rows()[2]["low"] == "24"


def test_last_price_uses_representative_value(tmp_path):
    st = DailyStore(tmp_path / "d.csv")
    st.replace_date("2023-06-01", [drow("tomato", low=30.0, high=80.0)])          # 中間値 55
    st.replace_date("2023-06-02", [drow("tomato", low=40.0, high=160.0, prevailing=120.0, average=103.67)])
    assert st.last_price("tomato", before="2023-06-02") == 55.0
    assert st.last_price("tomato", before="2023-06-03") == 120.0
    assert st.last_price("tomato", before="2023-06-01") is None
    assert st.last_price("squid", before="2030-01-01") is None


def test_market_store_sorted(tmp_path):
    p = tmp_path / "m.csv"
    st = MarketStore(p)
    st.replace_date("2026-08-28", [
        {"market": "Cartimar", "commodity_id": "tomato", "low": 110.0, "high": 110.0, "price": 110.0, "source_url": "u"},
        {"market": "Cartimar", "commodity_id": "bangus", "low": 250.0, "high": 250.0, "price": 250.0, "source_url": "u"}])
    st.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,market,commodity_id,low,high,price,source_url"
    assert lines[1] == "2026-08-28,Cartimar,bangus,250,250,250,u"


def test_unmapped_log_counts_and_dates(tmp_path):
    p = tmp_path / "u.csv"
    log = UnmappedLog(p)
    log.add("Pompano, Local", "2026-02-23", "https://x/1.pdf")
    log.add("Pompano, Local", "2025-06-01", "https://x/2.pdf")
    log.add("Special", "2020-11-20", "https://x/3.pdf")
    log.save()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "raw_name,first_date,last_date,count,example_url"
    assert lines[1] == '"Pompano, Local",2025-06-01,2026-02-23,2,https://x/1.pdf'
    again = UnmappedLog(p)
    again.add("Special", "2020-11-21", "https://x/4.pdf")
    again.save()
    assert "Special,2020-11-20,2020-11-21,2,https://x/3.pdf" in p.read_text(encoding="utf-8")
```

- [x] **Step 2: 落ちることを確かめる**

Run: `pytest tests/test_ledger.py tests/test_store.py`
Expected: FAIL（モジュールが無い）

- [x] **Step 3: `ledger.py` と `store.py` を実装する**

読み書きは標準の `csv` モジュール（`lineterminator="\n"`）。保存は `path.with_suffix(".tmp")` に書いてから `os.replace` する。メモリ上では値を文字列で持ち、書き込むときに `fmt` を通す。

- [x] **Step 4: 通ることを確かめる**

Run: `pytest tests/test_ledger.py tests/test_store.py`
Expected: PASS

- [x] **Step 5: コミット**

```bash
git add src/mmp/ledger.py src/mmp/store.py tests/test_ledger.py tests/test_store.py
git commit -m "Add ledger and CSV stores with deterministic output"
```

---

### Task 4: 収集（差分取得・解析・保存）

**Files:**
- Create: `src/mmp/collect.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `links.extract_links`、`links.START_DATE`、`Ledger`、`DailyStore`、`MarketStore`、`UnmappedLog`、`RejectedLog`、`parsers.pdf.parse_pdf`、`names.NameMap`
- Produces:
  - `INDEX_URL = "https://www.da.gov.ph/price-monitoring/"`
  - `MIN_LINKS = 1000`
  - `class FetchError(Exception)`
  - `http_fetch(url: str) -> bytes`（requests。User-Agent付き、タイムアウト60秒、3回まで再試行。だめなら `FetchError`）
  - `@dataclass class Stats: new: int = 0; parsed: int = 0; failed: int = 0; skipped: int = 0; fetch_errors: int = 0`
  - `run(data_dir: Path, *, fetch: Callable[[str], bytes] = http_fetch, parse: Callable[[bytes], ParseResult] = parse_pdf, max_new: int | None = None, retry_failed: bool = False, delay: float = 3.0, cache_dir: Path | None = None, checkpoint_every: int = 25, now: Callable[[], datetime] = ...) -> Stats`
  - `main(argv=None) -> int`（`python -m mmp.collect --data-dir data [--max-new N] [--retry-failed] [--cache-dir .cache/pdf] [--delay 3]`）

**ふるまい（順番どおりに実装する）:**

1. `fetch(INDEX_URL)` で一覧を取り、`extract_links` にかける。リンクが `MIN_LINKS` 未満なら `FetchError("index looks broken")`。
2. 台帳に無いリンクを候補にする（`retry_failed` のときは `status == "failed"` も候補に戻す）。
3. 取得せずに片づくものを先に台帳へ載せる（`status="skipped"`、`error` に理由）。
   - `kind == "skip"` → `not_a_price_report`
   - 報告日が `START_DATE` より前 → `before_start_date`
4. 残りを**報告日の古い順**に並べる。同じ日の中は「通常版 → 訂正版」、「Price Monitoring → Daily Price Index」の順。ファイル名から日付が読めないものは最後に回す。
5. 1本ずつ処理する。`max_new` は、実際に中身を読んだ本数（取得したもの、キャッシュから読んだもの）で数え、達したらそこで終える（残りは次回に回る）。取得せずに `skipped` にしたものは数えない。
   - Daily Price Index で、同じ報告日に `parsed` のPrice Monitoringが台帳にあるなら、取得せず `skipped`（`pm_exists`）。
   - `fetch(url)`。`FetchError` なら台帳に**載せず**、`stats.fetch_errors += 1` して次へ。
   - 先頭が `%PDF` でなければ `FetchError` と同じ扱い（HTMLのエラーページ対策）。
   - `cache_dir` があれば、`<sha256の先頭16桁>.pdf` として保存し、次回は `fetch` の前にキャッシュを見る（URLから決まる名前ではなく、台帳の `sha256` で引く。台帳に無いURLは必ず取得する）。
   - `parse(data)`。例外が出たら `failed`（`error` は `例外の型名: メッセージの1行目`。例：`ValueError: boom`）。`failed` のときも台帳に `sha256` を残す（やり直すときにキャッシュを引くため）。
   - 報告日を決める：ファイル名の日付を優先。無ければ本文の日付（`ParseResult.report_date`）。どちらも無ければ `failed`（`no_date`）。両方あって違うときはファイル名を採り、`error` に `date_mismatch body=YYYY-MM-DD` と残す（`status` は `parsed` のまま）。
   - 決めた報告日が `START_DATE` より前なら `skipped`（`before_start_date`）。
   - `rows` が0件なら `failed`（`no_rows`）。
   - 品目名を `NameMap.lookup(raw_name, spec)` で引く。引けないものは `UnmappedLog.add`。同じPDFで同じ `commodity_id` が2回出たら、先に出たほうを採る。
   - 値の検査：代表値（`prevailing → average → (low+high)/2`）が0以下、または `DailyStore.last_price(commodity_id, before=date)` の5倍超・5分の1未満なら、その行は入れずに `RejectedLog.add`（`reason` は `non_positive` / `jump`）。
   - 保存の優先順位：その日付にすでに入っている行の出どころ（`source_url` → 台帳）と比べ、今回のほうが弱ければ入れない（`status="superseded"`）。強さは「訂正版のPrice Monitoring ＞ Price Monitoring ＞ 訂正版のDPI ＞ DPI」。同じ強さなら後から来たほうで置き換える。置き換えられた側の台帳は `superseded` にする。
   - `DailyStore.replace_date`。市場別は `market` が `Cartimar` で始まる行だけを、`market="Cartimar"` として `MarketStore.replace_date`（品目名が引けたものだけ）。
   - 台帳に `parsed` で載せる（`layout` は `"+".join(sorted(set(layouts) - {"skip"}))`、`rows` は入れた行数）。
   - `delay` 秒待つ（キャッシュから読んだときは待たない）。
6. `checkpoint_every` 本ごと、および最後に、**データ → ログ → 台帳の順**で保存する。台帳を最後に書くことで、途中で落ちても「台帳にあるのにデータに無い」状態にならない（データにあって台帳に無いPDFは、次回もう一度処理されて同じ結果になる）。
7. `main` は `Stats` を1行で表示し、0を返す。`FetchError`（一覧が取れない）のときは1を返す。

- [x] **Step 1: 落ちるテストを書く**

`tests/test_collect.py`。実物のPDFは使わず、`fetch` と `parse` を差し替える。

```python
import datetime as dt
from pathlib import Path

import pytest

from mmp import collect
from mmp.ledger import Ledger
from mmp.parsers.pdf import ParseResult
from mmp.store import DailyStore, MarketStore

BASE = "https://www.da.gov.ph/wp-content/uploads"
COMMODITIES = Path(__file__).parent.parent / "data" / "commodities.csv"
PDF = b"%PDF-1.4 "


def nrow(name, **kw):
    base = {"raw_name": name, "spec": "", "unit": "kg", "low": None, "high": None,
            "prevailing": None, "average": None}
    base.update(kw)
    return base


class World:
    """偽のDAサイト。URLごとに、返すバイト列と解析結果を決めておく。"""

    def __init__(self, tmp_path):
        self.data_dir = tmp_path / "data"
        self.data_dir.mkdir()
        (self.data_dir / "commodities.csv").write_bytes(COMMODITIES.read_bytes())
        self.files: dict[str, bytes] = {}
        self.listed: list[str] = []
        self.results: dict[bytes, ParseResult] = {}
        self.fetched: list[str] = []
        self.padding = 1000   # MIN_LINKS を満たすための、対象外リンクの数

    def add(self, name, rows=None, market_rows=None, body_date=None, raw=None, parse_error=None, missing=False):
        """missing=True は、一覧には載っているが取得すると404になるPDF。"""
        url = f"{BASE}/2099/01/{name}.pdf"
        data = raw if raw is not None else PDF + name.encode()
        self.listed.append(url)
        if not missing:
            self.files[url] = data
        self.results[data] = parse_error or ParseResult(
            report_date=body_date, layouts=["rowtable"], rows=rows or [], market_rows=market_rows or [])
        return url

    def publish(self, url):
        """missing=True で足したPDFを、取得できるようにする。"""
        name = url.rsplit("/", 1)[1][:-4]
        self.files[url] = PDF + name.encode()

    def index(self) -> bytes:
        hrefs = [f'<a href="{u}">x</a>' for u in self.listed]
        hrefs += [f'<a href="{BASE}/2018/02/Price-Watch-February-{i}-2018.pdf">x</a>' for i in range(self.padding)]
        return "\n".join(hrefs).encode()

    def fetch(self, url):
        self.fetched.append(url)
        if url == collect.INDEX_URL:
            return self.index()
        if url not in self.files:
            raise collect.FetchError("404")
        return self.files[url]

    def parse(self, data):
        r = self.results[data]
        if isinstance(r, Exception):
            raise r
        return r

    def run(self, **kw):
        return collect.run(self.data_dir, fetch=self.fetch, parse=self.parse, delay=0, **kw)

    def ledger(self):
        return Ledger(self.data_dir / "sources.csv")

    def daily(self):
        return DailyStore(self.data_dir / "daily.csv").rows()


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_parses_new_pdf_and_never_fetches_it_again(world):
    url = world.add("Price-Monitoring-November-20-2020",
                    rows=[nrow("Tomato", low=140.0, high=200.0, prevailing=180.0), nrow("Premium", prevailing=45.0)])
    stats = world.run()
    assert (stats.parsed, stats.failed) == (1, 0)
    assert [(r["date"], r["commodity_id"], r["prevailing"]) for r in world.daily()] == [("2020-11-20", "tomato", "180")]
    assert world.ledger().get(url)["status"] == "parsed"
    assert "Premium" in (world.data_dir / "unmapped.csv").read_text(encoding="utf-8")
    world.fetched.clear()
    stats = world.run()
    assert world.fetched == [collect.INDEX_URL] and stats.new == 0


def test_lookalike_and_old_reports_are_skipped_without_fetching(world):
    cig = world.add("Daily-Cigarette-Price-Monitoring-August-28-2026")
    weekly = world.add("Weekly-Average-Prices-July-27-August-2-2026")
    old = world.add("Price-Monitoring-October-30-2020")
    world.run()
    assert set(world.fetched) == {collect.INDEX_URL}
    led = world.ledger()
    assert led.get(cig)["status"] == led.get(weekly)["status"] == led.get(old)["status"] == "skipped"
    assert led.get(old)["error"] == "before_start_date"
    assert led.get(f"{BASE}/2018/02/Price-Watch-February-1-2018.pdf")["error"] == "not_a_price_report"


def test_index_with_too_few_links_raises(world):
    world.padding = 3
    world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=180.0)])
    with pytest.raises(collect.FetchError):
        world.run()
    assert world.daily() == []


def test_fetch_error_is_not_recorded_so_it_is_retried(world):
    url = world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=180.0)], missing=True)
    stats = world.run()
    assert stats.fetch_errors == 1 and not world.ledger().has(url)
    world.publish(url)
    assert world.run().parsed == 1


def test_html_error_page_with_200_is_treated_as_fetch_error(world):
    url = world.add("Price-Monitoring-November-20-2020", raw=b"<html>Not found</html>")
    stats = world.run()
    assert stats.fetch_errors == 1 and not world.ledger().has(url)


def test_image_only_pdf_becomes_failed_and_is_not_refetched(world):
    url = world.add("Price-Monitoring-May-1-2025", rows=[])
    assert world.run().failed == 1
    e = world.ledger().get(url)
    assert (e["status"], e["error"]) == ("failed", "no_rows")
    world.fetched.clear()
    world.run()
    assert url not in world.fetched
    world.results[world.files[url]] = ParseResult(None, ["summary"], [nrow("Tomato Kamatis", low=30.0, high=90.0)], [])
    assert world.run(retry_failed=True).parsed == 1


def test_parser_exception_becomes_failed(world):
    url = world.add("Price-Monitoring-May-2-2025", parse_error=ValueError("boom\ntrace"))
    world.run()
    e = world.ledger().get(url)
    assert e["status"] == "failed" and e["error"] == "ValueError: boom"


def test_date_from_body_when_file_name_has_none(world):
    url = world.add("Price-Monitoring-latest", rows=[nrow("Tomato", prevailing=50.0)], body_date=dt.date(2022, 1, 3))
    world.run()
    assert world.daily()[0]["date"] == "2022-01-03"
    assert world.ledger().get(url)["report_date"] == "2022-01-03"


def test_no_date_anywhere_is_failed(world):
    url = world.add("Price-Monitoring-latest", rows=[nrow("Tomato", prevailing=50.0)])
    world.run()
    assert world.ledger().get(url)["error"] == "no_date" and world.daily() == []


def test_date_mismatch_keeps_file_name_date_and_notes_it(world):
    url = world.add("Price-Monitoring-June-1-2021", rows=[nrow("Tomato", prevailing=40.0)], body_date=dt.date(2021, 5, 31))
    world.run()
    assert world.daily()[0]["date"] == "2021-06-01"
    e = world.ledger().get(url)
    assert e["status"] == "parsed" and e["error"] == "date_mismatch body=2021-05-31"


def test_revised_replaces_original_regardless_of_order(world):
    orig = world.add("Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=40.0), nrow("Tilapia", prevailing=120.0)])
    rev = world.add("Revised-Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=45.0)])
    world.run()
    assert [(r["commodity_id"], r["prevailing"]) for r in world.daily()] == [("tomato", "45")]
    led = world.ledger()
    assert led.get(orig)["status"] == "superseded" and led.get(rev)["status"] == "parsed"


def test_original_arriving_after_revised_does_not_overwrite(world):
    world.add("Revised-Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=45.0)])
    world.run()
    orig = world.add("Price-Monitoring-May-3-2023", rows=[nrow("Tomato", prevailing=40.0)])
    world.run()
    assert world.daily()[0]["prevailing"] == "45"
    assert world.ledger().get(orig)["status"] == "superseded"


def test_dpi_is_not_fetched_when_price_monitoring_exists(world):
    world.add("Price-Monitoring-June-2-2025", rows=[nrow("Tomato (Kamatis)", low=30.0, high=90.0, prevailing=60.0)])
    dpi = world.add("Daily-Price-Index-June-2-2025", rows=[nrow("Tomato", prevailing=61.0)])
    world.run()
    assert dpi not in world.fetched
    e = world.ledger().get(dpi)
    assert (e["status"], e["error"]) == ("skipped", "pm_exists")
    assert world.daily()[0]["prevailing"] == "60"


def test_dpi_fills_in_when_price_monitoring_failed(world):
    world.add("Price-Monitoring-May-1-2025", rows=[])
    world.add("Daily-Price-Index-May-1-2025", rows=[nrow("Tomato", spec="15-18 pcs/kg", prevailing=61.0)])
    world.run()
    assert [(r["date"], r["prevailing"]) for r in world.daily()] == [("2025-05-01", "61")]


def test_price_monitoring_arriving_later_replaces_dpi(world):
    dpi = world.add("Daily-Price-Index-June-3-2025", rows=[nrow("Tomato", prevailing=61.0)])
    world.run()
    world.add("Price-Monitoring-June-3-2025", rows=[nrow("Tomato (Kamatis)", prevailing=60.0)])
    world.run()
    assert world.daily()[0]["prevailing"] == "60"
    assert world.ledger().get(dpi)["status"] == "superseded"


def test_same_commodity_twice_in_one_pdf_keeps_first(world):
    world.add("Price-Monitoring-March-1-2024", rows=[nrow("Papaya", low=50.0, high=80.0), nrow("Papaya", low=10.0, high=20.0)])
    world.run()
    assert [(r["low"], r["high"]) for r in world.daily()] == [("50", "80")]


def test_jump_and_non_positive_values_are_rejected(world):
    world.add("Price-Monitoring-November-20-2020", rows=[nrow("Tomato", prevailing=100.0)])
    world.add("Price-Monitoring-November-23-2020",
              rows=[nrow("Tomato", prevailing=1000.0), nrow("Tilapia", prevailing=0.0), nrow("Bangus", prevailing=160.0)])
    world.run()
    assert [(r["date"], r["commodity_id"]) for r in world.daily()] == [
        ("2020-11-20", "tomato"), ("2020-11-23", "bangus")]
    rejected = (world.data_dir / "rejected.csv").read_text(encoding="utf-8")
    assert "2020-11-23,tomato,1000,100,jump" in rejected and "2020-11-23,tilapia,0,,non_positive" in rejected


def test_only_cartimar_market_rows_are_stored(world):
    world.add("Price-Monitoring-August-28-2026",
              rows=[nrow("Tomato (Kamatis)", prevailing=120.0)],
              market_rows=[{"market": "Cartimar Market", "raw_name": "Tomato", "low": 110.0, "high": 110.0, "price": 110.0},
                           {"market": "Pasay City Market", "raw_name": "Tomato", "low": 90.0, "high": 90.0, "price": 90.0},
                           {"market": "Cartimar Market", "raw_name": "*Egg (Medium)", "low": 8.5, "high": 8.5, "price": 8.5}])
    world.run()
    rows = MarketStore(world.data_dir / "market_daily.csv").rows()
    assert [(r["market"], r["commodity_id"], r["price"]) for r in rows] == [("Cartimar", "tomato", "110")]


def test_max_new_stops_early_and_next_run_continues_oldest_first(world):
    for day in (20, 23, 24):
        world.add(f"Price-Monitoring-November-{day}-2020", rows=[nrow("Tomato", prevailing=100.0 + day)])
    assert world.run(max_new=2).parsed == 2
    assert [r["date"] for r in world.daily()] == ["2020-11-20", "2020-11-23"]
    assert world.run(max_new=2).parsed == 1
    assert [r["date"] for r in world.daily()] == ["2020-11-20", "2020-11-23", "2020-11-24"]


def test_crash_midway_leaves_consistent_state_and_resumes(world):
    for day in (20, 23, 24):
        world.add(f"Price-Monitoring-November-{day}-2020", rows=[nrow("Tomato", prevailing=100.0 + day)])
    real_fetch = world.fetch

    def flaky(url):
        if "November-24" in url:
            raise KeyboardInterrupt
        return real_fetch(url)

    with pytest.raises(KeyboardInterrupt):
        collect.run(world.data_dir, fetch=flaky, parse=world.parse, delay=0, checkpoint_every=1)
    led = world.ledger()
    parsed_urls = {e["url"] for e in led.entries() if e["status"] == "parsed"}
    in_data = {r["source_url"] for r in world.daily()}
    assert parsed_urls <= in_data                     # 台帳にあるものは必ずデータにある
    assert len(parsed_urls) == 2
    assert world.run().parsed == 1
    assert len(world.daily()) == 3


def test_cache_is_used_on_retry(world, tmp_path):
    url = world.add("Price-Monitoring-May-1-2025", rows=[])
    cache = tmp_path / "cache"
    world.run(cache_dir=cache)
    assert len(list(cache.glob("*.pdf"))) == 1
    world.fetched.clear()
    world.results[world.files[url]] = ParseResult(None, ["summary"], [nrow("Tomato Kamatis", low=30.0, high=90.0)], [])
    assert world.run(retry_failed=True, cache_dir=cache).parsed == 1
    assert url not in world.fetched
```

- [x] **Step 2: 落ちることを確かめる**

Run: `pytest tests/test_collect.py`
Expected: FAIL（`mmp.collect` が無い）

- [x] **Step 3: `src/mmp/collect.py` を実装する**

上の「ふるまい」1〜7のとおり。`run` は200行を超えそうなら、「候補の決定」「1本の処理」「保存の優先順位」を関数に分ける。

- [x] **Step 4: 通ることを確かめる**

Run: `pytest`
Expected: PASS（全件）

- [x] **Step 5: 実物で1本だけ試す**

```bash
python -m mmp.collect --data-dir data --max-new 3 --cache-dir .cache/pdf
head -5 data/daily.csv && grep -c parsed data/sources.csv
```

Expected: `data/daily.csv` に2020年11月初めの行が入り、台帳に `parsed` が3行ある。`skipped` は1,000行あまり（対象外と開始日前）。3本より多くDAへ取りに行っていないこと。

- [x] **Step 6: コミット**

`data/*.csv` はまだコミットしない（Task 10でまとめて入れる）。試した結果は `git checkout data/ 2>/dev/null; git clean -fd data/` で消してから：

```bash
git add src/mmp/collect.py tests/test_collect.py
git commit -m "Collect new DA price PDFs incrementally with a fetch ledger"
```

---

### Task 5: 著者のExcelを取り込む

**Files:**
- Create: `src/mmp/import_own.py`
- Test: `tests/test_import_own.py`

**Interfaces:**
- Produces:
  - `read_own(xlsx: Path) -> list[dict]`
  - 行の形：`{"date": "YYYY-MM-DD", "sheet": "野菜"|"魚介", "item_ja": str, "name_tl": str, "name_en": str, "price": float, "market": "Cartimar"}`
  - `main(argv=None) -> int`（`python -m mmp.import_own docs/reference/own-cartimar-prices-2020-2024.xlsx --out data/own.csv`）
  - `data/own.csv` の列：`date, sheet, item_ja, name_tl, name_en, price, market`。並びは `sheet, item_ja, date`。

**ふるまい:**
- 1行目が見出し。A列＝英名、B列＝現地名、C列＝和名、D列以降は日付。
- 日付の見出しは3通りある：Excelのシリアル値（`44155` → 2020-11-20。起点は1899-12-30）、`datetime`、文字列（`"　5/23/2024"`。前後の空白と全角空白を取り、`月/日/年` として読む）。
- `item_ja` は前後の空白と全角空白を取る（`"メアジ　"` → `"メアジ"`）。途中の全角空白は残す（`"ナス　ローカル"`）。
- 数値でないセルと空のセルは飛ばす。和名が空の行は飛ばす。
- 設計書5.4節の `commodity_id` 列は持たない（1つの和名が複数の品目に対応することがあるため。対応は `commodities.csv` の `own_items` で引く）。

- [x] **Step 1: 落ちるテストを書く**

```python
from pathlib import Path

from mmp.import_own import main, read_own

XLSX = Path(__file__).parent.parent / "docs" / "reference" / "own-cartimar-prices-2020-2024.xlsx"


def pick(rows, item, date):
    hits = [r for r in rows if r["item_ja"] == item and r["date"] == date]
    assert len(hits) == 1
    return hits[0]


def test_counts_match_the_workbook():
    rows = read_own(XLSX)
    assert sum(1 for r in rows if r["sheet"] == "野菜") == 121
    assert sum(1 for r in rows if r["sheet"] == "魚介") == 6
    assert {r["market"] for r in rows} == {"Cartimar"}


def test_three_date_header_formats():
    rows = read_own(XLSX)
    assert pick(rows, "キャベツ", "2020-11-20")["price"] == 100     # シリアル値 44155
    assert pick(rows, "ジャガイモ", "2024-02-29")["price"] == 150   # datetime
    assert pick(rows, "ジャガイモ", "2024-05-23")["price"] == 120   # 文字列 '　5/23/2024'
    assert pick(rows, "ショウガ", "2024-05-23")["price"] == 240
    assert pick(rows, "カラス貝", "2020-12-22")["price"] == 150     # 魚介シートのシリアル値 44187
    assert pick(rows, "カラス貝", "2021-01-14")["price"] == 145


def test_names_are_trimmed_but_inner_spaces_kept():
    rows = read_own(XLSX)
    items = {r["item_ja"] for r in rows}
    assert "メアジ" in items and "メアジ　" not in items
    assert "ナス　ローカル" in items
    assert pick(rows, "カラス貝", "2020-12-22")["name_tl"] == "Tahong"
    assert pick(rows, "キャベツ", "2020-11-20")["name_en"] == "Cabbage"


def test_items_without_prices_produce_no_rows():
    assert not [r for r in read_own(XLSX) if r["item_ja"] == "マンゴー"]


def test_main_writes_sorted_csv(tmp_path):
    out = tmp_path / "own.csv"
    assert main([str(XLSX), "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,sheet,item_ja,name_tl,name_en,price,market"
    assert len(lines) == 128
    assert lines[1].split(",")[1] == "野菜" and lines[-1].split(",")[1] == "魚介"
```

- [x] **Step 2: 落ちることを確かめる** — Run: `pytest tests/test_import_own.py` / Expected: FAIL
- [x] **Step 3: `src/mmp/import_own.py` を実装する**（`openpyxl.load_workbook(path, data_only=True)`）
- [x] **Step 4: 通ることを確かめる** — Run: `pytest tests/test_import_own.py` / Expected: PASS
- [x] **Step 5: `data/own.csv` を作ってコミット**

```bash
python -m mmp.import_own docs/reference/own-cartimar-prices-2020-2024.xlsx --out data/own.csv
git add src/mmp/import_own.py tests/test_import_own.py data/own.csv
git commit -m "Import the author's Cartimar price records from Excel"
```

---

### Task 6: 日次から週次へ集計する

**Files:**
- Create: `src/mmp/aggregate.py`
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: `data/daily.csv`、`data/market_daily.csv`
- Produces:
  - `week_start(date: str) -> str`（その週の月曜日）
  - `representative(row: dict) -> tuple[float, str] | None`（`(値, "prevailing"|"average"|"midpoint")`）
  - `aggregate(daily: list[dict], market_daily: list[dict]) -> list[dict]`
  - 行の形と `data/weekly.csv` の列：`week_start, series, commodity_id, price, low, high, basis, n_days`。並びは `series, commodity_id, week_start`。
  - `main(argv=None) -> int`（`python -m mmp.aggregate --data-dir data`）

**ふるまい:**
- `series="ncr"`：日ごとの代表値（`prevailing → average → (low+high)/2`）の単純平均を `price` にする。`low` は週内の `low` の最小、`high` は週内の `high` の最大（どの日にも無ければ空）。`basis` は週内でいちばん多かったもの（同数なら `prevailing ＞ average ＞ midpoint` の順で採る）。`n_days` は代表値のあった日数。
- `series="cartimar"`：`market_daily` の `price` の単純平均。`low`・`high` は週内の最小・最大。`basis` は `"market"`。
- `price` は小数第2位に丸める。

- [x] **Step 1: 落ちるテストを書く**

```python
import pytest

from mmp.aggregate import aggregate, representative, week_start


@pytest.mark.parametrize("date, monday", [
    ("2020-11-20", "2020-11-16"),   # 金曜
    ("2020-11-16", "2020-11-16"),   # 月曜
    ("2020-11-22", "2020-11-16"),   # 日曜
    ("2020-12-31", "2020-12-28"),   # 年またぎ
    ("2021-01-03", "2020-12-28"),
    ("2024-02-29", "2024-02-26"),   # うるう日
])
def test_week_start(date, monday):
    assert week_start(date) == monday


def d(date, cid="tomato", low="", high="", prevailing="", average=""):
    return {"date": date, "commodity_id": cid, "spec": "", "unit": "kg", "low": low, "high": high,
            "prevailing": prevailing, "average": average, "source_url": "u"}


def test_representative_priority():
    assert representative(d("2026-08-28", low="40", high="160", prevailing="120", average="103.67")) == (120.0, "prevailing")
    assert representative(d("2025-02-01", low="50", high="130", average="93.58")) == (93.58, "average")
    assert representative(d("2023-06-01", low="30", high="80")) == (55.0, "midpoint")
    assert representative(d("2023-06-01", low="30")) is None
    assert representative(d("2023-06-01")) is None


def test_weekly_mean_and_range():
    rows = aggregate([
        d("2020-11-16", low="140", high="200", prevailing="180"),
        d("2020-11-18", low="120", high="190", prevailing="160"),
        d("2020-11-20", low="130", high="210", prevailing="170"),
        d("2020-11-23", low="100", high="150", prevailing="120"),
    ], [])
    assert rows == [
        {"week_start": "2020-11-16", "series": "ncr", "commodity_id": "tomato", "price": 170.0,
         "low": 120.0, "high": 210.0, "basis": "prevailing", "n_days": 3},
        {"week_start": "2020-11-23", "series": "ncr", "commodity_id": "tomato", "price": 120.0,
         "low": 100.0, "high": 150.0, "basis": "prevailing", "n_days": 1},
    ]


def test_basis_is_majority_and_range_may_be_missing():
    rows = aggregate([
        d("2023-06-05", low="30", high="80"),
        d("2023-06-06", low="40", high="80"),
        d("2023-06-07", prevailing="70"),
    ], [])
    assert rows[0]["basis"] == "midpoint" and rows[0]["price"] == 61.67 and rows[0]["n_days"] == 3
    rows = aggregate([d("2022-06-01", prevailing="80"), d("2022-06-02", prevailing="90")], [])
    assert rows[0]["low"] is None and rows[0]["high"] is None and rows[0]["price"] == 85.0


def test_basis_tie_prefers_prevailing():
    rows = aggregate([d("2023-06-05", low="30", high="80"), d("2023-06-06", prevailing="70")], [])
    assert rows[0]["basis"] == "prevailing"


def test_rows_without_any_value_are_ignored():
    assert aggregate([d("2023-06-05")], []) == []


def test_cartimar_series():
    m = lambda date, price, low, high: {"date": date, "market": "Cartimar", "commodity_id": "tilapia",
                                         "low": low, "high": high, "price": price, "source_url": "u"}
    rows = aggregate([], [m("2024-06-03", "155", "150", "160"), m("2024-06-05", "180", "180", "180")])
    assert rows == [{"week_start": "2024-06-03", "series": "cartimar", "commodity_id": "tilapia",
                     "price": 167.5, "low": 150.0, "high": 180.0, "basis": "market", "n_days": 2}]


def test_output_order_is_series_commodity_week():
    rows = aggregate([d("2021-01-04", cid="tomato", prevailing="1"), d("2020-11-16", cid="tomato", prevailing="1"),
                      d("2020-11-16", cid="bangus", prevailing="1")], [])
    assert [(r["commodity_id"], r["week_start"]) for r in rows] == [
        ("bangus", "2020-11-16"), ("tomato", "2020-11-16"), ("tomato", "2021-01-04")]
```

- [x] **Step 2: 落ちることを確かめる** — Run: `pytest tests/test_aggregate.py` / Expected: FAIL
- [x] **Step 3: `src/mmp/aggregate.py` を実装する**（CSVへ書くときは `store.fmt` を使う）
- [x] **Step 4: 通ることを確かめる** — Run: `pytest tests/test_aggregate.py` / Expected: PASS
- [x] **Step 5: コミット**

```bash
git add src/mmp/aggregate.py tests/test_aggregate.py
git commit -m "Aggregate daily prices into weekly series"
```

---

### Task 7: 画面用のJSONを作る

**Files:**
- Create: `src/mmp/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: `data/weekly.csv`、`data/own.csv`、`data/commodities.csv`、`data/sources.csv`
- Produces:
  - `build(weekly: list[dict], own: list[dict], commodities: list[dict], *, updated: str, latest_report: str) -> dict`
  - `main(argv=None) -> int`（`python -m mmp.build_site --data-dir data --out site/data.json`）
  - `site/data.json` の形：

```json
{
  "updated": "2026-10-05",
  "latest_report": "2026-10-02",
  "categories": [
    {"id": "vegetable", "label": "野菜"}, {"id": "spice", "label": "香味野菜"},
    {"id": "fruit", "label": "果物"}, {"id": "fish", "label": "魚介"}
  ],
  "items": [
    {
      "id": "tomato", "category": "vegetable",
      "name_ja": "トマト", "name_tl": "Kamatis", "name_en": "Tomato", "unit": "kg",
      "ncr": [["2020-11-16", 170, 120, 210, "prevailing"]],
      "cartimar": [["2024-06-03", 82.5]],
      "own": [["2021-01-29", 100]]
    }
  ]
}
```

**ふるまい:**
- `items` は `commodities.csv` の `display=1` の品目を `order` 順に並べる。`ncr` も `cartimar` も `own` も空の品目は出さない。
- `ncr` の要素は `[week_start, price, low, high, basis]`。`low`・`high` が無ければ `null`。
- `own` は、`commodities.csv` の `own_items`（`|` 区切り）に載っている和名の実測値を日付順に入れる。
- `commodities.csv` のどの `own_items` にも載っていない和名は、`id` を `own:<和名>` とした独立の品目にして `items` の末尾に足す。`category` は、シートが「魚介」なら `fish`、「野菜」なら `vegetable`。`name_tl`・`name_en` は `own.csv` の値（空でもよい）。`ncr` と `cartimar` は空配列。和名順に並べる。
- `unit` は当面すべて `"kg"`。
- `updated` は実行日（`main` ではフィリピン時間の今日）、`latest_report` は台帳の `parsed` のうち最新の `report_date`。
- JSONは `ensure_ascii=False`、区切りは `(",", ":")`、末尾に改行。

- [x] **Step 1: 落ちるテストを書く**

```python
from mmp.build_site import build

COMMODITIES = [
    {"commodity_id": "tomato", "category": "vegetable", "name_ja": "トマト", "name_tl": "Kamatis",
     "name_en": "Tomato", "aliases": "Tomato", "own_items": "トマトローカル", "display": "1", "order": "30"},
    {"commodity_id": "cabbage", "category": "vegetable", "name_ja": "キャベツ", "name_tl": "Repolyo",
     "name_en": "Cabbage", "aliases": "Cabbage", "own_items": "キャベツ", "display": "1", "order": "100"},
    {"commodity_id": "cabbage_scorpio", "category": "vegetable", "name_ja": "キャベツ（スコーピオ種）",
     "name_tl": "Repolyo", "name_en": "Cabbage (Scorpio)", "aliases": "Scorpio", "own_items": "キャベツ",
     "display": "1", "order": "101"},
    {"commodity_id": "bangus_large", "category": "fish", "name_ja": "バンゴス（大）", "name_tl": "Bangus",
     "name_en": "Milkfish (large)", "aliases": "x", "own_items": "", "display": "0", "order": "501"},
    {"commodity_id": "celery", "category": "vegetable", "name_ja": "セロリ", "name_tl": "",
     "name_en": "Celery", "aliases": "Celery", "own_items": "セロリ", "display": "1", "order": "190"},
    {"commodity_id": "melon", "category": "fruit", "name_ja": "メロン", "name_tl": "Melon",
     "name_en": "Melon", "aliases": "Melon", "own_items": "", "display": "1", "order": "450"},
]


def w(week, cid, price, series="ncr", low="", high="", basis="prevailing"):
    return {"week_start": week, "series": series, "commodity_id": cid, "price": price,
            "low": low, "high": high, "basis": basis, "n_days": "3"}


def o(date, item, price, sheet="野菜", tl="", en=""):
    return {"date": date, "sheet": sheet, "item_ja": item, "name_tl": tl, "name_en": en,
            "price": price, "market": "Cartimar"}


WEEKLY = [
    w("2020-11-16", "tomato", "170", low="120", high="210"),
    w("2022-06-06", "tomato", "80"),
    w("2024-06-03", "tomato", "82.5", series="cartimar", basis="market"),
    w("2020-11-16", "cabbage_scorpio", "100"),
    w("2025-06-02", "bangus_large", "219.44"),
]
OWN = [
    o("2020-11-20", "キャベツ", "100", en="Cabbage", tl="Repolyo"),
    o("2021-01-29", "トマトローカル", "100"),
    o("2024-05-23", "セロリ", "120"),
    o("2021-01-21", "パセリ", "400"),
    o("2020-12-22", "カラス貝", "150", sheet="魚介", tl="Tahong"),
]


def build_default():
    return build(WEEKLY, OWN, COMMODITIES, updated="2026-10-05", latest_report="2026-10-02")


def item(data, item_id):
    return next(i for i in data["items"] if i["id"] == item_id)


def test_header_and_categories():
    data = build_default()
    assert (data["updated"], data["latest_report"]) == ("2026-10-05", "2026-10-02")
    assert [c["id"] for c in data["categories"]] == ["vegetable", "spice", "fruit", "fish"]
    assert data["categories"][1]["label"] == "香味野菜"


def test_item_series_shapes():
    tomato = item(build_default(), "tomato")
    assert tomato["ncr"] == [["2020-11-16", 170, 120, 210, "prevailing"], ["2022-06-06", 80, None, None, "prevailing"]]
    assert tomato["cartimar"] == [["2024-06-03", 82.5]]
    assert tomato["own"] == [["2021-01-29", 100]]
    assert (tomato["name_ja"], tomato["name_tl"], tomato["name_en"], tomato["unit"]) == ("トマト", "Kamatis", "Tomato", "kg")


def test_one_own_item_can_feed_two_commodities():
    data = build_default()
    assert item(data, "cabbage")["own"] == [["2020-11-20", 100]]
    assert item(data, "cabbage_scorpio")["own"] == [["2020-11-20", 100]]


def test_own_only_commodity_is_kept_and_empty_or_hidden_ones_are_dropped():
    ids = [i["id"] for i in build_default()["items"]]
    assert "celery" in ids                 # 公的データは無いが実測値がある
    assert "cabbage" in ids                # 同上
    assert "melon" not in ids              # どの系列も空
    assert "bangus_large" not in ids       # display=0


def test_unmatched_own_items_become_standalone_items_at_the_end():
    data = build_default()
    ids = [i["id"] for i in data["items"]]
    assert ids == ["tomato", "cabbage", "cabbage_scorpio", "celery", "own:カラス貝", "own:パセリ"]
    shell = item(data, "own:カラス貝")
    assert (shell["category"], shell["name_ja"], shell["name_tl"]) == ("fish", "カラス貝", "Tahong")
    assert shell["ncr"] == [] and shell["cartimar"] == [] and shell["own"] == [["2020-12-22", 150]]
    assert item(data, "own:パセリ")["category"] == "vegetable"
```

- [x] **Step 2: 落ちることを確かめる** — Run: `pytest tests/test_build_site.py` / Expected: FAIL
- [x] **Step 3: `src/mmp/build_site.py` を実装する**
- [x] **Step 4: 通ることを確かめる** — Run: `pytest tests/test_build_site.py` / Expected: PASS
- [x] **Step 5: コミット**

```bash
git add src/mmp/build_site.py tests/test_build_site.py
git commit -m "Build site data.json from weekly series and own records"
```

---

### Task 8: グラフ画面

**Files:**
- Create: `site/index.html`、`site/app.js`、`site/style.css`、`site/vendor/chart.umd.min.js`
- Create: `tests/e2e/data.sample.json`
- Test: `tests/e2e/test_site.py`

**Interfaces:**
- Consumes: `site/data.json`（Task 7の形）
- Produces: `site/index.html`。URLの `?item=<id>` で初期表示の品目を指定できる。`?data=<path>` で読むJSONを差し替えられる（テスト用。既定は `data.json`）。

**画面の決まり（設計書6節を具体化したもの）:**

構成（上から）：
1. 分類のタブ（野菜／香味野菜／果物／魚介）。`role="tablist"`。品目が1つも無い分類は出さない。
2. 品目の選択（`<select id="item">`）。表示は「トマト（Kamatis／Tomato）」。タガログ名・英名が空なら、あるほうだけ。両方空なら和名だけ。
3. 期間のボタン（1年／3年／全期間）。初期は全期間。
4. グラフ（`<canvas id="chart">`）。高さは固定（スマホ280px、幅600px以上で340px）。
5. 数値の欄（`<dl id="stats">`）：最新週の価格、前週比、前年同週比。
6. 注記と出典。

系列の見せ方：

| 系列 | 見た目 | 凡例 |
|---|---|---|
| 首都圏の市場平均 | 太さ2の実線、色 `#1B6E8C`。`basis` が `midpoint` の区間は破線 `[6, 4]` | 首都圏の市場平均（農業省調べ） |
| 週内の安値〜高値 | 同じ色の帯、不透明度0.15 | 安値〜高値 |
| カルティマール市場 | 太さ2の点線 `[2, 3]`、色 `#B4531A`、点なし | カルティマール市場（農業省調べ） |
| 著者の実測 | 線なしの点、ひし形（`rectRot`）、大きさ5、色 `#1F2933`、白い縁取り | カルティマールでの実測（著者） |

- 横軸は時間（Chart.jsの `type: "linear"` に、日付を「1970-01-01からの日数」に直して渡す。日付アダプターは入れない）。目盛りは年、または期間が1年のときは月。目盛りの表示は `2021`、`3月` の形。
- 縦軸はペソ。0から始める。目盛りは `₱100` の形。軸の題は「1kgあたり（ペソ）」。
- 週が4週以上あいたところは線をつながない（`spanGaps: false` にし、あいた箇所に `null` を入れる）。
- 触れると、その週の日付（`2026年9月21日の週`）と各系列の値（`₱120`、帯は `₱45〜₱160`）が出る。
- 数値の欄：最新週は `ncr` の最後の点。前週比は1つ前の点が7日前のときだけ、前年同週比は364日前±7日の点があるときだけ出す。無ければ「—」。増減は `+12%`／`−8%` と矢印（▲▼）で示し、色だけに頼らない。`ncr` が空の品目では、最新の実測値と日付を出す。
- 選んだ期間に点が1つも無いときは、グラフの上に「この期間のデータはありません」と出す（`<p id="empty">`）。
- `?item=` のIDが `items` に無いときは、最初の品目を表示する。
- 文字は `system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif`。本文16px、注記13px。背景は白、文字は `#1F2933`。iframeの中で使うので、余白は左右12pxだけ。ページ見出し（h1）は付けない。
- 注記の文面：
  - 「首都圏の公設市場（農業省の調査対象）の平均です。店や日によって値段は違います。」
  - 「破線の期間（2023〜2024年ごろ）は、安値と高値の中間の値です。」（`basis` が `midpoint` の点が表示範囲にあるときだけ出す）
  - 「◆は著者がカルティマール市場で買ったときの値段です。」（`own` があるときだけ）
  - 「出典：フィリピン農業省 DA-AMAS Bantay Presyo ／ 最終更新 2026年10月5日（データは10月2日分まで）」。出典名は `https://www.da.gov.ph/price-monitoring/` へのリンク（`target="_blank" rel="noopener"`）。
- 色の組み合わせは白背景で文字・線ともコントラスト比3:1以上を保つ。上の3色はその条件を満たすものとして選んである。変える場合は条件を確かめること。

- [x] **Step 1: Chart.jsを同梱する**

```bash
mkdir -p site/vendor
curl -L -o site/vendor/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js
head -c 200 site/vendor/chart.umd.min.js   # "Chart.js v4.4.4" と書いてあること
```

- [x] **Step 2: テスト用のデータを書く**

`tests/e2e/data.sample.json`（1行でよい。読みやすさのため整形して示す）：

```json
{
  "updated": "2026-10-05", "latest_report": "2026-10-02",
  "categories": [{"id": "vegetable", "label": "野菜"}, {"id": "spice", "label": "香味野菜"},
                 {"id": "fruit", "label": "果物"}, {"id": "fish", "label": "魚介"}],
  "items": [
    {"id": "tomato", "category": "vegetable", "name_ja": "トマト", "name_tl": "Kamatis", "name_en": "Tomato", "unit": "kg",
     "ncr": [["2020-11-16", 170, 120, 210, "prevailing"], ["2020-11-23", 160, 110, 200, "prevailing"],
             ["2023-06-05", 55, 30, 80, "midpoint"], ["2023-06-12", 60, 35, 85, "midpoint"],
             ["2025-09-22", 100, 40, 150, "prevailing"],
             ["2026-09-21", 110, 45, 160, "prevailing"], ["2026-09-28", 120, 45, 160, "prevailing"]],
     "cartimar": [["2026-09-21", 105], ["2026-09-28", 110]],
     "own": [["2021-01-29", 100]]},
    {"id": "celery", "category": "vegetable", "name_ja": "セロリ", "name_tl": "", "name_en": "Celery", "unit": "kg",
     "ncr": [], "cartimar": [], "own": [["2024-05-23", 120]]},
    {"id": "bangus", "category": "fish", "name_ja": "バンゴス（ミルクフィッシュ）", "name_tl": "Bangus", "name_en": "Milkfish", "unit": "kg",
     "ncr": [["2026-09-28", 240, 190, 300, "prevailing"]], "cartimar": [], "own": []},
    {"id": "own:パセリ", "category": "vegetable", "name_ja": "パセリ", "name_tl": "", "name_en": "", "unit": "kg",
     "ncr": [], "cartimar": [], "own": [["2021-01-21", 400], ["2021-02-18", 300]]}
  ]
}
```

- [x] **Step 3: 落ちるテストを書く**

`tests/e2e/test_site.py`（`pytest tests/e2e` で実行する。`pytest-playwright` の `page` フィクスチャを使う）：

```python
import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def site_url(tmp_path_factory):
    web = tmp_path_factory.mktemp("web")
    shutil.copytree(ROOT / "site", web, dirs_exist_ok=True)
    shutil.copy(Path(__file__).parent / "data.sample.json", web / "sample.json")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def errors(page):
    found = []
    page.on("pageerror", lambda e: found.append(str(e)))
    page.on("console", lambda m: found.append(m.text) if m.type == "error" else None)
    return found


def open_page(page, site_url, query=""):
    page.set_viewport_size({"width": 360, "height": 740})
    page.goto(f"{site_url}/index.html?data=sample.json{query}")
    page.wait_for_selector("#chart[data-ready='1']")


def test_default_view_shows_first_item_without_horizontal_scroll(page, site_url, errors):
    open_page(page, site_url)
    assert page.locator("#item").input_value() == "tomato"
    assert page.locator("#item option:checked").inner_text() == "トマト（Kamatis／Tomato）"
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert "₱120" in page.locator("#stats").inner_text()
    assert "+9%" in page.locator("#stats").inner_text()      # 前週 110 → 120
    assert "+20%" in page.locator("#stats").inner_text()     # 前年同週 100 → 120
    assert page.locator("#empty").is_hidden()
    assert errors == []


def test_legend_and_notes_match_the_series_present(page, site_url, errors):
    open_page(page, site_url)
    text = page.locator("body").inner_text()
    for label in ("首都圏の市場平均（農業省調べ）", "カルティマール市場（農業省調べ）", "カルティマールでの実測（著者）"):
        assert label in text
    assert "中間の値" in text and "最終更新 2026年10月5日" in text
    assert page.locator("a[href='https://www.da.gov.ph/price-monitoring/']").count() == 1
    assert errors == []


def test_item_query_selects_item_and_category(page, site_url, errors):
    open_page(page, site_url, "&item=bangus")
    assert page.locator("#item").input_value() == "bangus"
    assert page.locator("[role=tab][aria-selected=true]").inner_text() == "魚介"
    assert "—" in page.locator("#stats").inner_text()        # 1点しか無いので前週比は出ない
    assert errors == []


def test_unknown_item_falls_back_to_first(page, site_url, errors):
    open_page(page, site_url, "&item=nope")
    assert page.locator("#item").input_value() == "tomato"
    assert errors == []


def test_own_only_items_render_points_and_latest_record(page, site_url, errors):
    open_page(page, site_url, "&item=celery")
    assert page.locator("#item option:checked").inner_text() == "セロリ（Celery）"
    stats = page.locator("#stats").inner_text()
    assert "₱120" in stats and "2024年5月23日" in stats
    assert "中間の値" not in page.locator("body").inner_text()
    page.select_option("#item", "own:パセリ")
    page.wait_for_selector("#chart[data-ready='1']")
    assert page.locator("#item option:checked").inner_text() == "パセリ"
    assert errors == []


def test_period_without_data_shows_empty_message(page, site_url, errors):
    open_page(page, site_url, "&item=celery")
    page.get_by_role("button", name="1年").click()
    assert page.locator("#empty").is_visible()
    assert page.locator("#empty").inner_text() == "この期間のデータはありません"
    page.get_by_role("button", name="全期間").click()
    assert page.locator("#empty").is_hidden()
    assert errors == []


def test_empty_categories_are_not_shown_and_height_is_stable(page, site_url, errors):
    open_page(page, site_url)
    tabs = page.locator("[role=tab]").all_inner_texts()
    assert tabs == ["野菜", "魚介"]
    before = page.evaluate("document.documentElement.scrollHeight")
    page.select_option("#item", "celery")
    page.wait_for_selector("#chart[data-ready='1']")
    after = page.evaluate("document.documentElement.scrollHeight")
    assert abs(before - after) <= 2
    assert errors == []
```

テストは、グラフを描き終えるたびに `#chart` に `data-ready="1"` が付くことを前提にしている（描き直しの前に外し、終わったら付ける）。高さが変わらないようにするため、注記の欄と数値の欄は、出す行が少ないときも同じ高さを確保する（`min-height`）。

- [x] **Step 4: 落ちることを確かめる**

```bash
playwright install chromium
pytest tests/e2e
```

Expected: FAIL（`site/index.html` が無い）

- [x] **Step 5: `site/index.html`、`site/app.js`、`site/style.css` を実装する**

フレームワークは使わない。`app.js` は1ファイル、300行前後を目安にする。「データの読み込みと選択状態」「系列の組み立て（期間の絞り込み、欠けた週への `null` の挿入）」「数値の欄」「描画」を関数に分ける。

- [x] **Step 6: 通ることを確かめる**

Run: `pytest tests/e2e`
Expected: PASS（7件）

- [x] **Step 7: 目で確かめる**

```bash
cp tests/e2e/data.sample.json site/data.json
python -m http.server -d site 8000
```

ブラウザの幅を360pxにして `http://localhost:8000/` を開き、次を確かめる：破線と実線の切り替わり、帯、ひし形の点、凡例、触れたときの表示、期間ボタン。確かめたら `site/data.json` は消す（Task 10で本物を作る）。

- [x] **Step 8: コミット**

```bash
git add site/index.html site/app.js site/style.css site/vendor tests/e2e
git commit -m "Add the price chart page"
```

---

### Task 9: 異常検知と自動実行

**Files:**
- Create: `src/mmp/check_health.py`
- Create: `.github/workflows/weekly.yml`、`.github/workflows/backfill.yml`
- Test: `tests/test_check_health.py`

**Interfaces:**
- Consumes: `Ledger`
- Produces:
  - `check(entries: list[dict], today: datetime.date, *, since: str | None = None) -> list[str]`（問題の文を返す。空なら正常）
  - `main(argv=None) -> int`（`python -m mmp.check_health --data-dir data [--since <ISO時刻>]`。問題があれば各行を表示して1を返す）

**ふるまい:**
- 問題1：`status == "parsed"` のうち最新の `report_date` が、`today` の14日前より古い → `"no parsed report in the last 14 days (latest: YYYY-MM-DD)"`。`parsed` が1件も無いときも同じ扱い（`latest: none`）。
- 問題2：`since` が渡されたとき、`fetched_at >= since` かつ `status` が `parsed` か `failed` の行のうち、`failed` が半分以上（行が2件以上あるときだけ判定）→ `"N of M newly fetched reports failed to parse"`。

- [x] **Step 1: 落ちるテストを書く**

```python
import datetime as dt

from mmp.check_health import check

TODAY = dt.date(2026, 10, 5)


def e(date, status="parsed", fetched="2026-10-05T00:10:00Z"):
    return {"url": f"https://x/{date}-{status}.pdf", "kind": "price_monitoring", "revised": "0",
            "report_date": date, "status": status, "layout": "", "rows": "0", "sha256": "",
            "fetched_at": fetched, "error": ""}


def test_half_of_new_reports_failing_is_unhealthy():
    assert check([e("2026-10-02"), e("2026-10-01", "failed")], TODAY, since="2026-10-05T00:00:00Z") == [
        "1 of 2 newly fetched reports failed to parse"]


def test_stale_when_latest_parsed_is_older_than_14_days():
    assert check([e("2026-09-20"), e("2026-10-02", "failed")], TODAY) == [
        "no parsed report in the last 14 days (latest: 2026-09-20)"]
    assert check([e("2026-09-21")], TODAY) == []


def test_stale_when_nothing_parsed():
    assert check([e("2026-10-02", "skipped")], TODAY) == ["no parsed report in the last 14 days (latest: none)"]


def test_half_or_more_new_failures():
    entries = [e("2026-10-02"), e("2026-10-01", "failed"), e("2026-09-30", "failed"),
               e("2026-09-01", "failed", fetched="2026-09-07T00:00:00Z")]
    assert check(entries, TODAY, since="2026-10-05T00:00:00Z") == ["2 of 3 newly fetched reports failed to parse"]


def test_single_new_failure_is_not_enough():
    assert check([e("2026-10-02", fetched="2026-09-28T00:00:00Z"), e("2026-10-03", "failed")],
                 TODAY, since="2026-10-05T00:00:00Z") == []
```

- [x] **Step 2: 落ちることを確かめる** — Run: `pytest tests/test_check_health.py` / Expected: FAIL
- [x] **Step 3: `src/mmp/check_health.py` を実装する**
- [x] **Step 4: 通ることを確かめる** — Run: `pytest` / Expected: PASS（全件）

- [x] **Step 5: `.github/workflows/weekly.yml` を書く**

```yaml
name: weekly
on:
  schedule:
    - cron: "17 23 * * 0"   # 日曜 23:17 UTC ＝ 月曜 07:17 フィリピン時間
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: data
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest
      - id: start
        run: echo "since=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GITHUB_OUTPUT"
      - run: python -m mmp.collect --data-dir data
      - run: python -m mmp.aggregate --data-dir data
      - run: python -m mmp.build_site --data-dir data --out site/data.json
      - name: Commit data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data site/data.json
          git diff --cached --quiet || git commit -m "Update prices ($(date -u +%Y-%m-%d))"
          git push
      - run: python -m mmp.check_health --data-dir data --since "${{ steps.start.outputs.since }}"
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deploy
        uses: actions/deploy-pages@v4
```

`check_health` はコミットの後、デプロイの前に置く。異常のときは、取れたデータは残しつつ、公開中のページは前のまま、実行は失敗になる（GitHubから著者にメールが届く）。

- [x] **Step 6: `.github/workflows/backfill.yml` を書く**

```yaml
name: backfill
on:
  workflow_dispatch:
    inputs:
      max_new:
        description: "今回取り込むPDFの上限"
        default: "400"
      retry_failed:
        description: "失敗分をやり直す (true/false)"
        default: "false"

permissions:
  contents: write

concurrency:
  group: data
  cancel-in-progress: false

jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - run: >
          python -m mmp.collect --data-dir data --max-new "${{ inputs.max_new }}"
          ${{ inputs.retry_failed == 'true' && '--retry-failed' || '' }}
      - run: python -m mmp.aggregate --data-dir data
      - name: Commit data
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data
          git diff --cached --quiet || git commit -m "Backfill prices"
          git push
```

- [x] **Step 7: コミット**

```bash
git add src/mmp/check_health.py tests/test_check_health.py .github/workflows
git commit -m "Add health check and scheduled workflows"
```

---

### Task 10: 初回取り込みと点検

ここはコードを書くタスクではなく、実物のデータを入れて確かめるタスク。**結果を著者に報告し、判断を仰ぐ点がある。**

**Files:**
- Create: `data/sources.csv`、`data/daily.csv`、`data/market_daily.csv`、`data/weekly.csv`、`data/unmapped.csv`、`data/rejected.csv`、`site/data.json`
- Create: `docs/backfill-report.md`
- Modify: `data/commodities.csv`（別名の追加）

- [ ] **Step 1: 手元で取り込む**

対象は約1,640本（Price Monitoring）。1本3秒で、読み取りを含めて2時間ほど。途中で止めても続きから進む。

```bash
python -m mmp.collect --data-dir data --cache-dir .cache/pdf --max-new 400
```

これを、`new=0` になるまで繰り返す。GitHub Actionsから動かす場合は `backfill` を手動実行する（設計書11節の5：DAが海外からのアクセスを拒むなら、手元で行う）。

- [ ] **Step 2: 点検の報告を書く**

`docs/backfill-report.md` に、次を表でまとめる（数は `data/sources.csv` などから集計する）。

1. 年月ごとの `parsed` / `failed` / `superseded` の本数と、`layout` の内訳。
2. `failed` の一覧（日付、URL、`error`）。画像だけのPDFが続く期間があれば、その範囲。
3. `error` に `date_mismatch` がある行の一覧。
4. `data/unmapped.csv` の上位50件。野菜・果物・魚介に当たるもの（米・肉・卵・砂糖・油・とうもろこし以外）に印を付ける。
5. `data/rejected.csv` の全件。
6. 品目ごとに、週次データのある最初の週・最後の週・週の数・4週以上あいている区間。
7. 見本の日付での突き合わせ：2020-11-20のトマトの実勢が180、キャベツ（スコーピオ種）が100、2026-08-28のカルティマールのバンゴスが250であること。

- [ ] **Step 3: 対応表を直してやり直す**

4で印を付けた名前を `data/commodities.csv` の `aliases` に足す（新しい品目なら行を足す。和名は著者に確認する印として、報告書に一覧を書く）。そのうえで、対応が取れなかった日を入れ直す。

未対応の名前は、最初の取り込みのときに捨てられている。入れ直すには、その名前が出ていた期間のPDFをもう一度解析する必要がある。`collect` に次のオプションを足す。

- `--reparse-from YYYY-MM-DD --reparse-to YYYY-MM-DD`：台帳の `parsed` のうち、報告日がこの範囲のものを、キャッシュ（`--cache-dir`。無ければ取得）から解析し直して入れ替える。

テストを `tests/test_collect.py` に足す：

```python
def test_reparse_picks_up_new_aliases_without_refetching(world, tmp_path):
    url = world.add("Price-Monitoring-June-1-2026", rows=[nrow("Tomato", prevailing=60.0), nrow("Dragon Fruit", prevailing=200.0)])
    cache = tmp_path / "cache"
    world.run(cache_dir=cache)
    assert [r["commodity_id"] for r in world.daily()] == ["tomato"]
    csv_path = world.data_dir / "commodities.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8")
                        + "dragon_fruit,fruit,ドラゴンフルーツ,,Dragon fruit,Dragon Fruit,,1,480\n", encoding="utf-8")
    world.fetched.clear()
    world.run(cache_dir=cache, reparse_from="2026-06-01", reparse_to="2026-06-01")
    assert url not in world.fetched
    assert [r["commodity_id"] for r in world.daily()] == ["dragon_fruit", "tomato"]
```

通ったら、該当期間を入れ直す。

- [ ] **Step 4: 著者に報告して止まる**

次の点は著者の判断がいる。報告書の冒頭に、質問として書く。

- 読めない期間（`failed` が続く区間、4週以上の空白）をどうするか。設計書の方針は「無理に埋めず、線を切る」。
- 2021年11月〜2022年1月ごろは、首都圏まとめのページが画像で、市場別の表の平均で代用している（品目は7つほど）。この扱いでよいか。
- 新しく足した品目の和名。
- `rejected.csv` に本物の値動き（2022〜23年のタマネギの高騰など）が入っていないか。入っていたら、5倍の基準を見直す。

- [ ] **Step 5: 集計して画面用データを作り、コミット**

```bash
python -m mmp.aggregate --data-dir data
python -m mmp.build_site --data-dir data --out site/data.json
pytest && pytest tests/e2e
git add data site/data.json docs/backfill-report.md src tests
git commit -m "Backfill prices from November 2020 and add the audit report"
```

- [ ] **Step 6: 実物のデータで画面を見る**

`python -m http.server -d site 8000` で開き、トマト、キャベツ（スコーピオ種）、赤タマネギ（国産）、バンゴス、パセリ（実測のみ）を、幅360pxと1024pxで見る。おかしな段差や飛び値があれば報告書に書く。

---

### Task 11: 公開と引き渡し

**Files:**
- Create: `README.md`

- [ ] **Step 1: GitHub Pagesを有効にする**（著者の作業、またはCodexが `gh` で行う）

リポジトリの Settings → Pages → Build and deployment → Source を「GitHub Actions」にする。`weekly` を手動実行し、表示されたURL（`https://<owner>.github.io/manila-market-prices/`）を開いて確かめる。

- [ ] **Step 2: `README.md` を書く**（日本語）

次の内容を入れる。

- これは何か（2〜3文）と、公開ページのURL。
- 仕組みの図（設計書4節の図）。
- 毎週の動き：いつ動くか、失敗したらメールが来ること、そのとき見る場所（Actionsの記録、`data/sources.csv` の `failed`）。
- よくある手入れ：
  - 新しい品目名が出た → `data/unmapped.csv` を見て `data/commodities.csv` の `aliases` に足し、`collect --reparse-from … --reparse-to …` で入れ直す。
  - DAがPDFの体裁を変えた → `tools/dump_fixture.py` で見本を作り、`tests/test_parsers.py` に期待値を足してから `src/mmp/parsers/` を直し、`collect --retry-failed`。
  - 実測値を足したい → Excelに列を足し、`python -m mmp.import_own …` を実行。
- WordPressに貼るコード：

```html
<iframe src="https://<owner>.github.io/manila-market-prices/" title="マニラの野菜・魚介の価格推移"
        style="width:100%;height:760px;border:0" loading="lazy"></iframe>
```

  `height` は、幅360pxで開いたときの実際のページの高さ（`document.documentElement.scrollHeight`）に20px足した値に直す。

- 出典と注意：データは農業省 DA-AMAS Bantay Presyo の公表値。首都圏の調査市場の平均で、個々の店の値段ではない。

- [ ] **Step 3: コミットしてpush**

```bash
git add README.md && git commit -m "Add README with operations notes and embed snippet" && git push
```

- [ ] **Step 4: 著者に引き渡す**

著者に、次の作業が残っていることを伝える。

1. `data/commodities.csv` の和名の確認。
2. WordPressの該当ページで、Googleスプレッドシートのiframe 2つを上のiframe 1つに差し替える。
3. ページの説明文を「カルティマール市場での仕入れ時の価格」から「農業省調べの首都圏平均と、著者の実測」に直す。
4. GitHubの通知メールが届く設定になっているかの確認（Settings → Notifications → Actions）。
