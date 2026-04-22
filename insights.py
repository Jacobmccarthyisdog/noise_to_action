import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI


DEFAULT_INSIGHT_PATH = Path("data/daily_insight.json")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
PROMPT_VERSION = "daily_ytd_v1"
SCHEMA_VERSION = 1


def get_default_insight_path():
    return DEFAULT_INSIGHT_PATH


def load_daily_insight(path=None):
    insight_path = Path(path) if path else get_default_insight_path()

    if not insight_path.exists():
        return None

    try:
        with insight_path.open("r", encoding="utf-8") as f:
            record = json.load(f)
            return record if isinstance(record, dict) else None
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


def _build_prompt(metrics_payload):
    return f"""
You are generating a daily dashboard insight for an investment tracking app.

Use only the metrics provided below.
Do not invent facts.
Do not provide financial advice.
Do not mention missing data unless it prevents a summary.
Write concise, dashboard-ready output.

Return valid JSON with exactly these keys:
- "summary": a short paragraph of 2 to 4 sentences
- "takeaways": an array of exactly 3 short bullet-style strings

Focus on:
- year-to-date performance
- relative context versus the benchmark
- top and bottom portfolio
- the highest-volatility portfolio
- notable holding-level leadership or weakness if provided

Metrics payload:
{json.dumps(metrics_payload, ensure_ascii=False, indent=2)}
""".strip()


def _parse_llm_json_response(raw_text):
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")

    summary = parsed.get("summary")
    takeaways = parsed.get("takeaways")

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Model response missing valid 'summary' string.")

    if not isinstance(takeaways, list) or len(takeaways) != 3:
        raise ValueError("Model response must include exactly 3 takeaways.")

    cleaned_takeaways = []
    for item in takeaways:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Each takeaway must be a non-empty string.")
        cleaned_takeaways.append(item.strip())

    return {
        "summary": summary.strip(),
        "takeaways": cleaned_takeaways,
    }


def generate_llm_insight(metrics_payload):
    as_of_date = metrics_payload.get("as_of_date")
    if not as_of_date:
        raise ValueError("metrics_payload must include a valid as_of_date")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    benchmark = metrics_payload.get("benchmark", "SPY")

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(metrics_payload)

    response = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=350,
    )

    raw_text = response.output_text
    parsed = _parse_llm_json_response(raw_text)

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": benchmark,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "status": "success",
        "payload": metrics_payload,
        "insight_text": parsed["summary"],
        "takeaways": parsed["takeaways"],
    }


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
        "schema_version": SCHEMA_VERSION,
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
