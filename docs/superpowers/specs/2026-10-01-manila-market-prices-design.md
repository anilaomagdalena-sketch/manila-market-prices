# マニラの野菜・魚介価格 自動更新ページ 設計書

- 作成日：2026-10-01
- 設計：Claude Code ／ 実装：Codex
- 状態：著者承認済み（2026-10-01）。12節は承認後の調査による更新

## 1. 目的

電子書籍『フィリピンの野菜 市場で迷わない80種の野菜ナビとレシピ40種』（モータクモー著、2020-11-29刊）の付録ページ「おまけ：マニラの野菜魚介価格」を、手入力なしで更新され続けるページに作り直す。

- 読者：マニラ首都圏に住む日本人。電子書籍の中のリンクからスマホで開く。
- 読者が知りたいこと：この野菜（魚）はいま1kgいくらくらいか。季節でどう動くか。スーパーの値段と比べて高いか安いか。
- 現状：著者がカルティマール市場で控えた値段をExcelに入れ、Googleスプレッドシートの公開グラフをWordPressにiframeで埋め込んでいた。2021年5月以降ほぼ更新が止まり、ページの最終更新は2024-08-10。

### 成功の条件

1. 2020年11月から現在まで、品目ごとの週次の価格推移がグラフで見られる。
2. 毎週、人の手を介さずに新しい週が追加される。
3. 一度取得したPDFは二度と取りに行かない。
4. 既存のURL（下記）は変えない。
5. 著者の実測値（Excel）がグラフ上に残る。

既存ページ：`https://divemagdalena.com/sea-creatuer-reference/マニラの野菜魚介価格/`

## 2. 範囲

### やること

- 農業省（DA）Bantay Presyo の日次PDFから、首都圏（NCR）の野菜・香味野菜・果物・魚介の小売価格を集める。
- 同じPDFに載っているカルティマール市場単独の価格も集める（載っている年代・品目のみ）。
- 著者のExcelを1回だけ取り込む。
- 週次に集計し、静的なグラフページとしてGitHub Pagesで公開する。
- GitHub Actionsで毎週自動実行する。

### やらないこと

- 首都圏以外の地域。
- 統計庁（PSA）OpenSTATの月次データ。
- 米・肉・卵・砂糖・油など、野菜・果物・魚介以外の品目の表示（CSVには残してよいが画面には出さない）。
- 英語版ページ。
- WordPressへの自動書き込み。WordPress側はiframeを1回手で差し替えるだけ。
- DA公式の週平均PDF（Weekly-Average-Prices）の取り込み。理由は5.3節。

## 3. データ源（2026-10-01に実物で確認した事実）

一覧ページ：`https://www.da.gov.ph/price-monitoring/`

- 1ページのHTMLにPDFへのリンクが3,313本ある（2018年〜）。ページ送りは無い。
- ブラウザ風のUser-Agentを付けた `curl` で取得できた（HTTP 200）。
- PDFのURLは `https://www.da.gov.ph/wp-content/uploads/YYYY/MM/<種類>-<月名>-<日>-<年>.pdf` の形。**`uploads/YYYY/MM` はアップロード月であり、報告日ではない**（例：`uploads/2025/01/Price-Monitoring-December-24-2024.pdf`）。報告日はファイル名とPDF本文から決める。
- ファイル名には表記ゆれがある（`Weeky-`、`Updated-`、`Revised-`、`http://` と `https://` の混在など）。

### 3.1 PDFの種類と本数（リンクの集計）

| 種類 | 年 | 本数 | 扱い |
|---|---|---|---|
| Price-Watch | 2018–2019 | 197 | 対象外（開始日より前） |
| Price-Monitoring | 2019 | 56 | 対象外 |
| Price-Monitoring | 2020–2026 | 年209〜305 | **主データ** |
| Revised-Price-Monitoring | 2023–2025 | 22 | 同じ日の通常版を上書き |
| Daily-Price-Index（Revised含む） | 2025–2026 | 約570 | **予備**（その日にPrice-Monitoringが無いときだけ使う） |
| Weekly-Average-Prices | 2023-11〜 | 約156 | 対象外 |
| Daily-Cigarette-Price-Monitoring | 2025–2026 | 474 | 対象外 |

