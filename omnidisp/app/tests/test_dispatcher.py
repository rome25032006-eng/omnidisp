import re

from omnidisp.app.dispatcher.dispatcher_controller import handle_message


def test_handle_message_basic(monkeypatch):
    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return "Готов помочь, опишите, пожалуйста, проблему подробнее."

    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Здравствуйте, сломалась стиральная машина, не отжимает",
        is_first_message=True,
    )

    assert "internal_trace" in result
    assert "client_answer" in result
    trace = result["internal_trace"]
    answer = result["client_answer"]

    assert trace.startswith("INTERNAL TRACE:")
    assert "Категория" in trace
    assert "Результат: разрешено" in trace
    assert "стирал" in trace.lower() or "washing_machine" in trace
    assert "Здравствуйте" in answer
    assert not re.search(r"\d", answer)


def test_handle_message_full_refuse(monkeypatch):
    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return "Здравствуйте. К сожалению, люстрами я не занимаюсь."

    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Здравствуйте, сколько стоит ремонт люстры?",
        is_first_message=True,
    )

    trace = result["internal_trace"]
    answer = result["client_answer"]

    assert "полный отказ" in trace
    assert "такими работами" in answer or "люстрами" in answer
    assert not re.search(r"\d", answer)


def test_handle_message_partial_refuse(monkeypatch):
    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return (
            "По люстре помочь не смогу, а розетку могу посмотреть. "
            "Опишите, пожалуйста, подробнее, что нужно сделать с розеткой."
        )

    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Нужно починить люстру и заменить розетку в комнате",
        is_first_message=False,
    )

    trace = result["internal_trace"]
    answer = result["client_answer"]

    assert "частичный отказ" in trace
    assert "люстр" in trace.lower()  # упоминаются запрещённые задачи
    assert "розет" in trace.lower()  # и разрешённые
    assert "част" in answer.lower() or "по люстре" in answer.lower()
    assert not re.search(r"\d", answer)


def test_handle_message_price_question_no_digits(monkeypatch):
    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return "Могу подъехать, обычно такая работа стоит 1500 рублей."

    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Здравствуйте, сколько стоит ремонт стиральной машины?",
        is_first_message=True,
    )

    answer = result["client_answer"]

    assert not re.search(r"\d", answer)
    assert "стоимость" in answer.lower() or "цен" in answer.lower()


def test_handle_message_second_price_with_min_price(monkeypatch):
    def fake_min_price(category: str) -> int | None:  # noqa: ANN001
        return 2500

    def fail_ask(self, prompt: str) -> str:  # noqa: ANN001
        raise AssertionError("LLM should not be called when price known")

    monkeypatch.setattr(
        "omnidisp.app.dispatcher.disp_logic.get_min_price",
        fake_min_price,
    )
    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fail_ask,
    )

    result = handle_message(
        "Сколько стоит ремонт стиральной машины?",
        is_first_message=False,
    )

    answer = result["client_answer"]

    assert "от 2500" in answer
    assert re.search(r"\d", answer)
    assert "диагност" in answer.lower() or "осмотр" in answer.lower()


def test_handle_message_second_price_without_min_price(monkeypatch):
    def fake_min_price(category: str) -> int | None:  # noqa: ANN001
        return None

    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return "Обычно выходит 2000, но надо посмотреть на месте."

    monkeypatch.setattr(
        "omnidisp.app.dispatcher.disp_logic.get_min_price",
        fake_min_price,
    )
    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Сколько стоит ремонт стиральной машины?",
        is_first_message=False,
    )

    answer = result["client_answer"]

    assert not re.search(r"\d", answer)
    assert "осмотр" in answer.lower() or "диагност" in answer.lower()
