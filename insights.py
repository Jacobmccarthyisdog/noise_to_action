import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DAILY_INSIGHT_PATH = Path("data/daily_insight.json")
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _safe_json_default(value: Any) -> str:
    """Fallback serializer for dates, timestamps, numpy/pandas scalar values, and other objects."""
    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return str(value)


def _json_dumps(payload: Any) -> str:
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        default=_safe_json_default,
    )


def _extract_date(metrics_payload: dict[str, Any]) -> str:
    for key in ["as_of_date", "date", "latest_date", "generated_for"]:
        value = metrics_payload.get(key)
        if value:
            return str(value)

    return datetime.now(timezone.utc).date().isoformat()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""
    if not text:
        raise ValueError("OpenAI returned an empty response.")

    cleaned = text.strip()

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Could not find a JSON object in OpenAI response: {text[:500]}")
        cleaned = cleaned[start : end + 1]

    parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise ValueError("OpenAI response JSON was not an object.")

    return parsed


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]

    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]

    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []

    return [str(value)]


def _normalize_openai_record(record: dict[str, Any], metrics_payload: dict[str, Any]) -> dict[str, Any]:
    as_of_date = (
        record.get("as_of_date")
        or record.get("date")
        or record.get("generated_for")
        or _extract_date(metrics_payload)
    )

    headline = (
        record.get("headline")
        or record.get("title")
        or "AI generated portfolio summary"
    )

    summary = (
        record.get("summary")
        or record.get("insight")
        or record.get("narrative")
        or record.get("analysis")
        or ""
    )

    bullets = (
        record.get("bullets")
        or record.get("key_points")
        or record.get("highlights")
        or record.get("takeaways")
        or []
    )

    risks = (
        record.get("risks")
        or record.get("watchouts")
        or record.get("watch_outs")
        or record.get("risk_factors")
        or []
    )

    actions = (
        record.get("actions")
        or record.get("recommendations")
        or record.get("suggested_actions")
        or record.get("next_steps")
        or []
    )

    normalized = {
        "as_of_date": str(as_of_date),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "openai",
        "model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "headline": str(headline),
        "summary": str(summary),
        "bullets": _normalize_list(bullets),
        "risks": _normalize_list(risks),
        "actions": _normalize_list(actions),
    }

    return normalized


def _build_prompt(metrics_payload: dict[str, Any]) -> list[dict[str, str]]:
    metrics_json = _json_dumps(metrics_payload)

    system_message = """
You are an investment dashboard analyst writing a concise daily portfolio summary.

Rules:
- Do not provide financial advice.
- Do not recommend buying or selling securities.
- Ground the response only in the metrics payload provided.
- Be specific, plain-English, and useful to a dashboard user.
- Return only valid JSON.
- Do not wrap the JSON in markdown fences.
""".strip()

    user_message = f"""
Create a daily AI generated summary for this portfolio dashboard.

Return exactly this JSON shape:
{{
  "as_of_date": "YYYY-MM-DD",
  "headline": "one concise headline",
  "summary": "2 to 4 sentence overview of what changed and what matters",
  "bullets": [
    "specific takeaway 1",
    "specific takeaway 2",
    "specific takeaway 3"
  ],
  "risks": [
    "watchout or uncertainty 1",
    "watchout or uncertainty 2"
  ],
  "actions": [
    "dashboard action the user can take, such as review a portfolio or compare against benchmark"
  ]
}}

Metrics payload:
{metrics_json}
""".strip()

    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


def _call_openai_chat_completions(messages: list[dict[str, str]]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it as a GitHub Actions repository secret."
        )

    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    request_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    request = urllib.request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=_json_dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP error {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API request failed: {exc}") from exc

    parsed_response = json.loads(response_body)

    try:
        return parsed_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenAI API response shape: {response_body}") from exc


def generate_placeholder_insight(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    as_of_date = _extract_date(metrics_payload)

    return {
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "placeholder",
        "model": None,
        "headline": "AI generated summary pending",
        "summary": (
            "The dashboard is wired to read data/daily_insight.json. "
            "A real OpenAI-generated summary will replace this placeholder once the daily job runs successfully."
        ),
        "bullets": [
            "The Streamlit dropdown is rendering correctly.",
            "The JSON file is valid and readable.",
            "The remaining step is a successful OpenAI generation run.",
        ],
        "risks": [
            "If this placeholder remains visible, verify the OPENAI_API_KEY secret and the GitHub Actions workflow run logs."
        ],
        "actions": [
            "Run the generate_daily_insight workflow manually.",
            "Check that data/daily_insight.json is updated in the branch after the workflow completes.",
        ],
    }


def generate_llm_insight(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    messages = _build_prompt(metrics_payload)
    openai_text = _call_openai_chat_completions(messages)
    openai_record = _extract_json_object(openai_text)
    return _normalize_openai_record(openai_record, metrics_payload)


def insight_exists_for_date(as_of_date: str, path: Path = DAILY_INSIGHT_PATH) -> bool:
    if not path.exists():
        return False

    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError):
        return False

    if isinstance(payload, dict):
        existing_date = (
            payload.get("as_of_date")
            or payload.get("date")
            or payload.get("generated_for")
        )
        source = payload.get("source")

        if str(existing_date) == str(as_of_date) and source == "openai":
            return True

        return False

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue

            existing_date = (
                item.get("as_of_date")
                or item.get("date")
                or item.get("generated_for")
            )
            source = item.get("source")

            if str(existing_date) == str(as_of_date) and source == "openai":
                return True

    return False


def save_daily_insight(record: dict[str, Any], path: Path = DAILY_INSIGHT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized_record = {
        "as_of_date": str(record.get("as_of_date") or record.get("date") or "unknown"),
        "generated_at": str(record.get("generated_at") or datetime.now(timezone.utc).isoformat()),
        "source": str(record.get("source") or "unknown"),
        "model": record.get("model"),
        "headline": str(record.get("headline") or "AI generated portfolio summary"),
        "summary": str(record.get("summary") or ""),
        "bullets": _normalize_list(record.get("bullets")),
        "risks": _normalize_list(record.get("risks")),
        "actions": _normalize_list(record.get("actions")),
    }

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            normalized_record,
            file,
            indent=2,
            ensure_ascii=False,
            default=_safe_json_default,
        )
        file.write("\n")

    return path
