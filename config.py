START_DATE = "2026-02-05"
PRICE_TTL_SECONDS = 86400

BENCHMARK_MAP = {
    "SPY": "SPY",
    "DIA": "DIA",
}

PORTFOLIO_CONFIG = [
    {"Portfolio": "Google 10", "Ticker": "AMZN", "Initial Investment": 142.42},
    {"Portfolio": "Google 10", "Ticker": "IBIT", "Initial Investment": 145.45},
    {"Portfolio": "Google 10", "Ticker": "LLY", "Initial Investment": 115.76},
    {"Portfolio": "Google 10", "Ticker": "MSFT", "Initial Investment": 226.67},
    {"Portfolio": "Google 10", "Ticker": "NVDA", "Initial Investment": 369.70},
    {"Portfolio": "Google 50", "Ticker": "AMZN", "Initial Investment": 145.33},
    {"Portfolio": "Google 50", "Ticker": "IBIT", "Initial Investment": 170.10},
    {"Portfolio": "Google 50", "Ticker": "LLY", "Initial Investment": 80.86},
    {"Portfolio": "Google 50", "Ticker": "MSFT", "Initial Investment": 234.09},
    {"Portfolio": "Google 50", "Ticker": "NVDA", "Initial Investment": 369.62},
    {"Portfolio": "Google 100", "Ticker": "AMZN", "Initial Investment": 146.29},
    {"Portfolio": "Google 100", "Ticker": "IBIT", "Initial Investment": 164.25},
    {"Portfolio": "Google 100", "Ticker": "LLY", "Initial Investment": 78.28},
    {"Portfolio": "Google 100", "Ticker": "MSFT", "Initial Investment": 242.71},
    {"Portfolio": "Google 100", "Ticker": "NVDA", "Initial Investment": 368.47},
    {"Portfolio": "OpenAI 10", "Ticker": "AMZN", "Initial Investment": 83.10},
    {"Portfolio": "OpenAI 10", "Ticker": "MSFT", "Initial Investment": 231.31},
    {"Portfolio": "OpenAI 10", "Ticker": "NVDA", "Initial Investment": 377.75},
    {"Portfolio": "OpenAI 10", "Ticker": "QQQ", "Initial Investment": 222.27},
    {"Portfolio": "OpenAI 10", "Ticker": "SOXX", "Initial Investment": 85.57},
    {"Portfolio": "OpenAI 50", "Ticker": "AMZN", "Initial Investment": 110.26},
    {"Portfolio": "OpenAI 50", "Ticker": "ARKK", "Initial Investment": 70.57},
    {"Portfolio": "OpenAI 50", "Ticker": "MSFT", "Initial Investment": 224.62},
    {"Portfolio": "OpenAI 50", "Ticker": "NVDA", "Initial Investment": 367.41},
    {"Portfolio": "OpenAI 50", "Ticker": "QQQ", "Initial Investment": 227.14},
    {"Portfolio": "OpenAI 100", "Ticker": "AMZN", "Initial Investment": 98.34},
    {"Portfolio": "OpenAI 100", "Ticker": "ARKK", "Initial Investment": 81.21},
    {"Portfolio": "OpenAI 100", "Ticker": "MSFT", "Initial Investment": 216.18},
    {"Portfolio": "OpenAI 100", "Ticker": "NVDA", "Initial Investment": 373.38},
    {"Portfolio": "OpenAI 100", "Ticker": "QQQ", "Initial Investment": 230.89},
    {"Portfolio": "Random A", "Ticker": "ADM", "Initial Investment": 246.84},
    {"Portfolio": "Random A", "Ticker": "DOC", "Initial Investment": 492.08},
    {"Portfolio": "Random A", "Ticker": "NRG", "Initial Investment": 9.99},
    {"Portfolio": "Random A", "Ticker": "PANW", "Initial Investment": 206.08},
    {"Portfolio": "Random A", "Ticker": "SMCI", "Initial Investment": 45.01},
    {"Portfolio": "Random B", "Ticker": "AKAM", "Initial Investment": 180.95},
    {"Portfolio": "Random B", "Ticker": "ALB", "Initial Investment": 135.00},
    {"Portfolio": "Random B", "Ticker": "APH", "Initial Investment": 420.46},
    {"Portfolio": "Random B", "Ticker": "GL", "Initial Investment": 117.34},
    {"Portfolio": "Random B", "Ticker": "NRG", "Initial Investment": 146.25},
    {"Portfolio": "SPY", "Ticker": "SPY", "Initial Investment": 1000.00},
    {"Portfolio": "DIA", "Ticker": "DIA", "Initial Investment": 1000.00},
]

GOOGLE_BLUES = [
    "#8ec5ff",
    "#5aa9ff",
    "#2f80ed",
    "#1f5fbf",
    "#153e75",
]

OPENAI_ORANGES = [
    "#ffd08a",
    "#ffb14e",
    "#f28c28",
    "#d96b00",
    "#a34b00",
]

