"""
YouTube Master Data — per-brand/month video breakdown with theme classification.
Ported from social-mcp's server.py (create_master_data_for_brand and friends),
adapted to: (a) reuse this project's existing get_videos_in_range() instead of
re-implementing playlist pagination, (b) write a local .xlsx instead of a
Google Sheet, (c) keep the JSON cache around (no auto-delete — it's the
durable local store now that there's no Sheets export to fall back on).
"""

import os
import json
import calendar
from datetime import datetime

from pdf_report_generator import COMPETITOR_CHANNELS, get_videos_in_range
from themes import classify_theme
import excel_builder as xb

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTER_DATA_DIR = os.path.join(ROOT, "master_data")
MASTER_DATA_XLSX_DIR = os.path.join(ROOT, "generated_master_data")
os.makedirs(MASTER_DATA_DIR, exist_ok=True)
os.makedirs(MASTER_DATA_XLSX_DIR, exist_ok=True)

ORGANIC_THEMES = {"Market Analysis for Tomorrow", "Live Trading Today",
                   "Intraday Insights", "Webinar", "Expiry ki Baat"}


def _safe(s):
    return s.lower().replace(" ", "_").replace("/", "_")


def _month_bounds(month_label):
    """'July 2026' -> ('2026-07-01', '2026-07-31')."""
    dt = datetime.strptime(month_label, "%B %Y")
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.strftime("%Y-%m-01"), dt.strftime(f"%Y-%m-{last_day:02d}")


def get_week(pub_str):
    try:
        dt = datetime.strptime(pub_str, "%Y-%m-%d")
        return f"Week {(dt.day - 1) // 7 + 1}"
    except Exception:
        return "Week 1"


def get_organic(theme):
    return "Organic" if theme in ORGANIC_THEMES else "Inorganic"


