import json
from pathlib import Path
from typing import Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import APP_CSS, BENCHMARK_MAP
from data_loader import load_data, fetch_price_history
from calculations import (
    money,
    pct,
    normalize_date_range,
    exclude_benchmark_portfolios,
    build_datasets,
    build_summary,
    summarize_benchmark,
    format_summary_table,
    format_holdings_table,
)
from charts import (
    build_return_bar_colors,
    build_portfolio_heatmap,
    build_line_style_map,
    apply_line_styles,
    chart_layout,
    render_chart,
    metric_card,
)

DAILY_INSIGHT_PATH = Path("data/daily_insight.json")

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(APP_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <style>
        .hero-banner {
            position: relative;
            overflow: hidden;
            padding: 28px 30px 24px 30px;
            border-radius: 22px;
            background:
                radial-gradient(circle at top right, rgba(0, 212, 170, 0.18), transparent 28%),
                radial-gradient(circle at bottom left, rgba(58, 123, 213, 0.16), transparent 24%),
                linear-gradient(135deg, rgba(10,14,22,0.98), rgba(16,22,35,0.96));
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 18px 50px rgba(0,0,0,0.28);
            margin-top: 1.2rem;
            margin-bottom: 0.9rem;
        }

        .hero-title {
            font-size: 2.6rem;
            line-height: 1.05;
            font-weight: 800;
            color: #F6FBFF;
            margin: 0;
            letter-spacing: -0.03em;
        }

        .hero-subtitle {
            margin-top: 10px;
            color: rgba(235, 244, 255, 0.78);
            font-size: 1rem;
            max-width: 920px;
        }

        .hero-meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 16px;
        }

        .hero-meta-pill {
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            color: rgba(240, 247, 255, 0.90);
            font-size: 0.85rem;
        }

        .ai-summary-status {
            color: rgba(235, 244, 255, 0.78);
            font-size: 0.95rem;
            line-height: 1.55;
            margin-bottom: 0.4rem;
        }

        .ai-summary-meta {
            color: rgba(208, 224, 240, 0.70);
            font-size: 0.82rem;
            margin-top: 0.25rem;
            margin-bottom: 0.85rem;
        }

        .ai-summary-section-title {
            color: #F6FBFF;
            font-weight: 800;
            margin-top: 1rem;
            margin-bottom: 0.25rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


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
        if len(values) >= 2 and values[-2] not in (0, None):
            prior_value = float(values[-2])
            if prior_value != 0:
                daily_move = (latest_value / prior_value) - 1

        sparkline = values[-20:] if len(values) >= 2 else values

        records.append(
            {
                "Portfolio": portfolio_name,
                "Latest Value": latest_value,
                "Daily Move": daily_move,
                "Sparkline": sparkline,
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
        return None, f"Could not find `{path.as_posix()}`. The daily insight job has not written the file into this app deployment yet."

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


def render_unknown_insight_fields(record: dict[str, Any], known_keys: set[str]) -> None:
    extra_items = {
        key: value
        for key, value in record.items()
        if key not in known_keys and value not in (None, "", [], {})
    }

    if not extra_items:
        return

    st.markdown('<div class="ai-summary-section-title">Additional detail</div>', unsafe_allow_html=True)

    for key, value in extra_items.items():
        label = key.replace("_", " ").title()

        if isinstance(value, list):
            if not value:
                continue

            st.markdown(f"**{label}**")
            for item in value:
                if isinstance(item, dict):
                    st.json(item)
                else:
                    st.markdown(f"- {item}")
        elif isinstance(value, dict):
            st.markdown(f"**{label}**")
            st.json(value)
        else:
            st.markdown(f"**{label}:** {value}")


def render_daily_ai_summary() -> None:
    payload, error_message = read_daily_insight_payload()
    record = get_latest_daily_insight(payload) if payload is not None else {}

    as_of_date = first_present(
        record,
        ["date", "as_of_date", "generated_for", "generated_at"],
        "not generated yet",
    )

    headline = first_present(
        record,
        ["headline", "title", "summary_title"],
        "AI generated summary",
    )

    summary = first_present(
        record,
        [
            "summary",
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

    bullets = as_list(
        record.get("bullets")
        or record.get("key_points")
        or record.get("highlights")
        or record.get("takeaways")
    )

    risks = as_list(
        record.get("risks")
        or record.get("watchouts")
        or record.get("watch_outs")
        or record.get("risk_factors")
    )

    actions = as_list(
        record.get("actions")
        or record.get("recommendations")
        or record.get("suggested_actions")
        or record.get("next_steps")
    )

    expander_label = f"AI generated summary • {as_of_date}"

    with st.expander(expander_label, expanded=False):
        if error_message:
            st.warning(error_message)
            st.markdown(
                """
                <div class="ai-summary-status">
                    This dropdown is rendering correctly. The missing piece is the generated JSON artifact.
                    Once the GitHub Action writes <code>data/daily_insight.json</code>, the summary will appear here.
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        if not record:
            st.warning("The daily insight file loaded, but no usable insight record was found.")
            st.markdown(
                """
                <div class="ai-summary-status">
                    This dropdown is rendering correctly, but the JSON structure does not contain a readable insight record.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.json(payload)
            return

        st.markdown(f"### {headline}")
        st.markdown(
            f'<div class="ai-summary-meta">Source: <code>{DAILY_INSIGHT_PATH.as_posix()}</code></div>',
            unsafe_allow_html=True,
        )

        if summary:
            st.markdown(summary)

        if bullets:
            st.markdown('<div class="ai-summary-section-title">Key takeaways</div>', unsafe_allow_html=True)
            for bullet in bullets:
                if isinstance(bullet, dict):
                    st.json(bullet)
                else:
                    st.markdown(f"- {bullet}")

        if risks:
            st.markdown('<div class="ai-summary-section-title">Watchouts</div>', unsafe_allow_html=True)
            for risk in risks:
                if isinstance(risk, dict):
                    st.json(risk)
                else:
                    st.markdown(f"- {risk}")

        if actions:
            st.markdown('<div class="ai-summary-section-title">Suggested actions</div>', unsafe_allow_html=True)
            for action in actions:
                if isinstance(action, dict):
                    st.json(action)
                else:
                    st.markdown(f"- {action}")

        known_keys = {
            "date",
            "as_of_date",
            "generated_for",
            "generated_at",
            "headline",
            "title",
            "summary_title",
            "summary",
            "insight",
            "narrative",
            "text",
            "analysis",
            "ai_summary",
            "daily_summary",
            "portfolio_summary",
            "bullets",
            "key_points",
            "highlights",
            "takeaways",
            "risks",
            "watchouts",
            "watch_outs",
            "risk_factors",
            "actions",
            "recommendations",
            "suggested_actions",
            "next_steps",
        }
        render_unknown_insight_fields(record, known_keys)


def render_hero_banner(latest_date, benchmark_choice: str):
    st.markdown(
        f"""
        <div class="hero-banner">
            <h1 class="hero-title">Portfolio Dashboard</h1>
            <div class="hero-subtitle">
                <b>Access portfolio settings in the top left ">>"</b>
            </div>
            <div class="hero-meta-row">
                <div class="hero-meta-pill"><b>Data through:</b> {latest_date.strftime("%B %d, %Y")}</div>
                <div class="hero-meta-pill"><b>Benchmark:</b> {benchmark_choice}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_portfolio_ticker(banner_df: pd.DataFrame):
    if banner_df.empty:
        return

    items = []
    for _, row in banner_df.iterrows():
        daily_text = row["Daily Move Display"]
        overall_text = row["Overall Return Display"]
        latest_value = money(row["Latest Value"])

        daily_class = "ticker-flat"
        if pd.notna(row["Daily Move"]):
            daily_class = "ticker-up" if row["Daily Move"] >= 0 else "ticker-down"

        overall_class = "ticker-flat"
        if pd.notna(row["Overall Return"]):
            overall_class = "ticker-up" if row["Overall Return"] >= 0 else "ticker-down"

        items.append(
            f"""
            <div class="ticker-card">
                <div class="ticker-name">{row["Portfolio"]}</div>
                <div class="ticker-price">{latest_value}</div>
                <div class="ticker-stats">
                    <span class="{daily_class}">Day {daily_text}</span>
                    <span class="{overall_class}">Overall {overall_text}</span>
                </div>
            </div>
            """
        )

    cards_html = "".join(items)

    html = f"""
    <style>
        .ticker-wrap {{
            width: 100%;
            overflow: hidden;
            border-radius: 22px;
            border: 1px solid rgba(255,255,255,0.08);
            background:
                radial-gradient(circle at top right, rgba(0, 212, 170, 0.12), transparent 30%),
                radial-gradient(circle at bottom left, rgba(58, 123, 213, 0.10), transparent 26%),
                linear-gradient(135deg, rgba(10,14,22,0.98), rgba(16,22,35,0.96));
            box-shadow: 0 18px 50px rgba(0,0,0,0.28);
            padding: 12px 0;
            margin: 0.2rem 0 1rem 0;
        }}

        .ticker-track {{
            display: flex;
            width: max-content;
            animation: ticker-scroll 38s linear infinite;
            will-change: transform;
        }}

        .ticker-group {{
            display: flex;
            gap: 14px;
            padding-right: 14px;
        }}

        .ticker-card {{
            min-width: 240px;
            padding: 14px 16px;
            border-radius: 18px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.025));
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.03),
                0 10px 24px rgba(0,0,0,0.18);
            backdrop-filter: blur(4px);
        }}

        .ticker-name {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: rgba(208,224,240,0.72);
            margin-bottom: 8px;
            font-weight: 700;
            white-space: nowrap;
        }}

        .ticker-price {{
            font-size: 1.08rem;
            font-weight: 800;
            color: #F7FBFF;
            margin-bottom: 8px;
            white-space: nowrap;
        }}

        .ticker-stats {{
            display: flex;
            gap: 12px;
            flex-wrap: nowrap;
            font-size: 0.83rem;
            white-space: nowrap;
        }}

        .ticker-up {{
            color: #7CE3C3;
            font-weight: 700;
        }}

        .ticker-down {{
            color: #FF8D8D;
            font-weight: 700;
        }}

        .ticker-flat {{
            color: rgba(220, 232, 244, 0.72);
            font-weight: 700;
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
    </style>

    <div class="ticker-wrap">
        <div class="ticker-track">
            <div class="ticker-group">{cards_html}</div>
            <div class="ticker-group">{cards_html}</div>
        </div>
    </div>
    """

    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


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
default_benchmark = "SPY" if "SPY" in BENCHMARK_MAP else next(iter(BENCHMARK_MAP))
default_dates = (date_min, date_max)

if "selected_portfolios" not in st.session_state:
    st.session_state.selected_portfolios = default_portfolios
if "benchmark_choice" not in st.session_state:
    st.session_state.benchmark_choice = default_benchmark
if "date_range" not in st.session_state:
    st.session_state.date_range = default_dates

with st.sidebar:
    st.markdown("### Controls")

    if st.button("↻ Refresh Data", key="refresh_prices_button", use_container_width=True):
        fetch_price_history.clear()
        st.rerun()

    if st.button("Reset to Defaults", key="reset_defaults_button", use_container_width=True):
        st.session_state.selected_portfolios = default_portfolios
        st.session_state.benchmark_choice = default_benchmark
        st.session_state.date_range = default_dates
        st.rerun()

    st.multiselect(
        "Select portfolios",
        options=all_portfolios_source,
        default=st.session_state.selected_portfolios,
        key="selected_portfolios",
    )

    benchmark_options = [key for key, value in BENCHMARK_MAP.items() if value in prices.columns]
    if not benchmark_options:
        benchmark_options = list(BENCHMARK_MAP.keys())

    if st.session_state.benchmark_choice not in benchmark_options:
        st.session_state.benchmark_choice = benchmark_options[0]

    st.selectbox(
        "Benchmark comparison",
        options=benchmark_options,
        key="benchmark_choice",
    )

    st.date_input(
        "Date range",
        value=st.session_state.date_range,
        min_value=date_min,
        max_value=date_max,
        key="date_range",
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

initial_start_date, initial_end_date = normalize_date_range(
    st.session_state.date_range,
    date_min,
    date_max,
)

initial_selected = [
    portfolio for portfolio in st.session_state.selected_portfolios if portfolio in all_portfolios
] or default_portfolios

initial_benchmark = (
    st.session_state.benchmark_choice
    if st.session_state.benchmark_choice in BENCHMARK_MAP
    else default_benchmark
)

portfolio_history_initial = portfolio_history[
    (portfolio_history["Portfolio"].isin(initial_selected))
    & (portfolio_history["Date"] >= initial_start_date)
    & (portfolio_history["Date"] <= initial_end_date)
].copy()

summary_initial = build_summary(portfolio_history_initial)

banner_df = build_banner_stats(
    portfolio_history_df=portfolio_history_initial,
    summary_df=summary_initial,
)

render_hero_banner(
    latest_date=latest_available_date,
    benchmark_choice=initial_benchmark,
)

render_daily_ai_summary()

render_portfolio_ticker(banner_df)

selected_portfolios = [
    portfolio for portfolio in st.session_state.selected_portfolios if portfolio in all_portfolios
]
benchmark_choice = st.session_state.benchmark_choice
date_range = st.session_state.date_range

if not selected_portfolios:
    st.warning("Select at least one portfolio.")
    st.stop()

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

if not summary_f.empty:
    best_row = summary_f.sort_values("Return", ascending=False).iloc[0]
    riskiest_row = summary_f.sort_values("Volatility", ascending=False).iloc[0]

    alpha_summary_f = exclude_benchmark_portfolios(summary_f, portfolio_col="Portfolio")
    avg_return = alpha_summary_f["Return"].mean() if not alpha_summary_f.empty else None

    relative_vs_benchmark = None
    avg_dollar_alpha = None

    if (
        not alpha_summary_f.empty
        and benchmark_summary is not None
        and benchmark_summary["Return"] is not None
        and avg_return is not None
    ):
        relative_vs_benchmark = avg_return - benchmark_summary["Return"]
        display_alpha_pct = round(relative_vs_benchmark * 100, 2)
        avg_dollar_alpha = display_alpha_pct * 10

    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card(
            f"Avg Alpha vs {benchmark_choice}",
            pct(relative_vs_benchmark) if relative_vs_benchmark is not None else "-",
            f"{money(avg_dollar_alpha)} higher than the {benchmark_choice}",
        )

    with c2:
        metric_card(
            "Optimal Portfolio",
            best_row["Portfolio"],
            f"{pct(best_row['Return'])} | {money(best_row['Dollar Change'])}",
        )

    with c3:
        metric_card(
            "Most Volatile",
            riskiest_row["Portfolio"],
            f"{pct(riskiest_row['Volatility'])} daily vol",
        )
else:
    st.info("No summary metrics are available for the selected filters.")

st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

st.markdown("### Total Return by Portfolio")
if not summary_f.empty:
    bar_df = summary_f.sort_values("Return", ascending=False).copy()
    bar_colors = build_return_bar_colors(bar_df["Return"])

    fig_bar = go.Figure(
        data=[
            go.Bar(
                x=bar_df["Portfolio"],
                y=bar_df["Return"],
                text=bar_df["Return"].map(lambda x: "-" if x is None else f"{x:.1%}"),
                textposition="outside",
                marker=dict(
                    color=bar_colors,
                    line=dict(color="rgba(255,255,255,0.06)", width=1),
                ),
                hovertemplate="<b>%{x}</b><br>Return: %{y:.2%}<extra></extra>",
            )
        ]
    )

    chart_layout(fig_bar, height=380, yaxis_title="Return")
    fig_bar.update_yaxes(tickformat=".0%")
    render_chart(fig_bar, key="fig_bar")
else:
    st.info("No return data available.")

st.markdown("### Portfolio Heatmap")
st.markdown(
    '<div class="small-note">Brighter cells = stronger relative performance, while lower volatility is rewarded.</div>',
    unsafe_allow_html=True,
)
if not summary_f.empty:
    heatmap_fig = build_portfolio_heatmap(summary_f, money, pct)
    render_chart(heatmap_fig, key="heatmap_fig")
else:
    st.info("No heatmap data available.")

st.markdown("### Cumulative Return Comparison")
st.markdown(
    '<div class="small-note">Shows percent return since the start of the selected time range.</div>',
    unsafe_allow_html=True,
)

cumret_plot_df = portfolio_cumret_f[["Date", "Portfolio", "Cumulative Return"]].copy()

benchmark_already_present = benchmark_choice in {
    str(name).strip() for name in cumret_plot_df["Portfolio"].dropna().unique()
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

    fig_cumret = px.line(
        cumret_plot_df,
        x="Date",
        y="Cumulative Return",
        color="Portfolio",
    )
    apply_line_styles(fig_cumret, cumret_line_styles)
    chart_layout(fig_cumret, height=450, yaxis_title="Cumulative Return (%)")
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
        margin=dict(b=110),
    )
    render_chart(fig_cumret, key="fig_cumret")
else:
    st.info("No cumulative return data available.")

st.markdown("### Portfolio Drilldown")

chosen_portfolio = st.selectbox("Choose a portfolio", selected_portfolios)

detail_holdings = holdings_snapshot_f[holdings_snapshot_f["Portfolio"] == chosen_portfolio].copy()
detail_history = portfolio_history_f[portfolio_history_f["Portfolio"] == chosen_portfolio].copy()

d1, d2 = st.columns([1.1, 1.4])

with d1:
    st.markdown("#### Holdings Snapshot")
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
    st.markdown("#### Portfolio Value Trend")
    if not detail_history.empty:
        fig_single = px.area(
            detail_history,
            x="Date",
            y="Portfolio Value",
        )
        chart_layout(fig_single, height=380, yaxis_title="Value ($)")
        fig_single.update_yaxes(range=[900, detail_history["Portfolio Value"].max() * 1.03])
        render_chart(fig_single, key="fig_single")
    else:
        st.info("No history available for this portfolio.")

with st.expander("See portfolio summary table"):
    st.dataframe(
        format_summary_table(summary_f),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("See price table preview"):
    st.dataframe(prices.head(20), use_container_width=True, hide_index=True)
