from typing import Literal

from pydantic import BaseModel, Field, field_validator

ETSY_MAX_TAGS = 13
ETSY_MAX_TAG_LENGTH = 20


class TagReplacement(BaseModel):
    remove: str
    add: str
    reason: str


ETSY_MAX_TITLE_LENGTH = 140
MAX_MISSING_TAGS = 5


class TitleAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    character_count: int
    primary_keyword_present: bool
    primary_keyword_position: Literal[
        "first_3_words", "first_half", "second_half", "absent"
    ]
    issues: list[str]
    optimized_title: str = Field(max_length=ETSY_MAX_TITLE_LENGTH)
    title_change_rationale: str

    @field_validator("optimized_title", mode="before")
    @classmethod
    def clamp_title(cls, value: object) -> object:
        # Don't fail the whole analysis over a slightly-too-long title.
        if isinstance(value, str) and len(value) > ETSY_MAX_TITLE_LENGTH:
            return value[:ETSY_MAX_TITLE_LENGTH].rstrip()
        return value


class TagsAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    current_tag_count: int
    unused_slots: int
    weak_tags: list[str]
    missing_high_value_tags: list[str] = Field(max_length=MAX_MISSING_TAGS)
    replacement_tags: list[TagReplacement]
    full_optimized_tag_set: list[str] = Field(max_length=ETSY_MAX_TAGS)

    @field_validator("full_optimized_tag_set", mode="before")
    @classmethod
    def clean_optimized_tags(cls, tags: object) -> object:
        # Etsy caps tags at 13 of ≤20 chars. The model only gets this as a hint,
        # so enforce it here by dropping offenders instead of failing the run.
        if not isinstance(tags, list):
            return tags
        cleaned: list[str] = []
        for tag in tags:
            if isinstance(tag, str):
                tag = tag.strip()
                if tag and len(tag) <= ETSY_MAX_TAG_LENGTH:
                    cleaned.append(tag)
        return cleaned[:ETSY_MAX_TAGS]

    @field_validator("missing_high_value_tags", mode="before")
    @classmethod
    def cap_missing_tags(cls, tags: object) -> object:
        if isinstance(tags, list):
            return [t for t in tags if isinstance(t, str)][:MAX_MISSING_TAGS]
        return tags


class DescriptionAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    keyword_density_ok: bool
    missing_sections: list[str]
    first_paragraph_optimized: bool
    recommended_additions: list[str]
    # Full ready-to-publish description rewritten per the recommendations.
    optimized_description: str = Field(min_length=1)


class SeoAnalysisResult(BaseModel):
    """Validated structured output of the SEO Analyzer (ai-agent-spec §3.1)."""

    overall_score: int = Field(ge=0, le=100)
    title_analysis: TitleAnalysis
    tags_analysis: TagsAnalysis
    description_analysis: DescriptionAnalysis
    priority: Literal["critical", "high", "medium", "low"]
    estimated_traffic_lift_percent: int
    competitor_gap_summary: str


class SeoApplyIn(BaseModel):
    """Which recommendation fields to turn into pending optimizations."""

    fields: list[Literal["title", "tags", "description"]] = Field(
        default=["title", "tags"], min_length=1
    )


class OptimizationRejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
