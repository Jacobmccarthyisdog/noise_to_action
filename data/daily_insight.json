import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from data_loader import load_data
from calculations import build_datasets, build_ytd_metrics_snapshot
from insights import (
    generate_llm_insight,
    insight_exists_for_date,
    save_daily_insight,
)


def main(force=False):
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
        benchmark_choice="SPY",
    )

    as_of_date = metrics_payload.get("as_of_date")
    if not as_of_date:
        raise ValueError("Could not determine as_of_date for daily insight generation.")

    if not force and insight_exists_for_date(as_of_date):
        print(f"Daily insight already exists for {as_of_date}. Skipping generation.")
        return

    record = generate_llm_insight(metrics_payload)
    output_path = save_daily_insight(record)

    print(f"Saved daily insight for {as_of_date} to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the daily portfolio insight artifact.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate the insight even if one already exists for the current as_of_date.",
    )
    args = parser.parse_args()

    main(force=args.force)