def create_master_data_for_brand(brand, month_label, progress_cb=None):
    channel_id = COMPETITOR_CHANNELS.get(brand)
    if not channel_id:
        return {"success": False, "brand": brand, "month": month_label,
                "error": f"Brand '{brand}' not found. Available: {', '.join(COMPETITOR_CHANNELS.keys())}"}

    try:
        start_date, end_date = _month_bounds(month_label)
    except ValueError:
        return {"success": False, "brand": brand, "month": month_label,
                "error": "Invalid month format. Use e.g. 'July 2026'"}

    if progress_cb:
        progress_cb({"stage": "fetch", "label": f"Fetching {brand} videos for {month_label}...", "pct": 10})

    raw_videos = get_videos_in_range(channel_id, start_date, end_date)

    all_videos = []
    for v in raw_videos:
        theme = classify_theme(v["title"])
        engagement = v["likes"] + v["comments"]
        all_videos.append({**v, "theme": theme, "engagement": engagement})
    all_videos.sort(key=lambda v: v["views"], reverse=True)

    if progress_cb:
        progress_cb({"stage": "classify", "label": "Classifying themes...", "pct": 55})

    themes = {}
    for v in all_videos:
        t = themes.setdefault(v["theme"], {"posts": 0, "views": 0, "engagement": 0, "likes": 0, "comments": 0})
        t["posts"] += 1
        t["views"] += v["views"]
        t["engagement"] += v["engagement"]
        t["likes"] += v["likes"]
        t["comments"] += v["comments"]

    result = {
        "brand": brand,
        "channel_id": channel_id,
        "month": month_label,
        "total_videos": len(all_videos),
        "total_views": sum(v["views"] for v in all_videos),
        "total_engagement": sum(v["engagement"] for v in all_videos),
        "videos": all_videos,
        "themes": themes,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    safe_brand, safe_month = _safe(brand), _safe(month_label)
    json_path = os.path.join(MASTER_DATA_DIR, f"{safe_brand}_{safe_month}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if progress_cb:
        progress_cb({"stage": "xlsx", "label": "Building Excel workbook...", "pct": 85})

    xlsx_filename = f"{safe_brand}_{safe_month}_master_data.xlsx"
    xlsx_path = os.path.join(MASTER_DATA_XLSX_DIR, xlsx_filename)
    build_master_data_xlsx(result, xlsx_path)

    if progress_cb:
        progress_cb({"stage": "done", "label": "Master data ready", "pct": 100})

    return {
        "success": True, "brand": brand, "month": month_label,
        "total_videos": result["total_videos"], "total_views": result["total_views"],
        "total_engagement": result["total_engagement"], "themes_found": len(themes),
        "xlsx_filename": xlsx_filename, "local_json": json_path,
    }


def create_master_data_all_brands(month_label, progress_cb=None):
    brands = list(COMPETITOR_CHANNELS.keys())
    results = []
    for i, brand in enumerate(brands):
        if progress_cb:
            pct = int(i / len(brands) * 100)
            progress_cb({"stage": "brand", "label": f"Processing {brand} ({i+1}/{len(brands)})...", "pct": pct})
        try:
            results.append(create_master_data_for_brand(brand, month_label))
        except Exception as e:
            results.append({"success": False, "brand": brand, "month": month_label, "error": str(e)})
    if progress_cb:
        progress_cb({"stage": "done", "label": "All brands processed", "pct": 100})
    return results


def list_master_data():
    if not os.path.exists(MASTER_DATA_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(MASTER_DATA_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(MASTER_DATA_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        safe_brand, safe_month = _safe(d["brand"]), _safe(d["month"])
        xlsx_filename = f"{safe_brand}_{safe_month}_master_data.xlsx"
        xlsx_exists = os.path.exists(os.path.join(MASTER_DATA_XLSX_DIR, xlsx_filename))
        files.append({
            "brand": d["brand"], "month": d["month"], "total_videos": d["total_videos"],
            "file": fname, "xlsx_filename": xlsx_filename if xlsx_exists else None,
        })
    return files


# ── Excel workbook ───────────────────────────────────────────────────────

MASTER_HEADERS = ["Date", "Week", "Message", "Profile", "Network",
                   "Likes", "Comments", "Engagement", "Views", "Link",
                   "General Tagging", "Kotak Tagging", "Organic/Inorganic"]

THEME_HEADERS = ["General Tagging", "No. of Posts", "Total Views", "Total Likes",
                  "Total Comments", "Total Engagement", "Avg Views/Post",
                  "Avg Engagement/Post", "Organic/Inorganic"]


def _master_data_sheet(brand, month_label, all_videos):
    rows_xml = []
    hlink_rels = {}
    hlink_entries = []
    rid_counter = 1

    header_cells = [xb.cell(f"{xb.col_letter(c)}1", h, xb.STYLE_HEADER_BLUE)
                     for c, h in enumerate(MASTER_HEADERS, 1)]
    rows_xml.append(xb.row_xml(1, header_cells, height=26))

    for ri, v in enumerate(sorted(all_videos, key=lambda x: x["published"]), 2):
        bg = xb.STYLE_CELL_LIGHT if ri % 2 == 0 else xb.STYLE_CELL_WHITE
        link_ref = f"J{ri}"
        link_cell, (rid, url) = xb.hlink(link_ref, v["url"], v["url"], rid_counter)
        hlink_rels[rid] = url
        hlink_entries.append((link_ref, rid))
        rid_counter += 1

        try:
            date_str = datetime.strptime(v["published"], "%Y-%m-%d").strftime("%d-%b-%Y")
        except Exception:
            date_str = v["published"]

        row_cells = [
            xb.cell(f"A{ri}", date_str, bg),
            xb.cell(f"B{ri}", get_week(v["published"]), bg),
            xb.cell(f"C{ri}", v["title"], bg),
            xb.cell(f"D{ri}", brand, bg),
            xb.cell(f"E{ri}", "YouTube", bg),
            xb.cell(f"F{ri}", v["likes"], bg, t="n"),
            xb.cell(f"G{ri}", v["comments"], bg, t="n"),
            xb.cell(f"H{ri}", v["engagement"], bg, t="n"),
            xb.cell(f"I{ri}", v["views"], bg, t="n"),
            link_cell,
            xb.cell(f"K{ri}", v["theme"], bg),
            xb.cell(f"L{ri}", v["theme"], bg),
            xb.cell(f"M{ri}", get_organic(v["theme"]), bg),
        ]
        rows_xml.append(xb.row_xml(ri, row_cells, height=20))

    last_row = len(all_videos) + 1
    cols_xml = ('<cols>'
                '<col min="1" max="1" width="14" customWidth="1"/>'
                '<col min="2" max="2" width="10" customWidth="1"/>'
                '<col min="3" max="3" width="55" customWidth="1"/>'
                '<col min="4" max="4" width="16" customWidth="1"/>'
                '<col min="5" max="5" width="11" customWidth="1"/>'
                '<col min="6" max="7" width="10" customWidth="1"/>'
                '<col min="8" max="9" width="12" customWidth="1"/>'
                '<col min="10" max="10" width="42" customWidth="1"/>'
                '<col min="11" max="12" width="24" customWidth="1"/>'
                '<col min="13" max="13" width="16" customWidth="1"/>'
                '</cols>')

    ws_xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
              f'<sheetViews><sheetView showGridLines="0" workbookViewId="0">'
              f'<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
              f'</sheetView></sheetViews>'
              f'{cols_xml}'
              f'<sheetData>{"".join(rows_xml)}</sheetData>'
              f'{xb.hyperlinks_xml(hlink_entries)}'
              f'</worksheet>')
    return ws_xml, (hlink_rels if hlink_rels else None)


def _theme_summary_sheet(themes):
    rows_xml = []
    header_cells = [xb.cell(f"{xb.col_letter(c)}1", h, xb.STYLE_HEADER_BLUE)
                     for c, h in enumerate(THEME_HEADERS, 1)]
    rows_xml.append(xb.row_xml(1, header_cells, height=26))

    sorted_themes = sorted(themes.items(), key=lambda x: x[1]["engagement"], reverse=True)
    for ri, (theme, td) in enumerate(sorted_themes, 2):
        bg = xb.STYLE_CELL_LIGHT if ri % 2 == 0 else xb.STYLE_CELL_WHITE
        posts = td["posts"]
        avg_views = round(td["views"] / posts) if posts else 0
        avg_eng = round(td["engagement"] / posts, 1) if posts else 0
        row_cells = [
            xb.cell(f"A{ri}", theme, bg),
            xb.cell(f"B{ri}", posts, bg, t="n"),
            xb.cell(f"C{ri}", td["views"], bg, t="n"),
            xb.cell(f"D{ri}", td["likes"], bg, t="n"),
            xb.cell(f"E{ri}", td["comments"], bg, t="n"),
            xb.cell(f"F{ri}", td["engagement"], bg, t="n"),
            xb.cell(f"G{ri}", avg_views, bg, t="n"),
            xb.cell(f"H{ri}", avg_eng, bg, t="n"),
            xb.cell(f"I{ri}", get_organic(theme), bg),
        ]
        rows_xml.append(xb.row_xml(ri, row_cells, height=20))

    cols_xml = ('<cols>'
                '<col min="1" max="1" width="32" customWidth="1"/>'
                '<col min="2" max="9" width="18" customWidth="1"/>'
                '</cols>')

    ws_xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
              f'<sheetViews><sheetView showGridLines="0" workbookViewId="0">'
              f'<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
              f'</sheetView></sheetViews>'
              f'{cols_xml}'
              f'<sheetData>{"".join(rows_xml)}</sheetData>'
              f'</worksheet>')
    return ws_xml, None


def build_master_data_xlsx(result, out_path):
    ws1, ws1_rels = _master_data_sheet(result["brand"], result["month"], result["videos"])
    ws2, ws2_rels = _theme_summary_sheet(result["themes"])
    xb.write_xlsx(out_path, [
        ("Master data", ws1, ws1_rels),
        ("Theme Summary", ws2, ws2_rels),
    ])
    return out_path
