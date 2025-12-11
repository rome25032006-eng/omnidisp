import json
from pathlib import Path

from omnidisp.app.knowledge import loader


def test_load_knowledge_with_keywords_and_prices(tmp_path):
    categories_dir = Path(tmp_path)
    sample_category = {
        "category": "fridge",
        "title": "Холодильник",
        "keywords": ["морозильник"],
        "stop_phrases": ["газовый холодильник"],
        "jobs": [
            {
                "id": "diagnostic",
                "title": "Диагностика",
                "price_work_min": 1800,
            }
        ],
        "clarifying_questions": ["Когда техника перестала холодить?"],
    }
    (categories_dir / "fridge.json").write_text(
        json.dumps(sample_category), encoding="utf-8"
    )

    loader.load_knowledge(categories_dir)

    assert loader.KNOWLEDGE_DATA["fridge"]["title"] == "Холодильник"
    assert loader.KEYWORD_TO_CATEGORY.get("морозильник") == "fridge"
    assert loader.FORBIDDEN_TASKS
    assert loader.get_min_price("fridge") == 1800
    assert loader.find_recommend_question("fridge", ["не холодит холодильник"])

    # restore default empty knowledge
    loader.load_knowledge()


def test_load_knowledge_handles_empty_files(tmp_path):
    categories_dir = Path(tmp_path)
    (categories_dir / "washing_machine.json").write_text("{}", encoding="utf-8")

    loader.load_knowledge(categories_dir)

    assert "washing_machine" in loader.KNOWLEDGE_DATA
    assert loader.KEYWORD_TO_CATEGORY == {}
    assert loader.get_min_price("washing_machine") is None

    loader.load_knowledge()
