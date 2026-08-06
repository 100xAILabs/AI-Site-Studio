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


class GeminiAPIError(Exception):
    def __init__(self, status_code: int, message: str, model: str):
        self.status_code = status_code
        self.message = message
        self.model = model
        super().__init__(f"Gemini API returned status {status_code} for model {model}: {message}")


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
    escapes actual newlines inside quotes, repairs truncated JSON payloads, and slices off
    trailing garbage to resolve common LLM syntax generation bugs.
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
        return json.loads(text)
    except json.JSONDecodeError as e:
        # If it failed due to truncation (expecting delimiter/value/etc.), try fixing truncation
        if "Expecting" in str(e) or "Unterminated" in str(e) or "control character" in str(e):
            try:
                fixed_text = fix_truncated_json(text)
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass
        # Slice off trailing extra braces/garbage if detected early
        if "Extra data" in str(e) and e.pos is not None:
            try:
                return json.loads(text[:e.pos].strip())
            except json.JSONDecodeError:
                pass

    # Try common repairs
    # 1. Trailing commas e.g. [1, 2,] or {"a": 1,}
    text_repaired = re.sub(r',\s*([\]}])', r'\1', text)

    # 2. Escape actual newlines inside quotes
    def replace_newlines(match):
        return match.group(0).replace('\n', '\\n').replace('\r', '\\r')

    # Match double-quoted strings (supporting escaped quotes)
    text_repaired = re.sub(r'"(?:[^"\\]|\\.)*"', replace_newlines, text_repaired)

    try:
        return json.loads(text_repaired)
    except json.JSONDecodeError as e:
        # Try truncated JSON fix on repaired text
        if "Expecting" in str(e) or "Unterminated" in str(e) or "control character" in str(e):
            try:
                fixed_text = fix_truncated_json(text_repaired)
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass
        # Try slicing repaired string if extra data is still present
        if "Extra data" in str(e) and e.pos is not None:
            try:
                return json.loads(text_repaired[:e.pos].strip())
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON even after repairs: {e}. Raw input: {text}")
        raise e

# Feature-specific model mapping based on user requirements.
# Best Model (Gemini Pro / Flagship) is used as primary. Alternate is configured for future switches.
FEATURE_MODELS = {
    "ai_chat_assistant": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "website_content_generation": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "seo_generator": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "semantic_search": {
        "gemini": "text-embedding-004",
        "alternative": "text-embedding-3-large",
    },
    "template_recommendation": {
        "gemini": "text-embedding-004",
        "alternative": "text-embedding-3-large",
    },
    "accessibility_review": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "code_assistant": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "project_zip_analysis": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "translation": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "business_analysis": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "logo_ideas": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
    "image_generation": {
        "gemini": "flux",
        "alternative": "dall-e-3",
    },
    "ocr_document_understanding": {
        "gemini": "gemini-1.5-pro-latest",
        "alternative": "gpt-4o",
    },
}


class AIService:
    def __init__(self):
        pass

    @property
    def client(self):
        """
        Boolean-like indicator for route check compatibility (request.ai_fill and ai_service.client).
        Returns True if either Gemini or Azure OpenAI credentials are configured.
        """
        if settings.GEMINI_API_KEY:
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
                    elif response.status_code in (429, 503):
                        logger.warning(f"Gemini API returned temporary status {response.status_code} for {model_name} (attempt {attempt + 1}/{max_retries}). Retrying in 2s...")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2.0 * (attempt + 1))
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

    async def _generate_content(
        self,
        prompt: str,
        response_mime_type: str = "application/json",
        feature_name: str = "website_content_generation",
        fallback_azure: bool = True
    ) -> str:
        """
        Call LLM to generate content.
        Uses Gemini as primary with automatic model failover. Fallbacks to Azure OpenAI if configured.
        """
        # 1. Try Gemini
        if settings.GEMINI_API_KEY:
            model_name = self.get_model_for_feature(feature_name, provider="gemini")
            
            # Priority order for failover models
            models_to_try = [
                model_name,
                "gemini-flash-latest",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite"
            ]
                    
            seen = set()
            unique_models = []
            for m in models_to_try:
                if m not in seen:
                    seen.add(m)
                    unique_models.append(m)

            last_errors = []
            for target_model in unique_models:
                try:
                    logger.info(f"Attempting Gemini content generation for '{feature_name}' with model: {target_model}")
                    result = await self._call_gemini_api(prompt, target_model, response_mime_type)
                    if result:
                        return result
                    else:
                        last_errors.append(f"Model {target_model} returned empty response.")
                except GeminiAPIError as e:
                    err_msg = f"Model {target_model} failed (status {e.status_code}): {e.message}"
                    logger.warning(f"⚠️ Model {target_model} is temporarily unavailable (status {e.status_code}). Automatically rolling over to next model...")
                    last_errors.append(err_msg)
                except Exception as e:
                    err_msg = f"Model {target_model} failed ({type(e).__name__}): {e}"
                    logger.warning(f"⚠️ Model {target_model} encountered an issue. Automatically rolling over to next model...")
                    last_errors.append(err_msg)

            # If we attempted Gemini and all models failed
            gemini_error_summary = "; ".join(last_errors) if last_errors else "No valid models found in chain."
        else:
            gemini_error_summary = "GEMINI_API_KEY is not configured."

        # 2. Try Azure OpenAI Fallback
        if fallback_azure and settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
            try:
                logger.info(f"Attempting Azure OpenAI fallback for feature '{feature_name}'")
                return await self._generate_azure_content(prompt, feature_name, response_mime_type)
            except Exception as e:
                logger.error(f"Azure OpenAI fallback failed for feature '{feature_name}': {e}")
                raise RuntimeError(f"Both Gemini and Azure OpenAI fallback failed for feature '{feature_name}'. Gemini errors: [{gemini_error_summary}]. Azure error: {e}") from e

        # If no key was configured and fallback didn't run
        if not settings.GEMINI_API_KEY:
            raise ValueError(f"GEMINI_API_KEY is not configured and Azure fallback is not active for feature '{feature_name}'")

        raise ValueError(f"AI content generation failed for feature '{feature_name}'. Details: {gemini_error_summary}")

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
            models_to_try = [primary_model, "text-embedding-004", "embedding-001"]
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

    async def generate_image(self, prompt: str, feature_name: str = "image_generation") -> str:
        """
        Generate image using Azure OpenAI (DALL-E) fallback, or return a Pollinations AI URL by default.
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

        # Default fallback to Pollinations AI
        encoded_prompt = urllib.parse.quote(prompt[:120])
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=768&nologo=true"

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
        prompt = f"""You are the official support assistant for AI Site Studio, a premium platform for AI-powered website template generation and purchasing.
