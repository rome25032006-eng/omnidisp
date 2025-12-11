"""Helpers for loading the JSON knowledge base.

The loader keeps in-memory structures that mirror the target JSON schema
without requiring the files to be populated yet. As soon as JSON data is
added to ``knowledge/categories``, the dispatcher will start using it
without code changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from omnidisp.app.utils.text_normalizer import normalize_text


class JobInfo(TypedDict, total=False):
    """Service entry with optional pricing for future use.

    Fields mirror the expected JSON structure but stay optional to remain
    resilient to empty or partial data:

    - ``id``: internal code of the job.
    - ``title``: human-readable title for the master.
    - ``price_work_from``: minimal labour price.
    - ``price_parts_from``: minimal spare parts price.
    - ``notes``: free-form comments.
    """

    id: str
    title: str
    price_work_from: int
    price_parts_from: int
    notes: str


class SymptomInfo(TypedDict, total=False):
    """Typical problem description used for clarifying questions."""

    symptom: str
    example_phrases: List[str]
    clarify_question: str


class CategoryData(TypedDict, total=False):
    """Full category payload expected from JSON.

    - ``category``: machine-readable code (e.g. ``"fridge"``).
    - ``title``: human-friendly name.
    - ``keywords``: list of keywords to detect the category.
    - ``stop_phrases``: stop-factors specific to the category.
    - ``symptoms`` / ``common_issues``: lists of :class:`SymptomInfo`.
    - ``clarifying_questions``: fallback list of questions.
    - ``jobs``: list of :class:`JobInfo` with price ranges.
    """

    category: str
    title: str
    keywords: List[str]
    stop_phrases: List[str]
    symptoms: List[SymptomInfo]
    common_issues: List[SymptomInfo]
    clarifying_questions: List[str]
    jobs: List[JobInfo]


KNOWLEDGE_DATA: Dict[str, CategoryData] = {}
"""Category code -> full category dict."""

KEYWORD_TO_CATEGORY: Dict[str, str] = {}
"""Normalized keyword -> category code."""

FORBIDDEN_TASKS: List[str] = []
"""Global stop-phrases loaded from the knowledge base."""

_LOADED = False


def _load_category_file(path: Path) -> CategoryData:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError:
        raw_data = {}

    if not isinstance(raw_data, dict):
        return {}

    # Ensure we always work with a dict and leave absent fields empty.
    return raw_data  # type: ignore[return-value]


def load_knowledge(categories_dir: Optional[Path] = None) -> None:
    """Load category JSON files into in-memory structures.

    The loader tolerates empty ``{}`` files and missing fields so that the
    dispatcher can operate even before the knowledge base is filled.
    """

    global _LOADED
    KNOWLEDGE_DATA.clear()
    KEYWORD_TO_CATEGORY.clear()
    FORBIDDEN_TASKS.clear()

    base_dir = categories_dir or Path(__file__).resolve().parent / "categories"
    if not base_dir.exists():
        _LOADED = True
        return

    for path in sorted(base_dir.glob("*.json")):
        category_code = path.stem
        category_data = _load_category_file(path)
        KNOWLEDGE_DATA[category_code] = category_data

        keywords = category_data.get("keywords") or []
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                KEYWORD_TO_CATEGORY[normalize_text(keyword)] = category_code

        stop_phrases = category_data.get("stop_phrases") or []
        for phrase in stop_phrases:
            if isinstance(phrase, str) and phrase.strip():
                FORBIDDEN_TASKS.append(normalize_text(phrase))

    _LOADED = True


def _ensure_loaded() -> None:
    if not _LOADED:
        load_knowledge()


def find_recommend_question(category_code: str, tasks: List[str]) -> Optional[str]:
    """Pick a clarifying question for the detected category.

    The function first tries to match example phrases of symptoms/common
    issues against the provided tasks. If nothing matches, it falls back to
    the general ``clarifying_questions`` list.
    """

    _ensure_loaded()
    category = KNOWLEDGE_DATA.get(category_code) or {}

    normalized_tasks = [normalize_text(task) for task in tasks]
    symptom_entries = category.get("symptoms") or category.get("common_issues") or []
    for symptom in symptom_entries:
        examples = symptom.get("example_phrases") or []
        question = symptom.get("clarify_question")
        if not question:
            continue
        for example in examples:
            normalized_example = normalize_text(example)
            if any(normalized_example in task for task in normalized_tasks):
                return question

    questions = category.get("clarifying_questions") or []
    if questions:
        return questions[0]
    return None


def get_min_price(category_code: str) -> Optional[int]:
    """Return minimal labour price for the category if provided."""

    _ensure_loaded()
    category = KNOWLEDGE_DATA.get(category_code) or {}
    jobs = category.get("jobs") or []
    prices: List[int] = []
    for job in jobs:
        if "price_work_from" not in job:
            continue

        price_value = job.get("price_work_from")
        if isinstance(price_value, (int, float)):
            prices.append(int(price_value))
        elif isinstance(price_value, str) and price_value.strip().isdigit():
            prices.append(int(price_value.strip()))

    if not prices:
        return None
    return min(prices)
