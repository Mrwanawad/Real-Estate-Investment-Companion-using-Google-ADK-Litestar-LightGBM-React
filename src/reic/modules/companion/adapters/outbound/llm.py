"""LLM selection: provider chain with fallback and a circuit breaker, plus a scripted fake.

`anthropic` runs Claude through LiteLLM and falls back to Gemini when a Gemini key exists;
`gemini` runs Gemini only; `fake` runs the deterministic script below (tests, offline demo).
"""

import json
import logging
import os
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr

log = logging.getLogger(__name__)


class _Breaker:
    def __init__(self, threshold: int = 3, cooldown_s: float = 60.0) -> None:
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_s:
            self.opened_at = None  # half-open: let one call through
            self.failures = self.threshold - 1
            return False
        return True

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class FallbackLlm(BaseLlm):
    """Tries each model in order. Falls through only if a model fails before its first chunk."""

    models: list[BaseLlm]
    _breakers: list[_Breaker] = PrivateAttr(default_factory=list)

    def model_post_init(self, context: Any) -> None:
        self._breakers = [_Breaker() for _ in self.models]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last_error: Exception | None = None
        for model, breaker in zip(self.models, self._breakers, strict=True):
            if breaker.open:
                continue
            request = llm_request.model_copy(update={"model": model.model})
            started = False
            try:
                async for response in model.generate_content_async(request, stream=stream):
                    if response.error_code and not started:
                        raise RuntimeError(f"{response.error_code}: {response.error_message}")
                    started = True
                    yield response
            except Exception as exc:
                if started:
                    raise
                breaker.failure()
                last_error = exc
                log.warning("llm %s failed, falling back: %s", model.model, exc)
                continue
            breaker.success()
            return
        raise RuntimeError("all LLM providers failed or are cooling down") from last_error


# --- scripted fake -------------------------------------------------------------------------

_AREAS = {
    "new cairo": "New Cairo",
    "القاهرة الجديدة": "New Cairo",
    "zayed": "Sheikh Zayed",
    "زايد": "Sheikh Zayed",
    "october": "6th of October",
    "أكتوبر": "6th of October",
    "north coast": "North Coast",
    "الساحل": "North Coast",
    "capital": "New Administrative Capital",
    "العاصمة": "New Administrative Capital",
    "madinaty": "Madinaty",
    "مدينتي": "Madinaty",
    "maadi": "Maadi",
    "المعادي": "Maadi",
    "alamein": "New Alamein",
    "العلمين": "New Alamein",
    "sokhna": "Ain Sokhna",
    "السخنة": "Ain Sokhna",
    "mostakbal": "Mostakbal City",
    "heliopolis": "Heliopolis",
    "zamalek": "Zamalek",
}
_GOALS = {
    "rent": "rent",
    "إيجار": "rent",
    "ايجار": "rent",
    "أجر": "rent",
    "اجر": "rent",
    "income": "rent",
    "resell": "resell",
    "resale": "resell",
    "flip": "resell",
    "بيع": "resell",
    "live": "live",
    "family": "live",
    "سكن": "live",
    "أسكن": "live",
}
_KNOWLEDGE = re.compile(
    r"fee|cancel|refund|policy|contract|clause|late|delay|registration|transfer|maintenance"
    r"|رسوم|إلغاء|الغاء|عقد|تأخير|تسجيل|صيانة|استرداد",
    re.IGNORECASE,
)
_BROKER = re.compile(r"broker|agent|call me|contact|reserve|وسيط|تواصل|اتصل|حجز", re.IGNORECASE)
_REPORT = re.compile(r"report|pdf|تقرير", re.IGNORECASE)
_MONEY = re.compile(r"(\d+(?:\.\d+)?)\s*(m|million|مليون|k|ألف)?\b", re.IGNORECASE)
_YEARS = re.compile(r"(\d{1,2})\s*(?:-|\s)?(?:years?|yrs?|سنوات|سنة|سنين)", re.IGNORECASE)
_DIACRITICS = re.compile(r"[ً-ْـ]")
_PHONE = re.compile(r"(?:\+?20|0)1\d{9}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def parse_buyer_message(text: str) -> dict[str, Any]:
    """Best-effort profile facts from free text (used only by the fake model)."""
    text = _DIACRITICS.sub("", text)
    lowered = text.lower()
    facts: dict[str, Any] = {}
    for key, goal in _GOALS.items():
        if key in lowered:
            facts["goal"] = goal
            break
    areas = list(dict.fromkeys(name for key, name in _AREAS.items() if key in lowered))
    if areas:
        facts["areas"] = areas
    if m := _YEARS.search(text):
        facts["horizon_years"] = int(m.group(1))
    without_years = _YEARS.sub(" ", text)
    without_contact = _EMAIL.sub(" ", _PHONE.sub(" ", without_years))
    for m in _MONEY.finditer(without_contact.replace(",", "")):
        value = float(m.group(1))
        unit = (m.group(2) or "").lower()
        value *= 1e6 if unit in {"m", "million", "مليون"} else 1e3 if unit in {"k", "ألف"} else 1
        if value >= 100_000:
            facts["budget_egp"] = int(value)
            break
    if m := _PHONE.search(text):
        facts["phone"] = m.group(0)
    if m := _EMAIL.search(text):
        facts["email"] = m.group(0)
    return facts


def _call(name: str, args: dict[str, Any]) -> LlmResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]))


