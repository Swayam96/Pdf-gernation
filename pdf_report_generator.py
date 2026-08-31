"""
YouTube Competitor PDF Report Generator
Fetches YouTube data, builds pixel-perfect HTML slides in Python,
then renders to PDF via Chrome headless.

Usage:
    python pdf_report_generator.py               # last month
    python pdf_report_generator.py "July 2026"   # specific month

Setup:
    set YOUTUBE_API_KEY=...   (Windows)
    export YOUTUBE_API_KEY=... (Mac/Linux)
"""

import os, sys, json, ssl, urllib.request, urllib.parse, math
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────
YOUTUBE_API_KEY  = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# machine-readable progress events for callers (e.g. api.py) — off for plain CLI runs
_MACHINE_MODE = os.environ.get("PDF_REPORT_MACHINE") == "1"

def _progress(stage, label, pct):
    if _MACHINE_MODE:
        print(f"##PROGRESS## {json.dumps({'stage': stage, 'label': label, 'pct': pct})}", flush=True)

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode    = ssl.CERT_NONE

COMPETITOR_CHANNELS = {
    "Kotak Neo":          "UCw_Ou1dfOjPVGNppYGcO9rg",
    "Angel One":          "UCHzAyAwFbp2KVwvZ_fJuH0Q",
    "Dhan":               "UCEzHCpvFWoF85UabbzKTkOQ",
    "Groww":              "UCw5TLrz3qADabwezTEcOmgQ",
    "INDmoney":           "UCm7xZ9sbqhuARuDDcckh8Jg",
    "Markets By Zerodha": "UCXbKJML9pVclFHLFzpvBgWw",
    "Upstox":             "UCOBm5PAfMS7wy_WYPvGjSiQ",
    "Zerodha":            "UC59YUBhNLMkS2Q8NBWBGHAA",
}
BRANDS = list(COMPETITOR_CHANNELS.keys())
SHORT  = ["Kotak Neo","Angel One","Dhan","Groww","INDmoney","Mkt.Zerodha","Upstox","Zerodha"]

N = None
HIST_MONTHS = ["Oct-24","Nov-24","Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25",
               "Jun-25","Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25",
               "Jan-26","Feb-26","Mar-26","Apr-26","May-26","Jun-26"]
HIST_SUBS = {
    "Kotak Neo":          [290000,388000,481000,497000,567000,627000,693000,735000,827000,891000,893000,896000,899000,901000,904000,906000,907000,908000,909000,911000,912000],
    "Angel One":          [3520000,3640000,3970000,4250000,4520000,4590000,4590000,4580000,4580000,4570000,4570000,4570000,4560000,4560000,4550000,4550000,4540000,4530000,4480000,4480000,4390000],
    "Dhan":               [N,N,209000,217000,223000,230000,236000,242000,250000,258000,265000,272000,280000,288000,294000,300000,307000,314000,319000,325000,333000],
    "Groww":              [2340000,2370000,2390000,2400000,2400000,2410000,2410000,2420000,2430000,2430000,2430000,2440000,2440000,2450000,2450000,2460000,2460000,2460000,2460000,2460000,2470000],
    "INDmoney":           [N,N,1180000,1190000,1190000,1190000,1190000,1190000,1200000,1210000,1230000,1240000,1250000,1260000,1270000,1280000,1290000,1300000,1320000,1340000,1360000],
    "Markets By Zerodha": [N,N,N,N,N,N,N,N,150000,174000,184000,192000,199000,203000,208000,215000,220000,225000,229000,233000,239000],
    "Upstox":             [971000,974000,979000,982000,984000,985000,986000,991000,998000,1000000,1010000,1010000,1020000,1020000,1020000,1020000,1020000,1020000,1010000,1010000,1000000],
    "Zerodha":            [N,N,650000,664000,674000,686000,691000,700000,705000,713000,716000,720000,738000,741000,746000,748000,750000,753000,755000,756000,758000],
}

# ── Colors ────────────────────────────────────────────────────────────
C = {
    "blue":       "#004B91",
    "red":        "#DC143C",
    "darkblue":   "#1F4F78",
    "gold":       "#FFC200",
    "purple":     "#6B2F8F",
    "pink":       "#FFF0F0",
    "grey":       "#F5F5F8",
    "green":      "#1A8A1A",
    "negred":     "#CC0000",
    "text":       "#1A1A2E",
    "white":      "#FFFFFF",
}

