"""
YouTube competitor "Export Sheet" — Followers / Engagement / Views / No. of Posts
matrix across the last N months, for all tracked brands. Ported from social-mcp's
server.py export_to_google_sheets(), with the Google Sheets API calls replaced by
a local .xlsx build (excel_builder.write_xlsx).
"""

import os
from datetime import datetime

from pdf_report_generator import (
    COMPETITOR_CHANNELS, BRANDS,
    get_channel_stats, yt_api, MONTH_SEARCH_CAP,
    hist_val, save_subscriber_snapshot,
)
import excel_builder as xb

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_XLSX_DIR = os.path.join(ROOT, "generated_exports")
os.makedirs(EXPORT_XLSX_DIR, exist_ok=True)

SECTIONS = ["Followers", "Engagement (Likes + Comments)", "Views", "No. of Posts"]


def _get_last_n_months(n=6):
    """Return list of (label, start_iso, end_iso) for the last n complete months."""
    now = datetime.now()
    months = []
    for i in range(n - 1, -1, -1):
        m = now.month - 1 - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        start = datetime(y, m, 1)
        end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        label = start.strftime("%b-%y")
        months.append((label, start.strftime("%Y-%m-%dT00:00:00Z"), end.strftime("%Y-%m-%dT00:00:00Z")))
    return months


def _fetch_monthly_stats(channel_id, months):
    """Bucket a channel's uploads by month using the uploads playlist (1 quota unit/page)."""
    month_labels = [m[0] for m in months]
    results = {m: {"views": 0, "likes": 0, "comments": 0, "posts": 0} for m in month_labels}

    month_ranges = {
        label: (datetime.strptime(after[:10], "%Y-%m-%d"), datetime.strptime(before[:10], "%Y-%m-%d"))
        for label, after, before in months
    }
    oldest_dt = min(v[0] for v in month_ranges.values())

    playlist_id = "UU" + channel_id[2:]
    video_ids, pub_dates = [], {}
    page_token = None
    scanned = 0

    while scanned < MONTH_SEARCH_CAP:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        try:
            data = yt_api("playlistItems", params)
        except Exception:
            break
        items = data.get("items", [])
        if not items:
            break

        stop = False
        for item in items:
            scanned += 1
            vid_id = item["contentDetails"]["videoId"]
            pub = item["contentDetails"].get("videoPublishedAt", "")[:10]
            if not pub:
                continue
            try:
                pub_dt = datetime.strptime(pub, "%Y-%m-%d")
            except Exception:
                continue
            if pub_dt < oldest_dt:
                stop = True
                break
            video_ids.append(vid_id)
            pub_dates[vid_id] = pub_dt
        page_token = data.get("nextPageToken")
        if not page_token or stop:
            break

    if not video_ids:
        return results

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            vdata = yt_api("videos", {"part": "statistics", "id": ",".join(batch)})
        except Exception:
            continue
        for item in vdata.get("items", []):
            vid_id = item["id"]
            pub_dt = pub_dates.get(vid_id)
            if not pub_dt:
                continue
            bucket = next((lbl for lbl, (f, t) in month_ranges.items() if f <= pub_dt < t), None)
            if not bucket:
                continue
            st = item["statistics"]
            results[bucket]["views"] += int(st.get("viewCount", 0))
            results[bucket]["likes"] += int(st.get("likeCount", 0))
            results[bucket]["comments"] += int(st.get("commentCount", 0))
            results[bucket]["posts"] += 1

    return results