### 3.2 Price-Monitoring の体裁の変遷（各年1本の抜き取り確認）

どの年代も `pdftotext -layout` で文字が取れる（画像PDFではない）。ただし体裁は大きく変わる。

| 見本の日付 | 見出し | 値の形 | 市場別の表 |
|---|---|---|---|
| 2020-11-20, 2021-06-01 | Retail Prices of Selected Agri-fishery Commodities in Selected Markets in Metro Manila | 1ページ目が素直な表：`COMMODITY / SPECIFICATION / Unit / High / Low / Prevailing`。2ページ目は同じ内容の図版 | なし |
| 2022-06-01 | Prevailing Retail Prices of Selected Agri-fishery Commodities at NCR Markets | 図版レイアウト（多段組）。Today / Yesterday の実勢価格 | あり（カルティマール無し） |
| 2023-06-01 | Retail Price Range of Selected Agri-fishery Commodities at NCR Markets | 図版レイアウト。`150.00 - 240.00` の値幅のみ | あり（カルティマール無し） |
| 2024-06-01, 2024-12-24 | 同上 | 図版レイアウト。値幅のみ | **あり（カルティマールの行あり）** |
| 2026-08-28 | Prevailing Retail Price Range of Selected Agri-fishery Commodities per Market ほか | `安値 - 高値 実勢 平均` の4値 | あり（カルティマールの行あり） |

- 年代の境目の正確な日付は未確認。**パーサーは日付ではなく本文の見出し・列構成で体裁を判定する。**
- 図版レイアウトの年代は、品目名と値が同じ行に並ばないことがある。`pdftotext -layout` の行分割で足りなければ、単語の座標（`pdfplumber` の `extract_words`、または `pdftotext -bbox-layout`）で品目名と値を結びつける。
- 欠測の表記：`NOT AVAILABLE`、`n/a`、`-`、`NONE`。
- 調査市場は2020年に10か所、2026年に36か所。カルティマールが調査対象に入った時期は2023-06〜2024-06の間。

### 3.3 市場別の表でカルティマールの値が取れる品目（2026-08-28の見本）

バンゴス、ティラピア、ガルンゴン（国産）、アンパラヤ、ナス、トマト、キャベツ、ニンジン（国産）、ハヤトウリ、ペチャイバギオ、ジャガイモ（国産）、赤タマネギ（国産）、白タマネギ。ほかに米・卵・豚肉など（表示対象外）。

### 3.4 Daily-Price-Index（予備）

素直な表：`COMMODITY / SPECIFICATION / PREVAILING RETAIL PRICE PER UNIT`。値は実勢価格1つだけ。7〜8ページ。

### 3.5 著者の実測値

`docs/reference/own-cartimar-prices-2020-2024.xlsx`

- シート「野菜」：1行目が見出し（英名、現地名、和名、以降は日付）。44品目、日付18列（2020-11-20〜2024-05-23）。値のあるセルは約130。
- シート「魚介」：5品目、日付2列（2020-12-22、2021-01-14）。
- 日付セルはExcelのシリアル値、datetime、文字列（`　5/23/2024` のように全角空白つき）が混在する。
- 単位の列は無い。原則1kgあたりのペソとして扱う。
- 英名・現地名は5品目だけ入力済み。和名を正とする。

## 4. 全体構成

公開GitHubリポジトリ `manila-market-prices` 1つ。3つの部品がCSVファイルだけを介してつながる。

```
DA一覧ページ ─▶ collect ─▶ data/sources.csv（台帳）
                    │        data/daily.csv
                    │        data/market_daily.csv
Excel ─▶ import_own ─▶ data/own.csv        （初回のみ）
                    ▼
                 aggregate ─▶ data/weekly.csv
                    ▼
                 build_site ─▶ site/data.json ─▶ GitHub Pages ─▶ WordPressのiframe
```

