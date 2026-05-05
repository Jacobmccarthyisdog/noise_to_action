import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_INSIGHT_PATH = Path("data/daily_insight.json")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "daily_portfolio_insight_v2"
UPDATE_NOTE = "Updated 30 minutes before and after market close."


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


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_outperformance_context(metrics_payload: dict[str, Any]) -> str:
    avg_portfolio_return = _safe_float(metrics_payload.get("avg_portfolio_return"))
    benchmark_return = _safe_float(metrics_payload.get("benchmark_return"))
    avg_alpha = _safe_float(metrics_payload.get("avg_alpha"))
    benchmark = metrics_payload.get("benchmark", "SPY")

    if avg_portfolio_return is None or benchmark_return is None:
        return (
            f"The dashboard is positioned around comparing portfolio behavior against "
            f"{benchmark}, but the current payload does not include enough benchmark "
            f"return detail to quantify relative performance."
        )

    if avg_portfolio_return > benchmark_return:
        alpha_text = _format_percent(avg_alpha) if avg_alpha is not None else "positive"
        return (
            f"The portfolio set is outperforming {benchmark}, which makes the current "
            f"readout more useful than a simple return snapshot. Outperformance versus "
            f"a broad benchmark like SPY can help show whether the portfolio is holding "
            f"up during periods of market stress, macro uncertainty, rate volatility, "
            f"or global conflict headlines. Current average alpha is {alpha_text}, "
            f"meaning the portfolio group is not just rising in absolute terms, it is "
            f"also ahead of the benchmark comparison."
        )

    if avg_portfolio_return == benchmark_return:
        return (
            f"The portfolio set is tracking closely with {benchmark}. In this setup, "
            f"the dashboard is useful for monitoring whether the portfolio starts to "
            f"separate from the benchmark during market stress, macro uncertainty, "
            f"or global conflict headlines."
        )

    return (
        f"The portfolio set is currently trailing {benchmark}. That makes the benchmark "
        f"comparison especially important because it shows whether the portfolios are "
        f"absorbing market stress, macro uncertainty, or global conflict headlines better "
        f"or worse than a broad market proxy."
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

    benchmark_return = metrics_payload.get("benchmark_return")
    avg_portfolio_return = metrics_payload.get("avg_portfolio_return")
    avg_alpha = metrics_payload.get("avg_alpha")

    outperformance_context = _build_outperformance_context(metrics_payload)

    headline = "Portfolio performance versus benchmark"

    if _safe_float(avg_portfolio_return) is not None and _safe_float(benchmark_return) is not None:
        if float(avg_portfolio_return) > float(benchmark_return):
            headline = "Portfolio outperforms benchmark YTD"
        elif float(avg_portfolio_return) < float(benchmark_return):
            headline = "Portfolio trails benchmark YTD"
        else:
            headline = "Portfolio tracks benchmark YTD"

    summary = (
        f"As of {as_of_date}, the portfolio group has an average return of "
        f"{_format_percent(avg_portfolio_return)} versus {benchmark} at "
        f"{_format_percent(benchmark_return)}, producing average alpha of "
        f"{_format_percent(avg_alpha)}. {outperformance_context} "
        f"The strongest portfolio is {top_name}, with a return of "
        f"{_format_percent(top_portfolio.get('return'))} and current value of "
        f"{_format_currency(top_portfolio.get('current_value'))}. The weakest "
        f"portfolio is {bottom_name}, with a return of "
        f"{_format_percent(bottom_portfolio.get('return'))}, while {volatile_name} "
        f"is the portfolio showing the highest volatility. "
        f"Note: {UPDATE_NOTE}"
    )

    takeaways = [
        (
            f"{top_name} is the strongest YTD performer, returning "
            f"{_format_percent(top_portfolio.get('return'))} with a dollar change of "
            f"{_format_currency(top_portfolio.get('dollar_change'))}."
        ),
        (
            f"{bottom_name} is the lowest YTD performer, returning "
            f"{_format_percent(bottom_portfolio.get('return'))}, which still needs to "
            f"be interpreted against the {benchmark} benchmark return of "
            f"{_format_percent(benchmark_return)}."
        ),
        (
            f"The portfolio group average return of {_format_percent(avg_portfolio_return)} "
            f"compares to {benchmark} at {_format_percent(benchmark_return)}, giving the "
            f"dashboard a clear benchmark-relative read rather than just an absolute return view."
        ),
    ]

    if top_holding:
        takeaways.append(
            f"{top_holding_name} is the strongest holding, returning "
            f"{_format_percent(top_holding.get('return'))} with current value of "
            f"{_format_currency(top_holding.get('current_value'))}."
        )

    if bottom_holding:
        takeaways.append(
            f"{bottom_holding_name} is the weakest holding, returning "
            f"{_format_percent(bottom_holding.get('return'))} with current value of "
            f"{_format_currency(bottom_holding.get('current_value'))}."
        )

    return {
        "schema_version": 1,
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": benchmark,
        "model": None,
        "prompt_version": PROMPT_VERSION,
        "status": "success",
        "source": "fallback",
        "payload": metrics_payload,
        "headline": headline,
        "summary": summary,
        "insight_text": summary,
        "takeaways": takeaways,
        "update_note": UPDATE_NOTE,
    }


def _build_prompt(metrics_payload: dict[str, Any]) -> str:
    outperformance_context = _build_outperformance_context(metrics_payload)

    return f"""
You are generating a daily portfolio dashboard insight.

Use only the metrics in the JSON payload below.
Do not invent numbers.
Do not give financial advice.
Do not recommend buying, selling, or reallocating securities.
Write for a dashboard user who wants a specific, benchmark-relative explanation.

The user does not want generic watchouts or suggested actions.
Do not include risks.
Do not include watchouts.
Do not include suggested actions.
Do not include recommendations.

The insight should be more descriptive and less vague than a basic summary.
It should explain whether the portfolio is outperforming or underperforming the benchmark, especially SPY.
When the portfolio is outperforming SPY or the selected benchmark, frame that as a useful benchmark-relative signal during periods of broader market stress, macro uncertainty, rate volatility, or global conflict headlines.
Do not claim that a specific war or conflict caused the returns unless the payload explicitly says so.
Do not claim the portfolio is hedged or protected.
Do not overstate the result.
Focus on what the dashboard can show: relative performance, alpha, strongest portfolio, weakest portfolio, most volatile portfolio, strongest holding, and weakest holding.

Include this exact sentence at the end of summary:
Note: {UPDATE_NOTE}

Return valid JSON only with this exact shape:
{{
  "headline": "string",
  "summary": "string",
  "takeaways": ["string", "string", "string"]
}}

Writing rules:
- headline should be short and specific.
- summary should be 4 to 7 sentences.
- takeaways should contain 3 to 5 bullets.
- Use the benchmark name from the payload.
- Mention SPY when the benchmark is SPY.
- Explain why outperforming a benchmark matters.
- Avoid vague phrases like "robust performance" unless supported by numbers.
- Keep the tone clear and confident.

Benchmark-relative context to use:
{outperformance_context}

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


def _normalize_list(value: Any, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]

    value_as_string = str(value).strip()
    if not value_as_string:
        return fallback

    return [value_as_string]


def _normalize_llm_payload(
    llm_payload: dict[str, Any],
    metrics_payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    placeholder = generate_placeholder_insight(metrics_payload)

    headline = llm_payload.get("headline") or placeholder["headline"]
    summary = (
        llm_payload.get("summary")
        or llm_payload.get("insight_text")
        or placeholder["summary"]
    )

    if UPDATE_NOTE not in summary:
        summary = f"{summary.rstrip()} Note: {UPDATE_NOTE}"

    takeaways = _normalize_list(
        llm_payload.get("takeaways") or llm_payload.get("bullets"),
        placeholder["takeaways"],
    )

    return {
        "schema_version": 1,
        "as_of_date": metrics_payload.get("as_of_date"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": metrics_payload.get("period", "YTD"),
        "benchmark": metrics_payload.get("benchmark", "SPY"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "status": "success",
        "source": "openai",
        "payload": metrics_payload,
        "headline": str(headline),
        "summary": str(summary),
        "insight_text": str(summary),
        "takeaways": takeaways,
        "update_note": UPDATE_NOTE,
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
        record["source"] = "fallback"
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
                        "You write concise, factual, benchmark-relative portfolio dashboard insights. "
                        "You return valid JSON only. You do not provide financial advice."
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
        record["source"] = "fallback"
        record["error"] = str(exc)
        return record
