# 読み取り部分の試作（検証済み）

実装計画の Task 1 で、ここの中身を `src/`、`tests/`、`data/`、`tools/` へ移す。

- `mmp/parsers/` — PDFの読み取り。2020-11〜2026-09の各月1本（71本）で動かし、全ページが画像の2本を除いて行を取り出せた。
- `mmp/names.py` — 品目名を `commodity_id` に対応づける。
- `data/commodities.csv` — 品目の対応表の初版（54品目）。和名は著者の確認待ち。
- `tests/fixtures/*.json` — 実物のPDFから作った見本（ページごとの本文と、単語の座標）。PDF本体は置いていない。出典URLは各ファイルの `source_url`。
- `tests/` — 28件。期待値はPDFを目で読んだ値。
- `dump_fixture.py` — PDFから見本を作る。`python dump_fixture.py <pdf> <出典URL> <出力.json>`

## 動かし方

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pdfplumber pytest
python -m pytest -q tests     # 28 passed
```

## わかっている限界

- 全ページが画像のPDFは読めない（行が0件になる）。
- 2021-11〜2022-01ごろは、まとめのページが画像。市場別の表の平均で代用する（`layouts` の末尾が `market_only`）。
- 図版レイアウトで、ラベルが分類名とくっついて読めることがある（例：`VEGETABLES Pechay Tagalog`）。`names.normalize` が前の大文字語を落として吸収している。
- 境目の日付は月1本の抜き取りでしか確かめていない。全期間を取り込んだあとの点検（計画の Task 10）で、取りこぼしを洗い出す。
