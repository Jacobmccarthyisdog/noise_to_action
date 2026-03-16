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
    return_spread = best["Return"] - worst["Return"]

    # -----------------------------
    # Market tone / benchmark framing
    # -----------------------------
    if benchmark_summary is not None and pd.notna(benchmark_summary["Return"]) and pd.notna(avg_return):
        spread = avg_return - benchmark_summary["Return"]

        if spread >= 0.03:
            benchmark_sentence = (
                f"Across the selected window, the portfolio group is clearly outperforming {benchmark_choice}, "
                f"which points to stock selection and portfolio construction adding real value in this stretch."
            )
        elif spread >= 0:
            benchmark_sentence = (
                f"Across the selected window, the portfolio group is modestly ahead of {benchmark_choice}, "
                f"suggesting a slight edge versus simply owning the benchmark."
            )
        elif spread > -0.03:
            benchmark_sentence = (
                f"Across the selected window, the portfolio group is slightly trailing {benchmark_choice}, "
                f"so results have been competitive but not strong enough yet to decisively beat the market."
            )
        else:
            benchmark_sentence = (
                f"Across the selected window, the portfolio group is lagging {benchmark_choice} by a noticeable margin, "
                f"which suggests the current market environment is rewarding exposures outside the core portfolio mix."
            )
    else:
        benchmark_sentence = (
            f"Across the selected window, the portfolio group is posting mixed results, "
            f"with average daily volatility around {pct(avg_vol)}."
        )

    # -----------------------------
    # Fallback if no holdings
    # -----------------------------
    if insight_holdings.empty:
        return " ".join(
            [
                benchmark_sentence,
                f"At the portfolio level, {best['Portfolio']} is the strongest performer at {pct(best['Return'])}, while {worst['Portfolio']} is the weakest at {pct(worst['Return'])}.",
                f"The spread between the top and bottom portfolios is {pct(return_spread)}, which suggests positioning is mattering meaningfully right now.",
                "Without holding-level detail, the clearest takeaway is to lean toward the portfolios already showing stronger momentum and be more cautious with the laggards until leadership improves.",
            ]
        )

    # -----------------------------
    # Stock-level analysis
    # -----------------------------
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

    # -----------------------------
    # Theme / sector analysis
    # -----------------------------
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

    # -----------------------------
    # Narrative sections
    # -----------------------------
    leadership_sentence = (
        f"{best['Portfolio']} is setting the pace at {pct(best['Return'])}, while {worst['Portfolio']} is trailing at {pct(worst['Return'])}. "
        f"That gap of {pct(return_spread)} between first and last place tells us this has not been a flat market where everything is moving together."
    )

    winners_losers_sentence = (
        f"At the holding level, {strongest['Ticker']} has been one of the biggest tailwinds across the portfolios, "
        f"while {weakest['Ticker']} has been the clearest drag."
    )

    repeat_sentence = ""
    if top_names:
        repeat_sentence = (
            f"The strongest leadership is showing up repeatedly in {join_names(top_names)}, which suggests the winning positions are not isolated one-offs but part of a broader pattern across the portfolio set. "
        )
    else:
        repeat_sentence = (
            f"Leadership looks a bit narrower right now, with {strongest['Ticker']} standing out more than any broader cluster of repeat winners. "
        )

    if weak_names:
        repeat_sentence += f"On the weaker side, repeated pressure is coming from {join_names(weak_names)}."

    theme_sentence = ""
    if best_theme and worst_theme and best_theme != worst_theme:
        theme_sentence = (
            f"From a sector and exposure standpoint, leadership is strongest in {best_theme}, while the weakest pocket of the market appears to be {worst_theme}. "
            f"{get_theme_regime_comment(best_theme)}"
        )
    elif best_theme:
        theme_sentence = (
            f"From a sector and exposure standpoint, current leadership is centered around {best_theme}. "
            f"{get_theme_regime_comment(best_theme)}"
        )

    max_repeat_count = repeated["Portfolio_Count"].max() if not repeated.empty else 1
    if max_repeat_count >= 3:
        concentration_sentence = (
            "Performance also appears somewhat concentrated, meaning a fairly small group of winning names is likely doing an outsized share of the work."
        )
    else:
        concentration_sentence = (
            "Performance looks more balanced across holdings, which is usually a healthier sign that the results are coming from broader construction rather than one or two outsized winners."
        )

    # -----------------------------
    # Directional recommendation
    # -----------------------------
    if best_theme:
        parking_sentence = (
            f"If I were parking fresh money based on this snapshot alone, I would lean toward portfolios or sectors with exposure to {best_theme} and similar areas of leadership, "
            f"while avoiding overexposure to the weaker pocket of the tape. The broader message here is to stay aligned with the parts of the market already attracting strength rather than forcing money into areas still trying to stabilize."
        )
    else:
        parking_sentence = (
            "If I were parking fresh money based on this snapshot alone, I would lean toward the portfolios already showing stronger relative performance and healthier breadth, while being more selective around the laggards. The broader message is to follow strength rather than trying to catch weak areas too early."
        )

    return " ".join(
        [
            benchmark_sentence,
            leadership_sentence,
            winners_losers_sentence,
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
