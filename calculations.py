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
        return "Leadership is tilted toward growth-oriented and narrative-heavy exposures."
    if theme in {"Energy", "Financials", "Industrials"}:
        return "Leadership is tilted toward more cyclical exposures."
    if theme in {"Healthcare", "Defensive / Quality"}:
        return "Leadership is tilted toward steadier, more defensive exposures."
    if theme in {"Rate-sensitive", "Consumer / Housing"}:
        return "Rates and consumer sensitivity may be playing a larger role in relative performance."
    return "Leadership appears to be coming from a narrower part of the market."


def compute_ai_insight_facts(summary_df, holdings_df, benchmark_summary, benchmark_choice):
    facts = {
        "benchmark_choice": benchmark_choice,
        "benchmark_return": None,
        "avg_return": None,
        "avg_alpha": None,
        "winner": None,
        "loser": None,
        "most_volatile": None,
        "return_spread": None,
        "strongest_ticker": None,
        "weakest_ticker": None,
        "repeated_leaders": [],
        "repeated_laggards": [],
        "best_theme": None,
        "worst_theme": None,
        "theme_comment": None,
        "concentration_note": None,
        "winner_top_holdings": [],
    }

    if summary_df is None or summary_df.empty:
        return facts

    alpha_summary = exclude_benchmark_portfolios(summary_df, portfolio_col="Portfolio").copy()
    alpha_holdings = exclude_benchmark_portfolios(holdings_df, portfolio_col="Portfolio").copy()

    insight_summary = alpha_summary if not alpha_summary.empty else summary_df.copy()
    insight_holdings = alpha_holdings if not alpha_holdings.empty else holdings_df.copy()

    ranked = insight_summary.sort_values("Return", ascending=False).reset_index(drop=True)
    facts["winner"] = ranked.iloc[0].to_dict()
    facts["loser"] = ranked.iloc[-1].to_dict()
    facts["avg_return"] = ranked["Return"].mean()

    vol_sorted = insight_summary.sort_values("Volatility", ascending=False).reset_index(drop=True)
    facts["most_volatile"] = vol_sorted.iloc[0].to_dict()

    winner_return = facts["winner"].get("Return")
    loser_return = facts["loser"].get("Return")
    if pd.notna(winner_return) and pd.notna(loser_return):
        facts["return_spread"] = winner_return - loser_return

    if (
        benchmark_summary is not None
        and benchmark_summary.get("Return") is not None
        and pd.notna(benchmark_summary.get("Return"))
        and pd.notna(facts["avg_return"])
    ):
        facts["benchmark_return"] = benchmark_summary["Return"]
        facts["avg_alpha"] = facts["avg_return"] - benchmark_summary["Return"]

    if insight_holdings is None or insight_holdings.empty:
        return facts

    winner_name = facts["winner"]["Portfolio"]
    winner_holdings = insight_holdings[insight_holdings["Portfolio"] == winner_name].copy()
    if not winner_holdings.empty:
        sort_col = "Current Value" if "Current Value" in winner_holdings.columns else "Initial Investment"
        if sort_col in winner_holdings.columns:
            winner_holdings = winner_holdings.sort_values(sort_col, ascending=False)
            facts["winner_top_holdings"] = winner_holdings["Ticker"].head(3).astype(str).tolist()

    ticker_stats = (
        insight_holdings.groupby("Ticker", as_index=False)
        .agg(
            Avg_Return=("Return", "mean"),
            Avg_Dollar_Change=("Dollar Change", "mean"),
            Portfolio_Count=("Portfolio", "nunique"),
            Total_Current_Value=("Current Value", "sum"),
        )
        .reset_index(drop=True)
    )

    if not ticker_stats.empty:
        strongest = ticker_stats.sort_values(
            ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
            ascending=[False, False, False],
        ).iloc[0]
        weakest = ticker_stats.sort_values(
            ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
            ascending=[True, False, False],
        ).iloc[0]

        facts["strongest_ticker"] = strongest.to_dict()
        facts["weakest_ticker"] = weakest.to_dict()

        repeated = ticker_stats[ticker_stats["Portfolio_Count"] >= 2].copy()
        if not repeated.empty:
            repeated_leaders = repeated.sort_values(
                ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
                ascending=[False, False, False],
            )
            repeated_laggards = repeated.sort_values(
                ["Avg_Return", "Portfolio_Count", "Total_Current_Value"],
                ascending=[True, False, False],
            )

            facts["repeated_leaders"] = repeated_leaders["Ticker"].head(3).astype(str).tolist()
            facts["repeated_laggards"] = repeated_laggards["Ticker"].head(2).astype(str).tolist()

            max_repeat_count = repeated["Portfolio_Count"].max()
            if max_repeat_count >= 3:
                facts["concentration_note"] = (
                    "Performance appears somewhat concentrated in a relatively small group of names."
                )
            else:
                facts["concentration_note"] = (
                    "Performance appears relatively balanced across holdings."
                )
        else:
            facts["concentration_note"] = (
                "Leadership looks narrower, with fewer repeat winners across portfolios."
            )

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
        .reset_index(drop=True)
    )

    if not theme_stats.empty:
        best_theme_row = theme_stats.sort_values(
            ["Avg_Return", "Portfolio_Count", "Name_Count", "Total_Current_Value"],
            ascending=[False, False, False, False],
        ).iloc[0]
        worst_theme_row = theme_stats.sort_values(
            ["Avg_Return", "Portfolio_Count", "Name_Count", "Total_Current_Value"],
            ascending=[True, False, False, False],
        ).iloc[0]

        facts["best_theme"] = best_theme_row["Theme"]
        facts["worst_theme"] = worst_theme_row["Theme"]
        facts["theme_comment"] = get_theme_regime_comment(facts["best_theme"])

    return facts