| 部品 | 役割 | 入力 | 出力 |
|---|---|---|---|
| `collect` | 一覧を読み、未取得のPDFだけ取得・解析 | DAのHTMLとPDF、`sources.csv` | `sources.csv`、`daily.csv`、`market_daily.csv` |
| `parsers/*` | PDF 1本 → 行のリスト。体裁ごとに1モジュール | PDFのバイト列 | 行のリスト |
| `import_own` | Excel → CSV | xlsx | `own.csv` |
| `aggregate` | 日次 → 週次 | `daily.csv`、`market_daily.csv` | `weekly.csv` |
| `build_site` | CSV → 画面用JSON | `weekly.csv`、`own.csv`、`commodities.csv` | `site/data.json` |
| `site/` | グラフ画面（静的HTML+JS） | `data.json` | — |

言語はPython 3.12。PDFからの文字抽出は `pdfplumber` を基本とし、必要なら `poppler-utils` を併用する。グラフは Chart.js（CDNに頼らずリポジトリに同梱）。

## 5. データの形

すべてUTF-8のCSV、ヘッダーあり、日付はISO形式（`YYYY-MM-DD`）。行は決まった順に並べ替えて書き出す（差分を読みやすくするため）。

### 5.1 `data/sources.csv`（取得済み台帳）

| 列 | 内容 |
|---|---|
| `url` | PDFのURL（主キー。`http://` は `https://` に正規化） |
| `kind` | `price_monitoring` / `daily_price_index` / `skip` |
| `revised` | 0 / 1 |
| `report_date` | 報告日 |
| `status` | `parsed` / `failed` / `skipped` / `superseded` |
| `layout` | 判定した体裁の名前（`pm_table_2020` など） |
| `rows` | 取り出せた行数 |
| `sha256` | PDFのハッシュ |
| `fetched_at` | 取得時刻（UTC） |
| `error` | 失敗時の一行メッセージ |

規則：

- 台帳に `url` がある行は、`status` が何であれ**再取得しない**。
- `failed` をやり直したいときだけ、`collect --retry-failed` を明示して実行する（パーサーを直したあとに使う）。
- PDF本体はリポジトリに置かない。初回取り込み中は作業用のキャッシュフォルダ（`.cache/pdf/`、gitignore）に残し、パーサーを直しての再解析に使う。
- 報告日が開始日（`2020-11-01`）より前のもの、対象外の種類のものは `skipped` として台帳に載せる（次回また候補に上がらないようにするため）。

### 5.2 `data/daily.csv`（首都圏の日次）と `data/market_daily.csv`（市場別の日次）

`daily.csv`：

| 列 | 内容 |
|---|---|
| `date` | 報告日 |
| `commodity_id` | `commodities.csv` のID |
| `spec` | 規格の原文 |
| `unit` | `kg` / `pc` など |
| `low`, `high`, `prevailing`, `average` | PDFにある値だけ入れる。無ければ空 |
| `source_url` | 出典PDF |

`market_daily.csv`：`date, market, commodity_id, price, source_url`。`market` は当面 `Cartimar` のみ保存する。

規則：

- 主キーは `(date, commodity_id)`（market_daily は `(date, market, commodity_id)`）。
- 同じ日にRevised版があればRevised版の値で置き換え、通常版の台帳行は `superseded` にする。
- 同じ日にPrice-MonitoringとDaily-Price-Indexの両方があれば、Price-Monitoringだけ使う。
- `commodities.csv` に対応の無い品目名が出たら、その行は捨てずに `data/unmapped.csv`（`date, raw_name, spec, source_url`）へ書く。対応表の拡充に使う。

### 5.3 `data/weekly.csv`

| 列 | 内容 |
|---|---|
| `week_start` | その週の月曜日 |
| `series` | `ncr` / `cartimar` |
| `commodity_id` | |
| `price` | 週の代表値（下記） |
| `low`, `high` | 週内の最安・最高（`ncr` のみ。無ければ空） |
| `basis` | `prevailing` / `average` / `midpoint` |
| `n_days` | 集計に使った日数 |

日ごとの代表値の決め方（優先順）：`prevailing` → `average` → `(low + high) / 2`。週の `price` は日ごとの代表値の単純平均。`basis` は週内でいちばん多かったもの。

