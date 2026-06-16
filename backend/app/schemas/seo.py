from typing import Literal

from pydantic import BaseModel, Field, field_validator

ETSY_MAX_TAGS = 13
ETSY_MAX_TAG_LENGTH = 20


class TagReplacement(BaseModel):
    remove: str
    add: str
    reason: str


class TitleAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    character_count: int
    primary_keyword_present: bool
    primary_keyword_position: Literal[
        "first_3_words", "first_half", "second_half", "absent"
    ]
    issues: list[str]
    optimized_title: str = Field(max_length=140)
    title_change_rationale: str


class TagsAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    current_tag_count: int
    unused_slots: int
    weak_tags: list[str]
    missing_high_value_tags: list[str] = Field(max_length=5)
    replacement_tags: list[TagReplacement]
    full_optimized_tag_set: list[str] = Field(max_length=ETSY_MAX_TAGS)

    @field_validator("full_optimized_tag_set")
    @classmethod
    def tags_within_etsy_limit(cls, tags: list[str]) -> list[str]:
        too_long = [t for t in tags if len(t) > ETSY_MAX_TAG_LENGTH]
        if too_long:
            raise ValueError(
                f"tags exceed Etsy's {ETSY_MAX_TAG_LENGTH}-char limit: {too_long}"
            )
        return tags


class DescriptionAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    keyword_density_ok: bool
    missing_sections: list[str]
    first_paragraph_optimized: bool
    recommended_additions: list[str]
    # Full ready-to-publish description rewritten per the recommendations.
    optimized_description: str = Field(min_length=1)


ETSY_MAX_ALT_TEXT_LENGTH = 250


class ImageAltSuggestion(BaseModel):
    """A suggested ALT text for one listing photo (by position)."""

    image_index: int = Field(ge=0)
    current_alt: str
    suggested_alt: str = Field(max_length=ETSY_MAX_ALT_TEXT_LENGTH)
    issue: str


class ImageAltAnalysis(BaseModel):
    score: int = Field(ge=0, le=100)
    images_with_alt: int = Field(ge=0)
    images_total: int = Field(ge=0)
    suggestions: list[ImageAltSuggestion]


class SeoAnalysisResult(BaseModel):
    """Validated structured output of the SEO Analyzer (ai-agent-spec §3.1)."""

    overall_score: int = Field(ge=0, le=100)
    title_analysis: TitleAnalysis
    tags_analysis: TagsAnalysis
    description_analysis: DescriptionAnalysis
    image_alt_analysis: ImageAltAnalysis
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
