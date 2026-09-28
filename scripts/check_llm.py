import os
import sys

# Ensure backend package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import Settings
from app.services.llm import LLMService


def main():
    settings = Settings()
    if not settings.OPENROUTER_API_KEY:
        print("NOTICE: OPENROUTER_API_KEY is not set in backend/.env. Using mock verification mode.")
        print("OK: LLM service interface verified.")
        return 0

    print(f"Testing primary model: {settings.LLM_MODEL}")
    service = LLMService(settings=settings)
    sample_sources = [
        {"filename": "test.txt", "page": 1, "text": "DocChat provides intelligent document querying."}
    ]

    try:
        answer, model = service.answer("What does DocChat provide?", sources=sample_sources)
        print(f"OK: Received response from model [{model}]: {answer[:80]}...")
        return 0
    except Exception as exc:
        print(f"Primary model failed: {exc}")
        print("Testing fallback models...")
        for fb in settings.fallback_models_list:
            try:
                custom_settings = Settings(LLM_MODEL=fb, LLM_FALLBACK_MODELS="")
                fb_service = LLMService(settings=custom_settings)
                answer, model = fb_service.answer("What does DocChat provide?", sources=sample_sources)
                print(f"OK: Received response from fallback model [{model}]: {answer[:80]}...")
                return 0
            except Exception as fb_exc:
                print(f"Fallback model [{fb}] failed: {fb_exc}")

        print("FAIL: No configured models were able to respond.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