TICKER_THEME_MAP = {
    "NVDA": "AI / Semis",
    "AMD": "AI / Semis",
    "AVGO": "AI / Semis",
    "TSM": "AI / Semis",
    "MU": "AI / Semis",
    "QCOM": "AI / Semis",
    "INTC": "AI / Semis",
    "MSFT": "Mega-cap Growth",
    "GOOGL": "Mega-cap Growth",
    "GOOG": "Mega-cap Growth",
    "AMZN": "Mega-cap Growth",
    "META": "Mega-cap Growth",
    "AAPL": "Mega-cap Growth",
    "NFLX": "Mega-cap Growth",
    "TSLA": "High-beta Growth",
    "PLTR": "High-beta Growth",
    "SNOW": "High-beta Growth",
    "CRM": "Software",
    "ADBE": "Software",
    "ORCL": "Software",
    "JPM": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "BLK": "Financials",
    "SCHW": "Financials",
    "BRK.B": "Defensive / Quality",
    "BRK-B": "Defensive / Quality",
    "XOM": "Energy",
    "CVX": "Energy",
    "SLB": "Energy",
    "COP": "Energy",
    "CAT": "Industrials",
    "GE": "Industrials",
    "DE": "Industrials",
    "BA": "Industrials",
    "HON": "Industrials",
    "ETN": "Industrials",
    "LLY": "Healthcare",
    "JNJ": "Healthcare",
    "UNH": "Healthcare",
    "MRK": "Healthcare",
    "PFE": "Healthcare",
    "ABBV": "Healthcare",
    "COST": "Defensive / Quality",
    "WMT": "Defensive / Quality",
    "PG": "Defensive / Quality",
    "KO": "Defensive / Quality",
    "PEP": "Defensive / Quality",
    "MCD": "Defensive / Quality",
    "HD": "Consumer / Housing",
    "LOW": "Consumer / Housing",
    "NKE": "Consumer",
    "SBUX": "Consumer",
    "DIS": "Consumer / Media",
    "CMCSA": "Consumer / Media",
    "PLD": "Rate-sensitive",
    "AMT": "Rate-sensitive",
    "CCI": "Rate-sensitive",
}

APP_CSS = """
<style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(80,80,90,0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(120,120,140,0.10), transparent 24%),
            linear-gradient(180deg, #06070a 0%, #0b0d12 45%, #06070a 100%);
        color: #f3f4f6;
    }

    .block-container {
        padding-top: 1.15rem;
        padding-bottom: 2rem;
        max-width: 1425px;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
        color: #f8fafc;
    }

    h1 {
        font-weight: 800 !important;
    }

    .small-note {
        color: #9aa4b2;
        font-size: 0.88rem;
        margin-top: -0.35rem;
        margin-bottom: 0.75rem;
    }

    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(20,24,31,0.80) 0%, rgba(11,14,20,0.72) 100%);
        border: 1px solid rgba(255,255,255,0.08);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-radius: 18px;
        padding: 18px 18px 14px 18px;
        box-shadow:
            0 8px 30px rgba(0,0,0,0.34),
            inset 0 1px 0 rgba(255,255,255,0.04);
        margin-bottom: 12px;
    }

    .metric-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #94a3b8;
        margin-bottom: 8px;
        font-weight: 700;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.08;
    }

    .metric-sub {
        font-size: 0.92rem;
        margin-top: 8px;
        color: #cbd5e1;
        white-space: pre-line;
    }

    div[data-testid="stExpander"] {
        background: linear-gradient(180deg, rgba(17,22,30,0.78) 0%, rgba(9,12,18,0.70) 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        overflow: hidden;
        box-shadow:
            0 10px 28px rgba(0,0,0,0.26),
            inset 0 1px 0 rgba(255,255,255,0.04);
        margin-bottom: 1rem;
    }

    div[data-testid="stExpander"] details summary {
        font-weight: 700;
        color: #f8fafc;
    }

    div[data-testid="stDataFrame"] {
        background: rgba(10,14,19,0.55);
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.06);
        overflow: hidden;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="popover"] > div,
    .stDateInput > div > div,
    .stMultiSelect > div > div {
        background: rgba(12,16,22,0.88) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 14px !important;
        color: #f8fafc !important;
    }

    .stButton > button {
        background: linear-gradient(180deg, rgba(28,32,40,0.95) 0%, rgba(12,14,20,0.95) 100%);
        color: #f8fafc;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        font-weight: 700;
        padding: 0.6rem 1rem;
        box-shadow:
            0 8px 18px rgba(0,0,0,0.28),
            inset 0 1px 0 rgba(255,255,255,0.04);
    }

    .stButton > button:hover {
        border-color: rgba(255,255,255,0.18);
        background: linear-gradient(180deg, rgba(35,40,49,0.98) 0%, rgba(16,19,25,0.98) 100%);
        color: white;
    }

    label, .stMarkdown, p, span {
        color: #e5e7eb;
    }

    div[data-testid="stAlert"] {
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.07);
    }

    .glass-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
        margin: 0.25rem 0 1rem 0;
    }
</style>
"""