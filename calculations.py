import streamlit as st
import pandas as pd
import numpy as np

from config import BENCHMARK_MAP


def money(x):
    return "-" if pd.isna(x) else f"${x:,.2f}"


def pct(x):
    return "-" if pd.isna(x) else f"{x:.2%}"


def safe_divide(a, b):
    return np.nan if pd.isna(a) or pd.isna(b) or b == 0 else a / b


def normalize_date_range(value, fallback_start, fallback_end):
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return pd.to_datetime(value[0]), pd.to_datetime(value[1])
    if value:
        single = pd.to_datetime(value)
        return single, single
    return pd.to_datetime(fallback_start), pd.to_datetime(fallback_end)


def exclude_benchmark_portfolios(df, portfolio_col="Portfolio"):
    benchmark_names = {str(k).strip().upper() for k in BENCHMARK_MAP.keys()}
    benchmark_names.update({str(v).strip().upper() for v in BENCHMARK_MAP.values()})

    if portfolio_col not in df.columns:
        return df.copy()

    out = df.copy()
    portfolio_names = out[portfolio_col].astype(str).str.strip().str.upper()
    return out[~portfolio_names.isin(benchmark_names)].copy()


def build_benchmark_history(prices, benchmark_map):
    frames = []

    for label, ticker in benchmark_map.items():
        if ticker in prices.columns:
            frame = prices[["Date", ticker]].copy()
            frame = frame.rename(columns={ticker: "Benchmark Value"})
            frame["Benchmark"] = label
            frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["Date", "Benchmark Value", "Benchmark"])

    return pd.concat(frames, ignore_index=True)


def build_cumulative_return_series(df, value_col="Portfolio Value", group_col="Portfolio"):
    parts = []

    for _, group in df.groupby(group_col):
        group = group.sort_values("Date").copy()
        values = group[value_col].dropna()

        if values.empty:
            group["Cumulative Return"] = np.nan
        else:
            first = values.iloc[0]
            group["Cumulative Return"] = (group[value_col] / first) - 1 if first != 0 else np.nan

        parts.append(group)

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def compute_holdings_snapshot(merged):
    valid = merged.dropna(subset=["Price"]).copy()

    if valid.empty:
        return pd.DataFrame(
            columns=[
                "Portfolio",
                "Ticker",
                "Initial Investment",
                "Shares",
                "Current Price",
                "Current Value",
                "Dollar Change",
                "Return",
            ]
        )

    latest_date = valid["Date"].max()
    latest = valid[valid["Date"] == latest_date].copy()

    latest["Current Price"] = latest["Price"]
    latest["Current Value"] = latest["Position Value"]
    latest["Dollar Change"] = latest["Current Value"] - latest["Initial Investment"]
    latest["Return"] = np.where(
        latest["Initial Investment"].fillna(0) != 0,
        latest["Current Value"] / latest["Initial Investment"] - 1,
        np.nan,
    )

    columns = [
        "Portfolio",
        "Ticker",
        "Initial Investment",
        "Shares",
        "Current Price",
        "Current Value",
        "Dollar Change",
        "Return",
    ]
    return latest[columns].sort_values(["Portfolio", "Current Value"], ascending=[True, False])


