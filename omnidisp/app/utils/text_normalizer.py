"""Utility helpers for normalizing client text."""


def normalize_text(text: str) -> str:
    """Lowercase text and unify characters for matching.

    The dispatcher relies on simple substring checks, so we only
    standardize basic casing and the ``ё`` letter to keep behavior
    predictable.
    """

    return text.lower().replace("ё", "е")
