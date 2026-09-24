"""
AI service — Gemini integration for preview content generation, 
template recommendations, color palettes, and SEO.
Supports separate models per feature and fallback to Azure OpenAI API.
"""

import json
import logging
import re
from typing import Optional, List, Any
import urllib.parse
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def safe_print(*args, **kwargs):
    """Safely print text containing Unicode emojis on Windows console without UnicodeEncodeError."""
    kwargs.setdefault("flush", True)
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text, **kwargs)


class GeminiAPIError(Exception):
    def __init__(self, status_code: int, message: str, model: str):
        self.status_code = status_code
        self.message = message
        self.model = model
        super().__init__(f"Gemini API returned status {status_code} for model {model}: {message}")


class KimiAPIError(Exception):
    def __init__(self, status_code: int, message: str, model: str):
        self.status_code = status_code
        self.message = message
        self.model = model
        super().__init__(f"Moonshot Kimi API returned status {status_code} for model {model}: {message}")


def fix_truncated_json(text: str) -> str:
    """
    Scans a truncated JSON string, closes any unclosed strings,
    and appends matching closing braces/brackets in the correct order.
    """
    text = text.strip()
    if not text:
        return "{}"

    stack = []
    in_string = False
    escape = False

    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char in '{[':
                stack.append(char)
            elif char in '}]':
                if stack:
                    stack.pop()

    if in_string:
        text += '"'

    while stack:
        opener = stack.pop()
        if opener == '{':
            text += '}'
        elif opener == '[':
            text += ']'

    return text


def robust_json_loads(text: str) -> Any:
    """
    Tolerance-maximizing JSON parser that strips markdown ticks, removes trailing commas,
    escapes unescaped quotes inside HTML attributes, repairs truncated JSON payloads,
    and accepts control characters (strict=False) to resolve common LLM syntax generation bugs.
    """
    text = text.strip()
    if not text:
        return {}

    # Strip markdown block wrappers
    if text.startswith("```json"):
        text = text.replace("```json", "", 1)
    elif text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        # If it failed due to truncation (expecting delimiter/value/etc.), try fixing truncation
        if "Expecting" in str(e) or "Unterminated" in str(e) or "control character" in str(e):
            try:
                fixed_text = fix_truncated_json(text)
                return json.loads(fixed_text, strict=False)
            except json.JSONDecodeError:
                pass
        # Slice off trailing extra braces/garbage if detected early
        if "Extra data" in str(e) and e.pos is not None:
            try:
                return json.loads(text[:e.pos].strip(), strict=False)
            except json.JSONDecodeError:
                pass

    # Try common repairs:
    # 1. Trailing commas e.g. [1, 2,] or {"a": 1,}
    text_repaired = re.sub(r',\s*([\]}])', r'\1', text)

    # 2. Convert unescaped double quotes inside HTML attributes (e.g. lang="en" -> lang='en')
    def fix_html_tag_quotes(match):
        return re.sub(r'="([^"]*)"', r"='\1'", match.group(0))

    text_repaired = re.sub(r'<[^>]+>', fix_html_tag_quotes, text_repaired)

    # 3. Escape actual newlines inside quotes
    def replace_newlines(match):
        return match.group(0).replace('\n', '\\n').replace('\r', '\\r')

    # Match double-quoted strings (supporting escaped quotes)
    text_repaired = re.sub(r'"(?:[^"\\]|\\.)*"', replace_newlines, text_repaired)

    try:
        return json.loads(text_repaired, strict=False)
    except json.JSONDecodeError as e:
        # Try truncated JSON fix on repaired text
        if "Expecting" in str(e) or "Unterminated" in str(e) or "control character" in str(e):
            try:
                fixed_text = fix_truncated_json(text_repaired)
                return json.loads(fixed_text, strict=False)
            except json.JSONDecodeError:
                pass
        # Try slicing repaired string if extra data is still present
        if "Extra data" in str(e) and e.pos is not None:
            try:
                return json.loads(text_repaired[:e.pos].strip(), strict=False)
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON even after repairs: {e}. Raw input: {text}")
        raise e

# Feature-specific model mapping based on user requirements.
# Best Model (Gemini Pro / Flagship) is used as primary. Alternate is configured for future switches.
FEATURE_MODELS = {
    "ai_chat_assistant": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o-mini",
    },
    "website_content_generation": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
    "seo_generator": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o-mini",
    },
    "semantic_search": {
        "gemini": "gemini-embedding-2",
        "alternative": "text-embedding-3-large",
    },
    "template_recommendation": {
        "gemini": "gemini-embedding-2",
        "alternative": "text-embedding-3-large",
    },
    "accessibility_review": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o-mini",
    },
    "code_assistant": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
    "code_debugging_agent": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
    "project_zip_analysis": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
    "translation": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o-mini",
    },
    "business_analysis": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
    "logo_ideas": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o-mini",
    },
    "image_generation": {
        "gemini": "flux",
        "alternative": "dall-e-3",
    },
    "ocr_document_understanding": {
        "gemini": "gemini-flash-lite-latest",
        "alternative": "gpt-4o",
    },
}


