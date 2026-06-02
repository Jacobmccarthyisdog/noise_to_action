import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import BENCHMARK_MAP
from data_loader import load_data, fetch_price_history
from calculations import (
    money,
    pct,
    normalize_date_range,
    exclude_benchmark_portfolios,
    build_datasets,
    build_summary,
    summarize_benchmark,
    build_ytd_metrics_snapshot,
    format_summary_table,
    format_holdings_table,
)
from charts import (
    build_portfolio_heatmap,
    build_line_style_map,
    apply_line_styles,
    chart_layout,
    render_chart,
)
from insights import generate_llm_insight, save_daily_insight


DAILY_INSIGHT_PATH = Path("data/daily_insight.json")

SEDONA_BG = "#F5F1E8"
SEDONA_SURFACE = "#FBF8F1"
SEDONA_SIDEBAR = "#EDE8DA"
SEDONA_INK = "#2B2925"
SEDONA_INK_SOFT = "#6B665C"
SEDONA_INK_FAINT = "#9A9386"
SEDONA_LINE = "#E2DCCE"
SEDONA_LINE_STRONG = "#D4CBB8"

ACCENT_BLUE = "#D85A30"
CORAL = "#D85A30"
CORAL_BG = "#FAECE7"
CORAL_INK = "#993C1D"
SAGE = "#5DCAA5"
SAGE_BG = "#E1F5EE"
SAGE_INK = "#0F6E56"
AMBER = "#EF9F27"
AMBER_BG = "#FAEEDA"
AMBER_INK = "#854F0B"
BRICK = "#A32D2D"
BRICK_BG = "#FCEBEB"
BRICK_INK = "#791F1F"


