"""Pydantic schemas that validate every AI output before it is stored or published."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Dashboard topical categories (the "press" tab is derived from source type, not AI output)
CATEGORIES = [
    "jde_peets", "kdp_impact", "competitors_direct", "competitors_adjacent",
    "legislation", "draft_legislation", "case_law_investigations", "eu_communications",
    "supply_chain", "sustainability", "consumers_marketing_competition", "tech_data_ai",
]

Category = Literal[
    "jde_peets", "kdp_impact", "competitors_direct", "competitors_adjacent",
    "legislation", "draft_legislation", "case_law_investigations", "eu_communications",
    "supply_chain", "sustainability", "consumers_marketing_competition", "tech_data_ai",
]

Confidence = Literal[
    "confirmed_fact", "company_statement", "third_party_claim",
    "analysis", "inference", "unconfirmed",
]


class AnalyzedItem(BaseModel):
    item_id: int
    relevant: bool
    relevance: float = Field(ge=0.0, le=1.0)
    title_en: str = ""
    summary_en: str = ""
    category: Category | None = None
    categories: list[Category] = []
    countries: list[str] = []
    entities: list[str] = []
    brands: list[str] = []
    impact: Literal["high", "medium", "low"] = "low"
    horizon: Literal["immediate", "short_term", "medium_term", "long_term"] = "short_term"
    confidence: Confidence = "unconfirmed"
    keywords: list[str] = []

    @field_validator("countries")
    @classmethod
    def _upper_iso(cls, v: list[str]) -> list[str]:
        return [c.strip().upper()[:3] for c in v if c.strip()]

    @field_validator("summary_en")
    @classmethod
    def _max_two_paragraphs(cls, v: str) -> str:
        paras = [p for p in v.split("\n\n") if p.strip()]
        return "\n\n".join(paras[:2])


class BatchResult(BaseModel):
    items: list[AnalyzedItem]
