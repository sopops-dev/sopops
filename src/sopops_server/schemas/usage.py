"""Model spend: tokens and estimated cost of model calls, by purpose, model and day. And calls: sessions received, by day."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from .base import BaseModel

Purpose = Literal["route", "check", "review", "cluster", "theme", "suggestion", "calibrate", "onboarding"]


class SpendTotals(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float = Field(description="Estimated from the price table in use (USD); calls to a model without a price add nothing.")
    unpriced_calls: int = Field(description="Calls to a model with no price: their tokens count, their cost doesn't.")


class PurposeSpend(SpendTotals):
    purpose: Purpose


class ModelSpend(SpendTotals):
    model: str


class DaySpend(SpendTotals):
    day: date = Field(description="A UTC day.")


class UsageResponse(BaseModel):
    start: datetime
    end: datetime
    total: SpendTotals
    by_purpose: list[PurposeSpend] = Field(description="route, check, review (the reviewer on flagged rules), cluster (assigning findings, splitting and naming "
                                           "patterns), theme, suggestion, calibrate, onboarding. Largest cost first.")
    by_model: list[ModelSpend]
    sessions: int = Field(description="Sessions with a model call about them in the window.")
    per_session_usd: float | None = Field(description="The cost of calls about a session (routing, checks, review, assigning its findings), per session.")
    daily: list[DaySpend] = Field(description="Every UTC day of the window, empty ones included.")


class ModelPrice(BaseModel):
    model: str = Field(description="Matches a model string without its provider, or as a prefix (a dated snapshot).")
    input_per_m: float = Field(description="USD per million input tokens.")
    output_per_m: float = Field(description="USD per million output tokens.")
    source: Literal["default", "env"]


class RolePrice(BaseModel):
    role: Literal["fast", "reasoning", "decide"]
    model: str | None = Field(description="Null when no model is configured for it.")
    input_per_m: float | None = Field(description="Null when the model has no price.")
    output_per_m: float | None


class PricesResponse(BaseModel):
    prices: list[ModelPrice]
    roles: list[RolePrice] = Field(description="The models in use, and the price each gets.")
    env: str = Field(description="The variable that overrides or extends the table: JSON, {\"model\": [input, output]}.")


class FeaturesOut(BaseModel):
    features: list[str] = Field(description="Features this server adds beyond open-source sopops, turned on by its extensions: `fine_tune` on hosted sopops.")


class NoticeOut(BaseModel):
    id: str = Field(description="Stable: the UI remembers a dismissal by it.")
    level: Literal["info", "warning", "blocking"] = Field(description="`info` and `warning`: a banner; `blocking`: a dialog, a warning banner once closed.")
    title: str
    body: str
    action_label: str | None = None
    action_url: str | None = Field(None, description="Opened in a new tab.")


class SettingsRowOut(BaseModel):
    label: str
    value: str
    used: float | None = Field(None, description="With `limit`: a progress bar, used of limit.")
    limit: float | None = None
    note: str | None = None


class SettingsActionOut(BaseModel):
    label: str
    url: str = Field(description="Opened in a new tab.")
    kind: Literal["primary", "secondary"] = "secondary"


class SettingsSectionOut(BaseModel):
    id: str = Field(description="The page's path under Settings: /settings/<id>.")
    title: str
    rows: list[SettingsRowOut]
    actions: list[SettingsActionOut]
    description: str | None = None
    note: str | None = None
    icon: Literal["card", "gauge", "info", "shield"] | None = None


class SettingsSectionsOut(BaseModel):
    sections: list[SettingsSectionOut] = Field(description="From this server's extensions; none on open-source sopops.")


class NoticesOut(BaseModel):
    notices: list[NoticeOut] = Field(description="From this server's extensions; none on open-source sopops.")


class DayCalls(BaseModel):
    day: date = Field(description="A UTC day.")
    calls: int


class CallsResponse(BaseModel):
    start: datetime
    end: datetime = Field(description="Exclusive.")
    calls: int = Field(description="Sessions received in full (posted whole, or streamed and closed) that started in [start, end).")
    daily: list[DayCalls] = Field(description="Every UTC day of the period, empty ones included.")
