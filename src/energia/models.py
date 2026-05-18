"""Pydantic models for energia — Bill and BillComposition."""
from datetime import date
from decimal import Decimal
from typing import Annotated, TypeAlias

from pydantic import BaseModel, Field, StringConstraints

PeriodStr: TypeAlias = Annotated[
    str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
]


class BillComposition(BaseModel):
    """Breakdown of a bill's R$ total into regulatory components."""

    tusd: Decimal = Field(description="Tarifa de Uso do Sistema de Distribuição (R$)")
    te: Decimal = Field(description="Tarifa de Energia (R$)")
    icms: Decimal = Field(description="ICMS state tax (R$)")
    pis: Decimal | None = Field(default=None, description="PIS federal tax (R$)")
    cofins: Decimal | None = Field(default=None, description="COFINS federal tax (R$)")
    cosip: Decimal | None = Field(
        default=None, description="Public lighting contribution (R$)"
    )
    bandeira_surcharge: Decimal | None = Field(
        default=None, description="Bandeira tarifária surcharge (R$)"
    )
    other: Decimal = Field(default=Decimal("0"), description="Anything else not classified")


class Bill(BaseModel):
    """A single monthly energy bill."""

    distributor: str = Field(description="Distribuidora name, e.g. 'Enel Rio'")
    installation_number: str = Field(description="Número da instalação / UC")
    period: PeriodStr = Field(description="YYYY-MM reference month")
    issue_date: date = Field(description="Data de emissão")
    due_date: date = Field(description="Data de vencimento")
    consumption_kwh: Decimal = Field(description="Total kWh consumed in period")
    tariff_group: str = Field(description="B1, B2, B3, etc.")
    modalidade: str = Field(description="Convencional or Branca")
    bandeira: str | None = Field(
        default=None,
        description="Verde, Amarela, Vermelha 1, Vermelha 2, or null",
    )
    total_brl: Decimal = Field(description="Total R$ to pay")
    composition: BillComposition
    confidence: float = Field(ge=0, le=1, description="Vision extraction confidence, 0-1")


class ParseResult(BaseModel):
    """Wraps a parsed Bill with its workflow flag.

    needs_user_confirmation is True when any extracted field's confidence < 0.85;
    the chatbot orchestrator must check this flag before consuming bill data in a
    tool call.
    """

    bill: Bill
    needs_user_confirmation: bool