def build_export_workbook(months=6, progress_cb=None):
    month_tuples = _get_last_n_months(months)
    month_labels = [m[0] for m in month_tuples]

    if progress_cb:
        progress_cb({"stage": "fetch", "label": "Fetching YouTube data for all brands...", "pct": 5})

    all_monthly, all_subs = {}, {}
    for i, brand in enumerate(BRANDS):
        channel_id = COMPETITOR_CHANNELS.get(brand)
        if channel_id:
            all_monthly[brand] = _fetch_monthly_stats(channel_id, month_tuples)
            st = get_channel_stats(channel_id)
            all_subs[brand] = st.get("subscribers", "-")
        else:
            all_monthly[brand] = {m: {"views": 0, "likes": 0, "comments": 0, "posts": 0} for m in month_labels}
            all_subs[brand] = "-"
        if progress_cb:
            pct = 5 + int((i + 1) / len(BRANDS) * 70)
            progress_cb({"stage": "fetch", "label": f"Fetched {brand} ({i+1}/{len(BRANDS)})...", "pct": pct})

    # The live subscriber count reflects "right now" — closest to the most recent
    # month in this window — so that's the month it gets persisted under.
    save_subscriber_snapshot(month_labels[-1], all_subs)

    def v(brand, m, key):
        val = all_monthly[brand][m][key]
        return val if val > 0 else "-"

    def eng(brand, m):
        val = all_monthly[brand][m]["likes"] + all_monthly[brand][m]["comments"]
        return val if val > 0 else "-"

    def subs(brand, m):
        val = hist_val(brand, m)
        return val if val is not None else all_subs.get(brand, "-")

    extractors = {
        "Followers": subs,
        "Engagement (Likes + Comments)": eng,
        "Views": lambda b, m: v(b, m, "views"),
        "No. of Posts": lambda b, m: v(b, m, "posts"),
    }

    if progress_cb:
        progress_cb({"stage": "build", "label": "Building Excel workbook...", "pct": 85})

    ws_xml = _build_worksheet(month_labels, extractors)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"youtube_export_{ts}.xlsx"
    out_path = os.path.join(EXPORT_XLSX_DIR, filename)
    xb.write_xlsx(out_path, [("YouTube", ws_xml, None)])

    if progress_cb:
        progress_cb({"stage": "done", "label": "Export ready", "pct": 100})

    return {"filename": filename, "months": month_labels}


def _build_worksheet(month_labels, extractors):
    n_brands = len(BRANDS)
    n_cols = len(month_labels) + 1
    rows_xml = []
    r = 1

    for section in SECTIONS:
        # blank spacer row
        rows_xml.append(xb.row_xml(r, [], height=8))
        r += 1

        # section title row
        title_cell = xb.cell(f"A{r}", section, xb.STYLE_HEADER_GOLD)
        rows_xml.append(xb.row_xml(r, [title_cell], height=22))
        r += 1

        # header row: Brands\Months, month1, month2, ...
        header_cells = [xb.cell(f"A{r}", "Brands\\Months", xb.STYLE_HEADER_BLUE)]
        for ci, m in enumerate(month_labels, 2):
            header_cells.append(xb.cell(f"{xb.col_letter(ci)}{r}", m, xb.STYLE_HEADER_BLUE))
        rows_xml.append(xb.row_xml(r, header_cells, height=22))
        r += 1

        # brand rows
        for bi, brand in enumerate(BRANDS):
            bg = xb.STYLE_CELL_LIGHT if bi % 2 == 1 else xb.STYLE_CELL_WHITE
            row_cells = [xb.cell(f"A{r}", brand, bg)]
            for ci, m in enumerate(month_labels, 2):
                val = extractors[section](brand, m)
                t = "n" if isinstance(val, (int, float)) else "inlineStr"
                row_cells.append(xb.cell(f"{xb.col_letter(ci)}{r}", val, bg, t=t))
            rows_xml.append(xb.row_xml(r, row_cells, height=20))
            r += 1

    col_widths = [f'<col min="1" max="1" width="24" customWidth="1"/>']
    col_widths.append(f'<col min="2" max="{n_cols}" width="13" customWidth="1"/>')
    cols_xml = "<cols>" + "".join(col_widths) + "</cols>"

    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheetViews><sheetView showGridLines="0" workbookViewId="0">'
            f'<pane xSplit="1" topLeftCell="B1" activePane="topRight" state="frozen"/>'
            f'</sheetView></sheetViews>'
            f'{cols_xml}'
            f'<sheetData>{"".join(rows_xml)}</sheetData>'
            f'</worksheet>')


def list_export_files():
    files = []
    for fname in os.listdir(EXPORT_XLSX_DIR):
        if not fname.lower().endswith(".xlsx"):
            continue
        fpath = os.path.join(EXPORT_XLSX_DIR, fname)
        st = os.stat(fpath)
        files.append({"filename": fname, "size_kb": st.st_size // 1024, "mtime": st.st_mtime})
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files