値幅しか無い年代（2023〜2024年ごろ）は中間値になり、前後の年代と性質が違う。**ごまかさず、`basis` を画面まで運び、該当期間は線を破線にして注記を出す。**

DA公式の週平均PDFを使わない理由：2023年11月以前には無く、途中で定義が切り替わるとグラフに段差ができる。全期間を「日次の代表値の平均」で統一する。

### 5.4 `data/own.csv`

`date, item_ja, commodity_id, price, unit, market, note`。`market` は `Cartimar`。`commodity_id` は対応があれば入れ、無ければ空（`item_ja` 単独の系列として表示する）。

### 5.5 `data/commodities.csv`（手で管理する対応表）

| 列 | 内容 |
|---|---|
| `commodity_id` | 例：`cabbage_scorpio`、`tomato`、`bangus` |
| `category` | `vegetable` / `spice` / `fruit` / `fish` / `other` |
| `name_ja`, `name_tl`, `name_en` | 表示名 |
| `aliases` | DAのPDFに出てくる表記を `|` 区切りで全部（年代で変わる。例：`Cabbage (Scorpio)|Cabbage Repolyo (Scorpio)`） |
| `own_items` | 対応するExcelの和名を `|` 区切り |
| `display` | 1 / 0（画面に出すか） |
| `order` | 並び順 |

方針：

- 産地・品種の違うものは別品目にする（キャベツ3品種、国産と輸入のタマネギ・ニンニクなど）。勝手に平均しない。
- 途中で品種の区別が増えた品目（2020年の `Cabbage (Scorpio)` のみ → のちに3品種）は、同じ表記どうしだけをつなぐ。
- 照合は、前後の空白・連続空白・大文字小文字・`ᵃ` や `*` などの注記記号を取り除いてから行う。
- 和名は著者のExcelと書籍の表記に合わせる。初版は実装者が埋め、著者が確認する。

## 6. 画面

1ページの静的サイト。iframeの中で使われる前提で、ヘッダーやフッターの装飾は付けない。

- 上部：分類タブ（野菜／香味野菜／果物／魚介）と品目の選択。品目名は「和名（タガログ名／英名）」。
- グラフ：横軸は週、縦軸はペソ（1kgあたり。単位が違う品目は単位を明示）。
  - 実線：首都圏の市場平均（`series=ncr`）。`basis=midpoint` の期間は破線。
  - 帯：週内の安値〜高値。
  - 2本目の線：カルティマール市場（DA調べ、`series=cartimar`）。ある品目・期間だけ。
  - 点：著者の実測値（`own.csv`）。
- 期間の切り替え：1年／3年／全期間。初期表示は全期間。
- グラフの下：最新週の価格、前週比、前年同週比。
- DAにデータが無くExcelにだけある品目（パセリ、シイタケ、アオリイカなど）は、点だけのグラフとして選べる。
- 末尾：出典「フィリピン農業省 DA-AMAS Bantay Presyo」へのリンク、最終更新日、「首都圏の調査市場の平均であり、店や日によって違う」「2023〜2024年ごろは値幅の中間値」の注記。
- スマホ縦画面（幅360px）で、横スクロールなしに読めること。
- iframeの高さは固定値で足りる作りにする（品目を変えても高さが変わらない）。
- 配色・タイポグラフィは実装時に `dataviz` の指針に沿って決める。色だけに頼らず、線種と凡例で系列を区別する。

URLの `?item=<commodity_id>` で初期表示の品目を指定できる（将来、書籍の各野菜ページから直接飛ばせるようにするため）。

## 7. 自動実行

GitHub Actions のワークフロー2本。

- `weekly.yml`：毎週月曜 07:17（フィリピン時間）と手動実行。`collect` → `aggregate` → `build_site` → テスト → `data/` の変更をコミット → Pagesへデプロイ。
- `backfill.yml`：手動実行のみ。`collect --max-new 400` のように上限つきで動かし、初回の約1,900本を数回に分けて取り込む。上限に達したら正常終了し、続きは次回の実行で拾う。

取得の作法：