def _text(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _fmt_egp(value: Any) -> str:
    return f"{float(value):,.0f} EGP"


class FakeLlm(BaseLlm):
    """Deterministic tool-calling script: profile -> shortlist -> financing -> returns."""

    model: str = "fake-companion"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield self._next(llm_request)

    def _next(self, request: LlmRequest) -> LlmResponse:
        contents = list(request.contents or [])
        user_index = max(
            (
                i
                for i, c in enumerate(contents)
                if c.role == "user" and any(p.text for p in c.parts or [])
            ),
            default=-1,
        )
        message = (
            "".join(p.text or "" for p in contents[user_index].parts or [])
            if user_index >= 0
            else ""
        )
        done: dict[str, dict[str, Any]] = {}
        for content in contents[user_index + 1 :]:
            for part in content.parts or []:
                if part.function_response:
                    done[part.function_response.name or ""] = dict(
                        part.function_response.response or {}
                    )
        instruction = str(request.config.system_instruction or "") if request.config else ""
        arabic = "Arabic" in instruction.split("Known buyer profile")[0]
        facts = parse_buyer_message(message)

        if facts and "update_profile" not in done:
            return _call("update_profile", facts)
        profile = done.get("update_profile", {}).get("profile") or {}
        has_budget = bool(profile.get("budget_egp")) or "'budget_egp'" in instruction
        has_goal = bool(profile.get("goal")) or "'goal'" in instruction
        has_horizon = bool(profile.get("horizon_years")) or "'horizon_years'" in instruction

        if _BROKER.search(message):
            if "create_lead" not in done:
                return _call(
                    "create_lead", {"summary": f"Buyer asked for a broker: {message[:200]}"}
                )
            return _text(self._lead_text(done["create_lead"], arabic))
        if _REPORT.search(message):
            if "build_report" not in done:
                return _call("build_report", {})
            return _text("تقريرك جاهز للتحميل." if arabic else "Your report is ready to download.")
        if _KNOWLEDGE.search(message) and not facts.get("budget_egp"):
            if "search_knowledge" not in done:
                return _call("search_knowledge", {"query": message})
            return _text(self._knowledge_text(done["search_knowledge"], arabic))
        if not (has_budget and has_goal):
            return _text(
                "ما هو هدفك (سكن، إيجار، أو إعادة بيع) وما هي ميزانيتك الإجمالية؟"
                if arabic
                else "What is your goal (live, rent out or resell) and your total budget in EGP?"
            )
        if "search_units" not in done:
            return _call("search_units", {})
        units = done["search_units"].get("units") or []
        if not units:
            return _text(
                "لا توجد وحدات مطابقة. هل نوسّع المناطق أو الميزانية؟"
                if arabic
                else "No available unit matches. Shall we widen the areas or the budget?"
            )
        top = units[0]["code"]
        if "compare_financing" not in done:
            return _call("compare_financing", {"unit_code": top})
        if has_horizon and "project_returns" not in done:
            return _call("project_returns", {"unit_code": top})
        return _text(self._summary(units, done, arabic, has_horizon))

    @staticmethod
    def _lead_text(result: dict[str, Any], arabic: bool) -> str:
        if "error" in result:
            return (
                "يسعدني توصيلك بوسيط. ما رقم هاتفك أو بريدك الإلكتروني؟"
                if arabic
                else "Happy to connect you with a broker. "
                "What phone number or email should they use?"
            )
        return (
            "تم تحويل طلبك إلى وسيط وسيتواصل معك قريبًا."
            if arabic
            else "Done. A broker has your details and will contact you shortly."
        )

    @staticmethod
    def _knowledge_text(result: dict[str, Any], arabic: bool) -> str:
        sources = result.get("sources") or []
        if not sources:
            return (
                "لم أجد ذلك في مستندات الشركة."
                if arabic
                else "I could not find that in the company documents."
            )
        first = sources[0]
        snippet = str(first.get("text", ""))[:300].strip()
        lead = "وفقًا لمستندات الشركة" if arabic else "According to the company documents"
        return f"{lead} [1]: {snippet}"

    @staticmethod
    def _summary(
        units: list[dict[str, Any]], done: dict[str, Any], arabic: bool, has_horizon: bool
    ) -> str:
        top = units[0]
        lines = [
            f"I found {len(units)} units. The best fit is **{top['code']}** in "
            f"{top.get('area_name')} at {_fmt_egp(top['price_egp'])}."
        ]
        financing = done.get("compare_financing", {})
        if cheapest := financing.get("cheapest_label"):
            lines.append(f"- Cheapest way to pay in today's money: **{cheapest}**.")
        returns = done.get("project_returns", {})
        if value := returns.get("value"):
            lines.append(
                f"- Value at horizon (P10 / P50 / P90): {_fmt_egp(value['p10'])} / "
                f"{_fmt_egp(value['p50'])} / {_fmt_egp(value['p90'])}."
            )
        elif not has_horizon:
            lines.append("- How many years do you plan to hold it? I can then project returns.")
        lines.append("These are scenarios on synthetic data, not a promise.")
        if arabic:
            lines.insert(0, "إليك النتائج (الأرقام في البطاقات أدناه):")
        return "\n".join(lines)


GEMINI_TIMEOUT_MS = 60_000
GEMINI_ATTEMPTS = 3


def build_llm(
    provider: str,
    *,
    anthropic_model: str,
    gemini_model: str,
    anthropic_api_key: str | None,
    gemini_api_key: str | None,
) -> BaseLlm:
    if provider == "fake":
        return FakeLlm()
    models: list[BaseLlm] = []
    if provider == "anthropic":
        from google.adk.models.lite_llm import LiteLlm

        key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            models.append(LiteLlm(model=f"anthropic/{anthropic_model}", api_key=key))
    gemini_key = (
        gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    if gemini_key:
        from google.adk.models.google_llm import Gemini
        from google.genai import types

        # Fail a stuck call instead of hanging the chat turn, and retry Google's transient
        # 429/5xx ("high demand") with backoff before the fallback chain sees the error.
        http = types.HttpOptions(timeout=GEMINI_TIMEOUT_MS)
        models.append(
            Gemini(
                model=gemini_model,
                client_kwargs={"api_key": gemini_key, "http_options": http},
                retry_options=types.HttpRetryOptions(attempts=GEMINI_ATTEMPTS, initial_delay=1.0),
            )
        )
    if not models:
        raise RuntimeError(f"LLM_PROVIDER={provider} but no API key is configured")
    return models[0] if len(models) == 1 else FallbackLlm(model="fallback", models=models)


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