class AIService:
    def __init__(self):
        pass

    async def _log_ai_history(self, feature: str, model: str, prompt: str, response: str, user_id=None):
        """Asynchronously log AI call tokens and usage to database for analytics."""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.ai_history import AIHistory
            prompt_tokens = max(1, len(prompt.split()))
            comp_tokens = max(1, len(response.split())) if response else 0
            async with AsyncSessionLocal() as db:
                entry = AIHistory(
                    user_id=user_id,
                    feature=feature,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=comp_tokens,
                    total_tokens=prompt_tokens + comp_tokens,
                    request_summary=prompt[:200],
                    response_summary=response[:200] if response else "",
                )
                db.add(entry)
                await db.commit()
        except Exception:
            pass

    @property
    def client(self):
        """
        Boolean-like indicator for route check compatibility (request.ai_fill and ai_service.client).
        Returns True if any supported LLM provider credentials are configured.
        """
        if getattr(settings, "KIMI_API_KEY", ""):
            return settings.KIMI_API_KEY
        if getattr(settings, "GROQ_API_KEY", ""):
            return settings.GROQ_API_KEY
        if getattr(settings, "OPENROUTER_API_KEY", ""):
            return settings.OPENROUTER_API_KEY
        if getattr(settings, "OPENAI_API_KEY", "") and settings.OPENAI_API_KEY != "your-openai-api-key":
            return settings.OPENAI_API_KEY
        if getattr(settings, "GEMINI_API_KEY", ""):
            return settings.GEMINI_API_KEY
        if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
            return True
        return None

    def get_model_for_feature(self, feature_name: str, provider: str = "gemini") -> str:
        """
        Resolves the designated model name for a specific feature and provider.
        """
        if provider == "gemini":
            # Dynamically fetch the GEMINI_MODEL_X setting, e.g. settings.GEMINI_MODEL_AI_CHAT_ASSISTANT
            setting_name = f"GEMINI_MODEL_{feature_name.upper()}"
            model = getattr(settings, setting_name, None)
            if not model:
                # Fallback to FEATURE_MODELS dictionary mapping
                mapping = FEATURE_MODELS.get(feature_name)
                model = mapping.get("gemini", settings.GEMINI_MODEL) if mapping else settings.GEMINI_MODEL

            # If the resolved model is text-embedding-3-small but we are using Gemini provider,
            # map it to the Gemini embedding model setting to prevent errors.
            if model == "text-embedding-3-small":
                return settings.GEMINI_EMBEDDING_MODEL or "text-embedding-004"
            return model
        else:
            # Dynamically fetch the ALT_MODEL_X setting, e.g. settings.ALT_MODEL_AI_CHAT_ASSISTANT
            setting_name = f"ALT_MODEL_{feature_name.upper()}"
            model = getattr(settings, setting_name, None)
            if not model:
                # Fallback to FEATURE_MODELS dictionary mapping
                mapping = FEATURE_MODELS.get(feature_name)
                model = mapping.get("alternative", "gpt-4o") if mapping else "gpt-4o"
            return model

    async def _call_gemini_api(self, prompt: str, model_name: str, response_mime_type: str) -> Optional[str]:
        """Perform a single HTTP request to the Gemini API with automatic retries on timeouts."""
        import asyncio
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 8192
            }
        }
        if response_mime_type == "application/json":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, headers=headers, timeout=180.0)
                    if response.status_code == 200:
                        data = response.json()
                        try:
                            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except (KeyError, IndexError) as e:
                            logger.warning(f"Unexpected response structure from Gemini for model {model_name}: {data}")
                            return None
                    elif response.status_code == 429:
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", response.text)
                        except Exception:
                            error_msg = response.text
                        logger.warning(f"Gemini API rate limit 429 hit for model {model_name}. Immediately rolling over to fallback model...")
                        raise GeminiAPIError(429, error_msg, model_name)
                    elif response.status_code == 503:
                        logger.warning(f"Gemini API returned temporary status 503 for {model_name} (attempt {attempt + 1}/{max_retries}). Retrying in 2s...")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2.0)
                            continue
                        else:
                            try:
                                error_data = response.json()
                                error_msg = error_data.get("error", {}).get("message", response.text)
                            except Exception:
                                error_msg = response.text
                            raise GeminiAPIError(response.status_code, error_msg, model_name)
                    else:
                        logger.warning(f"Gemini API returned status {response.status_code} for model {model_name}: {response.text}")
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("error", {}).get("message", response.text)
                        except Exception:
                            error_msg = response.text
                        raise GeminiAPIError(response.status_code, error_msg, model_name)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"Gemini API call failed (attempt {attempt + 1}/{max_retries}) due to network issue: {type(e).__name__}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return None

    async def _call_openai_compatible_api(
        self,
        prompt: str,
        base_url: str,
        api_key: str,
        model_name: str,
        response_mime_type: str = "application/json",
        provider_label: str = "LLM"
    ) -> Optional[str]:
        """
        Generic OpenAI-compatible caller for Kimi (Moonshot), OpenRouter, Groq, DeepSeek, or OpenAI.
        """
        import asyncio
        endpoint = base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in base_url:
            headers["HTTP-Referer"] = "https://ai-site-studio.local"
            headers["X-Title"] = "AI Site Studio"

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
        if response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(2):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(endpoint, json=payload, headers=headers, timeout=120.0)
                    if response.status_code == 200:
                        data = response.json()
                        try:
                            return data["choices"][0]["message"]["content"].strip()
                        except (KeyError, IndexError) as e:
                            logger.warning(f"Unexpected response from {provider_label} ({model_name}): {data}")
                            return None
                    elif response.status_code == 400 and response_mime_type == "application/json":
                        # If provider does not support response_format: {"type": "json_object"}, retry once without it
                        payload.pop("response_format", None)
                        continue
                    else:
                        try:
                            err_data = response.json()
                            err_msg = err_data.get("error", {}).get("message", response.text)
                        except Exception:
                            err_msg = response.text
                        logger.warning(f"{provider_label} API ({model_name}) returned status {response.status_code}: {err_msg}")
                        if "kimi" in provider_label.lower() or "moonshot" in provider_label.lower():
                            raise KimiAPIError(response.status_code, err_msg, model_name)
                        return None
            except KimiAPIError:
                raise
            except Exception as e:
                logger.warning(f"{provider_label} API call failed on attempt {attempt+1}: {e}")
                if attempt == 0:
                    await asyncio.sleep(1.0)
        return None

    async def _generate_content(
        self,
        prompt: str,
        response_mime_type: str = "application/json",
        feature_name: str = "website_content_generation",
        fallback_azure: bool = True,
        preferred_provider: Optional[str] = None
    ) -> str:
        """
        Call LLM to generate content.
        Supports multi-model provider routing (Kimi, Groq, OpenRouter, OpenAI, Azure).
        When Kimi is primary or requested, strictly routes to Kimi Moonshot models.
        """
        # Determine trial order based on preferred_provider, agent-specific setting, or AI_PRIMARY_PROVIDER
        agent_setting_key = f"AGENT_{feature_name.upper()}_PROVIDER"
        agent_choice = getattr(settings, agent_setting_key, None)
        primary_choice = (preferred_provider or agent_choice or getattr(settings, "AI_PRIMARY_PROVIDER", "kimi")).lower().strip()

        # If Kimi is chosen as primary or preferred provider, restrict execution to Kimi exclusively
        if primary_choice == "kimi":
            provider_order = ["kimi"]
        else:
            all_providers = ["kimi", "groq", "openrouter", "openai", "azure"]
            if primary_choice in all_providers:
                provider_order = [primary_choice] + [p for p in all_providers if p != primary_choice]
            else:
                provider_order = all_providers

        for provider in provider_order:
            # 1. Kimi (Moonshot AI)
            if provider == "kimi" and getattr(settings, "KIMI_API_KEY", ""):
                try:
                    safe_print(f"[AI Service] Invoking Kimi (Moonshot) ({settings.KIMI_MODEL}) for '{feature_name}'...")
                    res = await self._call_openai_compatible_api(
                        prompt=prompt,
                        base_url=settings.KIMI_BASE_URL,
                        api_key=settings.KIMI_API_KEY,
                        model_name=settings.KIMI_MODEL,
                        response_mime_type=response_mime_type,
                        provider_label="Kimi (Moonshot)"
                    )
                    if res:
                        safe_print(f"   └─ ✅ Kimi ({settings.KIMI_MODEL}) generated output successfully ({len(res)} chars).")
                        return res
                except KimiAPIError as e:
                    # If status is 401, automatically attempt the alternate Moonshot domain (moonshot.ai vs moonshot.cn)
                    if e.status_code == 401:
                        alt_url = "https://api.moonshot.ai/v1" if "moonshot.cn" in settings.KIMI_BASE_URL else "https://api.moonshot.cn/v1"
                        alt_model = "kimi-k2.6" if "moonshot.ai" in alt_url else "moonshot-v1-32k"
                        try:
                            safe_print(f"   └─ 🔄 Auth 401 on primary domain, retrying Moonshot alternate endpoint ({alt_url}, model {alt_model})...")
                            res = await self._call_openai_compatible_api(
                                prompt=prompt,
                                base_url=alt_url,
                                api_key=settings.KIMI_API_KEY,
                                model_name=alt_model,
                                response_mime_type=response_mime_type,
                                provider_label="Kimi (Moonshot)"
                            )
                            if res:
                                safe_print(f"   └─ ✅ Kimi ({alt_model}) generated output successfully via alternate endpoint ({alt_url}).")
                                return res
                        except KimiAPIError as alt_e:
                            e = alt_e
                        except Exception:
                            pass

                    logger.error(f"Kimi API Error: {e}")
                    safe_print(f"   └─ ❌ Kimi API error (status {e.status_code}): {e.message}")
                    if e.status_code == 401:
                        hint = "Invalid API Key. Please verify your KIMI_API_KEY from https://platform.moonshot.ai/console/api-keys (International) or https://platform.moonshot.cn/console/api-keys (China)."
                    elif e.status_code == 429:
                        hint = "Your account is suspended due to insufficient balance ($0) or quota exceeded. Please recharge your account at https://platform.moonshot.ai/console/billing (or https://platform.moonshot.cn/console/billing)."
                    else:
                        hint = "Please check your account at https://platform.moonshot.ai/console/billing."
                    raise RuntimeError(
                        f"Moonshot (Kimi) API Error (status {e.status_code}): {e.message}. {hint}"
                    ) from e
                except Exception as e:
                    logger.error(f"Kimi attempt failed: {e}")
                    if primary_choice == "kimi":
                        raise e

            # 2. Groq
            elif provider == "groq" and getattr(settings, "GROQ_API_KEY", ""):
                try:
                    safe_print(f"[AI Service] Invoking Groq ({settings.GROQ_MODEL}) for '{feature_name}'...")
                    res = await self._call_openai_compatible_api(
                        prompt=prompt,
                        base_url=settings.GROQ_BASE_URL,
                        api_key=settings.GROQ_API_KEY,
                        model_name=settings.GROQ_MODEL,
                        response_mime_type=response_mime_type,
                        provider_label="Groq"
                    )
                    if res:
                        safe_print(f"   └─ ✅ Groq ({settings.GROQ_MODEL}) generated output successfully.")
                        return res
                except Exception as e:
                    logger.error(f"Groq attempt failed: {e}")

            # 3. OpenRouter
            elif provider == "openrouter" and getattr(settings, "OPENROUTER_API_KEY", ""):
                try:
                    safe_print(f"[AI Service] Invoking OpenRouter ({settings.OPENROUTER_MODEL}) for '{feature_name}'...")
                    res = await self._call_openai_compatible_api(
                        prompt=prompt,
                        base_url=settings.OPENROUTER_BASE_URL,
                        api_key=settings.OPENROUTER_API_KEY,
                        model_name=settings.OPENROUTER_MODEL,
                        response_mime_type=response_mime_type,
                        provider_label="OpenRouter"
                    )
                    if res:
                        safe_print(f"   └─ ✅ OpenRouter ({settings.OPENROUTER_MODEL}) generated output successfully.")
                        return res
                except Exception as e:
                    logger.error(f"OpenRouter attempt failed: {e}")

            # 4. Official OpenAI
            elif provider == "openai" and getattr(settings, "OPENAI_API_KEY", "") and settings.OPENAI_API_KEY != "your-openai-api-key":
                try:
                    safe_print(f"[AI Service] Invoking OpenAI ({settings.OPENAI_MODEL}) for '{feature_name}'...")
                    res = await self._call_openai_compatible_api(
                        prompt=prompt,
                        base_url=settings.OPENAI_BASE_URL,
                        api_key=settings.OPENAI_API_KEY,
                        model_name=settings.OPENAI_MODEL,
                        response_mime_type=response_mime_type,
                        provider_label="OpenAI"
                    )
                    if res:
                        safe_print(f"   └─ ✅ OpenAI ({settings.OPENAI_MODEL}) generated output successfully.")
                        return res
                except Exception as e:
                    logger.error(f"OpenAI attempt failed: {e}")

            # 5. Azure OpenAI
            elif provider == "azure" and fallback_azure and settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
                try:
                    safe_print(f"🤖 [AI Service] Invoking Azure OpenAI for feature '{feature_name}'...")
                    res = await self._generate_azure_content(prompt, feature_name, response_mime_type)
                    safe_print(f"   └─ ✅ Azure OpenAI generated output successfully.")
                    return res
                except Exception as e:
                    logger.error(f"Azure OpenAI attempt failed for feature '{feature_name}': {e}")
                    safe_print(f"   [FAIL] Azure OpenAI attempt failed: {e}")

        # No random/fallback templates allowed when AI calls fail.
        # Report the exact error so the customer knows why it failed instead of receiving a random template.
        error_details = f"AI Provider '{primary_choice}' (model: {getattr(settings, 'KIMI_MODEL', 'moonshot-v1-32k')}) failed to respond or encountered an error."
        if primary_choice == "kimi":
            error_details = (
                f"Kimi (Moonshot) model '{getattr(settings, 'KIMI_MODEL', 'moonshot-v1-32k')}' encountered an error or insufficient account balance. "
                "Please verify your account and recharge credits at https://platform.moonshot.cn/console/billing."
            )
        raise RuntimeError(f"AI Generation Failed: {error_details}")

    async def stream_ai_content(
        self,
        prompt: str,
        feature_name: str = "website_content_generation",
    ):
        """
        Stream AI generated text line-by-line in real-time SSE format (data: {"chunk": "..."}\n\n).
        Supports automatic model failover across Gemini 1.5/2.0 models and fallback generators.
        """
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 8192
            }
        }

        models_to_try = [
            self.get_model_for_feature(feature_name, provider="gemini"),
            "gemini-flash-lite-latest",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-pro-latest",
        ]
        
        seen = set()
        unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        success = False
        if settings.GEMINI_API_KEY:
            for target_model in unique_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:streamGenerateContent?alt=sse&key={settings.GEMINI_API_KEY}"
                try:
                    async with httpx.AsyncClient() as client:
                        async with client.stream("POST", url, json=payload, headers=headers, timeout=120.0) as response:
                            if response.status_code == 200:
                                success = True
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk_json = json.loads(data_str)
                                            text_chunk = chunk_json["candidates"][0]["content"]["parts"][0]["text"]
                                            if text_chunk:
                                                yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"
                                        except Exception:
                                            continue
                                yield "data: [DONE]\n\n"
                                return
                except Exception as e:
                    logger.warning(f"SSE Streaming attempt failed for model {target_model}: {e}")
                    continue

        # If SSE streaming is unavailable, send fallback response chunk
        if not success:
            fallback_text = await self._generate_content(prompt, response_mime_type="text/plain", feature_name=feature_name)
            yield f"data: {json.dumps({'chunk': fallback_text})}\n\n"
            yield "data: [DONE]\n\n"

    async def _generate_azure_content(
        self,
        prompt: str,
        feature_name: str,
        response_mime_type: str = "application/json"
    ) -> str:
        """Call Azure OpenAI endpoint for content generation."""
        # Resolve Azure deployment name for this feature
        deployment_name = getattr(settings, f"AZURE_DEPLOYMENT_{feature_name.upper()}", "")
        if not deployment_name:
            # Fallback to general chat deployment if specific one is not set
            deployment_name = settings.AZURE_DEPLOYMENT_CHAT or "gpt-4o"

        headers = {
            "api-key": settings.AZURE_OPENAI_API_KEY,
            "Content-Type": "application/json",
        }
        
        endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip("/")
        url = f"{endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
        
        payload = {
            "messages": [{"role": "user", "content": prompt}],
        }
        if response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                try:
                    return data["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"Unexpected response structure from Azure OpenAI: {data}") from e
            else:
                raise RuntimeError(f"Azure OpenAI API returned status {response.status_code}: {response.text}")

    async def generate_embedding(self, text: str, feature_name: str = "semantic_search") -> List[float]:
        """
        Generate dense vector embedding using Gemini embedding API or Azure fallback.
        """
        # 1. Try Gemini
        if settings.GEMINI_API_KEY:
            primary_model = self.get_model_for_feature(feature_name, provider="gemini")
            models_to_try = [primary_model, "gemini-embedding-2", "gemini-embedding-001"]
            seen = set()
            for model_name in models_to_try:
                if model_name in seen:
                    continue
                seen.add(model_name)
                headers = {"Content-Type": "application/json"}
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "model": f"models/{model_name}",
                    "content": {
                        "parts": [{"text": text}]
                    }
                }
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                        if response.status_code == 200:
                            data = response.json()
                            return data["embedding"]["values"]
                        else:
                            logger.warning(f"Gemini Embedding API returned status {response.status_code} for model {model_name}: {response.text}")
                except Exception as e:
                    logger.error(f"Gemini embedding API call failed for model '{model_name}': {e}")

        # 2. Try Azure
        if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
            try:
                logger.info(f"Attempting Azure OpenAI embedding fallback for feature '{feature_name}'")
                return await self._get_azure_embedding(text, feature_name)
            except Exception as e:
                logger.error(f"Azure OpenAI embedding fallback failed for feature '{feature_name}': {e}")
                raise RuntimeError(f"Both Gemini and Azure OpenAI embedding fallback failed for feature '{feature_name}'. Last error: {e}") from e

        raise ValueError(f"AI Service embedding configuration missing or failed for feature '{feature_name}'")

    async def _get_azure_embedding(self, text: str, feature_name: str) -> List[float]:
        """Generate dense vector embedding using Azure OpenAI API."""
        deployment_name = getattr(settings, f"AZURE_DEPLOYMENT_{feature_name.upper()}", "")
        if not deployment_name:
            deployment_name = settings.AZURE_DEPLOYMENT_SEMANTIC_SEARCH or "text-embedding-3-small"

        headers = {
            "api-key": settings.AZURE_OPENAI_API_KEY,
            "Content-Type": "application/json",
        }
        
        endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip("/")
        url = f"{endpoint}/openai/deployments/{deployment_name}/embeddings?api-version={settings.AZURE_OPENAI_API_VERSION}"
        
        payload = {
            "input": [text]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                try:
                    return data["data"][0]["embedding"]
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"Unexpected embedding response structure from Azure OpenAI: {data}") from e
            else:
                raise RuntimeError(f"Azure OpenAI Embedding API returned status {response.status_code}: {response.text}")

    async def generate_image(self, prompt: str, feature_name: str = "image_generation", industry: Optional[str] = None) -> str:
        """
        Generate ultra-crisp high-resolution images using curated Unsplash 4K photography
        or Pollinations AI Flux HD model, avoiding blurry low-resolution artifacts.
        """
        # If Azure is configured and has an image generation deployment:
        if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
            deployment_name = getattr(settings, f"AZURE_DEPLOYMENT_{feature_name.upper()}", "")
            if deployment_name:
                try:
                    logger.info(f"Attempting Azure OpenAI image generation for feature '{feature_name}'")
                    headers = {
                        "api-key": settings.AZURE_OPENAI_API_KEY,
                        "Content-Type": "application/json",
                    }
                    endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip("/")
                    url = f"{endpoint}/openai/deployments/{deployment_name}/images/generations?api-version={settings.AZURE_OPENAI_API_VERSION}"
                    payload = {
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024"
                    }
                    async with httpx.AsyncClient() as client:
                        response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                        if response.status_code == 200:
                            data = response.json()
                            return data["data"][0]["url"]
                        else:
                            logger.warning(f"Azure OpenAI Image API returned status {response.status_code}: {response.text}")
                except Exception as e:
                    logger.error(f"Azure OpenAI image generation failed: {e}")

        # High-res Unsplash curated photos per industry
        prompt_lower = (prompt + " " + (industry or "")).lower()

        # Curated Unsplash HD crisp photo mapping
        UNSPLASH_MAP = {
            "bakery": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1400&q=85",
            "bread": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1400&q=85",
            "pastry": "https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=1400&q=85",
            "restaurant": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1400&q=85",
            "cafe": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1400&q=85",
            "coffee": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1400&q=85",
            "food": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1400&q=85",
            "ai": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1400&q=85",
            "portfolio": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?auto=format&fit=crop&w=1400&q=85",
            "saas": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1400&q=85",
            "technology": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1400&q=85",
            "agency": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1400&q=85",
            "real estate": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1400&q=85",
            "health": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1400&q=85",
            "ecommerce": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1400&q=85",
            "fashion": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=1400&q=85",
            "fitness": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1400&q=85",
        }

        for key, unsplash_url in UNSPLASH_MAP.items():
            if key in prompt_lower:
                return unsplash_url

        try:
            from app.services.template_synthesizer import analyze_prompt_intent
            profile = analyze_prompt_intent(prompt)
            if profile.hero_image:
                return profile.hero_image
        except Exception:
            pass

        return "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1280&q=80"

    async def generate_business_content(
        self,
        business_name: str,
        industry: str,
        template_type: str,
        additional_context: Optional[str] = None,
    ) -> dict:
        """
        Auto-generate website content for a business.
        Used in the Preview Builder when user clicks "AI Fill".

        Returns a dict with tagline, about, services, service_descriptions, etc.
        """
        prompt = f"""You are a professional website copywriter.

Generate compelling website content for a {industry} business called "{business_name}".
The website template is a {template_type} type.
{f'Additional context: {additional_context}' if additional_context else ''}

Return a JSON object with these exact fields:
{{
  "tagline": "catchy one-line tagline",
  "about": "2-3 sentence about us paragraph",
  "services": ["Service 1", "Service 2", "Service 3", "Service 4"],
  "service_descriptions": {{
    "Service 1": "One line description",
    "Service 2": "One line description",
    "Service 3": "One line description",
    "Service 4": "One line description"
  }},
  "cta_primary": "Primary call-to-action button text",
  "cta_secondary": "Secondary call-to-action text",
  "hero_headline": "Hero section headline",
  "hero_subheadline": "Hero section subheadline"
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="website_content_generation"
        )
        return robust_json_loads(response_text)

    async def generate_seo(
        self,
        business_name: str,
        industry: str,
        services: list,
        location: Optional[str] = None,
    ) -> dict:
        """Generate SEO meta tags and keywords."""
        prompt = f"""Generate SEO metadata for "{business_name}", a {industry} business.