- PDF 1本ごとに3秒あける。同時接続は1本。
- User-Agentにリポジトリ名と連絡先URLを入れる。
- HTTPエラーは3回まで再試行し、それでもだめなら台帳に載せずに次へ進む（次回また試す）。取得できたが解析できなかったものだけ `failed` にする。

## 8. 壊れたときの備え

- PDF 1本の解析失敗では全体を止めない。`failed` として記録して続ける。
- 次のどれかに当たったらワークフローを失敗させる（GitHubから著者にメールが届く）。
  - 一覧ページが取得できない、またはPDFリンクが極端に少ない（1,000本未満）。
  - 直近14日の報告日のPDFが1本も `parsed` になっていない。
  - 今回新しく取得したPDFの半分以上が `failed`。
- 失敗しても、すでにあるデータでの再デプロイは行わない（公開中のページはそのまま残る）。
- 値の検査：価格が0以下、または同じ品目の前回値の5倍超・5分の1未満の行は取り込まずに `data/rejected.csv` へ書く。

## 9. テスト

- **パーサー**：体裁ごとに実物のPDFを `tests/fixtures/` に1〜2本ずつ置き、期待する行（品目・値）を突き合わせる。本設計書の3.2節の見本日を最低限含める。確認済みの期待値の例：
  - 2020-11-20：`Cabbage (Scorpio)` 高値150 / 安値90 / 実勢100、`Tomato` 高値200 / 安値140 / 実勢180、`White Onion` は欠測。
  - 2021-06-01：`Tomato` 高値50 / 安値24 / 実勢40、`Bangus` 高値220 / 安値130 / 実勢150。
  - 2026-08-28：カルティマールの `Bangus` 250、`Tilapia` 180、`Galunggong (Local)` 380、`Ampalaya` 200。
- **差分取得**：台帳に載っているURLは取得関数が呼ばれないこと。Revised版が通常版を置き換えること。
- **集計**：代表値の優先順、週の区切り（月曜始まり）、`basis` の決め方。
- **Excel取り込み**：3種類の日付表記がすべて正しい日付になること。値のあるセル数が元と一致すること。
- **照合の突き合わせ**：2020-11-20の実測キャベツ100ペソと、同日のDA実勢100ペソが同じグラフに載ること（取り込みの通し確認）。
- **画面**：`data.json` を読み込んで主要品目のグラフが描けること、幅360pxで横スクロールが出ないことをPlaywrightで確認する。

ネットワークに出るテストは作らない。DAへの実アクセスは `collect` の実行時だけ。

## 10. 公開までの手順（人の作業）

1. 著者がGitHubに公開リポジトリを作る（またはCodexに作らせる）。
2. Codexが実装し、`backfill` を数回実行して全期間を取り込む。
3. GitHub Pagesを有効にする。
4. 著者が `commodities.csv` の和名を確認する。
5. 著者がWordPressの該当ページを編集し、Googleスプレッドシートのiframe 2つを、新しいページのiframe 1つに差し替える。説明文も「カルティマール市場での仕入れ時の価格」から「農業省調べの首都圏平均＋著者の実測」に直す。

## 11. 残っている不確かさ

実装の最初に確かめること。

1. **体裁の境目と種類の数**。3.2節は各年1本の抜き取りにすぎない。最初の作業として、2020-11以降の各月から1本ずつ取得して体裁を分類し、パーサーが何種類要るかを確定する。
2. **図版レイアウト（2022〜2024年）の解析の難しさ**。座標を使っても安定して取れない体裁があれば、その期間は市場別の表だけ使う、または欠測として線を切る。無理に埋めない。判断は著者に確認する。
3. **カルティマールの行が始まる日**。始まった日からだけ `cartimar` 系列を作る。
4. **Price-Monitoring と Daily-Price-Index の値の差**。同じ日の同じ品目で両者を比べ、大きくずれるなら予備として使う是非を見直す。
5. **GitHub ActionsからDAのサイトに届くか**。海外IPを弾く設定だった場合は、初回取り込みだけ手元のMacで実行し、週次の実行方法を再検討する。

## 12. 調査結果による更新（2026-10-01、実装計画の作成時）

