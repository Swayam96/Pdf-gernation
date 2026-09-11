"""
YouTube video title -> theme classifier, keyword-matched.
Ported from social-mcp's shared/themes.py.
"""

THEME_RULES = [
    ("IPO Updates",                   ["ipo", "initial public offering", "listing", "allotment", "subscribe"]),
    ("Stalking Stocks",               ["stalking stock", "stalk"]),
    ("Guess the Stock",               ["guess the stock", "guess which"]),
    ("Mutual Funds",                  ["mutual fund", "sip ", "nfo", "fund house", "amc"]),
    ("Memes",                         ["meme", "😂", "funny", "humor"]),
    ("Neo Shorts",                    ["#shorts", "#short"]),
    ("Learning Technical Analysis",   ["technical analysis", "chart pattern", "candlestick", "rsi", "macd", "ema", "support", "resistance", "breakout"]),
    ("Masterclass",                   ["masterclass", "master class"]),
    ("Collab Post",                   ["collab", "ft.", "featuring", "with special guest"]),
    ("Trade from Charts",             ["trade setup", "trade from chart", "chart setup"]),
    ("Market Analysis for Tomorrow",  ["market analysis for tomorrow", "tomorrow market", "nifty outlook tomorrow"]),
    ("Live Trading Today",            ["live trading today", "live trade", "live market"]),
    ("Intraday Insights",             ["intraday insight", "intraday tip", "intraday strategy"]),
    ("Webinar",                       ["webinar", "live session", "live webinar", "register now"]),
    ("Expiry ki Baat",                ["expiry ki baat", "expiry day", "weekly expiry"]),
    ("Product Feature",               ["feature", "app update", "new feature", "introducing", "launch"]),
    ("Top Stock Picks",               ["top stock", "best stock", "stock picks", "multibagger"]),
    ("Tez Mindset",                   ["tez mindset", "tez ", "stay tez", "jo tez"]),
    ("Understanding Markets 101",     ["markets 101", "understanding market", "basics of"]),
    ("Buzzing News",                  ["buzzing", "breaking news", "market news"]),
    ("Neo Explainer",                 ["explainer", "what is", "kya hota", "kya hai"]),
    ("Company Close up",              ["company close", "close up", "company profile"]),
    ("Basic Mistakes",                ["mistake", "avoid this", "common error"]),
    ("Market Bytes",                  ["market byte", "quick update", "60 second"]),
    ("The Bullish Minds",             ["bullish mind", "podcast", "episode"]),
    ("Infographic",                   ["infographic"]),
    ("Product Promotions",            ["promotion", "offer", "discount", "cashback", "free brokerage"]),
    ("Event",                         ["event", "meetup", "conference", "summit"]),
    ("Topical",                       ["republic day", "independence day", "diwali", "holi", "navratri", "festival"]),
    ("Economic & Market Insights",    ["economy", "gdp", "inflation", "rbi", "fed", "fii", "dii", "sensex", "nifty", "market insight", "market update", "sector"]),
    ("Investment Advice & Tips",      ["invest", "portfolio", "wealth", "returns", "profit", "loss"]),
    ("Financial Education",           ["finance", "financial", "tax", "budget", "saving", "loan", "insurance"]),
]


def classify_theme(title):
    tl = title.lower()
    for theme, keywords in THEME_RULES:
        for kw in keywords:
            if kw in tl:
                return theme
    return "General"
