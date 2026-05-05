import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_loader import load_data
from calculations import build_datasets, build_ytd_metrics_snapshot
from insights import (
    generate_llm_insight,
    generate_placeholder_insight,
    insight_exists_for_date,
    save_daily_insight,
)


def main(force: bool = False, allow_placeholder: bool = False) -> None:
    portfolios, prices = load_data()

    (
        portfolio_history,
        _merged_positions,
        holdings_snapshot,
        benchmark_history,
        _portfolio_cumret,
        _benchmark_cumret,
    ) = build_datasets(portfolios, prices)

    metrics_payload = build_ytd_metrics_snapshot(
        portfolio_history=portfolio_history,
        holdings_snapshot=holdings_snapshot,
        benchmark_history=benchmark_history,
    )

    as_of_date = (
        metrics_payload.get("as_of_date")
        or metrics_payload.get("date")
        or metrics_payload.get("latest_date")
    )

    if not as_of_date:
        raise RuntimeError("build_ytd_metrics_snapshot did not return an as_of_date/date/latest_date value.")

    as_of_date = str(as_of_date)

    if not force and insight_exists_for_date(as_of_date):
        print(f"OpenAI daily insight already exists for {as_of_date}. Skipping generation.")
        return

    try:
        record = generate_llm_insight(metrics_payload)
    except Exception as exc:
        if not allow_placeholder:
            raise

        print(f"OpenAI insight generation failed. Writing placeholder instead. Error: {exc}")
        record = generate_placeholder_insight(metrics_payload)

    output_path = save_daily_insight(record)

    print(f"Saved daily insight for {as_of_date} to {output_path}")
    print(f"Insight source: {record.get('source')}")
    print(f"Headline: {record.get('headline')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the daily OpenAI portfolio insight.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate the daily insight even if an OpenAI insight already exists for the date.",
    )
    parser.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="Write a placeholder record if the OpenAI call fails.",
    )

    args = parser.parse_args()
    main(force=args.force, allow_placeholder=args.allow_placeholder)
