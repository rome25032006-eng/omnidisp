from omnidisp.app.dispatcher.dispatcher_controller import handle_message


def test_handle_message_basic(monkeypatch):
    def fake_ask(self, prompt: str) -> str:  # noqa: ANN001
        return "Готов помочь, расскажите подробнее, что случилось."

    monkeypatch.setattr(
        "omnidisp.app.llm.llm_client.LLMClient.ask",
        fake_ask,
    )

    result = handle_message(
        "Здравствуйте, у меня сломалась стиралка",
        is_first_message=True,
    )

    assert "internal_trace" in result
    assert "client_answer" in result
    assert result["internal_trace"].startswith("INTERNAL TRACE:")
    assert "Здравствуйте" in result["client_answer"]
    assert result["client_answer"]
