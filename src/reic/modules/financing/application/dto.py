"""Input DTOs. Every ``*_pct`` field is a fraction: 0.10 means 10 percent."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallmentTerms(_Input):
    down_payment_pct: Decimal = Field(allow_inf_nan=False)
    years: int
    frequency: Literal["monthly", "quarterly", "semiannual", "annual"] = "quarterly"
    delivery_payment_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)
    delivery_month: int = 0
    maintenance_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)
    annual_escalation_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)


class InstallmentScheduleInput(InstallmentTerms):
    price_egp: Decimal = Field(allow_inf_nan=False)
    cash_discount_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)


class MortgageTerms(_Input):
    down_payment_pct: Decimal = Field(allow_inf_nan=False)
    annual_rate_pct: Decimal = Field(allow_inf_nan=False)
    years: int
    rate_type: Literal["fixed"] = "fixed"


class MortgageScheduleInput(MortgageTerms):
    price_egp: Decimal = Field(allow_inf_nan=False)


class NamedInstallmentTerms(InstallmentTerms):
    label: str


class NamedMortgageTerms(MortgageTerms):
    label: str


class CompareFinancingInput(_Input):
    price_egp: Decimal = Field(allow_inf_nan=False)
    discount_rate_pct: Decimal = Field(
        allow_inf_nan=False,
        description="Annual discount rate as a fraction, chosen by the caller (e.g. 0.20).",
    )
    cash_discount_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)
    installment_plans: list[NamedInstallmentTerms] = Field(default_factory=list)
    mortgages: list[NamedMortgageTerms] = Field(default_factory=list)
