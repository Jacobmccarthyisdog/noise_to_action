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

    if raw is None or raw.empty:
        raise ValueError("yfinance returned no price history.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise ValueError("Downloaded data does not contain Close prices.")
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            raise ValueError("Downloaded data does not contain a Close column.")
        single_ticker = tickers[0]
        close = raw[["Close"]].copy()
        close.columns = [single_ticker]

    close = close.reset_index()
    date_col = "Date" if "Date" in close.columns else close.columns[0]
    close = close.rename(columns={date_col: "Date"})
    close["Date"] = pd.to_datetime(close["Date"], errors="coerce").dt.tz_localize(None)
    close = close.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    expected_cols = ["Date"] + tickers
    for ticker in tickers:
        if ticker not in close.columns:
            close[ticker] = np.nan

    close = close[expected_cols].copy()

    for col in tickers:
        close[col] = pd.to_numeric(close[col], errors="coerce")

    return close


def fetch_single_ticker_inception_close(ticker, start_date, end_date):
    raw = yf.download(
        tickers=ticker,
        start=start_date,
        end=end_date,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if raw is None or raw.empty or "Close" not in raw.columns:
        return np.nan, pd.NaT

    df = raw[["Close"]].copy().reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")

    if df.empty:
        return np.nan, pd.NaT

    first_row = df.iloc[0]
    return first_row["Close"], first_row["Date"]


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
