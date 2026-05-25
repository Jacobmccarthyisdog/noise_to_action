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
ACCENT_BLUE = "#2997FF"


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
    :root {{
        --bg: #050505;
        --bg-soft: #0B0B0D;
        --surface: rgba(255,255,255,0.045);
        --surface-strong: rgba(255,255,255,0.075);
        --text: #F5F5F7;
        --muted: #A1A1A6;
        --muted-2: #6E6E73;
        --border: rgba(255,255,255,0.105);
        --border-strong: rgba(255,255,255,0.16);
        --accent: {ACCENT_BLUE};
        --good: #30D158;
        --bad: #FF453A;
    }}

    .stApp {{
        background:
            radial-gradient(circle at 50% -10%, rgba(41,151,255,0.18), transparent 32%),
            radial-gradient(circle at 8% 20%, rgba(41,151,255,0.08), transparent 24%),
            linear-gradient(180deg, #050505 0%, #08080A 44%, #050505 100%);
        color: var(--text);
    }}

    .block-container {{
        max-width: 1240px;
        padding-top: 1.35rem;
        padding-bottom: 4rem;
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: var(--text);
        letter-spacing: -0.035em;
    }}

    p, label, span, div {{
        color: inherit;
    }}

    section[data-testid="stSidebar"] {{
        background: rgba(10,10,12,0.96);
        border-right: 1px solid var(--border);
    }}

    div[data-testid="stExpander"] {{
        border: 1px solid var(--border) !important;
        border-radius: 26px !important;
        background:
            linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.028)) !important;
        box-shadow: 0 24px 70px rgba(0,0,0,0.22);
        overflow: hidden;
        margin-bottom: 1rem;
    }}

    div[data-testid="stExpander"] details {{
        border: none !important;
    }}

    div[data-testid="stExpander"] summary {{
        color: var(--text) !important;
        font-weight: 750 !important;
        letter-spacing: -0.01em;
    }}

    .main-hero {{
        position: relative;
        overflow: hidden;
        padding: 42px 44px 38px 44px;
        border-radius: 34px;
        background:
            radial-gradient(circle at top right, rgba(41,151,255,0.22), transparent 32%),
            linear-gradient(145deg, rgba(255,255,255,0.082), rgba(255,255,255,0.028));
        border: 1px solid var(--border);
        box-shadow:
            0 32px 100px rgba(0,0,0,0.34),
            inset 0 1px 0 rgba(255,255,255,0.08);
        margin-bottom: 1rem;
    }}

    .hero-kicker {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 11px;
        border-radius: 999px;
        background: rgba(41,151,255,0.12);
        border: 1px solid rgba(41,151,255,0.28);
        color: #B9DDFF;
        font-size: 0.75rem;
        font-weight: 760;
        text-transform: uppercase;
        letter-spacing: 0.115em;
        margin-bottom: 18px;
    }}

    .hero-title {{
        font-size: clamp(2.4rem, 6vw, 5.2rem);
        line-height: 0.94;
        font-weight: 850;
        letter-spacing: -0.07em;
        color: var(--text);
        margin: 0;
        max-width: 980px;
    }}

    .hero-subtitle {{
        margin-top: 18px;
        max-width: 780px;
        color: rgba(245,245,247,0.76);
        font-size: 1.14rem;
        line-height: 1.55;
        letter-spacing: -0.01em;
    }}

    .hero-meta-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 26px;
    }}

    .hero-pill {{
        padding: 9px 13px;
        border-radius: 999px;
        background: rgba(255,255,255,0.055);
        border: 1px solid var(--border);
        color: rgba(245,245,247,0.84);
        font-size: 0.86rem;
        font-weight: 620;
    }}

    .hero-pill b {{
        color: var(--text);
        font-weight: 760;
    }}

    .section-label {{
        margin-top: 2rem;
        margin-bottom: 0.65rem;
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 780;
        letter-spacing: 0.13em;
        text-transform: uppercase;
    }}

    .section-title {{
        margin-top: 0;
        margin-bottom: 0.7rem;
        color: var(--text);
        font-size: 1.55rem;
        font-weight: 810;
        letter-spacing: -0.04em;
    }}

    .small-note {{
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.45;
        margin-top: -0.25rem;
        margin-bottom: 0.9rem;
    }}

    .glass-divider {{
        height: 1px;
        width: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.14), transparent);
        margin: 1.35rem 0;
    }}

    .control-card {{
        padding: 20px;
        border-radius: 26px;
        background:
            linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.026));
        border: 1px solid var(--border);
        margin-bottom: 1rem;
    }}

    .ai-card {{
        position: relative;
        overflow: hidden;
        padding: 28px 30px 26px 30px;
        border-radius: 30px;
        background:
            radial-gradient(circle at top right, rgba(41,151,255,0.22), transparent 34%),
            linear-gradient(145deg, rgba(255,255,255,0.072), rgba(255,255,255,0.026));
        border: 1px solid var(--border);
        box-shadow:
            0 28px 90px rgba(0,0,0,0.28),
            inset 0 1px 0 rgba(255,255,255,0.07);
        margin-top: 0.9rem;
        margin-bottom: 1.2rem;
    }}

    .ai-kicker {{
        color: #B9DDFF;
        font-size: 0.74rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 12px;
    }}

    .ai-headline {{
        color: var(--text);
        font-size: clamp(1.4rem, 2.8vw, 2.2rem);
        line-height: 1.08;
        font-weight: 830;
        letter-spacing: -0.045em;
        margin-bottom: 12px;
    }}

    .ai-summary {{
        color: rgba(245,245,247,0.82);
        font-size: 1.02rem;
        line-height: 1.62;
        max-width: 980px;
    }}

    .ai-meta {{
        margin-top: 16px;
        color: var(--muted);
        font-size: 0.86rem;
    }}

    .metric-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin-top: 0.7rem;
        margin-bottom: 1.2rem;
    }}

    .premium-metric {{
        position: relative;
        overflow: hidden;
        min-height: 152px;
        padding: 22px 22px 20px 22px;
        border-radius: 28px;
        background:
            linear-gradient(180deg, rgba(255,255,255,0.066), rgba(255,255,255,0.027));
        border: 1px solid var(--border);
        box-shadow:
            0 24px 75px rgba(0,0,0,0.24),
            inset 0 1px 0 rgba(255,255,255,0.06);
    }}

    .premium-metric::after {{
        content: "";
        position: absolute;
        inset: -1px;
        pointer-events: none;
        background: radial-gradient(circle at top right, rgba(41,151,255,0.14), transparent 36%);
    }}

    .metric-label {{
        position: relative;
        z-index: 1;
        color: var(--muted);
        font-size: 0.77rem;
        font-weight: 780;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 14px;
    }}

    .metric-value {{
        position: relative;
        z-index: 1;
        color: var(--text);
        font-size: clamp(1.5rem, 3vw, 2.15rem);
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.055em;
        margin-bottom: 12px;
    }}

    .metric-sub {{
        position: relative;
        z-index: 1;
        color: rgba(245,245,247,0.66);
        font-size: 0.93rem;
        line-height: 1.45;
    }}

    .metric-positive {{
        color: var(--accent);
    }}

    .metric-negative {{
        color: var(--bad);
    }}

    .metric-neutral {{
        color: var(--text);
    }}

    .ticker-shell {{
        width: 100%;
        overflow: hidden;
        border-radius: 30px;
        border: 1px solid var(--border);
        background:
            radial-gradient(circle at top right, rgba(41,151,255,0.13), transparent 30%),
            linear-gradient(180deg, rgba(255,255,255,0.058), rgba(255,255,255,0.025));
        box-shadow:
            0 24px 80px rgba(0,0,0,0.24),
            inset 0 1px 0 rgba(255,255,255,0.06);
        padding: 12px 0;
        margin: 0.8rem 0 1.35rem 0;
    }}

    .ticker-track {{
        display: flex;
        width: max-content;
        animation: ticker-scroll 42s linear infinite;
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
        min-width: 238px;
        padding: 15px 16px 14px 16px;
        border-radius: 22px;
        background:
            linear-gradient(180deg, rgba(255,255,255,0.062), rgba(255,255,255,0.026));
        border: 1px solid var(--border);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.045);
    }}

    .ticker-name {{
        color: var(--muted);
        font-size: 0.74rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.11em;
        margin-bottom: 9px;
        white-space: nowrap;
    }}

    .ticker-price {{
        color: var(--text);
        font-size: 1.08rem;
        font-weight: 820;
        letter-spacing: -0.025em;
        margin-bottom: 8px;
        white-space: nowrap;
    }}

    .ticker-stats {{
        display: flex;
        gap: 12px;
        flex-wrap: nowrap;
        font-size: 0.82rem;
        font-weight: 720;
        white-space: nowrap;
    }}

    .ticker-up {{
        color: var(--accent);
    }}

    .ticker-down {{
        color: var(--bad);
    }}

    .ticker-flat {{
        color: rgba(245,245,247,0.62);
    }}

    @keyframes ticker-scroll {{
        from {{ transform: translateX(0); }}
        to {{ transform: translateX(-50%); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .ticker-track {{
            animation: none;
        }}
    }}

    @media (max-width: 900px) {{
        .main-hero {{
            padding: 30px 24px 28px 24px;
            border-radius: 28px;
        }}

        .metric-grid {{
            grid-template-columns: 1fr;
        }}

        .ticker-card {{
            min-width: 210px;
        }}
    }}

    div[data-testid="stDataFrame"] {{
        border-radius: 20px;
        overflow: hidden;
        border: 1px solid var(--border);
    }}

    .stButton > button {{
        border-radius: 999px;
        border: 1px solid rgba(41,151,255,0.38);
        background: rgba(41,151,255,0.13);
        color: #D7ECFF;
        font-weight: 760;
    }}

    .stButton > button:hover {{
        border-color: rgba(41,151,255,0.72);
        background: rgba(41,151,255,0.20);
        color: #FFFFFF;
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
        return None, f"Could not find `{path.as_posix()}`. The daily insight job has not written the file yet."

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
            f"Daily AI insight refreshed. Status: `{status}`. Source: `{source}`. Saved to `{output_path.as_posix()}`.",
        )

    except Exception as exc:
        return False, f"Could not refresh daily AI insight: {exc}"


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
                AI-generated market narratives, measured against reality. A calm view of whether repeated model-selected portfolios are separating from benchmarks and random baselines.
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

        st.markdown("#### AI summary refresh")

        p1, p2 = st.columns([1.2, 0.8])

        with p1:
            ai_refresh_password = st.text_input(
                "Refresh password",
                type="password",
                key="ai_refresh_password",
                help="Required to manually regenerate the daily AI portfolio summary.",
            )

        with p2:
            st.write("")
            st.write("")
            if st.button("Refresh AI summary", key="refresh_ai_summary_button", use_container_width=True):
                expected_password = get_ai_refresh_password()

                if not expected_password:
                    st.error("AI refresh password is not configured.")
                elif ai_refresh_password != expected_password:
                    st.error("Incorrect password.")
                else:
                    with st.spinner("Refreshing daily AI summary..."):
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
                <div class="ai-kicker">AI readout</div>
                <div class="ai-headline">Daily insight is not available yet.</div>
                <div class="ai-summary">
                    The dashboard is running. The missing piece is the generated JSON artifact at <code>{h(DAILY_INSIGHT_PATH.as_posix())}</code>.
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
                <div class="ai-kicker">AI readout</div>
                <div class="ai-headline">Daily insight is waiting for usable data.</div>
                <div class="ai-summary">
                    The insight file loaded, but no readable insight record was found.
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
            <div class="ai-kicker">AI readout</div>
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

            This project asks whether repeated LLM-generated market narratives can produce portfolios that behave differently from passive benchmarks and random stock selections.

            The goal is not to claim that AI predicts the market. The goal is to measure whether recurring AI-generated themes show up in portfolio performance when tracked from the same start date and evaluated with the same benchmark lens.

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
st.markdown('<div class="section-title">The benchmark-relative readout</div>', unsafe_allow_html=True)

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
    cumret_line_styles = build_line_style_map(cumret_plot_df["Portfolio"].unique().tolist())

    if benchmark_choice in cumret_line_styles:
        cumret_line_styles[benchmark_choice]["color"] = ACCENT_BLUE
        cumret_line_styles[benchmark_choice]["width"] = 4
        cumret_line_styles[benchmark_choice]["dash"] = "dot"

    fig_cumret = px.line(
        cumret_plot_df,
        x="Date",
        y="Cumulative Return",
        color="Portfolio",
    )

    apply_line_styles(fig_cumret, cumret_line_styles)
    chart_layout(fig_cumret, height=470, yaxis_title="Cumulative Return")
    fig_cumret.update_yaxes(tickformat=".0%")
    fig_cumret.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            title=None,
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
        ACCENT_BLUE if pd.notna(value) and value >= 0 else "#FF453A"
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
                    line=dict(color="rgba(255,255,255,0.10)", width=1),
                ),
                hovertemplate="<b>%{x}</b><br>Return: %{y:.2%}<extra></extra>",
            )
        ]
    )

    chart_layout(fig_bar, height=390, yaxis_title="Return")
    fig_bar.update_yaxes(tickformat=".0%")
    render_chart(fig_bar, key="fig_bar")
else:
    st.info("No return data available.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Signal map</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Portfolio heatmap</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-note">Brighter cells indicate stronger relative performance. Lower volatility is rewarded.</div>',
    unsafe_allow_html=True,
)

if not summary_f.empty:
    heatmap_fig = build_portfolio_heatmap(summary_f, money, pct)

    if heatmap_fig is not None:
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