@st.cache_data(show_spinner=False)
def build_datasets(portfolios, prices):
    ticker_cols = [col for col in prices.columns if col != "Date"]
    if not ticker_cols:
        raise ValueError("No ticker columns found in price data.")

    price_long = prices.melt(
        id_vars="Date",
        value_vars=ticker_cols,
        var_name="Ticker",
        value_name="Price",
    )
    price_long["Ticker"] = price_long["Ticker"].astype(str).str.strip().str.upper()

    merged = portfolios.merge(price_long, on="Ticker", how="left")
    merged["Position Value"] = merged["Shares"] * merged["Price"]

    portfolio_history = (
        merged.groupby(["Date", "Portfolio"], as_index=False)["Position Value"]
        .sum()
        .rename(columns={"Position Value": "Portfolio Value"})
        .sort_values(["Portfolio", "Date"])
        .reset_index(drop=True)
    )

    holdings_snapshot = compute_holdings_snapshot(merged)
    benchmark_history = build_benchmark_history(prices, BENCHMARK_MAP)

    portfolio_cumret = build_cumulative_return_series(
        portfolio_history,
        value_col="Portfolio Value",
        group_col="Portfolio",
    )

    benchmark_cumret = pd.DataFrame()
    if not benchmark_history.empty:
        benchmark_cumret = build_cumulative_return_series(
            benchmark_history.rename(
                columns={"Benchmark Value": "Portfolio Value", "Benchmark": "Portfolio"}
            ),
            value_col="Portfolio Value",
            group_col="Portfolio",
        )

    return (
        portfolio_history,
        merged,
        holdings_snapshot,
        benchmark_history,
        portfolio_cumret,
        benchmark_cumret,
    )


def build_summary(portfolio_history):
    rows = []

    for portfolio, group in portfolio_history.groupby("Portfolio"):
        group = group.sort_values("Date").dropna(subset=["Portfolio Value"]).copy()
        if len(group) < 2:
            continue

        start = group["Portfolio Value"].iloc[0]
        current = group["Portfolio Value"].iloc[-1]
        high = group["Portfolio Value"].max()
        low = group["Portfolio Value"].min()

        running_max = group["Portfolio Value"].cummax()
        drawdown = group["Portfolio Value"] / running_max - 1
        group["Daily Return"] = group["Portfolio Value"].pct_change()

        rows.append(
            {
                "Portfolio": portfolio,
                "Start Value": start,
                "Current Value": current,
                "Dollar Change": current - start,
                "Return": safe_divide(current, start) - 1 if start != 0 else np.nan,
                "High Value": high,
                "Low Value": low,
                "Max Drawdown": drawdown.min(),
                "Volatility": group["Daily Return"].std(),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Portfolio",
                "Start Value",
                "Current Value",
                "Dollar Change",
                "Return",
                "High Value",
                "Low Value",
                "Max Drawdown",
                "Volatility",
            ]
        )

    return pd.DataFrame(rows).sort_values("Return", ascending=False).reset_index(drop=True)


def summarize_benchmark(benchmark_history, benchmark_label, start_date, end_date):
    benchmark = benchmark_history[benchmark_history["Benchmark"] == benchmark_label].copy()
    benchmark = benchmark[(benchmark["Date"] >= start_date) & (benchmark["Date"] <= end_date)]
    benchmark = benchmark.dropna(subset=["Benchmark Value"]).sort_values("Date")

    if len(benchmark) < 2:
        return None

    start = benchmark["Benchmark Value"].iloc[0]
    end = benchmark["Benchmark Value"].iloc[-1]

    return {
        "Benchmark": benchmark_label,
        "Start Value": start,
        "End Value": end,
        "Return": safe_divide(end, start) - 1 if start != 0 else np.nan,
    }


def format_summary_table(df):
    out = df.copy()
    out["Start Value"] = out["Start Value"].map(money)
    out["Current Value"] = out["Current Value"].map(money)
    out["Dollar Change"] = out["Dollar Change"].map(money)
    out["Return"] = out["Return"].map(pct)
    out["High Value"] = out["High Value"].map(money)
    out["Low Value"] = out["Low Value"].map(money)
    out["Max Drawdown"] = out["Max Drawdown"].map(pct)
    out["Volatility"] = out["Volatility"].map(pct)
    return out


def format_holdings_table(df):
    out = df.copy()
    out["Initial Investment"] = out["Initial Investment"].map(money)
    out["Shares"] = out["Shares"].map(lambda x: "-" if pd.isna(x) else f"{x:,.4f}")
    out["Current Price"] = out["Current Price"].map(money)
    out["Current Value"] = out["Current Value"].map(money)
    out["Dollar Change"] = out["Dollar Change"].map(money)
    out["Return"] = out["Return"].map(pct)
    return out