def render_ai_insight_text(facts):
    if not facts or facts["winner"] is None:
        return "There is not enough filtered portfolio history to generate insights yet."

    parts = []

    winner_name = facts["winner"]["Portfolio"]
    winner_return = facts["winner"].get("Return")
    loser_name = facts["loser"]["Portfolio"]
    loser_return = facts["loser"].get("Return")
    spread = facts.get("return_spread")

    parts.append(
        f"Winner: {winner_name} at {pct(winner_return)} total return. "
        f"Laggard: {loser_name} at {pct(loser_return)}."
    )

    if spread is not None and pd.notna(spread):
        parts.append(
            f"The spread between the top and bottom portfolios is {pct(spread)}, which shows that positioning has mattered meaningfully over this window."
        )

    if facts.get("avg_alpha") is not None and pd.notna(facts["avg_alpha"]):
        alpha = facts["avg_alpha"]
        benchmark_choice = facts["benchmark_choice"]

        if alpha >= 0.03:
            parts.append(
                f"Against {benchmark_choice}, the average non-benchmark portfolio is ahead by {pct(alpha)}, indicating clear outperformance."
            )
        elif alpha >= 0:
            parts.append(
                f"Against {benchmark_choice}, the average non-benchmark portfolio is ahead by {pct(alpha)}, indicating modest outperformance."
            )
        elif alpha > -0.03:
            parts.append(
                f"Against {benchmark_choice}, the average non-benchmark portfolio is behind by {pct(abs(alpha))}, indicating roughly competitive but weaker performance."
            )
        else:
            parts.append(
                f"Against {benchmark_choice}, the average non-benchmark portfolio is behind by {pct(abs(alpha))}, indicating meaningful underperformance."
            )

    most_volatile = facts.get("most_volatile")
    if most_volatile is not None:
        parts.append(
            f"Highest volatility: {most_volatile['Portfolio']} at {pct(most_volatile.get('Volatility'))} daily volatility."
        )

    strongest_ticker = facts.get("strongest_ticker")
    weakest_ticker = facts.get("weakest_ticker")
    if strongest_ticker is not None and weakest_ticker is not None:
        parts.append(
            f"At the holding level, {strongest_ticker['Ticker']} has been one of the strongest contributors on average, while {weakest_ticker['Ticker']} has been the weakest."
        )

    if facts.get("repeated_leaders"):
        parts.append(
            f"{join_names(facts['repeated_leaders'])} are experiencing consistant above average perfromance, while"
        )

    if facts.get("repeated_laggards"):
        parts.append(
            f"repeated weakness is showing up in {join_names(facts['repeated_laggards'])}."
        )

    best_theme = facts.get("best_theme")
    worst_theme = facts.get("worst_theme")
    theme_comment = facts.get("theme_comment")
    if best_theme and worst_theme and best_theme != worst_theme:
        parts.append(
            f"By theme, the strongest area is {best_theme}, while the weakest area is {worst_theme}. {theme_comment}"
        )
    elif best_theme:
        parts.append(
            f"By theme, leadership is centered around {best_theme}. {theme_comment}"
        )

    if facts.get("winner_top_holdings"):
        parts.append(
            f"Top holdings in the leading portfolio: {join_names(facts['winner_top_holdings'])}."
        )

    if facts.get("concentration_note"):
        parts.append(facts["concentration_note"])

    return " ".join(parts)


def build_ai_insights(summary_df, holdings_df, benchmark_summary, benchmark_choice):
    facts = compute_ai_insight_facts(
        summary_df=summary_df,
        holdings_df=holdings_df,
        benchmark_summary=benchmark_summary,
        benchmark_choice=benchmark_choice,
    )
    return render_ai_insight_text(facts)


def build_ai_dvisor_insights(summary_df, holdings_df, benchmark_summary, benchmark_choice):
    return build_ai_insights(
        summary_df=summary_df,
        holdings_df=holdings_df,
        benchmark_summary=benchmark_summary,
        benchmark_choice=benchmark_choice,
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