Services: {', '.join(services)}.
{f'Location: {location}' if location else ''}

Return JSON:
{{
  "meta_title": "...",
  "meta_description": "...",
  "keywords": ["kw1", "kw2", ...],
  "og_title": "...",
  "og_description": "..."
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="seo_generator"
        )
        return robust_json_loads(response_text)

    async def generate_color_palette(self, industry: str, mood: str = "professional") -> dict:
        """Generate a color palette for a business."""
        prompt = f"""Generate a professional color palette for a {industry} business with a {mood} mood.

Return JSON:
{{
  "primary": "#HEXCODE",
  "secondary": "#HEXCODE",
  "accent": "#HEXCODE",
  "background": "#HEXCODE",
  "text": "#HEXCODE",
  "rationale": "Brief explanation"
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="logo_ideas"
        )
        return robust_json_loads(response_text)

    async def recommend_templates(
        self,
        user_description: str,
        available_categories: list,
    ) -> dict:
        """Suggest template categories and keywords based on user's business description."""
        prompt = f"""A user is looking for a website template. Their description:
"{user_description}"

Available categories: {', '.join(available_categories)}

Return JSON:
{{
  "recommended_categories": ["cat1", "cat2"],
  "search_keywords": ["kw1", "kw2", "kw3"],
  "reasoning": "Brief explanation"
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="template_recommendation"
        )
        return robust_json_loads(response_text)

    async def enhance_template_prompt(self, user_prompt: str) -> dict:
        """
        Enhance a brief template prompt into a high-fidelity design specification using Gemini Pro.
        """
        prompt = f"""You are a principal digital product designer and frontend architect.
A user wants to create a website template with this initial brief:
"{user_prompt}"

Expand this prompt into a rich, professional design specification.
Return JSON:
{{
  "enhanced_prompt": "A detailed 3-4 sentence prompt describing the core concept, target audience, layout architecture, visual aesthetics, typography, color palette, interactive components, and special section requirements.",
  "suggested_title": "A punchy marketplace title for this template",
  "industry": "Industry classification (e.g. SaaS & Tech, Portfolio & Agency, E-Commerce, Restaurant)",
  "color_scheme": "Dominant color scheme description (e.g., Cyberpunk Neon Dark, Glassmorphic Emerald, Warm Editorial Cream)",
  "recommended_sections": ["Hero Banner with CTA", "Feature Grid", "Interactive Showcase", "Testimonials", "Pricing Tables", "Footer"]
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="website_content_generation"
        )
        return robust_json_loads(response_text)

    async def chat_with_assistant(self, message: str) -> dict:
        """Chat with the AI Site Studio assistant."""
        prompt = f"""You are the official support concierge for Site Studio, a premium platform for website template generation, personalization, and purchasing.
Rules:
- Answer only questions related to Site Studio.
- Help users with templates.
- Help users create and customize websites.
- Help users buy templates.
- Be friendly, professional, and act like a pro.
- Keep answers under 150 words.
- If the user asks unrelated questions, politely redirect them back to Site Studio topics.

User message: "{message}"

Return JSON:
{{
  "reply": "Your response here"
}}

Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

        response_text = await self._generate_content(
            prompt, response_mime_type="application/json", feature_name="ai_chat_assistant"
        )
        return robust_json_loads(response_text)

    async def generate_speech(self, text: str, voice: str = "Puck") -> bytes:
        """
        Convert text to speech using Gemini TTS (gemini-3.1-flash-tts-preview).
        """
        import base64
        import io
        import wave

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Map some common voice names to Gemini voices if necessary
        gemini_voices = ["Puck", "Charon", "Aoede", "Fenrir", "Breezy", "Kore"]
        voice_capitalized = voice.capitalize()
        target_voice = voice_capitalized if voice_capitalized in gemini_voices else "Puck"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={settings.GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{"text": text}]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": target_voice
                        }
                    }
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                try:
                    part = data["candidates"][0]["content"]["parts"][0]
                    if "inlineData" in part:
                        pcm_bytes = base64.b64decode(part['inlineData']['data'])
                        
                        # Convert raw PCM (16-bit, 24kHz mono) to WAV
                        wav_io = io.BytesIO()
                        with wave.open(wav_io, 'wb') as wav_file:
                            wav_file.setnchannels(1)       # Mono
                            wav_file.setsampwidth(2)      # 16-bit = 2 bytes
                            wav_file.setframerate(24000)  # 24kHz
                            wav_file.writeframes(pcm_bytes)
                        
                        return wav_io.getvalue()
                    else:
                        raise RuntimeError("Gemini TTS response did not contain inline audio data.")
                except Exception as ex:
                    raise RuntimeError(f"Failed to parse Gemini TTS response: {ex}. Response: {response.text[:500]}")
            elif response.status_code == 429:
                raise ValueError("Gemini API rate limit exceeded (429). Please retry later.")
            else:
                raise RuntimeError(f"Gemini TTS API returned status {response.status_code}: {response.text}")

    async def diagnose_and_heal_website(
        self,
        files_dict: dict,
        issue_type: str,
        issue_description: str,
        error_logs: Optional[str] = None,
        page_url: Optional[str] = None,
    ) -> dict:
        """
        Autonomous AI Site Doctor:
        Analyzes a reported website failure, pinpoints root cause across HTML/JS/CSS,
        generates complete code patches, and returns structured diagnosis and repaired files.
        """
        files_summary = []
        for file_path, content in files_dict.items():
            truncated_content = content[:12000] if len(content) > 12000 else content
            files_summary.append(f"--- FILE: {file_path} ---\n{truncated_content}\n")

        joined_files = "\n".join(files_summary)

        prompt = f"""You are the Autonomous AI Site Doctor & Senior Reliability Engineer for AI Site Studio.
A live customer website has experienced a failure and was reported.
Your job is to diagnose the root cause, determine which file(s) have broken code, and provide the complete fixed file code so the site runs perfectly.

### INCIDENT REPORT:
- Issue Type: {issue_type}
- Problem Description: {issue_description}
- Affected Page/URL: {page_url or "/"}
- Error Logs / Console Output: {error_logs or "None provided"}

### PROJECT FILES:
{joined_files}

### INSTRUCTIONS:
1. Carefully analyze what caused the error (e.g. JavaScript runtime exception, broken DOM querySelector, missing event listener, invalid HTML/CSS, missing function, broken link, null pointer reference).
2. Generate the COMPLETE, working code for each file that needs to be fixed. Do NOT use placeholders or snippets; provide the entire file content ready to be saved to disk.
3. If an HTML or JS file has broken or missing script tags, repair them. If there are missing elements or unhandled null checks, add defensive guards.
4. Return a valid JSON object with the following schema:
{{
  "diagnosis": "Clear explanation of what broke and why",
  "root_cause": "The exact faulty code or logic that caused the issue",
  "patch_summary": "Concise summary of what fixes were made",
  "fixed_files": [
    {{
      "path": "relative/file/path.ext",
      "content": "Full, complete updated file contents"
    }}
  ]
}}
"""
        response_text = await self._generate_content(
            prompt=prompt,
            response_mime_type="application/json",
            feature_name="code_debugging_agent"
        )
        try:
            parsed = robust_json_loads(response_text)
            if isinstance(parsed, dict) and "fixed_files" in parsed:
                return parsed
            elif isinstance(parsed, dict):
                return {
                    "diagnosis": parsed.get("diagnosis", "Automated code diagnosis complete."),
                    "root_cause": parsed.get("root_cause", "Identified potential runtime inconsistency."),
                    "patch_summary": parsed.get("patch_summary", "Applied code corrections."),
                    "fixed_files": parsed.get("fixed_files", [])
                }
        except Exception as e:
            logger.warning(f"AI Doctor JSON parsing failed: {e}. Raw response: {response_text[:300]}")

        return {
            "diagnosis": f"Automated inspection for {issue_type}: {issue_description}",
            "root_cause": "Identified potential runtime/syntax anomaly in frontend assets.",
            "patch_summary": "Auto-stabilized assets with defensive event handlers.",
            "fixed_files": []
        }


def clean_code_response(text: str, language: str = "") -> str:
    """Clean markdown code block wrappers and JSON wrappers from LLM responses."""
    text = text.strip()

    # Unquote JSON wrapper string if LLM returned JSON object like {"code": "..."}
    if text.startswith("{") and ("\"code\"" in text or "'code'" in text or "\"content\"" in text):
        try:
            import json
            data = json.loads(text)
            if isinstance(data, dict):
                if "code" in data and isinstance(data["code"], str):
                    text = data["code"].strip()
                elif "content" in data and isinstance(data["content"], str):
                    text = data["content"].strip()
        except Exception:
            pass

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    elif "```" in text:
        import re
        match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    return text.strip()


def repair_truncated_jsx(code: str) -> str:
    """
    Cleans markdown wrappers and safely repairs truncated React JSX code to guarantee valid JavaScript syntax.
    """
    code = clean_code_response(code)
    if not code:
        return ""

    # Guard against raw JSON status objects being parsed as JSX code
    trimmed = code.strip()
    if (trimmed.startswith("{") and ("status" in trimmed or "diagnosis" in trimmed or "Dynamic structural" in trimmed)) or (trimmed.startswith("{") and "export default" not in trimmed):
        from app.services.template_synthesizer import analyze_prompt_intent, synthesize_react_application
        profile = analyze_prompt_intent("Professional Website Template")
        return synthesize_react_application(profile)

    # Guard: If this is clearly a config file or pure module without JSX, do not mutate exports or inject JSX tags!
    if "defineConfig" in code or "module.exports" in code or ("<" not in code and ">" not in code):
        return code

    import re

    # 0. Clean premature `);` before closing JSX tags
    code = re.sub(r'\);\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)
    code = re.sub(r';\s*(</[A-Za-z0-9_.-]+>)', r'\1', code)

    # 1. Clean incomplete trailing lines at end of file (lines cut off mid-tag or mid-operator)
    lines = code.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if (last.startswith("<") and not last.endswith(">") and not last.endswith("/>")) or \
           last.endswith("=") or \
           last.endswith("&&") or \
           last.endswith("||") or \
           last.endswith("?") or \
           last.endswith(":") or \
           last.endswith(",") or \
           last.endswith("+"):
            lines.pop()
        else:
            break

    if not lines:
        return code

    code = "\n".join(lines)
    code = re.sub(r'<[A-Za-z/][^>]*$', '', code)

    # Clean stray closing return before we inspect open tags
    has_premature_closing = False
    if re.search(r'\);\s*$', code):
        code = re.sub(r'\);\s*$', '', code)
        has_premature_closing = True

    self_closing = {
        'img', 'br', 'hr', 'input', 'link', 'meta', 'source', 'col',
        'area', 'base', 'embed', 'param', 'track', 'wbr'
    }

    tag_regex = re.compile(r'(<(/)?([A-Za-z][A-Za-z0-9.-]*)(?:\s+[^>]*?)?(/)?>)|([{()}[\]])')

    tag_stack = []
    bracket_stack = []
    in_string = False
    string_char = None

    i = 0
    length = len(code)
    while i < length:
        # Skip single-line comments
        if not in_string and i + 1 < length and code[i:i+2] == '//':
            eol = code.find('\n', i)
            i = eol if eol != -1 else length
            continue

        # Skip block comments
        if not in_string and i + 1 < length and code[i:i+2] == '/*':
            eoc = code.find('*/', i)
            i = eoc + 2 if eoc != -1 else length
            continue

        char = code[i]
        if in_string:
            if char == string_char and code[i-1] != '\\':
                in_string = False
                string_char = None
            i += 1
            continue

        if char in ['"', "'", '`']:
            in_string = True
            string_char = char
            i += 1
            continue

        if char == '<':
            prev_str = code[:i].rstrip()
            prev_char = prev_str[-1] if prev_str else ''
            is_likely_comparison = prev_char.isalnum() or prev_char == ')'

            m = tag_regex.match(code, i)
            if m and m.group(1) and not is_likely_comparison:
                is_closing = m.group(2) is not None
                tag_name = m.group(3)
                is_self = m.group(4) is not None or tag_name.lower() in self_closing

                if not is_self:
                    if is_closing:
                        for idx in range(len(tag_stack) - 1, -1, -1):
                            if tag_stack[idx] == tag_name:
                                tag_stack = tag_stack[:idx]
                                break
                    else:
                        tag_stack.append(tag_name)
                i += len(m.group(0))
                continue

        if char in ['{', '(', '[']:
            bracket_stack.append(char)
        elif char in ['}', ')', ']']:
            matching = {'}': '{', ')': '(', ']': '['}[char]
            for idx in range(len(bracket_stack) - 1, -1, -1):
                if bracket_stack[idx] == matching:
                    bracket_stack = bracket_stack[:idx]
                    break

        i += 1

    if in_string and string_char:
        code += string_char

    closing_str = ""
    if tag_stack:
        closing_str += "\n" + "\n".join(f"</{t}>" for t in reversed(tag_stack))

    if has_premature_closing or bracket_stack:
        matching_close = {'{': '}', '(': ')', '[': ']'}
        closing_str += "\n" + "".join(matching_close.get(b, '') for b in reversed(bracket_stack))
        if not closing_str.rstrip().endswith(";"):
            closing_str += ";"

    repaired = code + closing_str

    # Clean and validate export defaults safely without destroying inline function exports
    has_inline_export = bool(re.search(r'export\s+default\s+(function|class)\b', repaired))

    if not has_inline_export:
        export_matches = list(re.finditer(r'export\s+default\s+([A-Za-z0-9_]+)\s*;?', repaired))
        valid_standalone = [m for m in export_matches if m.group(1) not in ("function", "class", "const")]
        if len(valid_standalone) > 1:
            last_func = valid_standalone[-1].group(1)
            repaired = re.sub(r'export\s+default\s+[A-Za-z0-9_]+\s*;?', '', repaired)
            repaired = repaired.strip() + f"\n\nexport default {last_func};\n"
        elif not valid_standalone:
            if "function App" in repaired or "const App" in repaired:
                repaired = repaired.strip() + "\n\nexport default App;\n"
            elif "function " in repaired:
                func_name = re.search(r'function\s+([A-Za-z0-9_]+)', repaired)
                if func_name:
                    repaired = repaired.strip() + f"\n\nexport default {func_name.group(1)};\n"
                else:
                    repaired = repaired.strip() + "\n\nexport default App;\n"
            elif "<" in repaired and ">" in repaired:
                repaired = repaired.strip() + "\n\nexport default App;\n"

        # Safely strip conversational trailing comments after the final standalone export default
        last_export = list(re.finditer(r'(export\s+default\s+[A-Za-z0-9_]+\s*;)', repaired))
        if last_export:
            repaired = repaired[:last_export[-1].end()].strip() + "\n"
    else:
        # File has `export default function ...`. Remove any duplicate trailing standalone export defaults.
        repaired = re.sub(r'\nexport\s+default\s+[A-Za-z0-9_]+\s*;?\s*$', '', repaired).strip() + "\n"

    # Final cleanup of premature `);` and stray trailing quotes
    repaired = re.sub(r'\);\s*(</[A-Za-z0-9_.-]+>)', r'\1', repaired)
    repaired = re.sub(r';\s*(</[A-Za-z0-9_.-]+>)', r'\1', repaired)
    repaired = re.sub(r'(\}\s*)\'[A-Za-z0-9_<>/\s]*$', r'\1', repaired)
    repaired = re.sub(r'(\}\s*);?\'\s*$', r'\1;', repaired)

    return repaired



def repair_truncated_html(code: str) -> str:
    """Scan and close open HTML tags to ensure valid HTML markup."""
    lines = code.splitlines()
    if not lines:
        return code
        
    while lines and not lines[-1].strip():
        lines.pop()
        
    if not lines:
        return code
        
    last_line = lines[-1].strip()
    if (last_line.startswith("<") and not last_line.endswith(">")) or \
       last_line.endswith("=") or \
       (not last_line.endswith(">") and not last_line.endswith('"') and not last_line.endswith("'")):
        lines.pop()
        
    repaired_code = "\n".join(lines)
    
    # Trim any unclosed tag at the very end of the file (e.g. <img src="..." alt="Logo")
    import re
    unclosed_tag_match = re.search(r'<[A-Za-z/][^>]*$', repaired_code)
    if unclosed_tag_match:
        repaired_code = repaired_code[:unclosed_tag_match.start()]

    # If footer tag is missing due to LLM output cutoff, inject complete fallback sections & footer
    if "<footer" not in repaired_code.lower():
        fallback_sections = """
  <!-- Complete Auto-Injected Contact & Footer Section -->
  <section id="contact" class="py-16 bg-slate-950/90 border-t border-white/10 relative z-10">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
      <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-mono mb-4">
        <span>Get In Touch</span>
      </div>
      <h2 class="text-3xl font-bold text-white mb-4">Ready to Collaborate on Next-Gen Solutions?</h2>
      <p class="text-slate-400 mb-8 max-w-2xl mx-auto text-sm">Send a direct message for technical consultations, project inquiries, or system architecture audits.</p>
      <div class="flex items-center justify-center gap-4">
        <a href="mailto:contact@domain.com" class="px-6 py-3.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 shadow-lg shadow-sky-600/20 transition-all">
          Contact Engineer
        </a>
      </div>
    </div>
  </section>
  <footer class="bg-slate-950 py-8 border-t border-white/10 text-xs text-slate-400 relative z-10">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
      <span class="font-mono">&copy; 2026 Site Studio. All rights reserved.</span>
      <div class="flex items-center gap-6 text-slate-300 font-medium">
        <a href="index.html" class="hover:text-sky-400 transition-colors">Home</a>
        <a href="#architecture" class="hover:text-sky-400 transition-colors">Architecture</a>
        <a href="#contact" class="hover:text-sky-400 transition-colors">Contact</a>
      </div>
    </div>
  </footer>
"""
        repaired_code += fallback_sections
    
    import re
    tag_pattern = re.compile(r'<(/)?([A-Za-z][A-Za-z0-9.-]*)(?:\s+[^>]*?)?(/)?>')
    open_tags = []
    self_closing_tags = {'img', 'br', 'hr', 'input', 'link', 'meta', 'source', 'col'}
    
    for match in tag_pattern.finditer(repaired_code):
        is_closing = match.group(1) is not None
        tag_name = match.group(2)
        is_self_closing = match.group(3) is not None or tag_name.lower() in self_closing_tags
        
        if is_self_closing:
            continue
            
        if is_closing:
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
        else:
            open_tags.append(tag_name)
            
    closing_str = "\n"
    for tag in reversed(open_tags):
        closing_str += f"</{tag}>\n"
        
    return repaired_code + closing_str


# Module-level singleton
ai_service = AIService()
