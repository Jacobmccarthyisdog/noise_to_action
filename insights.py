
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INSIGHT_PATH = Path("data/daily_insight.json")


def get_default_insight_path():
    return DEFAULT_INSIGHT_PATH


def load_daily_insight(path=None):
    insight_path = Path(path) if path else get_default_insight_path()

    if not insight_path.exists():
        return None

    try:
        with insight_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_daily_insight(record, path=None):
    insight_path = Path(path) if path else get_default_insight_path()
    insight_path.parent.mkdir(parents=True, exist_ok=True)

    with insight_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    return insight_path


def insight_exists_for_date(as_of_date, path=None):
    record = load_daily_insight(path=path)
    if not record:
        return False

    return record.get("as_of_date") == as_of_date


def generate_placeholder_insight(metrics_payload):
    as_of_date = metrics_payload.get("as_of_date")
    benchmark = metrics_payload.get("benchmark", "SPY")
    top_portfolio = metrics_payload.get("top_portfolio") or {}
    bottom_portfolio = metrics_payload.get("bottom_portfolio") or {}
    most_volatile = metrics_payload.get("most_volatile") or {}

    top_name = top_portfolio.get("name", "N/A")
    bottom_name = bottom_portfolio.get("name", "N/A")
    volatile_name = most_volatile.get("name", "N/A")

    takeaways = [
        f"Top portfolio YTD: {top_name}",
        f"Bottom portfolio YTD: {bottom_name}",
        f"Highest volatility portfolio: {volatile_name}",
    ]

    return {
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": benchmark,
        "model": None,
        "prompt_version": None,
        "status": "success",
        "payload": metrics_payload,
        "insight_text": (
            f"Placeholder daily insight for {as_of_date}. "
            f"This artifact confirms the daily insight pipeline is working. "
            f"LLM generation is not enabled yet. Benchmark context: {benchmark}."
        ),
        "takeaways": takeaways,
    }
