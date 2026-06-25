from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from calculations import (  # noqa: E402
    build_datasets,
    build_summary,
    build_ytd_metrics_snapshot,
    exclude_benchmark_portfolios,
)
from config import BENCHMARK_MAP, PORTFOLIO_CONFIG, START_DATE  # noqa: E402
from data_loader import load_data  # noqa: E402
from insights import load_daily_insight  # noqa: E402


DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "web" / "public" / "data" / "dashboard.json"


def json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if hasattr(value, "item"):
        return value.item()

    return value


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    cleaned = df.copy()

    for column in cleaned.columns:
        if pd.api.types.is_datetime64_any_dtype(cleaned[column]):
            cleaned[column] = cleaned[column].dt.strftime("%Y-%m-%d")

    cleaned = cleaned.where(pd.notna(cleaned), None)
    return [
        {str(key): json_safe(value) for key, value in row.items()}
        for row in cleaned.to_dict(orient="records")
    ]


def latest_daily_insight() -> dict[str, Any] | None:
    payload = load_daily_insight()

    if isinstance(payload, dict):
        return public_insight_record(payload)

    if isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
        if not items:
            return None
        latest = sorted(
            items,
            key=lambda item: str(item.get("as_of_date") or item.get("generated_at") or ""),
            reverse=True,
        )[0]
        return public_insight_record(latest)

    return None


def public_insight_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(record)
    cleaned.pop("error", None)
    return cleaned


def latest_complete_portfolio_date(portfolio_history: pd.DataFrame) -> pd.Timestamp:
    if portfolio_history is None or portfolio_history.empty or "Date" not in portfolio_history.columns:
        return pd.NaT
    return pd.to_datetime(portfolio_history["Date"]).max()


def build_export_payload() -> dict[str, Any]:
    portfolios, prices = load_data()

    (
        portfolio_history,
        _merged_positions,
        holdings_snapshot,
        benchmark_history,
        portfolio_cumret,
        benchmark_cumret,
    ) = build_datasets(portfolios, prices)

    summary = build_summary(portfolio_history)
    investable_summary = exclude_benchmark_portfolios(summary)
    investable_holdings = exclude_benchmark_portfolios(holdings_snapshot)
    latest_date = latest_complete_portfolio_date(portfolio_history)

    metrics_payload = build_ytd_metrics_snapshot(
        portfolio_history=portfolio_history,
        holdings_snapshot=holdings_snapshot,
        benchmark_history=benchmark_history,
        benchmark_choice="SPY",
    )

    return {
        "schema_version": 1,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "as_of_date": latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else None,
        "start_date": START_DATE,
        "benchmarks": BENCHMARK_MAP,
        "portfolio_config": PORTFOLIO_CONFIG,
        "portfolio_names": sorted(
            investable_summary["Portfolio"].dropna().astype(str).unique().tolist()
        )
        if not investable_summary.empty
        else [],
        "summary": records(investable_summary),
        "holdings": records(investable_holdings),
        "portfolio_history": records(exclude_benchmark_portfolios(portfolio_history)),
        "portfolio_cumulative_returns": records(exclude_benchmark_portfolios(portfolio_cumret)),
        "benchmark_history": records(benchmark_history),
        "benchmark_cumulative_returns": records(benchmark_cumret),
        "metrics_snapshot": metrics_payload,
        "daily_insight": latest_daily_insight(),
    }


def main(output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    payload = build_export_payload()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print(f"Exported dashboard data to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export the portfolio dashboard data contract for the Next.js app."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination JSON path. Defaults to web/public/data/dashboard.json.",
    )
    args = parser.parse_args()

    main(output_path=args.output)
