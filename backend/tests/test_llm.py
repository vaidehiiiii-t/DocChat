from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.errors import AppError
from app.services.llm import SYSTEM_PROMPT, LLMService


def test_strip_reasoning_tokens():
    text_with_think = "<think>The user wants to know about stars. Let's find astronomy data.</think>Stars shine brightly."
    cleaned = LLMService.strip_reasoning_tokens(text_with_think)
    assert cleaned == "Stars shine brightly."

    clean_text = "Direct answer without reasoning tokens."
    assert LLMService.strip_reasoning_tokens(clean_text) == clean_text


def test_format_context_prompt():
    sources = [
        {"filename": "report.pdf", "page": 4, "text": "Financial growth reached 15%."},
        {"filename": "notes.txt", "page": 1, "text": "Customer satisfaction at all-time high."},
    ]
    prompt = LLMService.format_context_prompt(sources, "What was the growth?")
    assert "[1] (report.pdf, page 4)\nFinancial growth reached 15%." in prompt
    assert "[2] (notes.txt, page 1)\nCustomer satisfaction at all-time high." in prompt
    assert "Question: What was the growth?" in prompt


def test_non_free_model_rejection():
    settings = Settings(ALLOW_PAID_MODELS=False, LLM_MODEL="openai/gpt-4o")
    with pytest.raises(ValueError, match="Non-free model"):
        LLMService(settings=settings)


def test_answer_generation_and_history_formatting():
    fake_client = MagicMock()
    mock_choice = SimpleNamespace(
        message=SimpleNamespace(content="<think>Analysis</think>Growth was 15% as shown in [1].")
    )
    fake_client.chat.completions.create.return_value = SimpleNamespace(choices=[mock_choice])

    settings = Settings(
        ALLOW_PAID_MODELS=True,
        LLM_MODEL="mock-model",
        HISTORY_TURNS=2,
    )
    service = LLMService(client=fake_client, settings=settings)

    sources = [{"filename": "doc.pdf", "page": 1, "text": "Growth was 15%."}]
    history = [
        {"role": "user", "content": "Old question 1"},
        {"role": "assistant", "content": "Old answer 1"},
        {"role": "user", "content": "Recent question"},
        {"role": "assistant", "content": "Recent answer"},
    ]

    answer, model = service.answer("What was growth?", sources=sources, history=history)
    assert answer == "Growth was 15% as shown in [1]."
    assert model == "mock-model"

    # Verify calls
    call_args = fake_client.chat.completions.create.call_args[1]
    sent_messages = call_args["messages"]

    # System prompt is first
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[0]["content"] == SYSTEM_PROMPT

    # History truncated to last 2 turns
    assert sent_messages[1]["role"] == "user"
    assert sent_messages[1]["content"] == "Recent question"
    assert sent_messages[2]["role"] == "assistant"
    assert sent_messages[2]["content"] == "Recent answer"

    # User turn with context is last
    assert sent_messages[3]["role"] == "user"
    assert "Context excerpts:" in sent_messages[3]["content"]


def test_answer_fallback_on_404():
    fake_client = MagicMock()
    # First call fails with 404, second call (fallback model) succeeds
    mock_choice = SimpleNamespace(message=SimpleNamespace(content="Answer from fallback model."))
    fake_client.chat.completions.create.side_effect = [
        Exception("Error 404: Model not found"),
        SimpleNamespace(choices=[mock_choice]),
    ]

    settings = Settings(
        ALLOW_PAID_MODELS=True,
        LLM_MODEL="primary:free",
        LLM_FALLBACK_MODELS="fallback:free",
        LLM_MAX_RETRIES=1,
    )
    service = LLMService(client=fake_client, settings=settings)

    answer, model = service.answer("Hello", sources=[])
    assert answer == "Answer from fallback model."
    assert model == "fallback:free"


def test_global_rate_limiting():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))]
    )

    settings = Settings(ALLOW_PAID_MODELS=True, LLM_MODEL="free:free", LLM_GLOBAL_RPM=3)
    service = LLMService(client=fake_client, settings=settings)

    # First 3 calls succeed
    service.answer("q1", [])
    service.answer("q2", [])
    service.answer("q3", [])

    # 4th call should be blocked with 429
    with pytest.raises(AppError) as exc_info:
        service.answer("q4", [])
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RATE_LIMITED"


def test_answer_retry_transient_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    fake_client = MagicMock()
    call_count = 0

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("500 Internal Server Error")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Recovered answer"))]
        )

    fake_client.chat.completions.create.side_effect = mock_create
    settings = Settings(
        ALLOW_PAID_MODELS=True,
        LLM_MODEL="primary:free",
        LLM_FALLBACK_MODELS="",
        LLM_MAX_RETRIES=2,
    )
    service = LLMService(client=fake_client, settings=settings)
    answer, model = service.answer("Question", sources=[])
    assert answer == "Recovered answer"
    assert call_count == 2


def test_answer_exhausts_retries_raises_503(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = Exception("503 Service Unavailable")

    settings = Settings(
        ALLOW_PAID_MODELS=True,
        LLM_MODEL="primary:free",
        LLM_FALLBACK_MODELS="",
        LLM_MAX_RETRIES=2,
    )
    service = LLMService(client=fake_client, settings=settings)

    with pytest.raises(AppError) as exc_info:
        service.answer("Question", sources=[])
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "LLM_UNAVAILABLE"


def test_stream_answer_chunks_in_order_and_think_suppressed():
    def fake_stream_generator():
        chunks = [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="<think>I need "))]
            ),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="to think "))]),
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="carefully</think>"))]
            ),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello "))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="world! "))]),
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="This is streamed."))]
            ),
        ]
        for c in chunks:
            yield c

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_stream_generator()

    settings = Settings(ALLOW_PAID_MODELS=True, LLM_MODEL="stream-model:free")
    service = LLMService(client=fake_client, settings=settings)

    token_stream = service.stream_answer("Hi", sources=[])
    tokens = list(token_stream)

    # Verify <think> tokens suppressed
    full_text = "".join(tokens)
    assert "<think>" not in full_text
    assert "think carefully" not in full_text
    assert "Hello world! This is streamed." in full_text
    assert service.last_stream_model == "stream-model:free"
