import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_INSIGHT_PATH = Path("data/daily_insight.json")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "daily_portfolio_insight_v1"


def get_default_insight_path() -> Path:
    return DEFAULT_INSIGHT_PATH


def load_daily_insight(path: str | Path | None = None) -> dict[str, Any] | list[Any] | None:
    insight_path = Path(path) if path else get_default_insight_path()

    if not insight_path.exists():
        return None

    try:
        with insight_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def save_daily_insight(record: dict[str, Any], path: str | Path | None = None) -> Path:
    insight_path = Path(path) if path else get_default_insight_path()
    insight_path.parent.mkdir(parents=True, exist_ok=True)

    with insight_path.open("w", encoding="utf-8") as file:
        json.dump(record, file, indent=2, ensure_ascii=False)

    return insight_path


def insight_exists_for_date(as_of_date: str, path: str | Path | None = None) -> bool:
    record = load_daily_insight(path=path)

    if not record:
        return False

    if isinstance(record, dict):
        return record.get("as_of_date") == as_of_date

    if isinstance(record, list):
        return any(
            isinstance(item, dict) and item.get("as_of_date") == as_of_date
            for item in record
        )

    return False


def _format_percent(value: Any) -> str:
    if value is None:
        return "N/A"

    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _format_currency(value: Any) -> str:
    if value is None:
        return "N/A"

    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _get_name(record: dict[str, Any] | None, fallback: str = "N/A") -> str:
    if not record:
        return fallback

    return (
        record.get("name")
        or record.get("portfolio")
        or record.get("ticker")
        or fallback
    )


def generate_placeholder_insight(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    as_of_date = metrics_payload.get("as_of_date")
    benchmark = metrics_payload.get("benchmark", "SPY")
    top_portfolio = metrics_payload.get("top_portfolio") or {}
    bottom_portfolio = metrics_payload.get("bottom_portfolio") or {}
    most_volatile = metrics_payload.get("most_volatile") or {}
    top_holding = metrics_payload.get("top_holding") or {}
    bottom_holding = metrics_payload.get("bottom_holding") or {}

    top_name = _get_name(top_portfolio)
    bottom_name = _get_name(bottom_portfolio)
    volatile_name = _get_name(most_volatile)
    top_holding_name = _get_name(top_holding)
    bottom_holding_name = _get_name(bottom_holding)

    takeaways = [
        f"Top portfolio YTD: {top_name} at {_format_percent(top_portfolio.get('return'))}.",
        f"Bottom portfolio YTD: {bottom_name} at {_format_percent(bottom_portfolio.get('return'))}.",
        f"Highest volatility portfolio: {volatile_name}.",
    ]

    if top_holding:
        takeaways.append(
            f"Best holding: {top_holding_name} at {_format_percent(top_holding.get('return'))}."
        )

    if bottom_holding:
        takeaways.append(
            f"Weakest holding: {bottom_holding_name} at {_format_percent(bottom_holding.get('return'))}."
        )

    benchmark_return = metrics_payload.get("benchmark_return")
    avg_portfolio_return = metrics_payload.get("avg_portfolio_return")
    avg_alpha = metrics_payload.get("avg_alpha")

    insight_text = (
        f"As of {as_of_date}, the portfolio set is being evaluated against {benchmark}. "
        f"The average portfolio return is {_format_percent(avg_portfolio_return)}, "
        f"versus benchmark return of {_format_percent(benchmark_return)}, "
        f"for average alpha of {_format_percent(avg_alpha)}. "
        f"{top_name} is the strongest YTD performer, while {bottom_name} is the weakest. "
        f"{volatile_name} is the portfolio to monitor most closely for volatility."
    )

    return {
        "schema_version": 1,
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": benchmark,
        "model": None,
        "prompt_version": None,
        "status": "success",
        "payload": metrics_payload,
        "headline": "Daily portfolio insight",
        "insight_text": insight_text,
        "takeaways": takeaways,
    }


def _build_prompt(metrics_payload: dict[str, Any]) -> str:
    return f"""
You are generating a concise daily portfolio dashboard insight.

Use only the metrics in the JSON payload below.
Do not invent numbers.
Do not give financial advice.
Do not recommend buying or selling securities.
Write for a portfolio dashboard user who wants a clear summary of what changed and what to watch.

Return valid JSON only with this exact shape:
{{
  "headline": "string",
  "insight_text": "string",
  "takeaways": ["string", "string", "string"],
  "risks": ["string"],
  "actions": ["string"]
}}

Rules:
- headline should be short.
- insight_text should be 3 to 5 sentences.
- takeaways should contain 3 to 5 bullets.
- risks should contain 1 to 3 watchouts.
- actions should contain 1 to 3 dashboard review actions, not trading instructions.
- Keep the language plain and useful.

Metrics payload:
{json.dumps(metrics_payload, indent=2, ensure_ascii=False)}
""".strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise

        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("LLM response was valid JSON but not a JSON object.")

    return parsed


def _normalize_llm_payload(
    llm_payload: dict[str, Any],
    metrics_payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    placeholder = generate_placeholder_insight(metrics_payload)

    headline = llm_payload.get("headline") or placeholder["headline"]
    insight_text = llm_payload.get("insight_text") or llm_payload.get("summary") or placeholder["insight_text"]

    takeaways = llm_payload.get("takeaways") or llm_payload.get("bullets") or placeholder["takeaways"]
    risks = llm_payload.get("risks") or llm_payload.get("watchouts") or []
    actions = llm_payload.get("actions") or llm_payload.get("recommendations") or []

    if not isinstance(takeaways, list):
        takeaways = [str(takeaways)]

    if not isinstance(risks, list):
        risks = [str(risks)]

    if not isinstance(actions, list):
        actions = [str(actions)]

    return {
        "schema_version": 1,
        "as_of_date": metrics_payload.get("as_of_date"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": metrics_payload.get("benchmark", "SPY"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "status": "success",
        "payload": metrics_payload,
        "headline": str(headline),
        "insight_text": str(insight_text),
        "takeaways": [str(item) for item in takeaways],
        "risks": [str(item) for item in risks],
        "actions": [str(item) for item in actions],
    }


def generate_llm_insight(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    if not api_key:
        record = generate_placeholder_insight(metrics_payload)
        record["status"] = "fallback_no_openai_api_key"
        record["model"] = None
        record["prompt_version"] = PROMPT_VERSION
        return record

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise, factual portfolio dashboard insights. "
                        "You return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(metrics_payload),
                },
            ],
        )

        content = response.choices[0].message.content or ""
        llm_payload = _extract_json_object(content)

        return _normalize_llm_payload(
            llm_payload=llm_payload,
            metrics_payload=metrics_payload,
            model=model,
        )

    except Exception as exc:
        record = generate_placeholder_insight(metrics_payload)
        record["status"] = "fallback_llm_error"
        record["model"] = model
        record["prompt_version"] = PROMPT_VERSION
        record["error"] = str(exc)
        return record
