"""Bill vision parser — Stage A."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Final

import anthropic

from energia.config import settings
from energia.models import Bill, ParseResult

logger = logging.getLogger(__name__)

SUPPORTED_MEDIA_TYPES: Final = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

_BILL_EXTRACTION_PROMPT = """\
Você é um parser de contas de energia elétrica brasileiras. Analise a imagem da conta \
e extraia os dados no formato JSON abaixo. Retorne APENAS o objeto JSON, sem texto adicional.

{
  "distributor": "<nome da distribuidora>",
  "installation_number": "<número da UC / instalação>",
  "period": "<YYYY-MM>",
  "issue_date": "<YYYY-MM-DD>",
  "due_date": "<YYYY-MM-DD>",
  "consumption_kwh": "<consumo em kWh, decimal com ponto>",
  "tariff_group": "<grupo tarifário, ex: B1>",
  "modalidade": "<Convencional|Branca>",
  "bandeira": "<Verde|Amarela|Vermelha 1|Vermelha 2>",
  "total_brl": "<valor total em R$, decimal com ponto>",
  "composition": {
    "tusd": "<valor TUSD em R$>",
    "te": "<valor TE em R$>",
    "icms": "<valor ICMS em R$>"
  },
  "confidence": <0.0 a 1.0>
}

Se não conseguir ler algum campo com certeza, reduza o valor de confidence.\
"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class BillParseError(Exception):
    """Raised for all parse failures: invalid input, API error, or validation error."""


def parse_bill_image(image_bytes: bytes, media_type: str) -> ParseResult:
    if not image_bytes:
        raise BillParseError("image_bytes is empty")
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise BillParseError(f"unsupported media type: {media_type!r}")

    logger.info(
        "parsing bill image",
        extra={"media_type": media_type, "size_bytes": len(image_bytes)},
    )

    import base64

    encoded = base64.b64encode(image_bytes).decode()
    response = _call_with_one_retry(encoded, media_type)
    bill = _parse_response(response)

    needs_confirmation = bill.confidence < 0.85
    return ParseResult(bill=bill, needs_user_confirmation=needs_confirmation)


def _call_with_one_retry(encoded: str, media_type: str) -> Any:
    messages: list[Any] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded,
                    },
                },
                {"type": "text", "text": _BILL_EXTRACTION_PROMPT},
            ],
        }
    ]

    try:
        return _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            messages=messages,
        )
    except anthropic.APIStatusError as exc:
        if exc.response.status_code < 500:
            raise BillParseError(f"API error {exc.response.status_code}: {exc}") from exc
        logger.warning("5xx on first attempt, retrying once: %s", exc)
    except anthropic.APIError as exc:
        raise BillParseError(f"API error: {exc}") from exc

    try:
        return _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            messages=messages,
        )
    except anthropic.APIError as exc:
        raise BillParseError(f"API error on retry: {exc}") from exc


def _parse_response(response: Any) -> Bill:
    raw: str = response.content[0].text if response.content else ""

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise BillParseError(f"no JSON object found in API response: {raw[:200]!r}")

    try:
        data = json.loads(match.group())
        return Bill.model_validate(data)
    except Exception as exc:
        raise BillParseError(f"bill validation failed: {exc}") from exc
