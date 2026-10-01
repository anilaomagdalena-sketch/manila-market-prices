"""PDFを、テスト用の軽いJSON（ページごとの本文と単語の座標）にする。"""
import json, sys
from mmp.parsers.pdf import load_pages
src, url, out = sys.argv[1:4]
pages = load_pages(open(src, 'rb').read())
json.dump({"source_url": url, "pages": [
    {"text": p.text, "words": [[w.text, round(w.x0, 1), round(w.x1, 1), round(w.top, 1), round(w.bottom, 1)] for w in p.words]}
    for p in pages]}, open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