st.set_page_config(
    page_title="From Noise to Action",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------
# Global visual system
# ---------------------------------------------------------------------

PREMIUM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Spline+Sans:wght@400;500;600&display=swap');

    :root {{
        --bg: {SEDONA_BG};
        --surface: {SEDONA_SURFACE};
        --sidebar: {SEDONA_SIDEBAR};
        --ink: {SEDONA_INK};
        --ink-soft: {SEDONA_INK_SOFT};
        --ink-faint: {SEDONA_INK_FAINT};
        --line: {SEDONA_LINE};
        --line-strong: {SEDONA_LINE_STRONG};

        --coral: {CORAL};
        --coral-bg: {CORAL_BG};
        --coral-ink: {CORAL_INK};

        --sage: {SAGE};
        --sage-bg: {SAGE_BG};
        --sage-ink: {SAGE_INK};

        --amber: {AMBER};
        --amber-bg: {AMBER_BG};
        --amber-ink: {AMBER_INK};

        --brick: {BRICK};
        --brick-bg: {BRICK_BG};
        --brick-ink: {BRICK_INK};

        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 18px;
    }}

    .stApp {{
        background: var(--bg);
        color: var(--ink);
        font-family: 'Spline Sans', sans-serif;
    }}

    .block-container {
        max-width: 1180px;
        padding-top: 3.25rem;
        padding-bottom: 4.5rem;
    }

    h1, h2, h3, h4, h5, h6 {{
        color: var(--ink);
        font-family: 'Fraunces', serif;
        font-weight: 500;
        letter-spacing: -0.01em;
    }}

    p, label, span, div {{
        color: inherit;
    }}

    section[data-testid="stSidebar"] {{
        background: var(--sidebar);
        border-right: 1px solid var(--line-strong);
    }}

    div[data-testid="stExpander"] {{
        border: 1px solid var(--line) !important;
        border-radius: var(--radius-md) !important;
        background: var(--surface) !important;
        box-shadow: none !important;
        overflow: hidden;
        margin-bottom: 1rem;
    }}

    div[data-testid="stExpander"] details {{
        border: none !important;
    }}

    div[data-testid="stExpander"] summary {{
        color: var(--ink) !important;
        font-family: 'Spline Sans', sans-serif !important;
        font-weight: 500 !important;
        letter-spacing: 0;
    }}

    .main-hero {{
        position: relative;
        overflow: hidden;
        padding: 38px 40px 34px 40px;
        border-radius: var(--radius-lg);
        background: var(--surface);
        border: 1px solid var(--line);
        box-shadow: none;
        margin-bottom: 1.25rem;
        animation: rise 0.55s ease forwards;
    }}

    .hero-kicker {{
        display: inline-block;
        padding: 4px 11px;
        border-radius: 20px;
        background: var(--coral-bg);
        color: var(--coral-ink);
        font-family: 'Spline Sans', sans-serif;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 18px;
    }}

    .hero-title {{
        font-family: 'Fraunces', serif;
        font-size: clamp(34px, 6vw, 52px);
        line-height: 1.04;
        font-weight: 500;
        letter-spacing: -0.015em;
        color: var(--ink);
        margin: 0;
        max-width: 940px;
    }}

    .hero-subtitle {{
        margin-top: 18px;
        max-width: 760px;
        color: var(--ink-soft);
        font-size: 16px;
        line-height: 1.65;
        letter-spacing: 0;
    }}

    .hero-meta-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 26px;
    }}

    .hero-pill {{
        display: inline-block;
        padding: 5px 12px;
        border-radius: 20px;
        background: var(--bg);
        border: 1px solid var(--line);
        color: var(--ink-soft);
        font-size: 12px;
        font-weight: 500;
        letter-spacing: 0.01em;
    }}

    .hero-pill b {{
        color: var(--ink);
        font-weight: 600;
    }}

    .section-label {{
        margin-top: 2.2rem;
        margin-bottom: 0.55rem;
        color: var(--coral-ink);
        font-family: 'Spline Sans', sans-serif;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }}

    .section-title {{
        margin-top: 0;
        margin-bottom: 0.75rem;
        color: var(--ink);
        font-family: 'Fraunces', serif;
        font-size: 28px;
        font-weight: 500;
        letter-spacing: -0.01em;
    }}

    .small-note {{
        color: var(--ink-soft);
        font-size: 14px;
        line-height: 1.6;
        margin-top: -0.25rem;
        margin-bottom: 1rem;
    }}

    .glass-divider {{
        height: 1px;
        width: 100%;
        background: var(--line);
        margin: 1.6rem 0;
    }}

    .control-card {{
        padding: 22px;
        border-radius: var(--radius-md);
        background: var(--surface);
        border: 1px solid var(--line);
        margin-bottom: 1rem;
        box-shadow: none;
    }}

    .ai-card {{
        position: relative;
        overflow: hidden;
        padding: 26px 28px 24px 28px;
        border-radius: var(--radius-lg);
        background: var(--surface);
        border: 1px solid var(--line);
        box-shadow: none;
        margin-top: 1rem;
        margin-bottom: 1.25rem;
        animation: rise 0.55s ease forwards;
    }}

    .ai-kicker {{
        display: inline-block;
        color: var(--coral-ink);
        background: var(--coral-bg);
        border-radius: 20px;
        padding: 4px 11px;
        font-family: 'Spline Sans', sans-serif;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 14px;
    }}

    .ai-headline {{
        color: var(--ink);
        font-family: 'Fraunces', serif;
        font-size: clamp(24px, 3vw, 34px);
        line-height: 1.12;
        font-weight: 500;
        letter-spacing: -0.01em;
        margin-bottom: 12px;
    }}

    .ai-summary {{
        color: var(--ink-soft);
        font-size: 15.5px;
        line-height: 1.75;
        max-width: 980px;
    }}

    .ai-meta {{
        margin-top: 18px;
        color: var(--ink-faint);
        font-size: 13px;
    }}

    .metric-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin-top: 0.8rem;
        margin-bottom: 1.35rem;
    }}

    .premium-metric {{
        position: relative;
        overflow: hidden;
        min-height: 146px;
        padding: 20px 22px;
        border-radius: var(--radius-md);
        background: var(--surface);
        border: 1px solid var(--line);
        box-shadow: none;
        transition: transform 0.18s ease, border-color 0.18s ease;
    }}

    .premium-metric:hover {{
        transform: translateY(-3px);
        border-color: var(--line-strong);
    }}

    .premium-metric::after {{
        display: none;
    }}

    .metric-label {{
        position: relative;
        z-index: 1;
        color: var(--ink-soft);
        font-family: 'Spline Sans', sans-serif;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 13px;
    }}

    .metric-value {{
        position: relative;
        z-index: 1;
        color: var(--coral);
        font-family: 'Fraunces', serif;
        font-size: clamp(27px, 3vw, 34px);
        line-height: 1;
        font-weight: 600;
        letter-spacing: -0.01em;
        margin-bottom: 12px;
    }}

    .metric-sub {{
        position: relative;
        z-index: 1;
        color: var(--ink-soft);
        font-size: 13.5px;
        line-height: 1.5;
    }}

    .metric-positive {{
        color: var(--sage-ink);
    }}

    .metric-negative {{
        color: var(--brick-ink);
    }}

    .metric-neutral {{
        color: var(--coral);
    }}

    .ticker-shell {{
        width: 100%;
        overflow: hidden;
        border-radius: var(--radius-lg);
        border: 1px solid var(--line);
        background: var(--surface);
        box-shadow: none;
        padding: 12px 0;
        margin: 0.9rem 0 1.45rem 0;
    }}

    .ticker-track {{
        display: flex;
        width: max-content;
        animation: ticker-scroll 46s linear infinite;
        will-change: transform;
    }}

    .ticker-shell:hover .ticker-track {{
        animation-play-state: paused;
    }}

    .ticker-group {{
        display: flex;
        gap: 12px;
        padding-right: 12px;
    }}

    .ticker-card {{
        min-width: 226px;
        padding: 14px 16px;
        border-radius: var(--radius-md);
        background: var(--bg);
        border: 1px solid var(--line);
        box-shadow: none;
    }}

    .ticker-name {{
        color: var(--ink-soft);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
        white-space: nowrap;
    }}

    .ticker-price {{
        color: var(--ink);
        font-family: 'Fraunces', serif;
        font-size: 21px;
        font-weight: 600;
        letter-spacing: -0.01em;
        margin-bottom: 8px;
        white-space: nowrap;
    }}

    .ticker-stats {{
        display: flex;
        gap: 12px;
        flex-wrap: nowrap;
        font-size: 12px;
        font-weight: 500;
        white-space: nowrap;
    }}

    .ticker-up {{
        color: var(--sage-ink);
    }}

    .ticker-down {{
        color: var(--brick-ink);
    }}

    .ticker-flat {{
        color: var(--ink-faint);
    }}

    @keyframes ticker-scroll {{
        from {{ transform: translateX(0); }}
        to {{ transform: translateX(-50%); }}
    }}

    @keyframes rise {{
        from {{ opacity: 0; transform: translateY(16px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .ticker-track {{
            animation: none;
        }}

        .ai-card,
        .main-hero {{
            animation: none;
        }}
    }}

    @media (max-width: 900px) {{
        .block-container {{
            padding-top: 1.25rem;
        }}

        .main-hero {{
            padding: 28px 24px;
            border-radius: var(--radius-lg);
        }}

        .metric-grid {{
            grid-template-columns: 1fr;
        }}

        .ticker-card {{
            min-width: 210px;
        }}
    }}

    div[data-testid="stDataFrame"] {{
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--line);
        background: var(--surface);
    }}

    .stButton > button {{
        border-radius: var(--radius-sm);
        border: none;
        background: var(--coral);
        color: var(--surface);
        font-family: 'Spline Sans', sans-serif;
        font-weight: 600;
        font-size: 14px;
        padding: 10px 20px;
        transition: opacity 0.18s ease, transform 0.18s ease;
    }}

    .stButton > button:hover {{
        opacity: 0.88;
        transform: translateY(-1px);
        border: none;
        color: var(--surface);
    }}

    .stButton > button:focus {{
        box-shadow: 0 0 0 3px rgba(216, 90, 48, 0.12);
    }}

    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {{
        background: var(--surface) !important;
        border-color: var(--line-strong) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--ink) !important;
        font-family: 'Spline Sans', sans-serif !important;
    }}

    .stTextInput input:focus {{
        border-color: var(--coral) !important;
        box-shadow: 0 0 0 3px rgba(216, 90, 48, 0.12) !important;
    }}

    [data-testid="stCaptionContainer"] {{
        color: var(--ink-faint);
        font-size: 13px;
    }}

    hr {{
        border-color: var(--line);
    }}

    code {{
        color: var(--coral-ink);
        background: var(--coral-bg);
        border-radius: 6px;
        padding: 2px 5px;
    }}
</style>
"""

st.markdown(PREMIUM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def h(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def delta_class(value: Any) -> str:
    if pd.isna(value):
        return "metric-neutral"
    return "metric-positive" if value >= 0 else "metric-negative"


def render_html(markup: str) -> None:
    if hasattr(st, "html"):
        st.html(markup)
    else:
        st.markdown(markup, unsafe_allow_html=True)


def apply_sedona_chart_theme(fig: go.Figure, height: int = 420, yaxis_title: str = "", xaxis_title: str = "") -> go.Figure:
    fig.update_layout(
        template=None,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SEDONA_SURFACE,
        margin=dict(l=12, r=12, t=24, b=18),
        font=dict(
            family="Spline Sans, sans-serif",
            color=SEDONA_INK,
            size=13,
        ),
        hoverlabel=dict(
            bgcolor=SEDONA_SURFACE,
            bordercolor=SEDONA_LINE_STRONG,
            font_size=13,
            font_color=SEDONA_INK,
            font_family="Spline Sans, sans-serif",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(color=SEDONA_INK_SOFT, size=12),
        ),
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=SEDONA_LINE_STRONG,
        tickfont=dict(color=SEDONA_INK_SOFT),
        title_font=dict(color=SEDONA_INK_SOFT),
        fixedrange=True,
    )

    fig.update_yaxes(
        gridcolor=SEDONA_LINE,
        zeroline=False,
        linecolor=SEDONA_LINE_STRONG,
        tickfont=dict(color=SEDONA_INK_SOFT),
        title_font=dict(color=SEDONA_INK_SOFT),
        fixedrange=True,
    )

    return fig


def build_sedona_line_style_map(portfolio_names: list[str]) -> dict[str, dict[str, Any]]:
    base_styles = build_line_style_map(portfolio_names)

    sedona_palette = [
        CORAL,
        SAGE,
        AMBER,
        BRICK,
        "#8A6F3D",
        "#4E7F71",
        "#B76E4C",
        "#6F6A5F",
    ]

    cleaned_names = [str(name).strip() for name in portfolio_names if pd.notna(name)]
    unique_names = list(dict.fromkeys(cleaned_names))

    style_map = {}
    for index, name in enumerate(unique_names):
        upper_name = name.upper()

        if upper_name in {"SPY", "US:SPY"}:
            style_map[name] = {"color": CORAL, "dash": "dot", "width": 3.5}
        elif upper_name in {"DIA", "US:DIA"}:
            style_map[name] = {"color": AMBER, "dash": "dot", "width": 3.5}
        elif "GOOGLE" in upper_name:
            style_map[name] = {"color": "#8A6F3D", "dash": "solid", "width": 2.8}
        elif "OPENAI" in upper_name:
            style_map[name] = {"color": CORAL, "dash": "solid", "width": 2.8}
        elif upper_name == "RANDOM A":
            style_map[name] = {"color": "#6F6A5F", "dash": "solid", "width": 2.4}
        elif upper_name == "RANDOM B":
            style_map[name] = {"color": "#9A9386", "dash": "solid", "width": 2.4}
        else:
            fallback = base_styles.get(name, {})
            style_map[name] = {
                "color": sedona_palette[index % len(sedona_palette)],
                "dash": fallback.get("dash", "solid"),
                "width": fallback.get("width", 2.5),
            }

    return style_map


def apply_sedona_heatmap_theme(fig: go.Figure) -> go.Figure:
    fig.update_traces(
        colorscale=[
            [0.00, BRICK_BG],
            [0.25, "#F5D3D0"],
            [0.49, "#F8E5DF"],
            [0.50, SEDONA_BG],
            [0.51, "#EAF4EA"],
            [0.76, SAGE_BG],
            [1.00, SAGE],
        ],
        colorbar=dict(
            title=dict(text="Strength", font=dict(color=SEDONA_INK_SOFT)),
            thickness=12,
            len=0.78,
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.14,
            yanchor="top",
            tickvals=[0, 0.5, 1],
            ticktext=["Soft", "Neutral", "Strong"],
            outlinewidth=0,
            tickfont=dict(color=SEDONA_INK_SOFT),
        ),
        textfont={"size": 12, "color": SEDONA_INK},
    )

    fig.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SEDONA_SURFACE,
        margin=dict(l=10, r=10, t=24, b=52),
        font=dict(
            family="Spline Sans, sans-serif",
            color=SEDONA_INK,
        ),
    )

    fig.update_xaxes(
        side="top",
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=12, color=SEDONA_INK_SOFT),
        showline=False,
        fixedrange=True,
    )

    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=13, color=SEDONA_INK),
        showline=False,
        fixedrange=True,
    )

    return fig


def build_banner_stats(portfolio_history_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    if portfolio_history_df.empty or summary_df.empty:
        return pd.DataFrame(
            columns=[
                "Portfolio",
                "Latest Value",
                "Daily Move",
                "Daily Move Display",
                "Overall Return",
                "Overall Return Display",
                "Sparkline",
            ]
        )

    history_sorted = portfolio_history_df.sort_values(["Portfolio", "Date"]).copy()
    records = []

    for portfolio_name, group in history_sorted.groupby("Portfolio"):
        group = group.sort_values("Date").copy()
        values = group["Portfolio Value"].dropna().tolist()

        if not values:
            continue

        latest_value = float(values[-1])
        daily_move = None

        if len(values) >= 2:
            prior_value = float(values[-2])
            if prior_value != 0:
                daily_move = (latest_value / prior_value) - 1

        records.append(
            {
                "Portfolio": portfolio_name,
                "Latest Value": latest_value,
                "Daily Move": daily_move,
                "Sparkline": values[-20:] if len(values) >= 2 else values,
            }
        )

    banner_df = pd.DataFrame(records)

    if banner_df.empty:
        return banner_df

    summary_slice = summary_df[["Portfolio", "Return"]].copy()
    banner_df = banner_df.merge(summary_slice, on="Portfolio", how="left")
    banner_df = banner_df.rename(columns={"Return": "Overall Return"})

    banner_df["Daily Move Display"] = banner_df["Daily Move"].apply(
        lambda x: "-" if pd.isna(x) else pct(x)
    )
    banner_df["Overall Return Display"] = banner_df["Overall Return"].apply(
        lambda x: "-" if pd.isna(x) else pct(x)
    )

    return banner_df.sort_values("Overall Return", ascending=False).reset_index(drop=True)


def read_daily_insight_payload(path: Path = DAILY_INSIGHT_PATH) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, f"Could not find `{path.as_posix()}`. The daily commentary job has not written the file yet."

    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        return None, f"`{path.as_posix()}` exists, but it is not valid JSON: {exc}"
    except OSError as exc:
        return None, f"`{path.as_posix()}` exists, but Streamlit could not read it: {exc}"

    return payload, None


def get_latest_daily_insight(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        if not payload:
            return {}

        dict_records = [item for item in payload if isinstance(item, dict)]

        if not dict_records:
            return {}

        return sorted(
            dict_records,
            key=lambda item: str(
                item.get("date")
                or item.get("as_of_date")
                or item.get("generated_for")
                or item.get("generated_at")
                or ""
            ),
            reverse=True,
        )[0]

    if isinstance(payload, dict):
        for collection_key in ["insights", "records", "daily_insights", "items"]:
            records = payload.get(collection_key)

            if isinstance(records, list) and records:
                dict_records = [item for item in records if isinstance(item, dict)]

                if dict_records:
                    return sorted(
                        dict_records,
                        key=lambda item: str(
                            item.get("date")
                            or item.get("as_of_date")
                            or item.get("generated_for")
                            or item.get("generated_at")
                            or ""
                        ),
                        reverse=True,
                    )[0]

        return payload

    return {}


def first_present(record: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return str(value)

    return default


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]


def format_generated_at(value: str) -> str:
    if not value:
        return ""

    raw_value = str(value).strip()

    try:
        from zoneinfo import ZoneInfo

        cleaned_value = raw_value.replace("Z", "+00:00")
        parsed_value = datetime.fromisoformat(cleaned_value)

        if parsed_value.tzinfo is None:
            parsed_value = parsed_value.replace(tzinfo=ZoneInfo("UTC"))

        central_time = parsed_value.astimezone(ZoneInfo("America/Chicago"))
        return central_time.strftime("%I:%M %p %B %d, %Y CT").lstrip("0")
    except Exception:
        return raw_value


def get_ai_refresh_password() -> str:
    try:
        secret_value = st.secrets.get("AI_REFRESH_PASSWORD", "")
        if secret_value:
            return str(secret_value)
    except Exception:
        pass

    return os.getenv("AI_REFRESH_PASSWORD", "")


def manually_refresh_daily_insight(
    portfolios_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    benchmark_choice: str,
) -> tuple[bool, str]:
    try:
        (
            portfolio_history_df,
            _merged_positions_df,
            holdings_snapshot_df,
            benchmark_history_df,
            _portfolio_cumret_df,
            _benchmark_cumret_df,
        ) = build_datasets(portfolios_df, prices_df)

        metrics_payload = build_ytd_metrics_snapshot(
            portfolio_history=portfolio_history_df,
            holdings_snapshot=holdings_snapshot_df,
            benchmark_history=benchmark_history_df,
            benchmark_choice=benchmark_choice,
        )

        record = generate_llm_insight(metrics_payload)
        output_path = save_daily_insight(record)

        status = record.get("status", "unknown")
        source = record.get("source", "unknown")

        return (
            True,
            f"Daily commentary refreshed. Status: `{status}`. Source: `{source}`. Saved to `{output_path.as_posix()}`.",
        )

    except Exception as exc:
        return False, f"Could not refresh daily commentary: {exc}"


# ---------------------------------------------------------------------
# Render components
# ---------------------------------------------------------------------

def render_hero_banner(
    latest_date: pd.Timestamp,
    benchmark_choice: str,
    portfolio_count: int,
) -> None:
    latest_label = latest_date.strftime("%B %d, %Y") if pd.notna(latest_date) else "Unavailable"

    st.markdown(
        f"""
        <div class="main-hero">
            <div class="hero-kicker">Live research dashboard</div>
            <h1 class="hero-title">From Noise to Action</h1>
            <div class="hero-subtitle">
                Market narratives, measured against reality. A calm read on whether recurring model-selected portfolios are separating from benchmarks and random baselines.
            </div>
            <div class="hero-meta-row">
                <div class="hero-pill"><b>Data through</b> {h(latest_label)}</div>
                <div class="hero-pill"><b>Benchmark</b> {h(benchmark_choice)}</div>
                <div class="hero-pill"><b>Portfolios tracked</b> {portfolio_count}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_control_panel(
    all_portfolios_source: list[str],
    benchmark_options: list[str],
    date_min,
    date_max,
    portfolios: pd.DataFrame,
    prices: pd.DataFrame,
) -> None:
    with st.expander("Refine view", expanded=False):
        st.markdown(
            """
            <div class="small-note">
                Keep the default view for the clean readout, or adjust portfolio set, benchmark, and date range.
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1.45, 0.8, 1.0])

        with c1:
            st.multiselect(
                "Portfolios",
                options=all_portfolios_source,
                default=st.session_state.selected_portfolios,
                key="selected_portfolios",
            )

        with c2:
            st.selectbox(
                "Benchmark",
                options=benchmark_options,
                key="benchmark_choice",
            )

        with c3:
            st.date_input(
                "Date range",
                value=st.session_state.date_range,
                min_value=date_min,
                max_value=date_max,
                key="date_range",
            )

        b1, b2, b3 = st.columns([0.9, 0.9, 2.2])

        with b1:
            if st.button("Refresh data", key="refresh_prices_button", use_container_width=True):
                fetch_price_history.clear()
                st.rerun()

        with b2:
            if st.button("Reset view", key="reset_defaults_button", use_container_width=True):
                st.session_state.selected_portfolios = all_portfolios_source
                st.session_state.benchmark_choice = (
                    "SPY" if "SPY" in benchmark_options else benchmark_options[0]
                )
                st.session_state.date_range = (date_min, date_max)
                st.rerun()

        with b3:
            st.caption("Data is cached for performance. Refresh only when you need a new yfinance pull.")

        st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

        st.markdown("#### Commentary refresh")

        p1, p2 = st.columns([1.2, 0.8])

        with p1:
            ai_refresh_password = st.text_input(
                "Refresh password",
                type="password",
                key="ai_refresh_password",
                help="Required to manually regenerate the daily portfolio commentary.",
            )

        with p2:
            st.write("")
            st.write("")
            if st.button("Refresh commentary", key="refresh_ai_summary_button", use_container_width=True):
                expected_password = get_ai_refresh_password()

                if not expected_password:
                    st.error("Commentary refresh password is not configured.")
                elif ai_refresh_password != expected_password:
                    st.error("Incorrect password.")
                else:
                    with st.spinner("Refreshing daily commentary..."):
                        success, message = manually_refresh_daily_insight(
                            portfolios_df=portfolios,
                            prices_df=prices,
                            benchmark_choice=st.session_state.benchmark_choice,
                        )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


def render_daily_ai_summary() -> None:
    payload, error_message = read_daily_insight_payload()
    record = get_latest_daily_insight(payload) if payload is not None else {}

    if error_message:
        st.markdown(
            f"""
            <div class="ai-card">
                <div class="ai-kicker">Market readout</div>
                <div class="ai-headline">Daily commentary is not available yet.</div>
                <div class="ai-summary">
                    The dashboard is running. The missing piece is the generated commentary artifact at <code>{h(DAILY_INSIGHT_PATH.as_posix())}</code>.
                </div>
                <div class="ai-meta">{h(error_message)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if not record:
        st.markdown(
            """
            <div class="ai-card">
                <div class="ai-kicker">Market readout</div>
                <div class="ai-headline">Daily commentary is waiting for usable data.</div>
                <div class="ai-summary">
                    The commentary file loaded, but no readable commentary record was found.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    headline = first_present(
        record,
        ["headline", "title", "summary_title"],
        "Portfolio performance readout",
    )

    summary = first_present(
        record,
        [
            "summary",
            "insight_text",
            "insight",
            "narrative",
            "text",
            "analysis",
            "ai_summary",
            "daily_summary",
            "portfolio_summary",
        ],
        "",
    )

    generated_at = first_present(record, ["generated_at"], "")
    formatted_generated_at = format_generated_at(generated_at)
    as_of_date = first_present(
        record,
        ["date", "as_of_date", "generated_for", "generated_at"],
        "not generated yet",
    )

    updated_label = formatted_generated_at or as_of_date

    update_note = first_present(
        record,
        ["update_note"],
        "Updated 30 minutes before and after market close.",
    )

    bullets = as_list(
        record.get("takeaways")
        or record.get("bullets")
        or record.get("key_points")
        or record.get("highlights")
    )

    st.markdown(
        f"""
        <div class="ai-card">
            <div class="ai-kicker">Market readout</div>
            <div class="ai-headline">{h(headline)}</div>
            <div class="ai-summary">{h(summary)}</div>
            <div class="ai-meta">{h(update_note)} Updated {h(updated_label)}.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if bullets:
        with st.expander("View key takeaways", expanded=False):
            for bullet in bullets:
                if isinstance(bullet, dict):
                    bullet_text = " | ".join(
                        f"{key}: {value}"
                        for key, value in bullet.items()
                        if value not in (None, "", [], {})
                    )
                    if bullet_text:
                        st.markdown(f"- {bullet_text}")
                else:
                    st.markdown(f"- {bullet}")


def render_portfolio_ticker(banner_df: pd.DataFrame) -> None:
    if banner_df.empty:
        return

    items = []

    for _, row in banner_df.iterrows():
        daily_move = row["Daily Move"]
        overall_return = row["Overall Return"]

        daily_class = "ticker-flat"
        if pd.notna(daily_move):
            daily_class = "ticker-up" if daily_move >= 0 else "ticker-down"

        overall_class = "ticker-flat"
        if pd.notna(overall_return):
            overall_class = "ticker-up" if overall_return >= 0 else "ticker-down"

        items.append(
            f"""
            <div class="ticker-card">
                <div class="ticker-name">{h(row["Portfolio"])}</div>
                <div class="ticker-price">{h(money(row["Latest Value"]))}</div>
                <div class="ticker-stats">
                    <span class="{daily_class}">Day {h(row["Daily Move Display"])}</span>
                    <span class="{overall_class}">Total {h(row["Overall Return Display"])}</span>
                </div>
            </div>
            """
        )

    cards_html = "".join(items)

    render_html(
        f"""
        <div class="ticker-shell">
            <div class="ticker-track">
                <div class="ticker-group">{cards_html}</div>
                <div class="ticker-group">{cards_html}</div>
            </div>
        </div>
        """
    )


def render_metric_card(title: str, value: str, subtitle: str = "", value_class: str = "metric-neutral") -> None:
    st.markdown(
        f"""
        <div class="premium-metric">
            <div class="metric-label">{h(title)}</div>
            <div class="metric-value {h(value_class)}">{h(value)}</div>
            <div class="metric-sub">{h(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_grid(
    summary_f: pd.DataFrame,
    benchmark_choice: str,
    benchmark_summary: dict[str, Any] | None,
) -> None:
    if summary_f.empty:
        st.info("No summary metrics are available for the selected filters.")
        return

    best_row = summary_f.sort_values("Return", ascending=False).iloc[0]
    riskiest_row = summary_f.sort_values("Volatility", ascending=False).iloc[0]
    alpha_summary_f = exclude_benchmark_portfolios(summary_f, portfolio_col="Portfolio")

    avg_return = alpha_summary_f["Return"].mean() if not alpha_summary_f.empty else None
    relative_vs_benchmark = None

    if (
        not alpha_summary_f.empty
        and benchmark_summary is not None
        and benchmark_summary.get("Return") is not None
        and avg_return is not None
    ):
        relative_vs_benchmark = avg_return - benchmark_summary["Return"]

    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        render_metric_card(
            title=f"Avg Alpha vs {benchmark_choice}",
            value=pct(relative_vs_benchmark) if relative_vs_benchmark is not None else "-",
            subtitle="Average selected portfolio return minus benchmark return.",
            value_class=delta_class(relative_vs_benchmark),
        )

    with c2:
        render_metric_card(
            title="Best Portfolio",
            value=str(best_row["Portfolio"]),
            subtitle=f"{pct(best_row['Return'])} total return",
            value_class=delta_class(best_row["Return"]),
        )

    with c3:
        render_metric_card(
            title="Most Volatile",
            value=str(riskiest_row["Portfolio"]),
            subtitle=f"{pct(riskiest_row['Volatility'])} daily volatility",
            value_class="metric-neutral",
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_about_why() -> None:
    with st.expander("Methodology", expanded=False):
        st.markdown(
            """
            ### What this is testing

            This project asks whether repeated market narratives can produce portfolios that behave differently from passive benchmarks and random stock selections.

            The goal is not to claim that models predict the market. The goal is to measure whether recurring themes show up in portfolio performance when tracked from the same start date and evaluated with the same benchmark lens.

            **This is not financial advice.** It is a live research dashboard about narrative signals, benchmark-relative performance, and disciplined measurement.
            """
        )


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

try:
    portfolios, prices = load_data()
except Exception as exc:
    st.error(f"Could not load portfolio data: {exc}")
    st.stop()

if prices.empty:
    st.error("No price data was returned from yfinance.")
    st.stop()

latest_available_date = prices["Date"].max()
all_portfolios_source = sorted(portfolios["Portfolio"].dropna().astype(str).unique().tolist())
date_min = prices["Date"].min().date()
date_max = prices["Date"].max().date()

default_portfolios = all_portfolios_source
benchmark_options = [key for key, value in BENCHMARK_MAP.items() if value in prices.columns]

if not benchmark_options:
    benchmark_options = list(BENCHMARK_MAP.keys())

default_benchmark = "SPY" if "SPY" in benchmark_options else benchmark_options[0]
default_dates = (date_min, date_max)

if "selected_portfolios" not in st.session_state:
    st.session_state.selected_portfolios = default_portfolios

if "benchmark_choice" not in st.session_state:
    st.session_state.benchmark_choice = default_benchmark

if "date_range" not in st.session_state:
    st.session_state.date_range = default_dates

if st.session_state.benchmark_choice not in benchmark_options:
    st.session_state.benchmark_choice = default_benchmark


# ---------------------------------------------------------------------
# App shell
# ---------------------------------------------------------------------

render_hero_banner(
    latest_date=latest_available_date,
    benchmark_choice=st.session_state.benchmark_choice,
    portfolio_count=len(default_portfolios),
)

render_control_panel(
    all_portfolios_source=all_portfolios_source,
    benchmark_options=benchmark_options,
    date_min=date_min,
    date_max=date_max,
    portfolios=portfolios,
    prices=prices,
)

try:
    (
        portfolio_history,
        merged_positions,
        holdings_snapshot,
        benchmark_history,
        portfolio_cumret,
        benchmark_cumret,
    ) = build_datasets(portfolios, prices)
except Exception as exc:
    st.error(f"Could not build dashboard datasets: {repr(exc)}")
    st.write("Portfolio columns:", portfolios.columns.tolist())
    st.write("Price columns:", prices.columns.tolist())
    st.write("Portfolio preview:", portfolios.head())
    st.write("Price preview:", prices.head())
    st.stop()

if portfolio_history.empty:
    st.error("No valid portfolio history could be built from price data.")
    st.stop()

all_portfolios = sorted(portfolio_history["Portfolio"].dropna().unique().tolist())

selected_portfolios = [
    portfolio
    for portfolio in st.session_state.selected_portfolios
    if portfolio in all_portfolios
]

if not selected_portfolios:
    st.warning("Select at least one portfolio.")
    st.stop()

benchmark_choice = st.session_state.benchmark_choice
date_range = st.session_state.date_range

start_date, end_date = normalize_date_range(date_range, date_min, date_max)

if start_date > end_date:
    st.warning("Start date must be before end date.")
    st.stop()

portfolio_history_f = portfolio_history[
    (portfolio_history["Portfolio"].isin(selected_portfolios))
    & (portfolio_history["Date"] >= start_date)
    & (portfolio_history["Date"] <= end_date)
].copy()

summary_f = build_summary(portfolio_history_f)

portfolio_cumret_f = portfolio_cumret[
    (portfolio_cumret["Portfolio"].isin(selected_portfolios))
    & (portfolio_cumret["Date"] >= start_date)
    & (portfolio_cumret["Date"] <= end_date)
].copy()

benchmark_cumret_f = benchmark_cumret[
    (benchmark_cumret["Date"] >= start_date)
    & (benchmark_cumret["Date"] <= end_date)
].copy()

holdings_snapshot_f = holdings_snapshot[
    holdings_snapshot["Portfolio"].isin(selected_portfolios)
].copy()

benchmark_summary = summarize_benchmark(
    benchmark_history=benchmark_history,
    benchmark_label=benchmark_choice,
    start_date=start_date,
    end_date=end_date,
)

banner_df = build_banner_stats(
    portfolio_history_df=portfolio_history_f,
    summary_df=summary_f,
)


# ---------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------

render_daily_ai_summary()

render_portfolio_ticker(banner_df)

st.markdown('<div class="section-label">Performance</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Benchmark-relative readout</div>', unsafe_allow_html=True)

render_metric_grid(
    summary_f=summary_f,
    benchmark_choice=benchmark_choice,
    benchmark_summary=benchmark_summary,
)

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Primary chart</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Cumulative return comparison</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-note">Percent return since the start of the selected date range.</div>',
    unsafe_allow_html=True,
)

cumret_plot_df = portfolio_cumret_f[["Date", "Portfolio", "Cumulative Return"]].copy()

benchmark_already_present = benchmark_choice in {
    str(name).strip()
    for name in cumret_plot_df["Portfolio"].dropna().unique()
}

if not benchmark_cumret_f.empty and not benchmark_already_present:
    benchmark_line = benchmark_cumret_f[benchmark_cumret_f["Portfolio"] == benchmark_choice].copy()

    if not benchmark_line.empty:
        cumret_plot_df = pd.concat(
            [cumret_plot_df, benchmark_line[["Date", "Portfolio", "Cumulative Return"]]],
            ignore_index=True,
        )

if not cumret_plot_df.empty:
    cumret_line_styles = build_sedona_line_style_map(cumret_plot_df["Portfolio"].unique().tolist())

    if benchmark_choice in cumret_line_styles:
        cumret_line_styles[benchmark_choice]["color"] = CORAL
        cumret_line_styles[benchmark_choice]["width"] = 3.8
        cumret_line_styles[benchmark_choice]["dash"] = "dot"

    fig_cumret = px.line(
        cumret_plot_df,
        x="Date",
        y="Cumulative Return",
        color="Portfolio",
    )

    apply_line_styles(fig_cumret, cumret_line_styles)
    chart_layout(fig_cumret, height=470, yaxis_title="Cumulative Return")
    apply_sedona_chart_theme(fig_cumret, height=470, yaxis_title="Cumulative Return")
    fig_cumret.update_yaxes(tickformat=".0%")
    fig_cumret.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            title=None,
            font=dict(color=SEDONA_INK_SOFT, size=12),
        ),
        margin=dict(b=112),
    )

    render_chart(fig_cumret, key="fig_cumret")
else:
    st.info("No cumulative return data available.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Portfolio ranking</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Total return by portfolio</div>', unsafe_allow_html=True)

if not summary_f.empty:
    bar_df = summary_f.sort_values("Return", ascending=False).copy()
    bar_colors = [
        SAGE if pd.notna(value) and value >= 0 else BRICK
        for value in bar_df["Return"]
    ]

    fig_bar = go.Figure(
        data=[
            go.Bar(
                x=bar_df["Portfolio"],
                y=bar_df["Return"],
                text=bar_df["Return"].map(lambda x: "-" if pd.isna(x) else f"{x:.1%}"),
                textposition="outside",
                marker=dict(
                    color=bar_colors,
                    line=dict(color=SEDONA_LINE_STRONG, width=1),
                ),
                hovertemplate="<b>%{x}</b><br>Return: %{y:.2%}<extra></extra>",
            )
        ]
    )

    chart_layout(fig_bar, height=390, yaxis_title="Return")
    apply_sedona_chart_theme(fig_bar, height=390, yaxis_title="Return")
    fig_bar.update_yaxes(tickformat=".0%")
    render_chart(fig_bar, key="fig_bar")
else:
    st.info("No return data available.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Signal map</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Portfolio heatmap</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-note">Warmer cells indicate softer relative performance. Cooler green cells indicate stronger relative performance. Lower volatility is rewarded.</div>',
    unsafe_allow_html=True,
)

if not summary_f.empty:
    heatmap_fig = build_portfolio_heatmap(summary_f, money, pct)

    if heatmap_fig is not None:
        apply_sedona_heatmap_theme(heatmap_fig)
        render_chart(heatmap_fig, key="heatmap_fig")
    else:
        st.info("No heatmap data available.")
else:
    st.info("No heatmap data available.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Drilldown</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Portfolio detail</div>', unsafe_allow_html=True)

chosen_portfolio = st.selectbox("Choose a portfolio", selected_portfolios)

detail_holdings = holdings_snapshot_f[
    holdings_snapshot_f["Portfolio"] == chosen_portfolio
].copy()

detail_history = portfolio_history_f[
    portfolio_history_f["Portfolio"] == chosen_portfolio
].copy()

d1, d2 = st.columns([1.05, 1.55])

with d1:
    st.markdown("#### Holdings")

    if not detail_holdings.empty:
        detail_display = format_holdings_table(detail_holdings)
        st.dataframe(
            detail_display[
                [
                    "Ticker",
                    "Initial Investment",
                    "Shares",
                    "Current Value",
                    "Dollar Change",
                    "Return",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No holdings available for this portfolio.")

with d2:
    st.markdown("#### Value trend")

    if not detail_history.empty:
        fig_single = px.area(
            detail_history,
            x="Date",
            y="Portfolio Value",
        )

        chart_layout(fig_single, height=380, yaxis_title="Value")
        apply_sedona_chart_theme(fig_single, height=380, yaxis_title="Value")
        fig_single.update_traces(
            line=dict(color=CORAL, width=2.5),
            fillcolor="rgba(216, 90, 48, 0.16)",
        )

        max_value = detail_history["Portfolio Value"].max()

        if pd.notna(max_value) and max_value > 0:
            fig_single.update_yaxes(range=[max(0, max_value * 0.88), max_value * 1.04])

        render_chart(fig_single, key="fig_single")
    else:
        st.info("No history available for this portfolio.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

render_about_why()

with st.expander("Technical details", expanded=False):
    st.markdown("#### Portfolio summary table")

    if not summary_f.empty:
        st.dataframe(
            format_summary_table(summary_f),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No summary table available.")

    st.markdown("#### Price table preview")
    st.dataframe(prices.head(20), use_container_width=True, hide_index=True)
