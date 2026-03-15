import streamlit as st
import pandas as pd
import numpy as np

from config import BENCHMARK_MAP, TICKER_THEME_MAP


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
            benchmark_history.rename(columns={"Benchmark Value": "Portfolio Value", "Benchmark": "Portfolio"}),
            value_col="Portfolio Value",
            group_col="Portfolio",
        )

    return portfolio_history, merged, holdings_snapshot, benchmark_history, portfolio_cumret, benchmark_cumret


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


def join_names(names):
    names = [str(name).strip() for name in names if pd.notna(name) and str(name).strip()]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]}, {names[1]}, and {names[2]}"


def get_theme_regime_comment(theme):
    if theme in {"AI / Semis", "Mega-cap Growth", "High-beta Growth", "Software"}:
        return "That points to a more risk-on tape where growth, innovation, and narrative-heavy leaders are doing more of the work."
    if theme in {"Energy", "Financials", "Industrials"}:
        return "That points to a more cyclical backdrop, where macro sensitivity, rate expectations, or commodity linkage may be playing a bigger role."
    if theme in {"Healthcare", "Defensive / Quality"}:
        return "That points to a steadier, more defensive market tone where resilience and earnings durability are being rewarded."
    if theme in {"Rate-sensitive", "Consumer / Housing"}:
        return "That suggests moves in rates and consumer demand may be having an outsized influence on returns."
    return "That suggests leadership is coming from a narrower pocket of the market rather than broad beta alone."


def build_ai_dvisor_insights(summary_df, holdings_df, benchmark_summary, benchmark_choice):
    if summary_df.empty:
        return "There is not enough filtered portfolio history to generate AI-dvisor insights yet."

    alpha_summary = exclude_benchmark_portfolios(summary_df, portfolio_col="Portfolio").copy()
    alpha_holdings = exclude_benchmark_portfolios(holdings_df, portfolio_col="Portfolio").copy()

    insight_summary = alpha_summary if not alpha_summary.empty else summary_df.copy()
    insight_holdings = alpha_holdings if not alpha_holdings.empty else holdings_df.copy()

    ranked = insight_summary.sort_values("Return", ascending=False).reset_index(drop=True)
    best = ranked.iloc[0]
    worst = ranked.iloc[-1]

    avg_return = ranked["Return"].mean()
    avg_vol = ranked["Volatility"].mean()

    if benchmark_summary is not None and pd.notna(benchmark_summary["Return"]) and pd.notna(avg_return):
        spread = avg_return - benchmark_summary["Return"]
        benchmark_sentence = (
            f"Across the selected window, the portfolio set is "
            f"{'outperforming' if spread >= 0 else 'lagging'} {benchmark_choice} "
            f"by {pct(abs(spread))} on average, with average daily volatility near {pct(avg_vol)}."
        )
    else:
        benchmark_sentence = (
            f"Across the selected window, the portfolio set is averaging performance with "
            f"average daily volatility near {pct(avg_vol)}."
        )

    if insight_holdings.empty:
        return " ".join(
            [
                benchmark_sentence,
                f"{best['Portfolio']} is the current leader at {pct(best['Return'])}, while {worst['Portfolio']} is the weakest at {pct(worst['Return'])}.",
                "The spread between leaders and laggards suggests portfolio construction is mattering materially in this tape, but there is not enough holding-level data to isolate the stock and macro drivers.",
            ]
        )

    ticker_stats = (
        insight_holdings.groupby("Ticker", as_index=False)
        .agg(
            Avg_Return=("Return", "mean"),
            Avg_Dollar_Change=("Dollar Change", "mean"),
            Portfolio_Count=("Portfolio", "nunique"),
            Total_Current_Value=("Current Value", "sum"),
        )
        .sort_values(
            ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )

    strongest = ticker_stats.iloc[0]
    weakest = ticker_stats.sort_values(
        ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
        ascending=[True, False, False],
    ).iloc[0]

    repeated = ticker_stats[ticker_stats["Portfolio_Count"] >= 2].copy()
    repeated_leaders = repeated.sort_values(
        ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
        ascending=[False, False, False],
    )
    repeated_laggards = repeated.sort_values(
        ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
        ascending=[True, False, False],
    )

    top_names = repeated_leaders["Ticker"].head(3).tolist()
    weak_names = repeated_laggards["Ticker"].head(2).tolist()

    holdings_with_theme = insight_holdings.copy()
    holdings_with_theme["Theme"] = holdings_with_theme["Ticker"].map(TICKER_THEME_MAP).fillna("Other")

    theme_stats = (
        holdings_with_theme.groupby("Theme", as_index=False)
        .agg(
            Avg_Return=("Return", "mean"),
            Portfolio_Count=("Portfolio", "nunique"),
            Name_Count=("Ticker", "nunique"),
            Total_Current_Value=("Current Value", "sum"),
        )
        .sort_values(
            ["Avg_Return", "Portfolio_Count", "Name_Count", "Total_Current_Value"],
            ascending=[False, False, False, False],
        )
        .reset_index(drop=True)
    )

    best_theme = theme_stats.iloc[0]["Theme"] if not theme_stats.empty else None
    worst_theme = theme_stats.iloc[-1]["Theme"] if not theme_stats.empty else None

    leadership_sentence = (
        f"{best['Portfolio']} is currently leading at {pct(best['Return'])}, while {worst['Portfolio']} trails at {pct(worst['Return'])}; "
        f"at the stock level, {strongest['Ticker']} has been the strongest average contributor and {weakest['Ticker']} has been the softest spot."
    )

    repeat_sentence = ""
    if top_names:
        repeat_sentence = (
            f"Repeated leadership across portfolios is showing up in {join_names(top_names)}, which suggests those names are doing a meaningful share of the heavy lifting rather than the outperformance being purely random. "
        )
    else:
        repeat_sentence = (
            f"Leadership looks narrower right now, with {strongest['Ticker']} standing out as the clearest single winner across the selected portfolios. "
        )

    if weak_names:
        repeat_sentence += f"On the weaker side, repeated drag appears to be coming from {join_names(weak_names)}."

    theme_sentence = ""
    if best_theme and worst_theme and best_theme != worst_theme:
        theme_sentence = (
            f"From a macro and exposure standpoint, the strongest pocket appears to be {best_theme}, while the softest pocket appears to be {worst_theme}. "
            f"{get_theme_regime_comment(best_theme)}"
        )
    elif best_theme:
        theme_sentence = (
            f"From a macro and exposure standpoint, current leadership appears centered around {best_theme}. "
            f"{get_theme_regime_comment(best_theme)}"
        )

    max_repeat_count = repeated["Portfolio_Count"].max() if not repeated.empty else 1
    if max_repeat_count >= 3:
        concentration_sentence = (
            "Performance also looks somewhat concentrated, meaning a relatively small cluster of names may be driving an outsized share of results."
        )
    else:
        concentration_sentence = (
            "Performance looks a bit more distributed, suggesting broader portfolio construction is contributing rather than one or two names alone."
        )

    parking_sentence = (
        f"If I were parking money based only on this snapshot, I would lean toward {best['Portfolio']} and portfolios aligned with the current leadership theme, "
        f"while staying more cautious around portfolios exposed to the weaker names and softer macro pocket."
    )

    return " ".join(
        [
            benchmark_sentence,
            leadership_sentence,
            repeat_sentence,
            theme_sentence,
            concentration_sentence,
            parking_sentence,
        ]
    )


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