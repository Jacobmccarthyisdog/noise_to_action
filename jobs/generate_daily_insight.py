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


VALID_RUN_TYPES = {"premarket", "postclose", "manual"}


def main(force=False, run_type="manual"):
    if run_type not in VALID_RUN_TYPES:
        raise ValueError(
            f"Invalid run_type '{run_type}'. Expected one of: {sorted(VALID_RUN_TYPES)}"
        )

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

    if not force and insight_exists_for_date(as_of_date, run_type=run_type):
        print(f"Daily insight already exists for {as_of_date} ({run_type}). Skipping generation.")
        return

    record = generate_llm_insight(
        metrics_payload=metrics_payload,
        run_type=run_type,
    )
    output_path = save_daily_insight(record)

    print(f"Saved {run_type} daily insight for {as_of_date} to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the daily portfolio insight artifact.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate the insight even if one already exists for the current as_of_date and run type.",
    )
    parser.add_argument(
        "--run-type",
        choices=sorted(VALID_RUN_TYPES),
        default="manual",
        help="Type of scheduled insight to generate.",
    )
    args = parser.parse_args()

    main(force=args.force, run_type=args.run_type)
