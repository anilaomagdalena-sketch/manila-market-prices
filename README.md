# マニラの野菜・魚介・肉の価格推移

フィリピン農業省（DA-AMAS Bantay Presyo）の公表資料から、首都圏の野菜・魚介・肉の価格を週ごとにまとめたページです。カルティマール市場の農業省調査値と、著者が現地で記録した実測値も表示します。肉は丸鶏、豚肉2部位、牛肉2部位が対象です。無修飾の品目名から産地や保存状態は推定しません。

公開ページ：<https://anilaomagdalena-sketch.github.io/manila-market-prices/>

## 仕組み

```text
農業省のPDF一覧 ── collect ── data/sources.csv（取得・解析の台帳）
                         ├── data/daily.csv（首都圏の日次価格）
                         └── data/market_daily.csv（市場別の日次価格）
著者のExcel ── import_own ── data/own.csv（著者の実測値）
                             │
                   aggregate ── data/weekly.csv
                             │
                   build_site ── site/data.json ── GitHub Pages
```

GitHub Actions の `weekly` は、フィリピン時間の毎週月曜07:17に動きます。新しいPDFを取り込み、週次価格と画面用データを更新してから公開します。GitHubから失敗通知のメールが届いたら、[Actions の実行記録](https://github.com/anilaomagdalena-sketch/manila-market-prices/actions)と `data/sources.csv` の `failed` 行を確認してください。PDF一覧の取得失敗、直近14日に解析成功がない場合、または今回の新規PDFの半分以上が解析失敗した場合は公開処理が止まります。

## 手入れ

新しい品目の表記が出たら、`data/unmapped.csv` を確認し、`data/commodities.csv` の `aliases` に追加します。その後、該当期間の保存済みPDFを `python -m mmp.collect --data-dir data --cache-dir .cache/pdf --reparse-from YYYY-MM-DD --reparse-to YYYY-MM-DD` で再解析し、`aggregate` と `build_site` を実行してください。PDFキャッシュがない場合は、取得済みPDFを再取得せず、元のキャッシュを復元します。

農業省がPDFの体裁を変えたときは、`tools/dump_fixture.py` で見本を作り、`tests/test_parsers.py` に期待値のテストを追加します。テストで誤りを再現してから `src/mmp/parsers/` を直し、`python -m mmp.collect --data-dir data --cache-dir .cache/pdf --retry-failed` で失敗分を再処理してください。

著者の実測値を増やすときは、元のExcelに列を追加し、`python -m mmp.import_own docs/reference/own-cartimar-prices-2020-2024.xlsx --out data/own.csv` で `data/own.csv` を更新します。`python -m mmp.aggregate --data-dir data` と `python -m mmp.build_site --data-dir data --out site/data.json` を実行すると、公開用データを作り直せます。

## WordPressへの埋め込み

```html
<iframe src="https://anilaomagdalena-sketch.github.io/manila-market-prices/" title="マニラの野菜・魚介・肉の価格推移"
        style="width:100%;height:914px;border:0" loading="lazy"></iframe>
```

高さ914pxは、幅360pxで実データのページを開いたときの高さ894pxに20pxを足した値です。WordPress側の横幅や文字設定で高さが変わる場合は、表示を見て調整してください。

## 出典と価格の見方

データの出典は[フィリピン農業省 DA-AMAS Bantay Presyo](https://www.da.gov.ph/price-monitoring/)です。首都圏の価格は調査市場の平均で、個々の店の販売価格ではありません。カルティマール市場の農業省調査値と、著者の実測値は別の系列で表示します。初回取り込みの件数、読めなかったPDF、欠測期間は[点検報告書](docs/backfill-report.md)にまとめています。