2020-11〜2026-09の各月から1本ずつ、計71本のPrice Monitoringを取得して読み取りを試作した。その結果で、上の節を次のとおり改める。食い違う箇所はこの節を正とする。

### 12.1 体裁の変遷（3.2節・11節の1〜3の答え）

| 期間（月1本の抜き取りによる） | 首都圏まとめ | 市場別の表 |
|---|---|---|
| 2020-11 〜 2021-08 | 行の表（高値・安値・実勢） | なし |
| 2021-09 〜 2022-12 | 図版レイアウト（今日・昨日の実勢）。**2021-11〜2022-01ごろは、まとめのページが画像で文字が取れない** | あり |
| 2023-01 〜 2025-01 | 図版レイアウト（値幅のみ。値が1つだけの品目もある） | あり。**カルティマールの行は2023-12から** |
| 2025-02 〜 | 列見出しつきの表（安値・高値・実勢・平均。2025-02は実勢なし） | あり（3ページ） |

- 対象のPrice Monitoringは1,639本（2020-11-03〜2026-09-30）。
- 71本のうち69本から行を取り出せた。残り2本（2025-05-01、2025-09-01）は全ページが画像。2025年以降は同じ日のDaily Price Indexで補える。
- 図版レイアウトは、単語の座標を使えば読める（値のすぐ左、上下1文字分の範囲にある単語をラベルとする）。`pdftotext -layout` の行分割では読めない。
- ページの大きさがPDFによって違う（2021-11は座標が2000を超える）。距離のしきい値は、文字の高さの倍数で持つ。

### 12.2 まとめが読めない期間の扱い（11節の2）

まとめのページから1行も取れず、市場別の表が読めたPDFは、市場別の値から品目ごとの平均・最安・最高を作って首都圏の値とする（`average` に入り、週次の `basis` は `average` になる）。この期間に取れる品目は7つほど（ティラピア、ガルンゴン、アンパラヤ、トマト、キャベツ、ペチャイバギオ、赤タマネギ）。ほかの品目はこの期間、線が切れる。画像の文字認識（OCR）は行わない。

### 12.3 データの形の変更（5節）

- `data/market_daily.csv` に `low`、`high` の列を足す（2024年ごろは市場別の表も値幅で書かれているため）。`price` は値幅の中間値。
- `data/unmapped.csv` は、1行＝1つの名前にまとめる（`raw_name, first_date, last_date, count, example_url`）。米・肉・卵などが毎日出るので、日ごとに書くと膨れあがる。
- `data/own.csv` から `commodity_id` 列を外し、`sheet`、`name_tl`、`name_en` を足す。1つの和名が複数の品目に対応することがあるため（「キャベツ」は品種の区別が無い時期の `cabbage` と `cabbage_scorpio` の両方に載せる）、対応は `commodities.csv` の `own_items` で引く。
- 品目名の照合は、「名前 [規格]」→ 名前 → 末尾の脚注文字を落とした名前、の順に試す（Daily Price Indexでは「Bangus」が規格違いで2行出るため）。
- 同じ日のデータの優先順位は「訂正版のPrice Monitoring ＞ Price Monitoring ＞ 訂正版のDaily Price Index ＞ Daily Price Index」。その日に読めたPrice Monitoringがあれば、Daily Price Indexは取得もしない。
- 過去分を解析し直すための `collect --reparse-from / --reparse-to` を足す（品目の対応表を直したあとに使う。キャッシュがあればDAへは取りに行かない）。

### 12.4 Excelの実数（3.5節の訂正）

野菜は45行（うち「マンゴー」は値なし）で、値のあるセルは121。魚介は5品目で値は6。合わせて127件。

### 12.5 リンクの取り違え

`Daily-Cigarette-Price-Monitoring-…` は、ファイル名の途中に `Price-Monitoring-` を含む。種類の判定は、ファイル名の**先頭**で行う。

### 12.6 試作

`docs/reference/parser-prototype/` に、読み取り部分の試作、実物のPDFから作った見本11本、テスト28件、品目の対応表の初版（54品目）を置いた。実装はこれを土台にする。