Rules:
- Answer only questions related to AI Site Studio.
- Help users with templates.
- Help users generate websites.
- Help users buy templates.
- Be friendly, professional, and act like a pro.
- Keep answers under 150 words.
- If the user asks unrelated questions, politely redirect them back to AI Site Studio topics.

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


def repair_truncated_jsx(code: str) -> str:
    """Scan and close open brackets and JSX elements in correct nested order to ensure syntactically valid code."""
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
       (not last_line.endswith(";") and not last_line.endswith("}") and not last_line.endswith(")") and not last_line.endswith(">") and not last_line.endswith('"') and not last_line.endswith("'")):
        lines.pop()
        
    repaired_code = "\n".join(lines)
    
    # Trim any unclosed tag at the very end of the file (e.g. <img src="..." alt="Logo")
    import re
    unclosed_tag_match = re.search(r'<[A-Za-z/][^>]*$', repaired_code)
    if unclosed_tag_match:
        repaired_code = repaired_code[:unclosed_tag_match.start()]
    
    # Unified nesting stack for chronological tags and brackets
    stack = []
    self_closing_tags = {'img', 'br', 'hr', 'input', 'link', 'meta', 'source', 'col'}
    
    # Tokenizer pattern for tag name matching
    token_pattern = re.compile(r'(<(/)?([A-Za-z][A-Za-z0-9.-]*)(?:\s+[^>]*?)?(/)?>)|([{()}[\]])')
    
    in_string = False
    string_char = None
    
    i = 0
    length = len(repaired_code)
    while i < length:
        # Skip single-line and block comments
        if not in_string:
            if i + 1 < length and repaired_code[i:i+2] == '//':
                eol = repaired_code.find('\n', i)
                i = eol if eol != -1 else length
                continue
            if i + 1 < length and repaired_code[i:i+2] == '/*':
                eoc = repaired_code.find('*/', i)
                i = eoc + 2 if eoc != -1 else length
                continue
                
        char = repaired_code[i]
        
        if in_string:
            if char == string_char and repaired_code[i-1] != '\\':
                in_string = False
                string_char = None
            i += 1
            continue
            
        if char in ['"', "'", '`']:
            in_string = True
            string_char = char
            i += 1
            continue
            
        # Parse tags
        if char == '<':
            tag_match = token_pattern.match(repaired_code, i)
            if tag_match and tag_match.group(1):
                is_closing = tag_match.group(2) is not None
                tag_name = tag_match.group(3)
                is_self_closing = tag_match.group(4) is not None or tag_name.lower() in self_closing_tags
                
                if not is_self_closing:
                    if is_closing:
                        for idx in range(len(stack) - 1, -1, -1):
                            if stack[idx] == ('tag', tag_name):
                                stack.pop(idx)
                                break
                    else:
                        stack.append(('tag', tag_name))
                i += len(tag_match.group(1))
                continue
                
        # Parse brackets
        if char in ['{', '(', '[']:
            stack.append(('bracket', char))
        elif char in ['}', ')', ']']:
            matching = {'}': '{', ')': '(', ']': '['}[char]
            for idx in range(len(stack) - 1, -1, -1):
                if stack[idx] == ('bracket', matching):
                    stack.pop(idx)
                    break
                    
        i += 1
        
    closing_str = "\n"
    for token_type, value in reversed(stack):
        if token_type == 'tag':
            closing_str += f"</{value}>\n"
        elif token_type == 'bracket':
            closing_char = {'{': '}', '(': ')', '[': ']'}[value]
            closing_str += closing_char
            if closing_char == ')':
                closing_str += ";"
                
    if "export default" not in repaired_code and "export default" not in closing_str:
        closing_str += "\nexport default App;\n"
        
    return repaired_code + closing_str


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
