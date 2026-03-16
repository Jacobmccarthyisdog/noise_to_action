import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import APP_CSS, BENCHMARK_MAP
from data_loader import load_data
from calculations import (
    money,
    pct,
    normalize_date_range,
    exclude_benchmark_portfolios,
    build_datasets,
    build_summary,
    summarize_benchmark,
    build_ai_dvisor_insights,
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

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(APP_CSS, unsafe_allow_html=True)

st.title("From Noise to Action")

try:
    portfolios, prices = load_data()
except Exception as exc:
    st.error(f"Could not load portfolio data: {exc}")
    st.stop()

if prices.empty:
    st.error("No price data was returned from yfinance.")
    st.stop()

latest_available_date = prices["Date"].max()
st.markdown(
    f'<div class="small-note"><b>Data through:</b> {latest_available_date.strftime("%B %d, %Y")}</div>',
    unsafe_allow_html=True,
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
date_min = prices["Date"].min().date()
date_max = prices["Date"].max().date()

default_portfolios = all_portfolios
default_benchmark = "SPY" if "SPY" in BENCHMARK_MAP else next(iter(BENCHMARK_MAP))
default_dates = (date_min, date_max)

if "selected_portfolios" not in st.session_state:
    st.session_state.selected_portfolios = default_portfolios
if "benchmark_choice" not in st.session_state:
    st.session_state.benchmark_choice = default_benchmark
if "date_range" not in st.session_state:
    st.session_state.date_range = default_dates

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
holdings_snapshot_initial = holdings_snapshot[
    holdings_snapshot["Portfolio"].isin(initial_selected)
].copy()

benchmark_summary_initial = summarize_benchmark(
    benchmark_history=benchmark_history,
    benchmark_label=initial_benchmark,
    start_date=initial_start_date,
    end_date=initial_end_date,
)

ai_dvisor_text = build_ai_dvisor_insights(
    summary_df=summary_initial,
    holdings_df=holdings_snapshot_initial,
    benchmark_summary=benchmark_summary_initial,
    benchmark_choice=initial_benchmark,
)

st.markdown("### AI-dvisor Insights")
with st.expander("Read more", expanded=False):
    st.write(ai_dvisor_text)

with st.expander("Dashboard Controls", expanded=False):
    b1, b2 = st.columns([1, 6])

    with b1:
        if st.button("Reset to Defaults", use_container_width=True):
            st.session_state.selected_portfolios = default_portfolios
            st.session_state.benchmark_choice = default_benchmark
            st.session_state.date_range = default_dates
            st.rerun()

    f1, f2, f3 = st.columns([1.8, 0.9, 1.2])

    with f1:
        selected_portfolios = st.multiselect(
            "Select portfolios",
            options=all_portfolios,
            default=st.session_state.selected_portfolios,
            key="selected_portfolios",
        )

    with f2:
        benchmark_options = [key for key, value in BENCHMARK_MAP.items() if value in prices.columns]
        if not benchmark_options:
            benchmark_options = list(BENCHMARK_MAP.keys())

        if st.session_state.benchmark_choice not in benchmark_options:
            st.session_state.benchmark_choice = benchmark_options[0]

        benchmark_choice = st.selectbox(
            "Benchmark comparison",
            options=benchmark_options,
            key="benchmark_choice",
        )

    with f3:
        date_range = st.date_input(
            "Date range",
            value=st.session_state.date_range,
            min_value=date_min,
            max_value=date_max,
            key="date_range",
        )

selected_portfolios = [portfolio for portfolio in st.session_state.selected_portfolios if portfolio in all_portfolios]
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

    avg_dollar_gain = alpha_summary_f["Dollar Change"].mean() if not alpha_summary_f.empty else None
    avg_return = alpha_summary_f["Return"].mean() if not alpha_summary_f.empty else None

    relative_vs_benchmark = None
    if (
        not alpha_summary_f.empty
        and benchmark_summary is not None
        and benchmark_summary["Return"] is not None
        and avg_return is not None
    ):
        relative_vs_benchmark = avg_return - benchmark_summary["Return"]

    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card(
            f"Avg Alfa vs {benchmark_choice}",
            pct(relative_vs_benchmark) if relative_vs_benchmark is not None else "-",
            f"{money(avg_dollar_gain)} average return",
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

if not benchmark_cumret_f.empty:
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
    