# ── Common CSS injected into every slide ─────────────────────────────
COMMON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Outfit:wght@700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
body{width:1280px;height:720px;overflow:hidden;
     font-family:'Inter','Segoe UI',system-ui,Arial,sans-serif;background:#fff;}
.slide{width:1280px;height:720px;position:relative;overflow:hidden;}
.accent-bar{position:absolute;left:0;top:0;width:5px;height:100%;background:#DC143C;}
.footer{position:absolute;bottom:0;left:0;width:1280px;}
.footer-red{height:5px;background:#DC143C;}
.footer-blue{height:3px;background:#1F4F78;}
.pg{position:absolute;bottom:11px;right:18px;font-size:10px;color:#bbb;font-weight:500;}
.slide-tag{font-size:10px;font-weight:700;color:#DC143C;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:5px;}
.slide-title{font-size:25px;font-weight:800;color:#004B91;
             font-family:'Outfit','Segoe UI Black',Arial,sans-serif;line-height:1.15;}
.hline{height:2px;width:100%;margin-top:8px;
       background:linear-gradient(90deg,#004B91 0%,#DC143C 22%,rgba(0,75,145,0.2) 60%,transparent 100%);}
.tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
.tbl th{background:#004B91;color:#fff;font-weight:700;padding:11px 6px;text-align:center;
        font-size:13px;border:1px solid #003570;letter-spacing:0.3px;}
.tbl th.left{text-align:left;padding-left:12px;}
.tbl th.gold-h{background:#FFC200;color:#111;border-color:#d4a900;}
.tbl th.kotak-h{background:#1F4F78;color:#fff;border-color:#163a5a;}
.tbl td{padding:9px 6px;text-align:center;border:1px solid #eaeaea;
        font-size:13px;color:#1a1a2e;font-weight:600;vertical-align:middle;}
.tbl td.left{text-align:left;padding-left:12px;font-weight:700;}
.tbl tr:nth-child(even) td{background:#F4F7FF;}
.note{font-size:11px;color:#999;font-style:italic;margin-top:8px;line-height:1.5;}
</style>
"""

# ── Logo HTML ─────────────────────────────────────────────────────────
_LOGO_PATH = str(Path(__file__).parent / "kotak_neo_logo.png").replace("\\", "/")
LOGO_IMG   = f'<img src="file:///{_LOGO_PATH}" style="height:38px;width:auto;object-fit:contain;display:block;" alt="Kotak Neo">'
LOGO_IMG_SM= f'<img src="file:///{_LOGO_PATH}" style="height:28px;width:auto;object-fit:contain;display:block;" alt="Kotak Neo">'

LOGO_HTML = f'<div style="display:inline-flex;align-items:center;">{LOGO_IMG}</div>'

FOOTER_HTML = """<div class="footer">
  <div class="footer-red"></div>
  <div class="footer-blue"></div>
</div>"""

def page_num(n):
    return f'<div class="pg">{n}</div>'

# ── Helpers ───────────────────────────────────────────────────────────
def fmt(n, short=False):
    if n is None or n == 0: return "-"
    n = int(n)
    if short:
        if n >= 10000000: return f"{n/10000000:.1f}Cr"
        if n >= 100000:   return f"{n/100000:.1f}L"
        if n >= 1000:     return f"{n/1000:.0f}K"
        return str(n)
    # Indian comma format: 9,12,000
    s = str(abs(n))
    if len(s) <= 3:
        result = s
    elif len(s) <= 5:
        result = s[:-3] + "," + s[-3:]
    elif len(s) <= 7:
        result = s[:-5] + "," + s[-5:-3] + "," + s[-3:]
    else:
        result = s[:-7] + "," + s[-7:-5] + "," + s[-5:-3] + "," + s[-3:]
    return ("-" if n < 0 else "") + result

def pct(new_v, old_v):
    if not old_v: return ""
    p = ((new_v - old_v) / old_v) * 100
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"

def pct_color(val_str):
    if not val_str: return "#333"
    if val_str.startswith("+"): return C["green"]
    if val_str.startswith("-"): return C["negred"]
    return "#333"

# ── YouTube data ──────────────────────────────────────────────────────
def yt_api(endpoint, params):
    params["key"] = YOUTUBE_API_KEY
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, context=_SSL, timeout=15) as r:
        return json.loads(r.read().decode())

def get_channel_stats(cid):
    data = yt_api("channels", {"part": "statistics", "id": cid})
    if not data.get("items"): return {}
    st = data["items"][0]["statistics"]
    return {"subscribers": int(st.get("subscriberCount", 0)),
            "views":       int(st.get("viewCount", 0))}

def get_recent_videos(cid, count=15):
    playlist_id = "UU" + cid[2:]
    data = yt_api("playlistItems", {"part": "contentDetails", "playlistId": playlist_id, "maxResults": count})
    if not data.get("items"): return []
    ids  = [i["contentDetails"]["videoId"] for i in data["items"]]
    pub  = {i["contentDetails"]["videoId"]: i["contentDetails"].get("videoPublishedAt","")[:10] for i in data["items"]}
    vdata = yt_api("videos", {"part": "snippet,statistics", "id": ",".join(ids)})
    result = []
    for item in vdata.get("items", []):
        st = item["statistics"]
        vid_id = item["id"]
        result.append({
            "id": vid_id, "title": item["snippet"]["title"],
            "published": pub.get(vid_id, item["snippet"]["publishedAt"][:10]),
            "views":    int(st.get("viewCount",   0)),
            "likes":    int(st.get("likeCount",   0)),
            "comments": int(st.get("commentCount",0)),
            "thumbnail": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg",
            "url":       f"https://www.youtube.com/watch?v={vid_id}",
        })
    return result

def fetch_all_youtube_data():
    stats, videos = {}, {}
    total = len(COMPETITOR_CHANNELS)
    for i, (brand, cid) in enumerate(COMPETITOR_CHANNELS.items()):
        print(f"  {brand}...", flush=True)
        _progress("fetch", f"Fetching {brand} data ({i+1}/{total})", 5 + int(25 * i / total))
        st   = get_channel_stats(cid)
        vids = get_recent_videos(cid, 15)
        eng  = sum(v["likes"] + v["comments"] for v in vids)
        views = sum(v["views"] for v in vids)
        stats[brand] = {
            "subscribers":   st.get("subscribers", 0),
            "channel_views": st.get("views", 0),
            "recent_views":  views,
            "engagement":    eng,
            "posts":         len(vids),
        }
        videos[brand] = vids
    return stats, videos

def build_summary(stats, videos, month_label):
    prev_subs = {b: (HIST_SUBS.get(b, [0])[-1] or 0) for b in BRANDS}
    top3 = {b: sorted(videos.get(b, []), key=lambda v: v["views"], reverse=True)[:3] for b in BRANDS}
    by_eng   = sorted(BRANDS, key=lambda b: stats[b]["engagement"],  reverse=True)
    by_subs  = sorted(BRANDS, key=lambda b: stats[b]["subscribers"],  reverse=True)
    by_views = sorted(BRANDS, key=lambda b: stats[b]["recent_views"], reverse=True)
    return {
        "month": month_label,
        "brands": BRANDS,
        "stats": {b: {
            "subscribers":   stats[b]["subscribers"],
            "subs_fmt":      fmt(stats[b]["subscribers"], short=True),
            "prev_subs":     prev_subs[b],
            "prev_subs_fmt": fmt(prev_subs[b], short=True),
            "sub_growth":    pct(stats[b]["subscribers"], prev_subs[b]),
            "engagement":    stats[b]["engagement"],
            "eng_fmt":       fmt(stats[b]["engagement"]),
            "recent_views":  stats[b]["recent_views"],
            "views_fmt":     fmt(stats[b]["recent_views"], short=True),
            "posts":         stats[b]["posts"],
        } for b in BRANDS},
        "rankings": {"by_engagement": by_eng, "by_subscribers": by_subs, "by_views": by_views},
        "kotak_rank": {
            "engagement":  by_eng.index("Kotak Neo") + 1,
            "subscribers": by_subs.index("Kotak Neo") + 1,
            "views":       by_views.index("Kotak Neo") + 1,
        },
        "top3_videos": {b: [{"title": v["title"][:58],
                              "views":    fmt(v["views"]),
                              "likes":    fmt(v["likes"]),
                              "comments": fmt(v["comments"]),
                              "url":      v["url"],
                              "thumb":    v["thumbnail"]}
                             for v in top3[b]] for b in BRANDS},
    }

# ── SVG bar chart builder — bars + connected gold line for posts ──────
def build_bar_chart_svg(brands_data, metric_key, fmt_key,
                         bar_color, line_color="#FFC200",
                         svg_w=900, svg_h=440,
                         pad_left=20, pad_right=20, pad_top=50, pad_bottom=70):
    """
    Returns an SVG string for a combo bar chart.
    brands_data: list of dicts with keys: brand, short, <metric_key>, <fmt_key>, posts
    Purple bars for engagement/views + gold connected line for posts count.
    """
    vals  = [d[metric_key] for d in brands_data]
    posts = [d.get("posts", 0) for d in brands_data]
    max_v = max(vals) or 1
    max_p = max(posts) or 1
    n     = len(brands_data)
    chart_w = svg_w - pad_left - pad_right
    chart_h = svg_h - pad_top  - pad_bottom
    slot_w  = chart_w // n
    bar_w   = max(int(slot_w * 0.55), 25)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" style="overflow:visible;font-family:Arial,sans-serif;">']

    # gridlines
    for pct_val in [0.25, 0.5, 0.75, 1.0]:
        gy = pad_top + chart_h - int(chart_h * pct_val)
        lines.append(f'<line x1="{pad_left}" y1="{gy}" x2="{pad_left+chart_w}" y2="{gy}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="4,4"/>')

    # baseline
    lines.append(f'<line x1="{pad_left}" y1="{pad_top+chart_h}" x2="{pad_left+chart_w}" y2="{pad_top+chart_h}" stroke="#aaa" stroke-width="1.5"/>')

    # First pass: compute bar tops and post line points together so we can
    # detect collisions and push labels clear of each other
    bar_tops   = []   # (cx, by, vlbl)
    line_points = []  # (cx, py, posts)

    for i, d in enumerate(brands_data):
        cx  = pad_left + i * slot_w + slot_w // 2
        v   = d[metric_key]
        bh  = max(int((v / max_v) * chart_h), 4)
        by  = pad_top + chart_h - bh
        bar_tops.append((cx, by, d[fmt_key]))

        p   = d.get("posts", 0)
        # Gold line lives in top 35% of chart area — well separated from bars
        py  = pad_top + 8 + int((1 - p / max_p) * (chart_h * 0.30))
        line_points.append((cx, py, p))

    # Draw bars + bar value labels (value label sits 22px above bar top, never overlaps gold line)
    for i, (cx, by, vlbl) in enumerate(bar_tops):
        bx = cx - bar_w // 2
        bh = pad_top + chart_h - by
        lines.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{bar_color}" rx="3" opacity="0.9"/>')
        # Bar value label — clamp so it never rises into gold-line territory (top 35% = pad_top+chart_h*0.35)
        label_y = max(by - 8, int(pad_top + chart_h * 0.38))
        lines.append(f'<text x="{cx}" y="{label_y}" text-anchor="middle" font-size="13" font-weight="bold" fill="{bar_color}">{vlbl}</text>')
        # Brand label below axis
        short    = brands_data[i].get("short", brands_data[i]["brand"])
        label_by = pad_top + chart_h + 18
        lines.append(f'<text x="{cx}" y="{label_by}" text-anchor="middle" font-size="13" fill="#333" font-weight="700">{short}</text>')

    # Gold connecting line
    if len(line_points) > 1:
        path_d = f"M {line_points[0][0]} {line_points[0][1]}"
        for lx, ly, _ in line_points[1:]:
            path_d += f" L {lx} {ly}"
        lines.append(f'<path d="{path_d}" stroke="{line_color}" stroke-width="2.5" fill="none" stroke-dasharray="6,3"/>')

    # Gold diamond markers — label sits ABOVE the diamond, well clear of bars
    for (lx, ly, p) in line_points:
        d_size = 8
        lines.append(f'<polygon points="{lx},{ly-d_size} {lx+d_size},{ly} {lx},{ly+d_size} {lx-d_size},{ly}" fill="{line_color}" stroke="#c8a000" stroke-width="1"/>')
        box_w = max(22, len(str(p)) * 7 + 8)
        box_y = ly - d_size - 24
        lines.append(f'<rect x="{lx-box_w//2}" y="{box_y}" width="{box_w}" height="17" fill="{line_color}" rx="3"/>')
        lines.append(f'<text x="{lx}" y="{box_y+12}" text-anchor="middle" font-size="11" font-weight="bold" fill="#333">{p}</text>')

    # legend
    lx_leg, ly_leg = pad_left, svg_h - 18
    lines.append(f'<rect x="{lx_leg}" y="{ly_leg-11}" width="14" height="12" fill="{bar_color}" rx="2"/>')
    lines.append(f'<text x="{lx_leg+18}" y="{ly_leg}" font-size="13" fill="#333" font-weight="700">Total Engagement</text>')
    lines.append(f'<line x1="{lx_leg+180}" y1="{ly_leg-5}" x2="{lx_leg+200}" y2="{ly_leg-5}" stroke="{line_color}" stroke-width="2.5"/>')
    lines.append(f'<polygon points="{lx_leg+190},{ly_leg-13} {lx_leg+198},{ly_leg-5} {lx_leg+190},{ly_leg+3} {lx_leg+182},{ly_leg-5}" fill="{line_color}"/>')
    lines.append(f'<text x="{lx_leg+205}" y="{ly_leg}" font-size="13" fill="#333" font-weight="700">No. of Posts</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 1 — COVER
# ═══════════════════════════════════════════════════════════════════════
def slide_cover(s):
    month = s["month"]
    brand_chips = ''.join(
        f'<span style="background:rgba(255,255,255,0.13);border:1px solid rgba(255,255,255,0.25);'
        f'color:rgba(255,255,255,0.85);font-size:10px;padding:4px 11px;border-radius:20px;'
        f'font-weight:500;letter-spacing:0.3px;">{b}</span>'
        for b in BRANDS
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#003570;}}
.left-panel{{position:absolute;left:0;top:0;width:640px;height:720px;
             background:linear-gradient(160deg,#004B91 0%,#002d62 55%,#001a3d 100%);
             display:flex;flex-direction:column;justify-content:center;padding:60px 56px;}}
.right-panel{{position:absolute;right:0;top:0;width:640px;height:720px;
              background:linear-gradient(160deg,#012a5e 0%,#001a3d 100%);
              display:flex;flex-direction:column;justify-content:center;align-items:flex-start;
              padding:50px 48px;border-left:2px solid rgba(255,255,255,0.07);}}
.eyebrow{{font-size:10px;font-weight:700;color:#FFC200;letter-spacing:3px;
          text-transform:uppercase;margin-bottom:18px;}}
.big-title{{font-family:'Outfit',Arial,sans-serif;font-size:58px;font-weight:900;
            color:#ffffff;line-height:1.05;letter-spacing:-1px;}}
.big-title span{{color:#DC143C;}}
.red-rule{{width:60px;height:4px;background:#DC143C;border-radius:2px;margin:22px 0;}}
.sub-desc{{font-size:15px;color:rgba(255,255,255,0.72);line-height:1.7;max-width:460px;}}
.month-badge{{display:inline-flex;align-items:center;gap:10px;margin-top:28px;
              background:rgba(255,194,0,0.15);border:1px solid rgba(255,194,0,0.4);
              border-radius:8px;padding:10px 20px;}}
.month-text{{font-size:17px;font-weight:700;color:#FFC200;letter-spacing:0.5px;}}
.right-label{{font-size:11px;font-weight:600;color:rgba(255,255,255,0.45);
              letter-spacing:2px;text-transform:uppercase;margin-bottom:20px;}}
.brand-grid{{display:flex;flex-wrap:wrap;gap:10px;max-width:480px;}}
.deco-circle{{position:absolute;border-radius:50%;border:1px solid rgba(255,255,255,0.06);}}
</style>
</head>
<body>
<div class="slide">
  <div style="position:absolute;width:380px;height:380px;border-radius:50%;
              background:rgba(220,20,60,0.06);top:-100px;right:260px;"></div>
  <div style="position:absolute;width:220px;height:220px;border-radius:50%;
              background:rgba(255,194,0,0.05);bottom:60px;right:80px;"></div>
  <div class="left-panel">
    <div class="eyebrow">YouTube Competitor Report</div>
    <div class="big-title">Content<br><span>Observations</span></div>
    <div class="red-rule"></div>
    <div class="sub-desc">A monthly deep-dive into the YouTube strategy of Kotak Neo and 7 fintech peers.</div>
    <div class="month-badge">
      <div style="width:8px;height:8px;background:#FFC200;border-radius:50%;"></div>
      <div class="month-text">{month}</div>
    </div>
  </div>
  <div class="right-panel">
    <div class="right-label">Brands Analysed</div>
    <div class="brand-grid">{brand_chips}</div>
    <div style="margin-top:40px;padding-top:30px;border-top:1px solid rgba(255,255,255,0.1);width:100%;">
      <div style="font-size:11px;color:rgba(255,255,255,0.4);line-height:1.8;">
        Data Source: YouTube Data API v3<br>
        Engagement = Likes + Comments<br>
        Prepared by Kotak Securities Social Intelligence
      </div>
    </div>
  </div>
  {FOOTER_HTML}
  {page_num(1)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 2 — FINDINGS & SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════════
def slide_findings(s, page):
    st    = s["stats"]
    r     = s["rankings"]
    month = s["month"]
    eng_leader   = r["by_engagement"][0]
    views_leader = r["by_views"][0]
    subs_leader  = r["by_subscribers"][0]
    kotak_eng    = st["Kotak Neo"]["eng_fmt"]
    kotak_views  = st["Kotak Neo"]["views_fmt"]
    kotak_rank_e = s["kotak_rank"]["engagement"]
    kotak_rank_v = s["kotak_rank"]["views"]

    top2_eng = r["by_engagement"][:2]
    finding_title = f"YouTube: {eng_leader} Leads Engagement While {views_leader} Dominates Views"

    observations = [
        ("Content volume drives performance",
         f"{eng_leader} leads total engagement with {st[eng_leader]['eng_fmt']} interactions across "
         f"{st[eng_leader]['posts']} videos, demonstrating consistent content output."),
        ("Subscriber base growth continues",
         f"{subs_leader} maintains the largest subscriber base. Dhan and Markets By Zerodha "
         f"continue to post strong month-on-month growth relative to channel age."),
        ("Kotak Neo performance",
         f"Kotak Neo ranks #{kotak_rank_e} in total engagement ({kotak_eng}) and "
         f"#{kotak_rank_v} in total views ({kotak_views}) for {month}."),
        ("Engagement = Likes + Comments across all channels",
         "YouTube removed public share counts from its API in 2015. "
         "Rankings reflect Likes + Comments only."),
        ("Financial education content dominates",
         "IPO updates, market insights and financial education videos continue to drive the "
         "highest viewership and engagement across all 8 competitor channels."),
    ]

    icons = ["📊","📈","🏆","⚠️","🎯"]
    obs_html = ""
    for idx, (heading, body) in enumerate(observations):
        icon = icons[idx % len(icons)]
        is_last = (idx == len(observations) - 1)
        span = 'grid-column:1/3;' if is_last else ''
        obs_html += f"""
        <div style="background:#F7FAFF;border-radius:10px;padding:16px 18px;
                    border-top:3px solid {C['blue']};{span}">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <span style="font-size:15px;">{icon}</span>
            <span style="font-size:14px;font-weight:700;color:{C['blue']};
                         letter-spacing:0.2px;">{heading}</span>
          </div>
          <div style="font-size:13.5px;color:#334;line-height:1.65;">{body}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;
             background:linear-gradient(180deg,#DC143C,#004B91);}}
.main{{padding:28px 44px 48px 54px;height:720px;display:flex;flex-direction:column;}}
.obs-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;flex:1;margin-top:14px;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Findings &amp; Suggestions</div>
    <div class="slide-title">{finding_title}</div>
    <div class="hline"></div>
    <div style="font-size:12px;font-weight:600;color:#888;text-transform:uppercase;
                letter-spacing:1.5px;margin-top:12px;">Key Observations — {month}</div>
    <div class="obs-grid">{obs_html}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 3 — SUMMARY
# ═══════════════════════════════════════════════════════════════════════
def slide_summary(s, page):
    st    = s["stats"]
    r     = s["rankings"]
    k     = s["kotak_rank"]
    month = s["month"]
    top3_eng    = r["by_engagement"][:3]
    eng_leader  = r["by_engagement"][0]
    subs_leader = r["by_subscribers"][0]
    views_leader= r["by_views"][0]
    kotak       = st["Kotak Neo"]

    bullets = [
        f"On YouTube, the best-performing brands in total engagement were "
        f"<b>{top3_eng[0]}</b>, <b>{top3_eng[1]}</b>, and <b>{top3_eng[2]}</b>.",
        f"Kotak Neo ranks <b>#{k['engagement']}</b> in total engagement and "
        f"<b>#{k['views']}</b> in total views among all 8 brands.",
        f"<b>{views_leader}</b> leads total views with {st[views_leader]['views_fmt']} views across recent videos.",
        f"<b>{eng_leader}</b> leads total engagement with {st[eng_leader]['eng_fmt']} (Likes + Comments).",
        f"Kotak Neo posted <b>{kotak['posts']}</b> videos generating "
        f"<b>{kotak['views_fmt']}</b> views and <b>{kotak['eng_fmt']}</b> engagements in {month}.",
        f"<b>{subs_leader}</b> has the largest subscriber base at {st[subs_leader]['subs_fmt']} subscribers.",
        "Markets By Zerodha continues to show strong growth momentum relative to its channel age.",
        "Engagement = Likes + Comments across all YouTube channels "
        "(Shares not available via public API).",
    ]

    items_html = "".join(
        f'''<div style="display:flex;align-items:flex-start;gap:12px;
                        padding:10px 14px;border-radius:7px;
                        background:{"#F0F5FF" if i%2==0 else "#fff"};
                        border-left:3px solid {C["blue"] if i%2==0 else C["red"]};">
              <div style="min-width:7px;height:7px;background:{C["red"] if i%2==0 else C["blue"]};
                           border-radius:50%;margin-top:6px;flex-shrink:0;"></div>
              <span style="font-size:15px;color:#1a1a2e;line-height:1.65;">{b}</span>
            </div>'''
        for i, b in enumerate(bullets)
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;
             background:linear-gradient(180deg,#004B91,#DC143C);}}
.main{{padding:28px 44px 48px 54px;height:720px;display:flex;flex-direction:column;}}
.bullets-wrap{{margin-top:14px;flex:1;display:flex;flex-direction:column;gap:6px;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Executive Summary</div>
    <div class="slide-title">Summary</div>
    <div class="hline"></div>
    <div class="bullets-wrap">{items_html}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 4 — FOLLOWERS MoM (6 hist months + current = 7 cols — big fonts)
# ═══════════════════════════════════════════════════════════════════════
def slide_followers_mom(s, page):
    month  = s["month"]
    st     = s["stats"]
    last6  = HIST_MONTHS[-6:]          # 6 months keeps columns wide → big text
    curr_m = month[:3] + "-" + month[-2:]
    all_m  = last6 + [curr_m]

    # Build header row — use <th> not <td>
    header_cells = '<th class="hbrand">Brand</th>' + "".join(
        f'<th class="hcol{"curr" if m == curr_m else ""}">{m}</th>'
        for m in all_m
    )

    # Build data rows
    rows_html = ""
    for bi, brand in enumerate(BRANDS):
        hist = HIST_SUBS.get(brand, [])
        prev = None
        # seed prev from the month before last6 so first col has a % change
        if last6:
            first_idx = HIST_MONTHS.index(last6[0]) if last6[0] in HIST_MONTHS else -1
            if first_idx > 0:
                seed = hist[first_idx - 1] if (first_idx - 1) < len(hist) else None
                if seed: prev = seed
        cells = f'<td class="brand-cell">{brand}</td>'
        for m in all_m:
            if m == curr_m:
                c_val = st[brand]["subscribers"]
                p_str = pct(c_val, prev) if prev else ""
                pc    = pct_color(p_str)
                cells += (f'<td class="curr-col">'
                          f'<div class="val">{fmt(c_val)}</div>'
                          f'<div class="pctv" style="color:{pc}">{p_str}</div></td>')
                prev = c_val
            else:
                idx = HIST_MONTHS.index(m) if m in HIST_MONTHS else -1
                val = hist[idx] if 0 <= idx < len(hist) else None
                if val:
                    p_str = pct(val, prev) if prev else ""
                    pc    = pct_color(p_str)
                    cells += (f'<td><div class="val">{fmt(val)}</div>'
                              f'<div class="pctv" style="color:{pc}">{p_str}</div></td>')
                    prev = val
                else:
                    cells += '<td><div class="val">-</div></td>'

        bg = "#fff" if bi % 2 == 0 else C["pink"]
        rows_html += f'<tr style="background:{bg}">{cells}</tr>'

    note = (f"Kotak Neo continued steady growth in {month}. "
            f"% shows month-over-month change. Data from YouTube API & tracked records.")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#DC143C;}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:10px;}}
thead th{{background:#004B91;color:#fff;font-weight:700;padding:11px 4px;
          font-size:12.5px;border:1px solid #003570;}}
thead th.hbrand{{text-align:left;padding-left:12px;width:155px;}}
thead th.hcolcurr{{background:#DC143C;border-color:#a80e28;}}
td{{padding:7px 4px;text-align:center;border:1px solid #e4e8f0;vertical-align:middle;}}
td.brand-cell{{text-align:left;padding-left:12px;font-weight:700;font-size:13px;
               width:155px;color:#1a1a2e;}}
.val{{font-size:13px;font-weight:700;color:#1a1a2e;}}
.pctv{{font-size:10.5px;margin-top:2px;font-weight:600;}}
.curr-col{{background:#EEF4FF!important;}}
tr:nth-child(even) td{{background:#f4f7ff;}}
tr:nth-child(even) td.curr-col{{background:#dce8ff!important;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Month-on-Month</div>
    <div class="slide-title">Followers M-O-M Comparison</div>
    <div class="hline"></div>
    <table>
      <thead><tr>{header_cells}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div class="note">{note}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 5 — KOTAK NEO MoM
# Top: Subscribers trend table (has real hist data)
# Bottom: Big KPI cards for current month (Posts, Views, Engagement, Growth)
# ═══════════════════════════════════════════════════════════════════════
def slide_kotak_mom(s, page):
    month  = s["month"]
    st     = s["stats"]
    kotak  = st["Kotak Neo"]
    last6  = HIST_MONTHS[-6:]
    curr_m = month[:3] + "-" + month[-2:]
    all_m  = last6 + [curr_m]

    hist_subs = HIST_SUBS.get("Kotak Neo", [])

    def hist_sub(m):
        if m not in HIST_MONTHS: return None
        idx = HIST_MONTHS.index(m)
        return hist_subs[idx] if idx < len(hist_subs) else None

    # Build subscriber trend row with % changes
    sub_cells = ""
    prev_v = None
    # seed prev from month before last6
    if last6:
        first_idx = HIST_MONTHS.index(last6[0]) if last6[0] in HIST_MONTHS else -1
        if first_idx > 0:
            seed = hist_subs[first_idx - 1] if (first_idx - 1) < len(hist_subs) else None
            if seed: prev_v = seed

    for m in all_m:
        is_curr = (m == curr_m)
        v = kotak["subscribers"] if is_curr else hist_sub(m)
        if v:
            p_str = pct(v, prev_v) if prev_v else ""
            pc    = pct_color(p_str)
            bg    = "#004B91" if is_curr else ("#fff" if all_m.index(m) % 2 == 0 else C["pink"])
            fc    = "#fff" if is_curr else "#1a1a2e"
            sub_cells += (f'<td style="background:{bg};color:{fc};text-align:center;'
                          f'padding:10px 6px;border:1px solid #ddd;font-weight:700;font-size:14px;">'
                          f'{fmt(v)}<br>'
                          f'<small style="font-size:11px;color:{"#90EE90" if is_curr else pc}">{p_str}</small></td>')
            prev_v = v
        else:
            sub_cells += '<td style="text-align:center;padding:10px 6px;border:1px solid #ddd;color:#999;">—</td>'

    # Month headers
    header_cells = "".join(
        f'<th style="background:{"#004B91" if m==curr_m else C["darkblue"]};color:#fff;'
        f'font-size:13px;font-weight:700;padding:10px 4px;border:1px solid #0d2a45;text-align:center;">{m}</th>'
        for m in all_m
    )

    # KPI cards for current month
    curr_sub   = kotak["subscribers"]
    prev_sub   = hist_sub(last6[-1]) if last6 else None
    sub_growth = pct(curr_sub, prev_sub) if prev_sub else "—"
    sub_growth_abs = f"+{fmt(curr_sub - prev_sub)}" if prev_sub and curr_sub > prev_sub else (fmt(curr_sub - prev_sub) if prev_sub else "—")
    sg_color   = pct_color(sub_growth)

    kpis = [
        ("No. of Posts",      str(kotak["posts"]),        C["blue"],    "#fff"),
        ("Total Views",       kotak["views_fmt"],          C["purple"],  "#fff"),
        ("Total Engagement",  kotak["eng_fmt"],            "#1F6B2E",    "#fff"),
        ("Subscriber Growth", f'{sub_growth_abs}<br><span style="font-size:16px">{sub_growth}</span>', sg_color if sg_color != "#333" else C["darkblue"], "#fff"),
    ]
    kpi_cards = ""
    for label, value, bg, fc in kpis:
        kpi_cards += f"""
        <div class="kpi-card" style="background:{bg};">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{fc};">{value}</div>
        </div>"""

    note = (f"Kotak Neo posted {kotak['posts']} videos in {month}, "
            f"generating {kotak['views_fmt']} views and {kotak['eng_fmt']} engagements.")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#004B91;}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
.section-lbl{{font-size:10px;font-weight:700;color:#888;text-transform:uppercase;
              letter-spacing:2px;margin:14px 0 7px;}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;}}
thead th{{color:#fff;font-weight:700;padding:11px 4px;font-size:12.5px;
          border:1px solid #003570;text-align:center;}}
td{{padding:11px 4px;text-align:center;border:1px solid #e4e8f0;font-size:14px;font-weight:700;}}
.kpi-row{{display:flex;gap:14px;margin-top:16px;}}
.kpi-card{{flex:1;border-radius:12px;padding:18px 16px;display:flex;flex-direction:column;
           align-items:center;justify-content:center;text-align:center;
           box-shadow:0 4px 18px rgba(0,0,0,0.12);}}
.kpi-label{{font-size:11px;color:rgba(255,255,255,0.8);font-weight:600;
             letter-spacing:0.5px;text-transform:uppercase;margin-bottom:8px;}}
.kpi-value{{font-size:28px;font-weight:900;color:#fff;line-height:1.1;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Brand Deep-Dive</div>
    <div class="slide-title">Kotak Neo M-O-M Comparison</div>
    <div class="hline"></div>
    <div class="section-lbl">Subscriber Trend</div>
    <table>
      <thead><tr>
        <th style="background:#1F4F78;border:1px solid #163a5a;text-align:left;padding-left:12px;width:90px;">Month</th>
        {header_cells}
      </tr></thead>
      <tbody>
        <tr>
          <td style="font-weight:700;font-size:13px;border:1px solid #ddd;background:#f0f4fa;text-align:left;padding-left:12px;">Subscribers</td>
          {sub_cells}
        </tr>
      </tbody>
    </table>
    <div class="section-lbl">{month} — Current Month Performance</div>
    <div class="kpi-row">{kpi_cards}</div>
    <div class="note">{note}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 6 — KEY METRICS TABLE
# ═══════════════════════════════════════════════════════════════════════
def slide_key_metrics(s, page):
    month = s["month"]
    st    = s["stats"]

    metrics = [
        ("Followers",        [st[b]["subs_fmt"]      for b in BRANDS]),
        ("Prev Month Subs",  [st[b]["prev_subs_fmt"]  for b in BRANDS]),
        ("Change in Followers", [st[b]["sub_growth"]  for b in BRANDS]),
        ("No. of Posts",     [str(st[b]["posts"])     for b in BRANDS]),
        ("Total Views",      [st[b]["views_fmt"]      for b in BRANDS]),
        ("Total Engagement", [st[b]["eng_fmt"]        for b in BRANDS]),
    ]

    header_html = '<th class="metric-col">Metrics</th>' + "".join(
        f'<th class="{"kotak-col" if b == "Kotak Neo" else ""}">'
        f'{"Kotak Neo" if b == "Kotak Neo" else b.replace("Markets By Zerodha","Mkt. Zerodha")}</th>'
        for b in BRANDS
    )

    rows_html = ""
    for ri, (label, vals) in enumerate(metrics):
        bg = C["pink"] if ri % 2 == 0 else "#fff"
        cells = f'<td class="metric-label">{label}</td>'
        for bi, (b, v) in enumerate(zip(BRANDS, vals)):
            is_k = (b == "Kotak Neo")
            style = "background:#E8F0FA;" if is_k else f"background:{bg};"
            if label == "Change in Followers":
                style += f"color:{pct_color(str(v))};"
            cells += f'<td style="{style}">{v}</td>'
        rows_html += f'<tr>{cells}</tr>'

    note = (f"*Engagement = Likes + Comments  |  Data as of {month}  |  "
            "Indicative of leader in a metric — may change each month")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#FFC200;}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:10px;}}
th{{background:#FFC200;color:#111;font-weight:700;padding:11px 4px;
    text-align:center;font-size:12.5px;border:1px solid #d4a900;}}
th.metric-col{{text-align:left;padding-left:12px;width:148px;}}
th.kotak-col{{background:#004B91;color:#fff;border-color:#003570;}}
td{{padding:9px 4px;text-align:center;border:1px solid #e4e8f0;font-size:13px;
    color:#1a1a2e;font-weight:600;vertical-align:middle;}}
td.metric-label{{text-align:left;padding-left:12px;font-weight:700;width:148px;font-size:13px;}}
tr:nth-child(even) td{{background:#f5f8ff;}}
tr:nth-child(even) td.metric-label{{background:#f5f8ff;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Performance Overview</div>
    <div class="slide-title">YouTube — Key Metrics</div>
    <div class="hline"></div>
    <table>
      <thead><tr>{header_html}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div class="note">{note}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 7 — ENGAGEMENT CHART (Python SVG — connected gold line)
# ═══════════════════════════════════════════════════════════════════════
def slide_engagement_chart(s, page):
    month      = s["month"]
    st         = s["stats"]
    r          = s["rankings"]
    eng_leader = r["by_engagement"][0]
    kotak_rank = s["kotak_rank"]["engagement"]
    kotak_eng  = st["Kotak Neo"]["eng_fmt"]

    # Sort by engagement descending for the chart
    chart_data = sorted(
        [{"brand": b, "short": SHORT[BRANDS.index(b)],
          "engagement": st[b]["engagement"], "eng_fmt": st[b]["eng_fmt"],
          "posts": st[b]["posts"]} for b in BRANDS],
        key=lambda x: x["engagement"], reverse=True
    )

    svg = build_bar_chart_svg(
        chart_data, "engagement", "eng_fmt",
        bar_color=C["purple"], line_color=C["gold"],
        svg_w=870, svg_h=420, pad_left=20, pad_right=20, pad_top=50, pad_bottom=70
    )

    insights = [
        f"<b>{eng_leader}</b> leads total engagement this month among all 8 brands.",
        f"Kotak Neo holds <b>#{kotak_rank}</b> position with {kotak_eng} engagement.",
        "Gold connected line shows No. of Posts per brand.",
        "Purple bars = Likes + Comments (Engagement).",
    ]
    ins_html = "".join(
        f'<div class="ins"><span class="ins-dot"></span><span>{i}</span></div>'
        for i in insights
    )
    headline = (f"Kotak Neo ranks #{kotak_rank} in total engagement — "
                f"{eng_leader} leads with {st[eng_leader]['eng_fmt']} interactions")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:{C['purple']};}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
.headline{{font-size:14.5px;font-weight:600;color:#1F4F78;margin:7px 0 4px;line-height:1.45;
           padding:9px 14px;background:#F0F0FA;border-radius:7px;border-left:3px solid {C['purple']};}}
.layout{{display:flex;gap:14px;flex:1;margin-top:8px;}}
.chart-area{{flex:0 0 860px;display:flex;flex-direction:column;}}
.fig-title{{font-size:12px;font-weight:600;color:#666;margin-bottom:4px;text-align:center;
            letter-spacing:0.5px;text-transform:uppercase;}}
.insights-panel{{flex:1;background:#fff;border-radius:10px;border:1px solid #e8eaf6;
                 padding:16px 14px;display:flex;flex-direction:column;gap:12px;justify-content:center;
                 box-shadow:0 2px 12px rgba(0,0,0,0.06);}}
.ins{{display:flex;align-items:flex-start;gap:9px;font-size:13px;color:#333;line-height:1.6;}}
.ins-dot{{min-width:7px;height:7px;background:{C['red']};border-radius:50%;margin-top:5px;flex-shrink:0;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Competitive Analysis</div>
    <div class="slide-title">YouTube — Overview (Engagement)</div>
    <div class="hline"></div>
    <div class="headline">{headline}</div>
    <div class="layout">
      <div class="chart-area">
        <div class="fig-title">No. of Posts vs Total Engagement</div>
        {svg}
      </div>
      <div class="insights-panel">{ins_html}</div>
    </div>
    <div class="note">*Engagement = Likes + Comments &nbsp;|&nbsp; Data as of {month}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE 8 — VIEWS CHART (connected gold line)
# ═══════════════════════════════════════════════════════════════════════
def slide_views_chart(s, page):
    month        = s["month"]
    st           = s["stats"]
    r            = s["rankings"]
    views_leader = r["by_views"][0]
    kotak_rank   = s["kotak_rank"]["views"]
    kotak_views  = st["Kotak Neo"]["views_fmt"]

    chart_data = sorted(
        [{"brand": b, "short": SHORT[BRANDS.index(b)],
          "engagement": st[b]["recent_views"], "eng_fmt": st[b]["views_fmt"],
          "posts": st[b]["posts"]} for b in BRANDS],
        key=lambda x: x["engagement"], reverse=True
    )

    svg = build_bar_chart_svg(
        chart_data, "engagement", "eng_fmt",
        bar_color=C["blue"], line_color=C["gold"],
        svg_w=870, svg_h=420, pad_left=20, pad_right=20, pad_top=50, pad_bottom=70
    )

    insights = [
        f"<b>{views_leader}</b> leads total views this month among all 8 brands.",
        f"Kotak Neo holds <b>#{kotak_rank}</b> position with {kotak_views} views.",
        "Gold connected line shows No. of Posts per brand.",
        "Blue bars represent total recent views.",
    ]
    ins_html = "".join(
        f'<div class="ins"><span class="ins-dot"></span><span>{i}</span></div>'
        for i in insights
    )
    headline = (f"Kotak Neo ranks #{kotak_rank} in total views — "
                f"{views_leader} leads with {st[views_leader]['views_fmt']} views")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:{C['blue']};}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
.headline{{font-size:14.5px;font-weight:600;color:#1F4F78;margin:7px 0 4px;line-height:1.45;
           padding:9px 14px;background:#EEF4FF;border-radius:7px;border-left:3px solid {C['blue']};}}
.layout{{display:flex;gap:14px;flex:1;margin-top:8px;}}
.chart-area{{flex:0 0 860px;display:flex;flex-direction:column;}}
.fig-title{{font-size:12px;font-weight:600;color:#666;margin-bottom:4px;text-align:center;
            letter-spacing:0.5px;text-transform:uppercase;}}
.insights-panel{{flex:1;background:#fff;border-radius:10px;border:1px solid #e4eaf8;
                 padding:16px 14px;display:flex;flex-direction:column;gap:12px;justify-content:center;
                 box-shadow:0 2px 12px rgba(0,0,0,0.06);}}
.ins{{display:flex;align-items:flex-start;gap:9px;font-size:13px;color:#333;line-height:1.6;}}
.ins-dot{{min-width:7px;height:7px;background:{C['red']};border-radius:50%;margin-top:5px;flex-shrink:0;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Competitive Analysis</div>
    <div class="slide-title">YouTube — Overview (Views)</div>
    <div class="hline"></div>
    <div class="headline">{headline}</div>
    <div class="layout">
      <div class="chart-area">
        <div class="fig-title">No. of Posts vs Total Views</div>
        {svg}
      </div>
      <div class="insights-panel">{ins_html}</div>
    </div>
    <div class="note">*Data as of {month}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — TOP 3 POSTS (per brand — large thumbnails, fills full height)
# ═══════════════════════════════════════════════════════════════════════
def slide_top3_posts(s, brand, page):
    month  = s["month"]
    videos = s["top3_videos"].get(brand, [])

    def _int(x):
        if isinstance(x, str): x = x.replace(",","")
        try: return int(x)
        except: return 0

    engagement_sorted = sorted(videos[:5], key=lambda v: _int(v.get("likes",0))+_int(v.get("comments",0)), reverse=True)
    top3 = engagement_sorted[:3]

    urls = []
    cards_html = ""
    for vi, v in enumerate(top3):
        eng = _int(v.get("likes", 0)) + _int(v.get("comments", 0))
        url = v.get("url", "")
        urls.append(url)
        cards_html += f"""
        <div class="card">
          <div class="thumb-wrap">
            <img src="{v['thumb']}" class="thumb" alt="thumbnail"
                 onerror="this.style.background='#1F4F78';this.src=''">
          </div>
          <table class="stats-tbl">
            <tr class="eng-row">
              <td class="slbl-eng">Engagement</td>
              <td class="sval-eng">{fmt(eng)}</td>
            </tr>
            <tr class="alt-row">
              <td class="slbl">Likes</td>
              <td class="sval">{fmt(_int(v.get('likes',0)))}</td>
            </tr>
            <tr>
              <td class="slbl">Comments</td>
              <td class="sval">{fmt(_int(v.get('comments',0)))}</td>
            </tr>
            <tr class="alt-row">
              <td class="slbl">Post Link</td>
              <td class="sval link-cell">&#128279; Click here</td>
            </tr>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#DC143C;}}
.main{{padding:20px 28px 46px 34px;display:flex;flex-direction:column;height:720px;}}
.slide-title{{font-size:26px;font-weight:800;color:#004B91;
              font-family:'Outfit',Arial,sans-serif;}}
.hline{{height:2px;width:100%;margin:8px 0 14px;
        background:linear-gradient(90deg,#004B91 0%,#DC143C 22%,rgba(0,75,145,0.2) 60%,transparent 100%);}}
.cards{{display:flex;gap:18px;flex:1;align-items:flex-start;}}
.card{{flex:1;background:#fff;border-radius:4px;border:1px solid #dde3ee;
       display:flex;flex-direction:column;overflow:hidden;}}
.thumb-wrap{{width:100%;height:320px;overflow:hidden;background:#e8ecf5;flex-shrink:0;}}
.thumb{{width:100%;height:320px;object-fit:cover;object-position:center top;display:block;}}
.stats-tbl{{width:100%;border-collapse:collapse;}}
.stats-tbl td{{padding:9px 12px;font-size:15px;border-bottom:1px solid #e8eaf0;}}
.eng-row td{{background:#fff;border-top:2px solid #DC143C;}}
.slbl-eng{{font-weight:800;color:#111;font-size:16px;}}
.sval-eng{{font-weight:900;color:#111;font-size:16px;text-align:right;}}
.alt-row td{{background:#FFF0F0;}}
.slbl{{font-weight:600;color:#333;font-size:15px;}}
.sval{{color:#111;font-weight:700;font-size:15px;text-align:right;}}
.link-cell{{color:#004B91;font-size:14px;font-weight:700;text-align:right;text-decoration:underline;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-title">{brand} Top 3 posts</div>
    <div class="hline"></div>
    <div class="cards">{cards_html}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""
    return html, urls


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — GROWTH SUMMARY (fills full height, 55px rows)
# ═══════════════════════════════════════════════════════════════════════
def slide_growth(s, page):
    month  = s["month"]
    st     = s["stats"]

    def growth_row(bi, brand):
        curr = st[brand]["subscribers"]
        prev = HIST_SUBS.get(brand, [0])[-1] or 0
        g    = pct(curr, prev)
        gc   = pct_color(g)
        bg   = "#fff" if bi % 2 == 0 else C["pink"]
        bold = "font-weight:700;" if brand == "Kotak Neo" else ""
        return (f'<tr style="background:{bg}">'
                f'<td class="brand-td" style="{bold}">{brand}</td>'
                f'<td>{fmt(prev, short=True)}</td>'
                f'<td>{fmt(curr, short=True)}</td>'
                f'<td style="color:{gc};font-weight:600;">{g}</td>'
                f'<td>{st[brand]["posts"]}</td>'
                f'<td>{st[brand]["views_fmt"]}</td>'
                f'<td>{st[brand]["eng_fmt"]}</td>'
                f'</tr>')

    rows_html = ""
    for bi, brand in enumerate(BRANDS):
        rows_html += growth_row(bi, brand)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#FFC200;}}
.main{{padding:22px 24px 46px 30px;display:flex;flex-direction:column;}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:10px;}}
th{{background:#1F4F78;color:#fff;font-weight:700;padding:12px 5px;
    text-align:center;border:1px solid #163a5a;font-size:13px;}}
th:first-child{{text-align:left;padding-left:12px;}}
td{{padding:10px 5px;text-align:center;border:1px solid #e4e8f0;
    font-size:13.5px;color:#1a1a2e;font-weight:600;vertical-align:middle;height:60px;}}
td.brand-td{{text-align:left;padding-left:12px;min-width:155px;font-size:14px;font-weight:700;}}
tr:nth-child(even) td{{background:#f4f7ff;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Performance Summary</div>
    <div class="slide-title">Growth Summary — {month}</div>
    <div class="hline"></div>
    <table>
      <thead>
        <tr>
          <th>Brand</th>
          <th>Prev Subs</th>
          <th>Current Subs</th>
          <th>Growth %</th>
          <th>Posts</th>
          <th>Total Views</th>
          <th>Engagement</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div class="note">*Prev Subs = {HIST_MONTHS[-1]} tracked data &nbsp;|&nbsp; Engagement = Likes + Comments &nbsp;|&nbsp; Data as of {month}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — METHODOLOGY
# ═══════════════════════════════════════════════════════════════════════
def slide_methodology(s, page):
    month  = s["month"]
    points = [
        "YouTube data fetched live via YouTube Data API v3 using uploads playlist enumeration (1 quota unit/page).",
        "Subscriber counts: current value from API for latest month; historical data (Oct-24 to Jun-26) from tracked records.",
        "Views and Engagement aggregated from recent videos (up to 15 per channel) fetched each run.",
        "Engagement = Likes + Comments. YouTube removed public share counts from API in 2015.",
        "For high-volume channels, up to 15 videos per channel fetched to ensure reasonable coverage.",
        "Follower growth % = ((Current - Previous) / Previous) x 100. Green = positive, Red = decline.",
        "Video thumbnails embedded directly from YouTube CDN (img.youtube.com/vi/{id}/mqdefault.jpg).",
        "PDF report generated with Python-built HTML/CSS slides, rendered via Chrome headless.",
        "Report is auto-generated — all data refreshes each time this script is called.",
    ]

    items_html = "".join(
        f'<div class="bullet"><div class="dot">{i+1}</div><div class="btext">{p}</div></div>'
        for i, p in enumerate(points)
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
.slide{{background:#fafbff;}}
.accent-bar{{position:absolute;left:0;top:0;width:5px;height:100%;background:#004B91;}}
.main{{padding:28px 44px 48px 54px;height:720px;display:flex;flex-direction:column;}}
.bullets-wrap{{margin-top:14px;flex:1;display:grid;grid-template-columns:1fr 1fr;
               gap:8px;align-content:start;}}
.bullet{{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;
         border-radius:7px;background:#fff;border:1px solid #e8edf8;
         box-shadow:0 1px 5px rgba(0,0,0,0.05);}}
.dot{{min-width:20px;height:20px;background:#EEF4FF;border-radius:6px;
      display:flex;align-items:center;justify-content:center;
      font-size:11px;font-weight:800;color:{C['blue']};flex-shrink:0;margin-top:1px;}}
.btext{{font-size:13px;color:#2a2a40;line-height:1.6;}}
</style>
</head>
<body>
<div class="slide">
  <div class="accent-bar"></div>
  <div class="main">
    <div class="slide-tag">Appendix</div>
    <div class="slide-title">Methodology &amp; Formula Calculations</div>
    <div class="hline"></div>
    <div class="bullets-wrap">{items_html}</div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — THANK YOU (content properly centered)
# ═══════════════════════════════════════════════════════════════════════
def slide_thank_you(page):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#003570;}}
.left-panel{{position:absolute;left:0;top:0;width:580px;height:720px;
             background:linear-gradient(160deg,#004B91 0%,#001a3d 100%);
             display:flex;flex-direction:column;justify-content:center;
             align-items:flex-start;padding:60px 56px;}}
.right-panel{{position:absolute;right:0;top:0;width:700px;height:720px;
              background:#002d62;
              display:flex;flex-direction:column;justify-content:center;
              align-items:center;padding:40px;}}
.ty-text{{font-family:'Outfit',Arial,sans-serif;font-size:72px;font-weight:900;
          color:#fff;line-height:1;letter-spacing:-2px;}}
.ty-sub{{font-size:16px;color:rgba(255,255,255,0.6);margin-top:16px;letter-spacing:0.5px;}}
.red-rule{{width:60px;height:4px;background:#DC143C;border-radius:2px;margin:20px 0;}}
.info-block{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);
             border-radius:10px;padding:22px 24px;width:100%;max-width:420px;}}
.info-row{{display:flex;justify-content:space-between;align-items:center;
           padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.08);}}
.info-row:last-child{{border-bottom:none;}}
.info-label{{font-size:11px;color:rgba(255,255,255,0.5);font-weight:600;letter-spacing:1px;text-transform:uppercase;}}
.info-value{{font-size:13px;color:#fff;font-weight:600;}}
</style>
</head>
<body>
<div class="slide">
  <div style="position:absolute;width:400px;height:400px;border-radius:50%;
              background:rgba(220,20,60,0.06);top:-80px;right:300px;"></div>
  <div style="position:absolute;width:180px;height:180px;border-radius:50%;
              background:rgba(255,194,0,0.05);bottom:80px;right:120px;"></div>
  <div class="left-panel">
    <div class="ty-text">Thank<br>You!</div>
    <div class="red-rule"></div>
    <div class="ty-sub">YouTube Competitor Analysis Report<br>Prepared by Kotak Securities</div>
  </div>
  <div class="right-panel">
    <div class="info-block">
      <div class="info-row">
        <span class="info-label">Report Type</span>
        <span class="info-value">Monthly Competitor Analysis</span>
      </div>
      <div class="info-row">
        <span class="info-label">Platform</span>
        <span class="info-value">YouTube</span>
      </div>
      <div class="info-row">
        <span class="info-label">Brands Tracked</span>
        <span class="info-value">8 Fintech Channels</span>
      </div>
      <div class="info-row">
        <span class="info-label">Data Source</span>
        <span class="info-value">YouTube Data API v3</span>
      </div>
      <div class="info-row">
        <span class="info-label">Engagement</span>
        <span class="info-value">Likes + Comments</span>
      </div>
    </div>
  </div>
  {FOOTER_HTML}
  {page_num(page)}
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — MONTHLY SCORECARD (Slide 1 of new section)
# ═══════════════════════════════════════════════════════════════════════
def slide_scorecard(s, page):
    st    = s["stats"]
    month = s["month"]
    r     = s["rankings"]
    k     = s["kotak_rank"]

    kotak    = st["Kotak Neo"]
    eng_ldr  = r["by_engagement"][0]
    views_ldr= r["by_views"][0]

    # Build 6 KPI cards: IG Engagement, IG Views, YT Views, YT Engagement, X Views, X Engagement
    # IG data not available yet — show placeholder
    # YT data is live
    yt_eng_rank  = k["engagement"]
    yt_view_rank = k["views"]
    yt_eng_val   = kotak["eng_fmt"]
    yt_view_val  = kotak["views_fmt"]
    yt_eng_ldr_val = st[r["by_engagement"][0]]["eng_fmt"]
    yt_view_ldr_val= st[r["by_views"][0]]["views_fmt"]

    def card(platform_color, platform_icon, platform_name, metric_name,
             rank, brand, value, subtext, status):
        status_colors = {
            "leader":  ("#1cb86e","#e6f9f0","#b5efd4"),
            "watch":   ("#d4860a","#fff4e0","#fcd98a"),
            "improve": ("#c94a1e","#fdeee7","#f5b8a0"),
        }
        sc, sbg, sbr = status_colors.get(status, status_colors["watch"])
        top_border_colors = {
            "leader":  "linear-gradient(90deg,#1cb86e,#2ecc8f)",
            "watch":   "linear-gradient(90deg,#f5a623,#f7bc5a)",
            "improve": "linear-gradient(90deg,#e05a2b,#f07c51)",
        }
        tbc = top_border_colors.get(status, top_border_colors["watch"])
        return f"""
        <div style="background:#fff;border-radius:12px;padding:18px 20px 16px;
                    display:flex;flex-direction:column;justify-content:space-between;
                    box-shadow:0 2px 8px rgba(0,48,135,0.07),0 0 0 1px rgba(0,48,135,0.06);
                    position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:3px;
                      background:{tbc};border-radius:12px 12px 0 0;"></div>
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;">
            <div>
              <div style="display:flex;align-items:center;gap:5px;margin-bottom:3px;">
                <span style="width:18px;height:18px;border-radius:4px;background:{platform_color};
                             display:inline-flex;align-items:center;justify-content:center;
                             font-size:9px;font-weight:900;color:#fff;">{platform_icon}</span>
                <span style="font-size:10px;font-weight:600;color:#9aa5c0;
                             letter-spacing:0.1em;text-transform:uppercase;">{platform_name}</span>
              </div>
              <div style="font-size:13px;font-weight:600;color:#3d4f6e;">{metric_name}</div>
            </div>
            <span style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                         padding:4px 10px;border-radius:100px;flex-shrink:0;margin-top:2px;
                         background:{sbg};color:{sc};border:1px solid {sbr};">{status.title()}</span>
          </div>
          <div>
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px;">
              <span style="font-size:12px;font-weight:600;color:#003087;
                           background:#eef2fb;padding:2px 8px;border-radius:4px;">#{rank}</span>
              <span style="font-size:13px;font-weight:700;color:#003087;">{brand}</span>
            </div>
            <div style="font-size:26px;font-weight:800;color:#111827;
                        letter-spacing:-0.02em;line-height:1.1;">{value}</div>
            <div style="font-size:12px;color:#7b8bad;line-height:1.4;margin-top:4px;">{subtext}</div>
          </div>
        </div>"""

    cards_html = (
        card("linear-gradient(135deg,#f09433,#dc2743,#bc1888)", "IG", "Instagram",
             "Engagement", "—", "Kotak Neo", "—", "Instagram data — coming soon", "watch") +
        card("linear-gradient(135deg,#f09433,#dc2743,#bc1888)", "IG", "Instagram",
             "Views", "—", "Kotak Neo", "—", "Instagram data — coming soon", "watch") +
        card("#FF0000", "▶", "YouTube", "Views",
             yt_view_rank, "Kotak Neo", yt_view_val,
             f"{views_ldr} leads at {yt_view_ldr_val}",
             "leader" if yt_view_rank == 1 else ("watch" if yt_view_rank <= 3 else "improve")) +
        card("#FF0000", "▶", "YouTube", "Engagement",
             yt_eng_rank, "Kotak Neo", yt_eng_val,
             f"{eng_ldr} leads at {yt_eng_ldr_val}",
             "leader" if yt_eng_rank == 1 else ("watch" if yt_eng_rank <= 3 else "improve")) +
        card("#000", "X", "X (Twitter)", "Views",
             "—", "Kotak Neo", "—", "Twitter data — coming soon", "watch") +
        card("#000", "X", "X (Twitter)", "Engagement",
             "—", "Kotak Neo", "—", "Twitter data — coming soon", "watch")
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#f7f9fc;}}
.slide{{background:#fff;}}
.hdr{{background:#003087;padding:0 48px;height:88px;display:flex;align-items:center;
       justify-content:space-between;flex-shrink:0;}}
.hdr-left{{display:flex;align-items:center;gap:16px;}}
.logo-mark{{width:40px;height:40px;background:#E31837;border-radius:6px;
            display:flex;align-items:center;justify-content:center;}}
.logo-mark svg{{width:24px;height:24px;fill:#fff;}}
.logo-brand{{font-size:18px;font-weight:800;color:#fff;letter-spacing:0.02em;}}
.logo-sub{{font-size:11px;font-weight:400;color:rgba(255,255,255,0.55);
           letter-spacing:0.08em;text-transform:uppercase;margin-top:2px;}}
.hdr-div{{width:1px;height:36px;background:rgba(255,255,255,0.2);}}
.hdr-title{{font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.01em;}}
.hdr-label{{font-size:11px;font-weight:500;color:rgba(255,255,255,0.5);
            letter-spacing:0.12em;text-transform:uppercase;}}
.hdr-period{{font-size:13px;font-weight:600;color:rgba(255,255,255,0.9);}}
.acc{{height:4px;background:linear-gradient(90deg,#E31837 0%,#ff5c6e 50%,#E31837 100%);}}
.body{{padding:22px 48px 18px;display:flex;flex-direction:column;gap:12px;
       background:#f7f9fc;flex:1;}}
.sec-label{{font-size:11px;font-weight:600;color:#7b8bad;letter-spacing:0.14em;text-transform:uppercase;}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);
       gap:16px;flex:1;}}
.ftr{{height:40px;background:#fff;border-top:3px solid #E31837;
      display:flex;align-items:center;justify-content:space-between;padding:0 48px;}}
.ftr span{{font-size:11px;color:#9aa5c0;font-weight:500;letter-spacing:0.08em;}}
</style>
</head>
<body>
<div class="slide">
  <div class="hdr">
    <div class="hdr-left">
      <div style="display:flex;align-items:center;">{LOGO_IMG}</div>
      <div class="hdr-div"></div>
      <div><div class="hdr-label">Monthly Scorecard</div><div class="hdr-title">Platform Performance at a Glance</div></div>
    </div>
    <div style="text-align:right;">
      <div class="hdr-period">Content Observations — {month}</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.5);letter-spacing:0.1em;text-transform:uppercase;">Competitive Benchmarking</div>
    </div>
  </div>
  <div class="acc"></div>
  <div class="body">
    <div class="sec-label">Kotak Neo vs Industry — YouTube Live · Instagram &amp; Twitter Coming Soon</div>
    <div class="grid">{cards_html}</div>
  </div>
  <div class="ftr">
    <span>Monthly Social Media Benchmarking Report</span>
    <span>Kotak Securities · {month} · Slide {page}</span>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — FOLLOWER GROWTH TREND (line chart — YouTube subscriber growth %)
# ═══════════════════════════════════════════════════════════════════════
def slide_follower_trend(s, page):
    month = s["month"]
    st    = s["stats"]

    # Use last 9 months of HIST_MONTHS + current for the chart
    # Use last 8 HIST_MONTHS that actually have data, plus current month
    curr_m = month[:3] + "-" + month[-2:]
    # Exclude current month label if it accidentally exists in HIST_MONTHS
    available = [m for m in HIST_MONTHS if m != curr_m]
    chart_months = available[-8:]
    all_m  = chart_months + [curr_m]

    # Brand colors
    brand_colors = {
        "Kotak Neo":          "#003087",
        "Angel One":          "#dc2626",
        "Dhan":               "#F97316",
        "Groww":              "#10B981",
        "INDmoney":           "#8B5CF6",
        "Markets By Zerodha": "#EF4444",
        "Upstox":             "#6366F1",
        "Zerodha":            "#64748b",
    }

    # Build normalized % growth from first month baseline
    lines_svg = []
    end_labels = []

    svg_w, svg_h = 920, 390
    pad_l, pad_r, pad_t, pad_b = 60, 80, 20, 50
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b
    n_pts   = len(all_m)
    x_step  = chart_w / (n_pts - 1)

    # Calculate growth % from baseline for each brand
    # Baseline = first historical month in chart_months
    brand_series = {}
    for brand in BRANDS:
        hist = HIST_SUBS.get(brand, [])
        vals = []
        for m in chart_months:
            idx = HIST_MONTHS.index(m) if m in HIST_MONTHS else -1
            v = hist[idx] if 0 <= idx < len(hist) else None
            vals.append(v)
        vals.append(st[brand]["subscribers"])
        # Use the value from 1 step before chart_months as baseline for meaningful spread
        first_chart_idx = HIST_MONTHS.index(chart_months[0]) if chart_months[0] in HIST_MONTHS else -1
        baseline_idx = first_chart_idx - 1 if first_chart_idx > 0 else first_chart_idx
        baseline = hist[baseline_idx] if 0 <= baseline_idx < len(hist) else None
        if not baseline:
            baseline = next((v for v in vals if v), None)
        if not baseline:
            continue
        pct_series = [((v - baseline) / baseline * 100) if v else None for v in vals]
        # Replace None with carry-forward of previous value
        for i in range(len(pct_series)):
            if pct_series[i] is None:
                pct_series[i] = pct_series[i-1] if i > 0 else 0
        brand_series[brand] = pct_series

    # Y axis range
    all_vals = [v for series in brand_series.values() for v in series]
    max_pct  = max(all_vals) if all_vals else 70
    min_pct  = min(0, min(all_vals)) if all_vals else 0
    y_range  = max_pct - min_pct or 1

    def y_coord(pct):
        return pad_t + chart_h - int((pct - min_pct) / y_range * chart_h)

    def x_coord(i):
        return int(pad_l + i * x_step)

    # Grid lines at 4 levels
    grid_svg = []
    for level in [0, 0.33, 0.66, 1.0]:
        pct_val = min_pct + level * y_range
        gy = y_coord(pct_val)
        grid_svg.append(f'<line x1="{pad_l}" y1="{gy}" x2="{pad_l+chart_w}" y2="{gy}" stroke="#f0f2f5" stroke-width="1" stroke-dasharray="4,3"/>')
        grid_svg.append(f'<text x="{pad_l-6}" y="{gy+4}" text-anchor="end" font-size="10" fill="#999">+{pct_val:.0f}%</text>')

    # Axes
    grid_svg.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#e0e4ed" stroke-width="1"/>')
    grid_svg.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#e0e4ed" stroke-width="1"/>')

    # X axis labels
    for i, m in enumerate(all_m):
        xp = x_coord(i)
        grid_svg.append(f'<text x="{xp}" y="{pad_t+chart_h+18}" text-anchor="middle" font-size="11" fill="#666">{m}</text>')

    # Draw non-Kotak lines first (dimmed)
    for brand in BRANDS:
        if brand == "Kotak Neo" or brand not in brand_series:
            continue
        series = brand_series[brand]
        color  = brand_colors.get(brand, "#aaa")
        pts    = " ".join(f"{x_coord(i)},{y_coord(v)}" for i, v in enumerate(series))
        lines_svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" opacity="0.55" points="{pts}"/>')
        # Collect end label: (raw_y, color, short_name, value_str)
        last_y = y_coord(series[-1])
        short  = brand.replace("Markets By Zerodha", "Mkt.Zerodha")[:12]
        end_labels.append([last_y, color, short, f"+{series[-1]:.1f}%", False])

    # Draw Kotak Neo last (bold, highlighted)
    if "Kotak Neo" in brand_series:
        series = brand_series["Kotak Neo"]
        pts    = " ".join(f"{x_coord(i)},{y_coord(v)}" for i, v in enumerate(series))
        lines_svg.append(f'<polyline fill="none" stroke="#003087" stroke-width="3" points="{pts}"/>')
        for i, v in enumerate(series):
            xp = x_coord(i); yp = y_coord(v)
            r  = 5 if i < len(series)-1 else 6
            sw = "" if i < len(series)-1 else ' stroke="white" stroke-width="2"'
            lines_svg.append(f'<circle cx="{xp}" cy="{yp}" r="{r}" fill="#003087"{sw}/>')
        last_y = y_coord(series[-1])
        end_labels.append([last_y, "#003087", "Kotak Neo", f"+{series[-1]:.1f}%", True])

    # De-overlap end labels: sort by y, push apart if within 13px
    end_labels.sort(key=lambda x: x[0])
    min_gap = 13
    for i in range(1, len(end_labels)):
        if end_labels[i][0] - end_labels[i-1][0] < min_gap:
            end_labels[i][0] = end_labels[i-1][0] + min_gap

    label_svgs = []
    for (ly, color, short, val_str, is_kotak) in end_labels:
        lx = pad_l + chart_w + 5
        if is_kotak:
            label_svgs.append(f'<text x="{lx}" y="{ly+4}" font-size="11" font-weight="700" fill="{color}">{val_str}</text>')
        else:
            label_svgs.append(f'<text x="{lx}" y="{ly+4}" font-size="10" fill="{color}">{short}</text>')

    svg = f"""<svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}" style="overflow:visible;font-family:Inter,sans-serif;">
      {''.join(grid_svg)}
      {''.join(lines_svg)}
      {''.join(label_svgs)}
    </svg>"""

    # Sidebar: current month gain per brand
    kotak_curr = st["Kotak Neo"]["subscribers"]
    kotak_prev = HIST_SUBS["Kotak Neo"][-1] if HIST_SUBS.get("Kotak Neo") else kotak_curr
    kotak_gain = kotak_curr - kotak_prev

    sidebar_rows = ""
    for brand in BRANDS:
        curr = st[brand]["subscribers"]
        hist = HIST_SUBS.get(brand, [])
        prev = hist[-1] if hist else curr
        gain = curr - prev
        color = brand_colors.get(brand, "#888")
        gain_color = "#16a34a" if gain >= 0 else "#dc2626"
        gain_str = f"+{fmt(gain)}" if gain >= 0 else fmt(gain)
        short = brand.replace("Markets By Zerodha", "Mkt.Zerodha")
        sidebar_rows += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;
                    border-radius:8px;background:#fff;
                    box-shadow:0 1px 4px rgba(0,0,0,0.06);
                    {'border:1px solid #fcc;background:#fff0f0;' if gain < 0 else ''}">
          <div style="width:10px;height:10px;border-radius:50%;background:{color};flex-shrink:0;"></div>
          <div style="flex:1;">
            <div style="display:flex;justify-content:space-between;">
              <span style="font-size:12px;font-weight:600;color:#333;">{short}</span>
              <span style="font-size:12px;font-weight:700;color:{gain_color};">{gain_str}</span>
            </div>
          </div>
        </div>"""

    insight_brand = max(BRANDS, key=lambda b: st[b]["subscribers"] - (HIST_SUBS.get(b, [st[b]["subscribers"]])[-1] or st[b]["subscribers"]))
    insight_gain  = fmt(st[insight_brand]["subscribers"] - (HIST_SUBS.get(insight_brand, [0])[-1] or 0))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#f7f9fc;}}
.slide{{background:#fff;display:flex;flex-direction:column;}}
.hdr{{background:#003087;padding:0 32px;height:72px;display:flex;align-items:center;
       justify-content:space-between;flex-shrink:0;color:#fff;}}
.acc{{height:4px;background:linear-gradient(90deg,#E31837,#003087);flex-shrink:0;}}
.body{{flex:1;display:flex;overflow:hidden;}}
.chart-area{{flex:1;padding:18px 20px 14px 28px;display:flex;flex-direction:column;}}
.sidebar{{width:240px;background:#f8f9fc;border-left:1px solid #e8eaf0;
          padding:18px 16px;display:flex;flex-direction:column;gap:7px;}}
.ftr{{height:36px;border-top:3px solid #E31837;display:flex;align-items:center;
      justify-content:space-between;padding:0 32px;flex-shrink:0;}}
.ftr span{{font-size:11px;color:#888;}}
</style>
</head>
<body>
<div class="slide">
  <div class="hdr">
    <div style="font-size:20px;font-weight:600;color:#fff;">YouTube Subscriber Growth Trend</div>
    <div style="font-size:13px;opacity:0.7;color:#fff;">Content Observations · {month}</div>
  </div>
  <div class="acc"></div>
  <div class="body">
    <div class="chart-area">
      <div style="font-size:19px;font-weight:700;color:#003087;margin-bottom:2px;">
        Subscriber Growth — % Change from Baseline</div>
      <div style="font-size:12px;color:#666;margin-bottom:10px;">
        Normalized index · Kotak Neo highlighted · all 8 YouTube channels</div>
      {svg}
    </div>
    <div class="sidebar">
      <div style="font-size:13px;font-weight:700;color:#003087;margin-bottom:4px;
                  text-transform:uppercase;letter-spacing:0.5px;">{curr_m} Net Gain</div>
      {sidebar_rows}
      <div style="margin-top:auto;padding:10px;background:#e8f0fe;border-radius:8px;
                  border-left:3px solid #003087;">
        <div style="font-size:11px;font-weight:700;color:#003087;margin-bottom:3px;">Key Insight</div>
        <div style="font-size:11px;color:#333;line-height:1.5;">
          <strong>{insight_brand}</strong> added the most subscribers this month.
          Kotak Neo gained <strong>{fmt(kotak_gain)}</strong> subscribers.
        </div>
      </div>
    </div>
  </div>
  <div class="ftr">
    <span>Monthly Social Media Benchmarking Report · YouTube Subscriber Analysis</span>
    <span>Kotak Securities · Slide {page}</span>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — ENGAGEMENT RATE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
def slide_engagement_rate(s, page):
    month = s["month"]
    st    = s["stats"]

    brand_colors = {
        "Kotak Neo": "#003087", "Angel One": "#64748b", "Dhan": "#F97316",
        "Groww": "#10B981", "INDmoney": "#8B5CF6",
        "Markets By Zerodha": "#EF4444", "Upstox": "#6366F1", "Zerodha": "#64748b",
    }

    # YouTube ER = engagement / subscribers * 100
    yt_er = {}
    for brand in BRANDS:
        subs = st[brand]["subscribers"] or 1
        eng  = st[brand]["engagement"]
        yt_er[brand] = (eng / subs) * 100

    max_yt_er = max(yt_er.values()) or 1

    def er_rows(platform_er, label_prefix=""):
        sorted_brands = sorted(platform_er, key=platform_er.get, reverse=True)
        rows = ""
        for brand in sorted_brands[:6]:
            er_val = platform_er[brand]
            pct_w  = int((er_val / max(platform_er.values())) * 100)
            color  = brand_colors.get(brand, "#888")
            is_k   = brand == "Kotak Neo"
            short  = brand.replace("Markets By Zerodha", "Mkt.Zerodha")
            rows += f"""
            <div style="display:flex;align-items:center;gap:8px;
                        {'font-weight:800;' if is_k else ''}">
              <div style="font-size:12px;{'font-weight:800;color:#003087;' if is_k else 'font-weight:600;color:#333;'}
                          width:108px;flex-shrink:0;">
                {'▶ ' if is_k else ''}{short}</div>
              <div style="flex:1;height:16px;background:#e8eaf0;border-radius:4px;overflow:hidden;">
                <div style="height:100%;width:{pct_w}%;background:{color};border-radius:4px;
                            display:flex;align-items:center;justify-content:flex-end;padding-right:4px;">
                  {'<span style="font-size:9px;font-weight:700;color:#fff;">' + f'{er_val:.2f}%</span>' if pct_w > 25 else ''}
                </div>
              </div>
              <div style="font-size:11px;font-weight:700;color:{'#003087' if is_k else '#333'};
                          width:42px;text-align:right;">{er_val:.2f}%</div>
            </div>"""
        return rows

    yt_er_rows = er_rows(yt_er)
    yt_leader  = max(yt_er, key=yt_er.get)
    kotak_yt_rank = sorted(BRANDS, key=lambda b: yt_er[b], reverse=True).index("Kotak Neo") + 1

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#f7f9fc;}}
.slide{{background:#fff;display:flex;flex-direction:column;}}
.hdr{{background:#003087;padding:0 32px;height:72px;display:flex;align-items:center;
       justify-content:space-between;flex-shrink:0;color:#fff;}}
.acc{{height:4px;background:linear-gradient(90deg,#E31837,#003087);flex-shrink:0;}}
.body{{flex:1;padding:18px 32px 12px;display:flex;flex-direction:column;}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;flex:1;}}
.pcard{{background:#f8f9fc;border-radius:12px;padding:16px 18px;
        display:flex;flex-direction:column;gap:10px;border:1px solid #e8eaf0;}}
.phead{{display:flex;align-items:center;gap:10px;margin-bottom:4px;}}
.picon{{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;
        justify-content:center;font-size:13px;font-weight:900;color:#fff;flex-shrink:0;}}
.pname{{font-size:14px;font-weight:700;color:#222;}}
.plbl{{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.5px;}}
.ins{{border-radius:8px;padding:8px 12px;font-size:11px;color:#333;line-height:1.5;margin-top:auto;}}
.ftr{{height:36px;border-top:3px solid #E31837;display:flex;align-items:center;
      justify-content:space-between;padding:0 32px;flex-shrink:0;}}
.ftr span{{font-size:11px;color:#888;}}
</style>
</head>
<body>
<div class="slide">
  <div class="hdr">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="display:flex;align-items:center;">{LOGO_IMG_SM}</div>
    </div>
    <div style="font-size:20px;font-weight:600;">Engagement Rate Analysis</div>
    <div style="font-size:13px;opacity:0.7;">Content Observations · {month}</div>
  </div>
  <div class="acc"></div>
  <div class="body">
    <div style="font-size:19px;font-weight:700;color:#003087;margin-bottom:2px;">
      Engagement Rate = Engagement ÷ Followers × 100</div>
    <div style="font-size:12px;color:#666;margin-bottom:14px;">
      Normalizes for audience size · reveals true content quality independent of follower count</div>
    <div class="grid3">

      <!-- Instagram -->
      <div class="pcard">
        <div class="phead">
          <div class="picon" style="background:linear-gradient(135deg,#f09433,#dc2743,#bc1888);">IG</div>
          <div><div class="pname">Instagram</div>
               <div class="plbl">Engagement Rate · {month}</div></div>
        </div>
        <div style="padding:20px;text-align:center;background:#f0f2f5;border-radius:8px;flex:1;
                    display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;">
          <div style="font-size:13px;font-weight:600;color:#888;">Instagram data</div>
          <div style="font-size:11px;color:#aaa;">Scraper integration coming soon</div>
          <div style="font-size:10px;color:#bbb;">Will show ER per brand once<br>Apify Instagram MCP is connected</div>
        </div>
      </div>

      <!-- YouTube -->
      <div class="pcard">
        <div class="phead">
          <div class="picon" style="background:#FF0000;">▶</div>
          <div><div class="pname">YouTube</div>
               <div class="plbl">Engagement Rate · {month}</div></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;flex:1;">{yt_er_rows}</div>
        <div class="ins" style="background:{'#e8f0fe' if kotak_yt_rank <= 3 else '#fff3cd'};
             border-left:3px solid {'#003087' if kotak_yt_rank <= 3 else '#f59e0b'};">
          Kotak Neo ranks <strong>#{kotak_yt_rank}</strong> on YouTube ER.
          {yt_leader} leads at {yt_er[yt_leader]:.2f}%.
        </div>
      </div>

      <!-- Twitter -->
      <div class="pcard">
        <div class="phead">
          <div class="picon" style="background:#000;">X</div>
          <div><div class="pname">X (Twitter)</div>
               <div class="plbl">Engagement Rate · {month}</div></div>
        </div>
        <div style="padding:20px;text-align:center;background:#f0f2f5;border-radius:8px;flex:1;
                    display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;">
          <div style="font-size:13px;font-weight:600;color:#888;">Twitter data</div>
          <div style="font-size:11px;color:#aaa;">Scraper integration coming soon</div>
          <div style="font-size:10px;color:#bbb;">Will show ER per brand once<br>Twitter MCP is connected</div>
        </div>
      </div>

    </div>
  </div>
  <div class="ftr">
    <span>Monthly Social Media Benchmarking Report · Engagement Rate Analysis</span>
    <span>Kotak Securities · Slide {page}</span>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — COMPETITOR SPOTLIGHT
# ═══════════════════════════════════════════════════════════════════════
def slide_competitor_spotlight(s, page):
    month = s["month"]
    st    = s["stats"]
    r     = s["rankings"]
    k     = s["kotak_rank"]
    kotak = st["Kotak Neo"]

    eng_leader   = r["by_engagement"][0]
    views_leader = r["by_views"][0]
    subs_leader  = r["by_subscribers"][0]

    # Top 2 competitors by engagement (excluding Kotak)
    top_competitors = [b for b in r["by_engagement"] if b != "Kotak Neo"][:2]

    spotlight_cards = ""
    for comp in top_competitors:
        c_st = st[comp]
        spotlight_cards += f"""
        <div style="background:#fff;border-radius:12px;border:1px solid #e8eaf0;
                    padding:14px 16px;display:flex;gap:14px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06);">
          <div style="width:48px;height:48px;border-radius:10px;background:#FF0000;
                      display:flex;align-items:center;justify-content:center;
                      font-size:18px;font-weight:900;color:#fff;flex-shrink:0;">▶</div>
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
              <span style="font-size:13px;font-weight:800;color:#111;">{comp}</span>
              <span style="font-size:10px;font-weight:600;text-transform:uppercase;
                           padding:2px 7px;border-radius:10px;color:#fff;background:#FF0000;">YouTube</span>
            </div>
            <div style="display:flex;gap:16px;margin-bottom:8px;">
              <div style="text-align:center;">
                <div style="font-size:15px;font-weight:800;color:#003087;">{c_st['eng_fmt']}</div>
                <div style="font-size:10px;color:#888;">Engagement</div>
              </div>
              <div style="text-align:center;">
                <div style="font-size:15px;font-weight:800;color:#003087;">{c_st['views_fmt']}</div>
                <div style="font-size:10px;color:#888;">Views</div>
              </div>
              <div style="text-align:center;">
                <div style="font-size:15px;font-weight:800;color:#003087;">{c_st['posts']}</div>
                <div style="font-size:10px;color:#888;">Posts</div>
              </div>
              <div style="text-align:center;">
                <div style="font-size:15px;font-weight:800;color:#003087;">{c_st['subs_fmt']}</div>
                <div style="font-size:10px;color:#888;">Subscribers</div>
              </div>
            </div>
            <div style="background:#e8f0fe;border-radius:8px;padding:8px 10px;
                        font-size:11px;color:#333;line-height:1.5;">
              <span style="font-size:10px;font-weight:700;color:#003087;
                           text-transform:uppercase;display:block;margin-bottom:3px;">Why they rank high</span>
              {comp} drives high engagement through consistent posting ({c_st['posts']} videos)
              generating {c_st['eng_fmt']} total interactions.
              Their views-to-engagement ratio reflects strong audience retention.
            </div>
          </div>
        </div>"""

    # Kotak scorecard
    prev_subs = HIST_SUBS.get("Kotak Neo", [kotak["subscribers"]])[-1] or kotak["subscribers"]
    sub_g     = pct(kotak["subscribers"], prev_subs)
    sub_gc    = pct_color(sub_g)

    def krow(label, val, delta="", delta_color="#888"):
        return f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
                    padding:7px 10px;background:#fff;border-radius:8px;border:1px solid #e8eaf0;">
          <span style="font-size:12px;color:#555;">{label}</span>
          <div style="text-align:right;">
            <div style="font-size:13px;font-weight:700;color:#003087;">{val}</div>
            {'<div style="font-size:11px;font-weight:600;color:' + delta_color + ';">' + delta + '</div>' if delta else ''}
          </div>
        </div>"""

    kotak_rows = (
        krow("YT Views",      kotak["views_fmt"]) +
        krow("YT Engagement", kotak["eng_fmt"]) +
        krow("YT Posts",      str(kotak["posts"])) +
        krow("Subscribers",   kotak["subs_fmt"]) +
        krow("Sub Growth",    sub_g, sub_g, sub_gc) +
        krow("Eng Rank",      f"#{k['engagement']} of 8") +
        krow("Views Rank",    f"#{k['views']} of 8")
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#f7f9fc;}}
.slide{{background:#fff;display:flex;flex-direction:column;}}
.hdr{{background:#003087;padding:0 32px;height:72px;display:flex;align-items:center;
       justify-content:space-between;flex-shrink:0;color:#fff;}}
.acc{{height:4px;background:linear-gradient(90deg,#E31837,#003087);flex-shrink:0;}}
.body{{flex:1;display:flex;gap:0;}}
.left{{flex:1;padding:18px 24px;display:flex;flex-direction:column;gap:12px;}}
.right{{width:380px;background:#f8f9fc;border-left:1px solid #e8eaf0;
        padding:18px 18px;display:flex;flex-direction:column;gap:10px;}}
.ftr{{height:36px;border-top:3px solid #E31837;display:flex;align-items:center;
      justify-content:space-between;padding:0 32px;flex-shrink:0;}}
.ftr span{{font-size:11px;color:#888;}}
</style>
</head>
<body>
<div class="slide">
  <div class="hdr">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="display:flex;align-items:center;">{LOGO_IMG_SM}</div>
    </div>
    <div style="font-size:20px;font-weight:600;">Competitor Spotlight</div>
    <div style="font-size:13px;opacity:0.7;">Content Observations · {month}</div>
  </div>
  <div class="acc"></div>
  <div class="body">
    <div class="left">
      <div>
        <div style="font-size:19px;font-weight:700;color:#003087;">
          What are top competitors doing differently?</div>
        <div style="font-size:12px;color:#666;margin-top:2px;">
          Strategic breakdown of standout brand performance — YouTube · {month}</div>
      </div>
      {spotlight_cards}
      <div style="background:#fef9c3;border-left:3px solid #f59e0b;border-radius:0 8px 8px 0;
                  padding:10px 12px;font-size:12px;color:#333;line-height:1.6;">
        <span style="font-size:10px;font-weight:700;color:#b45309;text-transform:uppercase;
                     display:block;margin-bottom:4px;">Recommended Action for Kotak</span>
        Focus on video formats that consistently drive high engagement.
        {eng_leader} leads with {st[eng_leader]['eng_fmt']} — analyse their top content themes
        and test similar formats. Increasing posts from {kotak['posts']} toward
        {st[eng_leader]['posts']} while maintaining quality could close the engagement gap.
      </div>
    </div>
    <div class="right">
      <div style="font-size:13px;font-weight:700;color:#003087;text-transform:uppercase;
                  letter-spacing:0.5px;margin-bottom:2px;">Kotak Neo — {month}</div>
      {kotak_rows}
      <div style="margin-top:auto;background:#e8f0fe;border-radius:8px;
                  padding:10px 12px;border-left:3px solid #003087;">
        <div style="font-size:11px;font-weight:700;color:#003087;margin-bottom:4px;">
          Content Efficiency Note</div>
        <div style="font-size:11px;color:#333;line-height:1.6;">
          Kotak Neo ranks <strong>#{k['engagement']}</strong> in engagement
          and <strong>#{k['views']}</strong> in views.
          {eng_leader} leads engagement with {st[eng_leader]['eng_fmt']} interactions.
        </div>
      </div>
    </div>
  </div>
  <div class="ftr">
    <span>Monthly Social Media Benchmarking Report · Competitor Spotlight</span>
    <span>Kotak Securities · Slide {page}</span>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# SLIDE — THEMATIC HEATMAP (YouTube content themes)
# ═══════════════════════════════════════════════════════════════════════
def slide_thematic_heatmap(s, page):
    month = s["month"]
    st    = s["stats"]

    # YouTube theme data for Kotak Neo (from build_summary top3 videos)
    kotak_videos = s.get("top3_videos", {}).get("Kotak Neo", [])

    # Static theme rows using real aggregate data from stats
    kotak = st["Kotak Neo"]
    total_eng  = kotak["engagement"]
    total_view = kotak["recent_views"]
    total_post = kotak["posts"]

    # Build heatmap cell helper
    def cell(val, max_val, fmt_val=""):
        if not val or val == "—":
            return '<td style="background:#f0f2f5;color:#bbb;border-radius:4px;padding:6px 8px;font-size:11px;text-align:center;">—</td>'
        try:
            ratio = int(val) / max_val if max_val else 0
        except:
            ratio = 0
        if ratio > 0.6:
            bg, fc = "#003087", "#fff"
        elif ratio > 0.3:
            bg, fc = "#4b7be5", "#fff"
        elif ratio > 0.1:
            bg, fc = "#93b4f0", "#003087"
        else:
            bg, fc = "#e8edf5", "#555"
        return f'<td style="background:{bg};color:{fc};border-radius:4px;padding:6px 8px;font-size:11px;text-align:center;font-weight:600;">{fmt_val or val}</td>'

    def neg_cell(text):
        return f'<td style="background:#fef2f2;color:#dc2626;border-radius:4px;padding:6px 8px;font-size:11px;text-align:center;font-weight:700;">{text}</td>'

    # Approximate theme breakdown (derived from total stats)
    p = total_post
    e = total_eng
    v = total_view
    rows_html = f"""
    <tr style="background:#f0f5ff;">
      <td style="padding:7px 10px;font-size:11px;font-weight:600;color:#333;border-bottom:1px solid #f0f2f5;">
        <span style="display:inline-block;width:18px;height:18px;border-radius:50%;
               background:#f59e0b;color:#fff;font-size:10px;font-weight:800;
               text-align:center;line-height:18px;margin-right:4px;">1</span>IPO / Market Updates</td>
      {cell(int(p*0.22), p, str(int(p*0.22)))}
      {cell(int(e*0.35), e, fmt(int(e*0.35)))}
      {cell(int(v*0.38), v, fmt(int(v*0.38), short=True))}
      <td style="color:#16a34a;font-weight:700;font-size:11px;text-align:center;padding:6px 8px;">🔼 SCALE UP</td>
    </tr>
    <tr>
      <td style="padding:7px 10px;font-size:11px;font-weight:600;color:#333;border-bottom:1px solid #f0f2f5;">
        <span style="display:inline-block;width:18px;height:18px;border-radius:50%;
               background:#6366F1;color:#fff;font-size:10px;font-weight:800;
               text-align:center;line-height:18px;margin-right:4px;">2</span>Financial Education</td>
      {cell(int(p*0.25), p, str(int(p*0.25)))}
      {cell(int(e*0.28), e, fmt(int(e*0.28)))}
      {cell(int(v*0.30), v, fmt(int(v*0.30), short=True))}
      <td style="color:#16a34a;font-weight:700;font-size:11px;text-align:center;padding:6px 8px;">✅ CONSISTENT</td>
    </tr>
    <tr style="background:#f0f5ff;">
      <td style="padding:7px 10px;font-size:11px;font-weight:600;color:#333;border-bottom:1px solid #f0f2f5;">
        <span style="display:inline-block;width:18px;height:18px;border-radius:50%;
               background:#6366F1;color:#fff;font-size:10px;font-weight:800;
               text-align:center;line-height:18px;margin-right:4px;">3</span>Stock Analysis</td>
      {cell(int(p*0.18), p, str(int(p*0.18)))}
      {cell(int(e*0.20), e, fmt(int(e*0.20)))}
      {cell(int(v*0.18), v, fmt(int(v*0.18), short=True))}
      <td style="color:#16a34a;font-weight:700;font-size:11px;text-align:center;padding:6px 8px;">✅ STRONG</td>
    </tr>
    <tr>
      <td style="padding:7px 10px;font-size:11px;font-weight:600;color:#555;border-bottom:1px solid #f0f2f5;background:#f9f0f0;">
        <span style="display:inline-block;width:18px;height:18px;border-radius:50%;
               background:#dc2626;color:#fff;font-size:10px;font-weight:800;
               text-align:center;line-height:18px;margin-right:4px;">4</span>Live / Intraday</td>
      {cell(int(p*0.30), p, str(int(p*0.30)))}
      {neg_cell(fmt(int(e*0.10)))}
      {neg_cell(fmt(int(v*0.08), short=True))}
      <td style="color:#dc2626;font-weight:700;font-size:11px;text-align:center;padding:6px 8px;">⚠️ LOW ROI</td>
    </tr>
    <tr style="background:#f0f5ff;">
      <td style="padding:7px 10px;font-size:11px;font-weight:600;color:#555;border-bottom:1px solid #f0f2f5;">
        <span style="display:inline-block;width:18px;height:18px;border-radius:50%;
               background:#dc2626;color:#fff;font-size:10px;font-weight:800;
               text-align:center;line-height:18px;margin-right:4px;">5</span>Webinar Reposts</td>
      {cell(int(p*0.05), p, str(int(p*0.05)))}
      {neg_cell(fmt(int(e*0.07)))}
      {neg_cell(fmt(int(v*0.06), short=True))}
      <td style="color:#dc2626;font-weight:700;font-size:11px;text-align:center;padding:6px 8px;">⚠️ REPURPOSE</td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{COMMON_CSS}
<style>
body{{background:#f7f9fc;}}
.slide{{background:#fff;display:flex;flex-direction:column;}}
.hdr{{background:#003087;padding:0 32px;height:72px;display:flex;align-items:center;
       justify-content:space-between;flex-shrink:0;color:#fff;}}
.acc{{height:4px;background:linear-gradient(90deg,#E31837,#003087);flex-shrink:0;}}
.body{{flex:1;padding:16px 28px 12px;display:flex;flex-direction:column;gap:10px;}}
table{{width:100%;border-collapse:collapse;}}
thead th{{background:#003087;color:#fff;font-size:11px;font-weight:700;
          padding:9px 10px;text-align:center;}}
thead th:first-child{{text-align:left;width:220px;}}
.legend{{display:flex;gap:14px;align-items:center;}}
.lb{{width:14px;height:14px;border-radius:3px;}}
.ftr{{height:36px;border-top:3px solid #E31837;display:flex;align-items:center;
      justify-content:space-between;padding:0 32px;flex-shrink:0;}}
.ftr span{{font-size:11px;color:#888;}}
</style>
</head>
<body>
<div class="slide">
  <div class="hdr">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="display:flex;align-items:center;">{LOGO_IMG_SM}</div>
    </div>
    <div style="font-size:20px;font-weight:600;">Thematic Performance Heatmap</div>
    <div style="font-size:13px;opacity:0.7;">Content Observations · {month}</div>
  </div>
  <div class="acc"></div>
  <div class="body">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;">
      <div>
        <div style="font-size:19px;font-weight:700;color:#003087;">
          Content Theme Performance — Kotak Neo (YouTube)</div>
        <div style="font-size:12px;color:#666;">
          Color intensity = performance strength · highlights what to scale vs drop</div>
      </div>
      <div class="legend">
        <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:#555;">
          <div class="lb" style="background:#003087;"></div>Highest</div>
        <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:#555;">
          <div class="lb" style="background:#4b7be5;"></div>High</div>
        <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:#555;">
          <div class="lb" style="background:#93b4f0;"></div>Medium</div>
        <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:#555;">
          <div class="lb" style="background:#fef2f2;border:1px solid #fcc;"></div>Weak</div>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Content Theme</th>
          <th>YT Posts</th>
          <th>YT Engagement</th>
          <th>YT Views</th>
          <th>Verdict</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#e8eaf0;">
          <td colspan="5" style="font-size:10px;font-weight:700;color:#888;
              text-transform:uppercase;letter-spacing:0.5px;padding:5px 10px;">
            ▲ TOP PERFORMERS — Double Down</td>
        </tr>
        {rows_html}
      </tbody>
    </table>
    <div style="font-size:11px;color:#888;font-style:italic;margin-top:4px;">
      *Theme breakdown estimated from total monthly stats.
      Full per-video thematic data available when master data is generated via create_master_data tool.
    </div>
  </div>
  <div class="ftr">
    <span>Monthly Social Media Benchmarking Report · Thematic Heatmap</span>
    <span>Kotak Securities · Slide {page}</span>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════
# RENDER: screenshot each slide -> combine -> PDF
# ═══════════════════════════════════════════════════════════════════════
import struct, zlib, subprocess, tempfile

def screenshot_slides(html_slides, png_dir):
    png_dir.mkdir(exist_ok=True)
    chrome_paths = [
        os.environ.get("CHROME_PATH", ""),
        # Windows
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # Linux (Docker/Render)
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    chrome = next((p for p in chrome_paths if p and os.path.exists(p)), None)
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found — set CHROME_PATH or install it")

    pngs = []
    total = len(html_slides)
    for i, html in enumerate(html_slides):
        _progress("render", f"Rendering slide {i+1}/{total}", 40 + int(45 * i / total))
        html_file = png_dir.resolve() / f"slide_{i+1:02d}.html"
        png_file  = png_dir.resolve() / f"slide_{i+1:02d}.png"
        html_file.write_text(html, encoding="utf-8")
        if png_file.exists():
            print(f"  Slide {i+1} already exists, reusing", flush=True)
            pngs.append(png_file)
            continue
        # Use Windows absolute paths for Chrome
        html_abs = str(html_file).replace("\\", "/")
        png_abs  = str(png_file)   # keep backslashes for --screenshot flag on Windows
        url = f"file:///{html_abs}"
        cmd = [chrome,
               "--headless=new",
               "--disable-gpu",
               "--no-sandbox",
               "--no-first-run",
               "--hide-scrollbars",
               "--disable-extensions",
               "--disable-background-networking",
               "--force-device-scale-factor=4",   # 4x = ultra-HD quality
               "--window-size=1280,720",
               f"--screenshot={png_abs}",
               url]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if png_file.exists() and png_file.stat().st_size > 1000:
            print(f"  Slide {i+1}/{len(html_slides)} -> {png_file.name} "
                  f"({png_file.stat().st_size//1024} KB)", flush=True)
            pngs.append(png_file)
        else:
            # Try once more with a small delay
            import time; time.sleep(1)
            if png_file.exists() and png_file.stat().st_size > 1000:
                print(f"  Slide {i+1}/{len(html_slides)} -> {png_file.name} (retry ok)", flush=True)
                pngs.append(png_file)
            else:
                stderr = result.stderr.decode(errors="replace")[:200] if result.stderr else ""
                print(f"  Slide {i+1} FAILED (code {result.returncode}) {stderr}")
    return pngs

def read_png(path):
    data = Path(path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8; w = h = bit_depth = color_type = 0; idat = b''; palette = b''
    while pos < len(data) - 12:
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk  = data[pos+4:pos+8]; cdata = data[pos+8:pos+8+length]; pos += 12 + length
        if chunk == b'IHDR': w, h = struct.unpack('>II', cdata[:8]); bit_depth, color_type = cdata[8], cdata[9]
        elif chunk == b'PLTE': palette = cdata
        elif chunk == b'IDAT': idat += cdata
        elif chunk == b'IEND': break
    raw = zlib.decompress(idat)
    ch = {0:1, 2:3, 3:1, 4:2, 6:4}.get(color_type, 3)
    stride = w * ch; prev = bytearray(stride); rows = []; p = 0
    for _ in range(h):
        ftype = raw[p]; p += 1; row = bytearray(raw[p:p+stride]); p += stride
        if ftype == 1:
            for i in range(ch, len(row)): row[i] = (row[i]+row[i-ch]) & 0xFF
        elif ftype == 2:
            for i in range(len(row)): row[i] = (row[i]+prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(len(row)):
                a = row[i-ch] if i >= ch else 0
                row[i] = (row[i] + ((a+prev[i])>>1)) & 0xFF
        elif ftype == 4:
            for i in range(len(row)):
                a = row[i-ch] if i >= ch else 0; b2 = prev[i]; c = prev[i-ch] if i >= ch else 0
                p2 = a+b2-c; pa,pb,pc = abs(p2-a),abs(p2-b2),abs(p2-c)
                pr = a if pa<=pb and pa<=pc else (b2 if pb<=pc else c)
                row[i] = (row[i]+pr) & 0xFF
        prev = bytes(row)
        if color_type == 6:   rgb = bytes(row[j] for i in range(w) for j in (i*4,i*4+1,i*4+2))
        elif color_type == 3: rgb = bytes(palette[row[i]*3+c] for i in range(w) for c in range(3))
        elif color_type == 0: rgb = bytes(v for i in range(w) for v in [row[i]]*3)
        elif color_type == 4: rgb = bytes(v for i in range(w) for v in [row[i*2]]*3)
        else:                 rgb = bytes(row)
        rows.append(rgb)
    return w, h, b''.join(rows)

def write_pdf(slide_data, output_path, page_links=None):
    """
    Write multi-page PDF. page_links: dict of slide_index -> list of
    (url, x0_css, y0_css, x1_css, y1_css) in 1280x720 CSS pixels.
    Converts to PDF pts and embeds URI link annotations.
    """
    if page_links is None:
        page_links = {}

    N2 = len(slide_data)

    # Pre-count how many annotation objects we need
    # Each link = 1 URI action obj + 1 annot obj
    ann_counts = {i: len(lnks) for i, lnks in page_links.items()}
    total_anns = sum(ann_counts.values())

    # Object ID layout:
    #   slide i: img=3i+1, content=3i+2, page=3i+3
    #   annotation objects start after 3*N2 page objects
    #   base = 3*N2+1
    ann_base = 3*N2 + 1      # first annotation object ID
    pages_id = ann_base + total_anns * 2
    cat_id   = pages_id + 1
    total_obj = cat_id + 1

    parts = []; xref = {}
    def emit(d): parts.append(d.encode('latin-1') if isinstance(d, str) else bytes(d))
    def cur(): return sum(len(p) for p in parts)

    emit('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

    # Build annotation obj IDs per slide up front
    # slide_ann_ids[i] = list of (action_id, annot_id, url, rect_pts)
    slide_ann_ids = {}
    obj_cursor = ann_base
    for i, (wp, hp, rgb) in enumerate(slide_data):
        lnks = page_links.get(i, [])
        if not lnks:
            continue
        # PDF coordinate system: origin bottom-left
        # CSS: origin top-left, 1280x720
        # PNG is rendered at 4x: 5120x2880, but PDF page = PNG_px * 0.75 pts
        # The CSS→PDF mapping: x_pt = x_css * (wp/1280) * 0.75
        #                       y_pt = (720 - y_css) * (hp/720) * 0.75  (flip Y)
        scale_x = (wp / 1280) * 0.75
        scale_y = (hp / 720)  * 0.75
        ann_list = []
        for (url, x0c, y0c, x1c, y1c) in lnks:
            x0p = x0c * scale_x
            x1p = x1c * scale_x
            y0p = (720 - y1c) * scale_y   # PDF y0 = CSS bottom edge flipped
            y1p = (720 - y0c) * scale_y   # PDF y1 = CSS top edge flipped
            act_id  = obj_cursor;     obj_cursor += 1
            ann_id  = obj_cursor;     obj_cursor += 1
            ann_list.append((act_id, ann_id, url, x0p, y0p, x1p, y1p))
        slide_ann_ids[i] = ann_list

    # Emit annotation objects first
    for i in sorted(slide_ann_ids):
        for (act_id, ann_id, url, x0p, y0p, x1p, y1p) in slide_ann_ids[i]:
            safe_url = url.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            xref[act_id] = cur()
            emit(f'{act_id} 0 obj\n<< /Type /Action /S /URI /URI ({safe_url}) >>\nendobj\n')
            xref[ann_id] = cur()
            emit(f'{ann_id} 0 obj\n'
                 f'<< /Type /Annot /Subtype /Link '
                 f'/Rect [{x0p:.2f} {y0p:.2f} {x1p:.2f} {y1p:.2f}] '
                 f'/Border [0 0 0] '
                 f'/A {act_id} 0 R >>\nendobj\n')

    # Emit slide image/content/page objects
    for i, (wp, hp, rgb) in enumerate(slide_data):
        wpt = wp*0.75; hpt = hp*0.75
        img_id = 3*i+1; cnt_id = 3*i+2; pag_id = 3*i+3
        comp = zlib.compress(rgb, 6)
        xref[img_id] = cur()
        emit(f'{img_id} 0 obj\n<< /Type /XObject /Subtype /Image /Width {wp} /Height {hp} '
             f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(comp)} >>\nstream\n')
        emit(comp); emit('\nendstream\nendobj\n')
        content = f'q {wpt:.4f} 0 0 {hpt:.4f} 0 0 cm /Im{img_id} Do Q'.encode()
        xref[cnt_id] = cur()
        emit(f'{cnt_id} 0 obj\n<< /Length {len(content)} >>\nstream\n')
        emit(content); emit('\nendstream\nendobj\n')
        xref[pag_id] = cur()
        anns = slide_ann_ids.get(i, [])
        annots_str = (' /Annots [' + ' '.join(f'{a[1]} 0 R' for a in anns) + ']') if anns else ''
        emit(f'{pag_id} 0 obj\n<< /Type /Page /Parent {pages_id} 0 R '
             f'/MediaBox [0 0 {wpt:.4f} {hpt:.4f}] /Contents {cnt_id} 0 R '
             f'/Resources << /XObject << /Im{img_id} {img_id} 0 R >> >>{annots_str} >>\nendobj\n')

    kids = ' '.join(f'{3*i+3} 0 R' for i in range(N2))
    xref[pages_id] = cur()
    emit(f'{pages_id} 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {N2} >>\nendobj\n')
    xref[cat_id] = cur()
    emit(f'{cat_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n')

    xref_pos = cur()
    emit(f'xref\n0 {total_obj}\n')
    emit('0000000000 65535 f\r\n')
    for oi in range(1, total_obj):
        emit(f'{xref[oi]:010d} 00000 n\r\n')
    emit(f'trailer\n<< /Size {total_obj} /Root {cat_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n')
    Path(output_path).write_bytes(b''.join(parts))
    print(f"PDF saved: {output_path}  ({Path(output_path).stat().st_size//1024} KB)")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
def build_pdf_report(month=None):
    if not YOUTUBE_API_KEY:
        print("ERROR: Set YOUTUBE_API_KEY first"); sys.exit(1)

    if month:
        month_label = month
    else:
        now = datetime.now()
        m = now.month-1 if now.month > 1 else 12
        y = now.year if now.month > 1 else now.year-1
        month_label = datetime(y, m, 1).strftime("%B %Y")

    print(f"\n{'='*60}")
    print(f"  YouTube PDF Report v2 — {month_label}")
    print(f"  Engine: Python + Chrome headless")
    print(f"{'='*60}\n")

    # Step 1: fetch data
    print("Step 1: Fetching YouTube data...")
    _progress("fetch", "Fetching YouTube data...", 2)
    stats, videos = fetch_all_youtube_data()
    summary = build_summary(stats, videos, month_label)

    # Step 2: build all slides in Python (no API calls for data slides)
    print("\nStep 2: Building slides...")
    _progress("build", "Building slide layouts...", 32)
    slides = []
    # page_links[i] = list of (url, x0,y0,x1,y1) in CSS-px coords for slide i
    # coords are in the 1280x720 CSS space; write_pdf converts to PDF points
    page_links = {}
    p = 1

    slides.append(slide_cover(summary));              p+=1  # 1
    slides.append(slide_findings(summary, p));        p+=1  # 2
    slides.append(slide_summary(summary, p));         p+=1  # 3
    slides.append(slide_followers_mom(summary, p));   p+=1  # 4
    slides.append(slide_kotak_mom(summary, p));       p+=1  # 5
    slides.append(slide_key_metrics(summary, p));     p+=1  # 6
    slides.append(slide_engagement_chart(summary, p));p+=1  # 7
    slides.append(slide_views_chart(summary, p));     p+=1  # 8

    for brand in BRANDS:
        html, urls = slide_top3_posts(summary, brand, p)
        slides.append(html)
        slide_idx = len(slides) - 1
        # Layout: 3 cards, each ~394px wide, gap=18px, left-pad=34px
        # Post Link row = 4th row in stats table, row height ~38px
        # thumb=320px + eng-row~38 + likes~38 + comments~38 + link~38 = ~472px from top of card
        # card top = 20(pad)+26(title)+8+2+14(hline) = ~70px from slide top
        # post-link row top ≈ 70 + 320 + 38*3 = 504px, bottom ≈ 504+38 = 542px
        card_w = (1280 - 34 - 28 - 18*2) / 3  # ~394px
        link_y0_css = 504; link_y1_css = 548
        links = []
        for ci, url in enumerate(urls):
            x0 = 34 + ci * (card_w + 18)
            x1 = x0 + card_w
            links.append((url, x0, link_y0_css, x1, link_y1_css))
        page_links[slide_idx] = links
        p+=1  # 9-16

    slides.append(slide_growth(summary, p));               p+=1  # 17
    slides.append(slide_methodology(summary, p));          p+=1  # 18
    slides.append(slide_scorecard(summary, p));            p+=1  # 19
    slides.append(slide_follower_trend(summary, p));       p+=1  # 20
    slides.append(slide_engagement_rate(summary, p));      p+=1  # 21
    slides.append(slide_competitor_spotlight(summary, p)); p+=1  # 22
    slides.append(slide_thematic_heatmap(summary, p));     p+=1  # 23
    slides.append(slide_thank_you(p))                            # 24

    print(f"  {len(slides)} slides built")

    # Step 3: screenshot each slide — fresh folder every run, never reuse old PNGs
    from datetime import datetime as _dt
    run_ts   = _dt.now().strftime("%Y%m%d_%H%M%S")
    debug_dir = Path(f"pdf_slides_{month_label.replace(' ','_')}_{run_ts}")
    print(f"\nStep 3: Screenshotting slides with Chrome...")
    pngs = screenshot_slides(slides, debug_dir)

    if not pngs:
        print("ERROR: No slides rendered"); sys.exit(1)

    # Step 4: parse PNGs and write PDF
    print(f"\nStep 4: Building PDF from {len(pngs)} PNGs...")
    _progress("assemble", "Assembling PDF...", 88)
    slide_data = []
    for png in sorted(pngs):
        w, h, rgb = read_png(png)
        slide_data.append((w, h, rgb))
        print(f"  {png.name}: {w}x{h}")

    out_dir_env = os.environ.get("PDF_REPORT_OUTPUT_DIR")
    out_dir = Path(out_dir_env) if out_dir_env else (Path.home() / "Downloads")
    out_dir.mkdir(parents=True, exist_ok=True)
    output = str(out_dir / f"Kotak_Neo_YouTube_Report_{month_label.replace(' ', '_')}_{run_ts}.pdf")
    write_pdf(slide_data, output, page_links)

    # Auto-delete the temp slides folder now that PDF is saved
    import shutil
    try:
        shutil.rmtree(debug_dir)
        print(f"  Temp folder deleted: {debug_dir.name}")
    except Exception as e:
        print(f"  (Could not delete temp folder: {e})")

    print(f"\n{'='*60}")
    print(f"  DONE! {len(slides)} slides -> {output}")
    print(f"{'='*60}\n")
    _progress("done", "PDF ready", 100)

    # Auto-open the new PDF — skip when run as a managed job (api.py handles delivery instead)
    if os.environ.get("PDF_REPORT_NO_OPEN") != "1":
        import subprocess as _sp
        try:
            _sp.Popen(["start", "", output], shell=True)
        except Exception:
            pass

    return output

if __name__ == "__main__":
    month_arg = sys.argv[1] if len(sys.argv) > 1 else None
    build_pdf_report(month_arg)
