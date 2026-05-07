import logging

from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)

MOCK_TITLE: str = "Local Man Discovers He's Been Doing Everything Wrong This Whole Time"
MOCK_DESCRIPTION: str = (
    "Experts confirm the situation is exactly as bad as it sounds, "
    "but stress there is still time to feel vaguely embarrassed about it."
)

_SYSTEM_PROMPT = (
    "You rewrite news articles as short, absurd satire. "
    "Given an original headline and description, return a satirical "
    "(title, description) pair that exaggerates the situation for comic "
    "effect while remaining recognizably about the same topic. "
    "Keep the title under 120 characters and the description to one short "
    "paragraph. Do not include offensive content, real names of private "
    "individuals, or factual claims that could be mistaken for news."
)


class SatiricalPair(BaseModel):
    title: str
    description: str


def _user_prompt(original_title: str, original_description: str) -> str:
    return (
        "Original title:\n"
        f"{original_title}\n\n"
        "Original description:\n"
        f"{original_description}\n\n"
        "Return a satirical title and description as JSON."
    )


async def generate_satirical(
    original_title: str,
    original_description: str,
) -> SatiricalPair:
    """Return a satirical (title, description) pair for the given article.

    When ``settings.openai_mock_mode`` is True, returns the canonical
    (MOCK_TITLE, MOCK_DESCRIPTION) pair without instantiating the OpenAI
    SDK or making any network request.

    Otherwise calls OpenAI with a structured-output (JSON-schema) request
    using ``settings.openai_model_transform``,
    ``settings.openai_temperature_transform``, and a per-request timeout
    of ``settings.openai_request_timeout_seconds`` seconds.

    Raises any OpenAI client / timeout / JSON / pydantic-validation
    exception. The caller (worker) is responsible for cleanup and logging
    per the failure-path contract.
    """
    if settings.openai_mock_mode:
        return SatiricalPair(title=MOCK_TITLE, description=MOCK_DESCRIPTION)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_request_timeout_seconds,
    )
    try:
        completion = await client.beta.chat.completions.parse(
            model=settings.openai_model_transform,
            temperature=settings.openai_temperature_transform,
            response_format=SatiricalPair,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _user_prompt(original_title, original_description),
                },
            ],
        )
        if not getattr(completion, "choices", None):
            raise ValueError("OpenAI returned no choices")
        message = completion.choices[0].message
        if getattr(message, "refusal", None) is not None or message.parsed is None:
            raise ValueError("OpenAI refused or returned no parsed payload")
        return message.parsed
    except Exception as exc:
        log.error(
            "openai_transform.failed model=%s exc_type=%s",
            settings.openai_model_transform,
            type(exc).__name__,
        )
        raise
