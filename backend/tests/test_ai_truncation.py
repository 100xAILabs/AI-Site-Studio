import pytest

from app.services.ai_service import AIService
from app.services.studio_service import _enforce_single_page_navigation, _site_reference_issues


class _Response:
    status_code = 200

    def json(self):
        return {
            "candidates": [{
                "content": {"parts": [{"text": '{"partial":'}]},
                "finishReason": "MAX_TOKENS",
            }]
        }


class _Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        return _Response()


@pytest.mark.asyncio
async def test_gemini_max_tokens_is_not_returned_as_success(monkeypatch):
    import sys
    import httpx

    ai_mod = sys.modules.get("app.services.ai_service")
    if not ai_mod or not hasattr(ai_mod, "_GEMINI_FALLBACK_MODELS"):
        import importlib
        ai_mod = importlib.import_module("app.services.ai_service")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr(AIService, "_gemini_api_keys", staticmethod(lambda: ["test-key"]))
    if hasattr(ai_mod, "_GEMINI_FALLBACK_MODELS"):
        monkeypatch.setattr(ai_mod, "_GEMINI_FALLBACK_MODELS", [])
    if hasattr(ai_mod, "_gemini_model_cooldowns"):
        monkeypatch.setattr(ai_mod, "_gemini_model_cooldowns", {})

    result = await AIService()._call_gemini_api("prompt", "test-model", "application/json")

    assert result is None


def test_single_page_links_become_matching_section_anchors():
    pages = {
        "index.html": '''<html><body><nav><a href="about.html">About</a>
        <a href="projects.html">Selected Projects</a><a href="contact.html">Contact</a></nav>
        <main><section><h2>About Me</h2></section><section><h2>Selected Projects</h2></section>
        <section><h2>Contact</h2></section></main></body></html>'''
    }

    result = _enforce_single_page_navigation(pages)

    assert 'href="#about"' in result["index.html"]
    assert 'href="#projects"' in result["index.html"]
    assert 'href="#contact"' in result["index.html"]
    assert not _site_reference_issues(result, set())
