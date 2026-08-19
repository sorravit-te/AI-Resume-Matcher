"""Deterministic Thai overall score rationale from scored results and job rubric."""

from __future__ import annotations

from decimal import Decimal

from app.models.job_definition import JobDefinition
from app.models.resume_score import CriterionScore, ResumeScore

_MAX_SUPPORTING = 3
_MAX_LIMITING = 3
_MIN_SUPPORTING_EFFECTIVE_RATING = 3
_DISCLAIMER = (
    "คะแนนนี้สะท้อนความสอดคล้องของหลักฐานในเรซูเม่กับ JD เท่านั้น "
    "ไม่ใช่การตัดสินรับหรือไม่รับเข้าทำงาน"
)


def build_overall_rationale(
    score: ResumeScore,
    job: JobDefinition,
) -> str:
    """Build a deterministic Thai rationale explaining the overall JD Match Score.

    Uses only the already-scored data in ``score`` and display names from
    ``job``.  No Gemini call.  No resume text.  No criterion rationale text.
    """

    criterion_display = _criterion_display_names(job)
    category_display = _category_display_names(job)

    parts: list[str] = []

    # --- A. Score composition ---
    parts.append(_score_composition(score, category_display))

    # --- B. Main score-supporting criteria ---
    supporting_text = _supporting_criteria_text(score, criterion_display)
    if supporting_text:
        parts.append(supporting_text)

    # --- C. Main score-limiting criteria ---
    limiting_text = _limiting_criteria_text(score, criterion_display)
    if limiting_text:
        parts.append(limiting_text)

    # --- Disclaimer ---
    parts.append(_DISCLAIMER)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _criterion_display_names(job: JobDefinition) -> dict[str, str]:
    """Map criterion ID -> display name from the authoritative job rubric."""

    return {criterion.id: criterion.name for criterion in job.criteria}


def _category_display_names(job: JobDefinition) -> dict[str, str]:
    """Map category ID -> display name from the authoritative job rubric."""

    return {category.id: category.name for category in job.categories}


def _format_score(value: Decimal) -> str:
    """Format a Decimal score as a compact number string."""

    float_value = float(value)
    rounded = round(float_value * 100) / 100
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def _score_composition(
    score: ResumeScore,
    category_display: dict[str, str],
) -> str:
    """Part A: explain how the overall score is composed from categories."""

    category_parts: list[str] = []
    for cat_score in score.category_scores:
        display_name = category_display.get(cat_score.category, cat_score.category)
        category_parts.append(
            f"{display_name} {_format_score(cat_score.score)}/{_format_score(cat_score.max_score)}"
        )

    joined = _thai_join(category_parts)
    return (
        f"{score.score_name} {_format_score(score.overall_score)}"
        f"/{_format_score(score.maximum_score)} มาจาก {joined}"
    )


def _supporting_criteria_text(
    score: ResumeScore,
    criterion_display: dict[str, str],
) -> str:
    """Part B: identify criteria with meaningful evidence contribution."""

    candidates = [
        cs for cs in score.criterion_scores
        if cs.effective_rating >= _MIN_SUPPORTING_EFFECTIVE_RATING
    ]

    if not candidates:
        # Edge case A: no criteria reach the threshold
        return (
            "โดยหลักฐานที่พบกระจายอยู่ในหลายเกณฑ์ "
            "แต่ยังไม่มีเกณฑ์ที่มี effective rating ตั้งแต่ 3 ขึ้นไป"
        )

    # Deterministic ranking: higher score contribution first, then higher
    # weight, then rubric order (stable index from criterion_scores list)
    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda pair: (-pair[1].score, -pair[1].weight, pair[0]))
    top = [cs for _, cs in indexed[:_MAX_SUPPORTING]]
    names = [criterion_display.get(cs.criterion_id, cs.criterion_id) for cs in top]

    return (
        "โดยพบหลักฐานที่สนับสนุนคะแนนอย่างชัดเจนใน "
        + _thai_join(names)
    )


def _limiting_criteria_text(
    score: ResumeScore,
    criterion_display: dict[str, str],
) -> str:
    """Part C: identify criteria responsible for missing points."""

    is_perfect = all(
        cs.score == cs.max_score for cs in score.criterion_scores
    )
    if is_perfect:
        # Edge case C: perfect score – no limitations
        return "โดยหลักฐานสนับสนุนเกณฑ์ที่ประเมินทุกเกณฑ์อย่างครบถ้วน"

    is_zero = score.overall_score == Decimal("0")
    if is_zero:
        # Edge case D: zero score
        return (
            "ขณะที่ยังไม่พบหลักฐานเพียงพอในเกณฑ์ที่ประเมินทั้งหมด "
            "ทั้งนี้การไม่พบหลักฐานไม่ได้หมายความว่าผู้สมัครไม่มีความสามารถดังกล่าว"
        )

    # Split into zero-evidence and low-evidence groups
    zero_criteria: list[tuple[int, CriterionScore]] = []
    low_criteria: list[tuple[int, CriterionScore]] = []
    high_but_incomplete = False

    for idx, cs in enumerate(score.criterion_scores):
        lost = cs.max_score - cs.score
        if lost <= Decimal("0"):
            continue
        if cs.effective_rating == 0:
            zero_criteria.append((idx, cs))
        elif cs.effective_rating in (1, 2):
            low_criteria.append((idx, cs))
        else:
            high_but_incomplete = True

    # Sort each group by lost_score desc, then rubric order asc
    zero_criteria.sort(key=lambda pair: (-(pair[1].max_score - pair[1].score), pair[0]))
    low_criteria.sort(key=lambda pair: (-(pair[1].max_score - pair[1].score), pair[0]))

    if not zero_criteria and not low_criteria:
        if high_but_incomplete:
            return "เกณฑ์ที่มีคะแนนไม่เต็มยังมีหลักฐานสนับสนุนที่ชัดเจน แต่ยังไม่ถึงระดับสูงสุดตาม rubric"
        # Edge case B: all criteria have full score (redundant with is_perfect above)
        return "โดยหลักฐานสนับสนุนเกณฑ์ที่ประเมินทุกเกณฑ์อย่างครบถ้วน"

    # Allocate slots: zero-evidence first, then low-evidence, total bounded
    clauses: list[str] = []
    remaining_slots = _MAX_LIMITING

    if zero_criteria and remaining_slots > 0:
        selected_zero = zero_criteria[:remaining_slots]
        remaining_slots -= len(selected_zero)
        names = [
            criterion_display.get(cs.criterion_id, cs.criterion_id)
            for _, cs in selected_zero
        ]
        clauses.append(
            "ขณะที่คะแนนถูกจำกัดจากเกณฑ์ที่ยังไม่พบหลักฐานเพียงพอ เช่น "
            + _thai_join(names)
        )

    if low_criteria and remaining_slots > 0:
        selected_low = low_criteria[:remaining_slots]
        names = [
            criterion_display.get(cs.criterion_id, cs.criterion_id)
            for _, cs in selected_low
        ]
        clauses.append(
            "รวมถึงบางเกณฑ์ที่มีหลักฐานในระดับจำกัด เช่น "
            + _thai_join(names)
        )

    return " ".join(clauses)


def _thai_join(items: list[str]) -> str:
    """Join items with Thai comma and conjunction."""

    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " และ " + items[-1]
