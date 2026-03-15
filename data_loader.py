import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

from config import START_DATE, PRICE_TTL_SECONDS, BENCHMARK_MAP, PORTFOLIO_CONFIG


def validate_columns(df, required, name):
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")


def get_end_date_string():
    return (pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _normalize_download_to_close_df(raw, expected_ticker=None):
    """
    Convert a yfinance download result into a 2-column dataframe:
    Date, <Ticker>
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["Date"])

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            return pd.DataFrame(columns=["Date"])
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame(columns=["Date"])
        ticker_name = expected_ticker or "VALUE"
        close = raw[["Close"]].copy()
        close.columns = [ticker_name]

    if isinstance(close, pd.Series):
        close = close.to_frame(name=expected_ticker or "VALUE")

    close = close.reset_index()
    date_col = "Date" if "Date" in close.columns else close.columns[0]
    close = close.rename(columns={date_col: "Date"})
    close["Date"] = pd.to_datetime(close["Date"], errors="coerce").dt.tz_localize(None)
    close = close.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    value_cols = [c for c in close.columns if c != "Date"]
    for col in value_cols:
        close[col] = pd.to_numeric(close[col], errors="coerce")

    return close


def fetch_single_ticker_history(ticker, start_date, end_date):
    raw = yf.download(
        tickers=ticker,
        start=start_date,
        end=end_date,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )

    df = _normalize_download_to_close_df(raw, expected_ticker=ticker)

    if "Date" not in df.columns:
        return pd.DataFrame(columns=["Date", ticker])

    if ticker not in df.columns:
        value_cols = [c for c in df.columns if c != "Date"]
        if value_cols:
            df = df.rename(columns={value_cols[0]: ticker})
        else:
            df[ticker] = np.nan

    return df[["Date", ticker]].copy()


def backfill_missing_tickers(prices, tickers, start_date, end_date):
    """
    For any ticker missing from the bulk pull, or present but entirely null,
    fetch it individually and merge it back into the main prices table.
    """
    out = prices.copy()

    for ticker in tickers:
        needs_backfill = ticker not in out.columns or out[ticker].isna().all()

        if not needs_backfill:
            continue

        single = fetch_single_ticker_history(ticker, start_date, end_date)

        if single.empty or ticker not in single.columns:
            if ticker not in out.columns:
                out[ticker] = np.nan
            continue

        if ticker not in out.columns:
            out = out.merge(single, on="Date", how="left")
        else:
            merged = out[["Date"]].merge(single, on="Date", how="left")
            out[ticker] = out[ticker].where(~out[ticker].isna(), merged[ticker])

    return out


@st.cache_data(show_spinner=False, ttl=PRICE_TTL_SECONDS)
def fetch_price_history(tickers_tuple, start_date, end_date):
    tickers = list(dict.fromkeys([str(t).strip().upper() for t in tickers_tuple if pd.notna(t)]))
    if not tickers:
        return pd.DataFrame(columns=["Date"])

    raw = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=True,
    )

    prices = _normalize_download_to_close_df(raw)

    if prices.empty:
        raise ValueError("yfinance returned no price history.")

    if "Date" not in prices.columns:
        raise ValueError("Downloaded price history did not include a Date column.")

    # Ensure every expected ticker exists as a column before backfill
    for ticker in tickers:
        if ticker not in prices.columns:
            prices[ticker] = np.nan

    prices = prices[["Date"] + tickers].copy()

    # Backfill any missing/all-null columns with single-ticker downloads
    prices = backfill_missing_tickers(prices, tickers, start_date, end_date)

    # Final numeric cleanup
    for ticker in tickers:
        prices[ticker] = pd.to_numeric(prices[ticker], errors="coerce")

    prices = prices.sort_values("Date").reset_index(drop=True)

    return prices


def fetch_single_ticker_inception_close(ticker, start_date, end_date):
    df = fetch_single_ticker_history(ticker, start_date, end_date)

    if df.empty or ticker not in df.columns:
        return np.nan, pd.NaT

    df = df.dropna(subset=["Date", ticker]).sort_values("Date").reset_index(drop=True)

    if df.empty:
        return np.nan, pd.NaT

    first_row = df.iloc[0]
    return first_row[ticker], first_row["Date"]


def build_portfolios_from_config(config_rows, prices, start_date):
    portfolios = pd.DataFrame(config_rows).copy()
    validate_columns(
        portfolios,
        ["Portfolio", "Ticker", "Initial Investment"],
        "PORTFOLIO_CONFIG",
    )

    portfolios["Portfolio"] = portfolios["Portfolio"].astype(str).str.strip()
    portfolios["Ticker"] = portfolios["Ticker"].astype(str).str.strip().str.upper()
    portfolios["Initial Investment"] = pd.to_numeric(portfolios["Initial Investment"], errors="coerce")

    start_ts = pd.to_datetime(start_date)
    first_prices = prices[prices["Date"] >= start_ts].copy()

    if first_prices.empty:
        raise ValueError(f"No price history found on or after {start_date}.")

    price_long = first_prices.melt(
        id_vars="Date",
        var_name="Ticker",
        value_name="Inception Close",
    ).dropna(subset=["Inception Close"])

    price_long = (
        price_long.sort_values(["Ticker", "Date"])
        .drop_duplicates(subset=["Ticker"], keep="first")
        .reset_index(drop=True)
    )

    portfolios = portfolios.merge(
        price_long[["Ticker", "Date", "Inception Close"]],
        on="Ticker",
        how="left",
    )
    portfolios = portfolios.rename(columns={"Date": "Inception Date"})

    missing_mask = portfolios["Inception Close"].isna()

    if missing_mask.any():
        end_date = get_end_date_string()
        missing_tickers = portfolios.loc[missing_mask, "Ticker"].dropna().unique().tolist()

        for ticker in missing_tickers:
            fallback_close, fallback_date = fetch_single_ticker_inception_close(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
            )

            ticker_mask = (portfolios["Ticker"] == ticker) & (portfolios["Inception Close"].isna())
            portfolios.loc[ticker_mask, "Inception Close"] = fallback_close
            portfolios.loc[ticker_mask, "Inception Date"] = fallback_date

    missing = portfolios[portfolios["Inception Close"].isna()]["Ticker"].dropna().unique().tolist()
    if missing:
        raise ValueError(f"Missing inception close for: {', '.join(missing)}")

    portfolios["Shares"] = np.where(
        portfolios["Inception Close"].fillna(0) != 0,
        portfolios["Initial Investment"] / portfolios["Inception Close"],
        np.nan,
    )

    return portfolios


def load_data():
    all_tickers = sorted(
        {
            str(row["Ticker"]).strip().upper()
            for row in PORTFOLIO_CONFIG
            if pd.notna(row.get("Ticker"))
        }
        | {str(v).strip().upper() for v in BENCHMARK_MAP.values()}
    )

    prices = fetch_price_history(tuple(all_tickers), START_DATE, get_end_date_string())

    if prices.empty:
        raise ValueError("No price data was downloaded from yfinance.")

    portfolios = build_portfolios_from_config(PORTFOLIO_CONFIG, prices, START_DATE)
    return portfolios, prices
