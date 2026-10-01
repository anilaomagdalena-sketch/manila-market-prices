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
