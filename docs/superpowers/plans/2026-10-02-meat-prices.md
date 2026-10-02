# Meat Prices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 農業省の価格資料にある主要な肉5品目の推移を、既存ページの「肉」タブで週ごとに表示し、自動更新する。

**Architecture:** 既存の名称対応表と収集・集計処理を使い、保存済みPDFを再解析して履歴を作る。画面用JSONへ `meat` 分類を加え、既存のグラフをそのまま使う。

**Tech Stack:** Python 3.11以上、pytest、Playwright、静的HTML/CSS/JavaScript、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-10-02-meat-prices-design.md`。既存仕様は `docs/superpowers/specs/2026-10-01-manila-market-prices-design.md` の12節を優先する。

## Global Constraints

- 対象は `whole_chicken`、`pork_kasim`、`pork_liempo`、`beef_rump`、`beef_brisket` の5品目、単位は `kg`。
- 無修飾名と `Local` は対応させ、`Imported`、`Frozen`、`fresh or chilled` と鶏卵は混ぜない。無修飾名の産地・保存状態は推定しない。
- 首都圏価格の選択順、0以下と前回比5倍超の除外、28日以上の空白で線を切る規則を引き継ぐ。
- DAへのアクセスは同時に1本、PDFごとに3秒あける。テストからDAへアクセスしない。取得済みPDFを再取得しない。PDFをGitへ入れない。WordPressに触らない。
- `mmp/parsers/` は実物PDFで誤りを確認したときだけ、見本と期待値テストを先に追加して直す。
- 各タスクでテストを先に書き、失敗を確認し、実装後に成功を確認してコミットする。設計と食い違う事実が出たら著者に報告する。

## Review Focus

- `Whole Chicken` と `Whole Chicken, Imported`：後者が鶏肉の通常品へ混ざらないことを Task 1 で確認する。
- `Pork Ham` と `Pork Kasim (per kg)`：年代で異なる名称が同じIDになることを Task 1 で確認する。
- `Frozen Kasim` と `Chicken Egg`：対象外の品目が対応しないことを Task 1 で確認する。
- 実測値の無い肉：肉タブの表示と直接リンクが動き、実測値の凡例が出ないことを Task 2 で確認する。
- 再解析中のPDFキャッシュ欠損：PDFをネットから再取得せず、件数を報告することを Task 3 で確認する。

---

### Task 1: 肉5品目の名称対応

**Files:** Modify `data/commodities.csv`; test `tests/test_names.py`。

**Interfaces:** `NameMap(Path("data/commodities.csv")).lookup(raw_name: str, spec: str = "") -> str | None` を使う。後続タスクが `category=meat` と5つのIDに依存する。

- [ ] **Step 1: 失敗する名称テストを書く。** `tests/test_names.py` に、`Whole Chicken`、`Whole Chicken (per kg)`、`Whole Chicken, Local` → `whole_chicken`、`Pork Ham` と `Pork Kasim (per kg)` → `pork_kasim`、`Pork Belly` と `Pork Liempo (per kg)` → `pork_liempo`、`Beef Rump` と `Beef Brisket` →各IDを加える。`Whole Chicken, Imported`、`Frozen Kasim`、`Chicken Egg`、`Pork Ham/Kasim (fresh or chilled)` → `None` も確認する。
- [ ] **Step 2: 失敗を確認する。** `python -m pytest tests/test_names.py -q`。追加ケースが失敗すること。
- [ ] **Step 3: `data/commodities.csv` に5行を追加する。** `category=meat`、`display=1`、`order=600,610,620,630,640`。表示名とIDは設計書2節のとおり。`aliases` は `data/unmapped.csv` の実在名を確認し、対象外の販売条件と衝突しないものだけを登録する。`name_en` は Whole Chicken / Pork Ham (Kasim) / Pork Belly (Liempo) / Beef Rump / Beef Brisket。`name_tl` は確認できた現地名だけを入れる。
- [ ] **Step 4: 成功を確認する。** `python -m pytest tests/test_names.py -q`。追加ケースと既存ケースがすべて通ること。
- [ ] **Step 5: コミットする。** `git add data/commodities.csv tests/test_names.py && git commit -m "Add five meat commodities and aliases"`。

### Task 2: 分類と画面表示

**Files:** Modify `src/mmp/build_site.py`, `tests/test_build_site.py`, `tests/e2e/data.sample.json`, `tests/e2e/test_site.py`, `site/index.html`, `README.md`。画面の横幅テストが失敗した場合だけ `site/style.css` も修正する。

**Interfaces:** Task 1 の `category=meat` の品目行を既存の `build(weekly, own, commodities, *, updated, latest_report) -> dict` に渡す。出力の `categories` の最後は `{"id":"meat","label":"肉"}`、5品目の `unit` は `kg`、実測系列 `own` は空。

- [ ] **Step 1: 失敗する生成・画面テストを書く。** `tests/test_build_site.py` の標本へ `whole_chicken` とその週次価格を追加し、分類順が野菜・香味野菜・果物・魚介・肉、鶏肉のNCR系列が存在して `own=[]` と確認する。`tests/e2e/data.sample.json` に肉タブと鶏肉の標本を加える。`tests/e2e/test_site.py` で `?item=whole_chicken` が肉タブと品目名を選び、実測値の凡例と注記が出ず、360pxで横スクロールしないことと、ページタイトルに「肉」が入ることを確認する。空分類のテストは肉を含む標本に合わせる。
- [ ] **Step 2: 失敗を確認する。** `python -m pytest tests/test_build_site.py -q` と `python -m pytest -o addopts='' tests/e2e/test_site.py -q`。追加した分類または画面ケースが失敗すること。
- [ ] **Step 3: 分類と文言を実装する。** `CATEGORIES` に肉を加え、`site/index.html` のタイトル、`README.md` の見出し・説明・埋め込みタイトルを「野菜・魚介・肉」に改める。実測値の無い品目は既存の表示分岐を使う。360pxの横幅テストが落ちた場合のみ分類タブを折り返すCSSを加える。
- [ ] **Step 4: 成功を確認する。** Step 2の両コマンドを再実行し、すべて通ること。既存の野菜と魚介の選択も維持されること。
- [ ] **Step 5: コミットする。** `git add src/mmp/build_site.py tests/test_build_site.py tests/e2e/data.sample.json tests/e2e/test_site.py site/index.html README.md site/style.css && git commit -m "Show meat category in price chart"`。CSSを変更しなかった場合は追加対象から外す。

### Task 3: 保存済みPDFの再解析と価格点検

**Files:** Modify `tests/test_collect.py`, `data/daily.csv`, `data/market_daily.csv`, `data/weekly.csv`, `data/unmapped.csv`, `data/rejected.csv`, `data/sources.csv`, `site/data.json`, `docs/backfill-report.md`。必要な不具合を再現できた場合だけ、対応する `src/mmp/` とテストを変更する。

**Interfaces:** `collect.run(..., reparse_from="2020-11-03", cache_dir=Path(".cache/pdf"))` は既存の `sources.csv` で `parsed` のPDFだけをキャッシュから読み、`aggregate.main` と `build_site.main` が公開JSONを更新する。

- [ ] **Step 1: 再解析の失敗する統合テストを書く。** `tests/test_collect.py` の偽サイトで、肉の名称が未登録だった初回取り込みと、Task 1 の対応表を加えた後のキャッシュ再解析を再現する。後者でPDFのURLが `fetch` に渡らず、肉の `daily.csv` 行が加わることを確認する。PDFキャッシュを消した場合は `fetch_errors` が増え、PDFのURLが `fetch` に渡らず、既存の日次行が失われないことも確認する。
- [ ] **Step 2: 失敗を確認する。** `python -m pytest tests/test_collect.py -q`。追加した再解析ケースが失敗すること。既存実装で最初から通るなら、実装を増やさず保護テストとして採用する。
- [ ] **Step 3: 必要な収集処理の修正を行う。** Step 2 で実際に失敗した条件だけ修正する。キャッシュのみの再解析を維持し、通常の週次収集は変えない。
- [ ] **Step 4: テストを通す。** `python -m pytest tests/test_collect.py -q` と `python -m pytest -q` が通ること。
- [ ] **Step 5: 実データをキャッシュから再解析する。** 競合する収集処理が無いことと `.cache/pdf` の所在・台帳との対応を確認する。`python -m mmp.collect --data-dir data --cache-dir .cache/pdf --reparse-from 2020-11-03` を実行する。PDF取得はしない。キャッシュ欠損や解析失敗は件数とURLを記録し、原因が不明なまま取得し直さない。
- [ ] **Step 6: 集計と点検を行う。** `python -m mmp.aggregate --data-dir data` と `python -m mmp.build_site --data-dir data --out site/data.json` を実行する。5品目の初日・最終日・週数・最大空白・除外件数・カルティマール行数を集計し、2020年・2022年・2025年・2026年の代表値を保存済みPDFと照合する。異常な段差や同日複数行の衝突があれば著者に報告して判断を待つ。点検結果と新しい件数を `docs/backfill-report.md` に追記する。
- [ ] **Step 7: 公開前の確認をする。** `python -m pytest -q`、`python -m pytest -o addopts='' tests/e2e/test_site.py -q` を実行する。`site/data.json` に5品目の価格系列があり、既存の品目も残ることを確認する。PDFがGitの追加対象に入っていないことを確認する。
- [ ] **Step 8: コミットする。** 変更したデータ・テスト・報告書だけを `git add` し、`git commit -m "Backfill and audit meat prices"`。`git status` でPDFが追跡されていないことを再確認する。
- [ ] **Step 9: 公開する。** `site/data.json` の5品目が空でなく、READMEの埋め込みタイトルが一致することを再確認する。`git push origin main` の後、GitHubオーナー `anilaomagdalena-sketch` の `weekly` workflowを手動起動し、成功を待つ。単なる `main` へのプッシュではPagesの配備が始まらないため、この手順を省かない。
- [ ] **Step 10: 公開結果を確認して報告する。** 公開ページと `data.json` がHTTP 200で、肉タブと5品目の価格を表示することを確認する。5品目のデータ範囲、欠測・除外、テスト結果、公開URLを著者へ日本語で伝える。WordPressは変更しない。
