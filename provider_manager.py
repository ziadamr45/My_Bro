"""
مدير المزودين - Provider Manager
نظام متعدد المزودين مع تبديل تلقائي عند الفشل

المزودين المدعومين:
- Groq (OpenAI-compatible) — سريع ومجاني (الأساسي)
- HuggingFace Inference (OpenAI-compatible via nscale) — مجاني
- Cohere (SDK خاص) — مجاني مع مفاتيح
- OpenRouter (OpenAI-compatible) — مجاني محدود (50 طلب/يوم)

البنية:
🧠 Chat: Groq Qwen3-32B → Groq Llama 3.3 70B → HuggingFace Llama 3.3 70B → Cohere Command A → OpenRouter Nemotron
⚡ Simple: HuggingFace Gemma 2 9B → OpenRouter Nemotron Nano
🔥 Deep Search: Cohere Command A Plus → HuggingFace Qwen3-235B
👨‍💻 Coding: HuggingFace Qwen Coder 32B → HuggingFace Llama 3.3 70B
📄 Summary: Cohere Command A → OpenRouter Nemotron
"""

import asyncio
import logging
import re
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import requests

from config import (
    GROQ_API_KEY, GROQ_BASE_URL,
    HUGGINGFACE_API_KEY, HUGGINGFACE_BASE_URL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    COHERE_API_KEY,
    CHAT_MODELS, SIMPLE_MODELS, DEEP_SEARCH_MODELS,
    CODING_MODELS, SUMMARY_MODELS, VISION_MODELS,
    REQUEST_TIMEOUT, FAST_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# أنواع المزودين - Provider Types
# ═══════════════════════════════════════

@dataclass
class ProviderConfig:
    """إعدادات مزود واحد"""
    name: str
    api_key: str
    base_url: str
    provider_type: str  # "openai_compatible" or "cohere"
    priority: int = 0  # أقل رقم = أولوية أعلى
    is_available: bool = True
    last_error: Optional[str] = None
    last_error_time: float = 0
    cooldown_until: float = 0  # لا تستخدم المزود قبل هذا الوقت


@dataclass
class ModelRoute:
    """مسار نموذج - يحدد المزود والنموذج"""
    provider_name: str
    model_id: str
    priority: int = 0


# ═══════════════════════════════════════
# مدير المزودين - Provider Manager
# ═══════════════════════════════════════

class ProviderManager:
    """
    مدير المزودين - يتعامل مع كل المزودين ويبدل تلقائياً عند الفشل
    """

    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self._cohere_client = None
        self._setup_providers()

    def _setup_providers(self):
        """تهيئة المزودين"""
        # Groq
        if GROQ_API_KEY:
            self.providers["groq"] = ProviderConfig(
                name="groq",
                api_key=GROQ_API_KEY,
                base_url=GROQ_BASE_URL,
                provider_type="openai_compatible",
                priority=1,
            )
            logger.info("✅ Groq provider configured")

        # HuggingFace
        if HUGGINGFACE_API_KEY:
            self.providers["huggingface"] = ProviderConfig(
                name="huggingface",
                api_key=HUGGINGFACE_API_KEY,
                base_url=HUGGINGFACE_BASE_URL,
                provider_type="openai_compatible",
                priority=2,
            )
            logger.info("✅ HuggingFace provider configured")

        # Cohere
        if COHERE_API_KEY:
            self.providers["cohere"] = ProviderConfig(
                name="cohere",
                api_key=COHERE_API_KEY,
                base_url="",
                provider_type="cohere",
                priority=3,
            )
            logger.info("✅ Cohere provider configured")

        # OpenRouter
        if OPENROUTER_API_KEY:
            self.providers["openrouter"] = ProviderConfig(
                name="openrouter",
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
                provider_type="openai_compatible",
                priority=4,
            )
            logger.info("✅ OpenRouter provider configured")

        logger.info(f"🔧 Provider Manager initialized with {len(self.providers)} providers")

    def _get_cohere_client(self):
        """الحصول على Cohere client"""
        if self._cohere_client is None:
            try:
                import cohere
                self._cohere_client = cohere.ClientV2(COHERE_API_KEY)
            except ImportError:
                logger.error("Cohere package not installed. Run: pip install cohere")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize Cohere client: {e}")
                return None
        return self._cohere_client

    def _is_provider_available(self, provider_name: str) -> bool:
        """فحص هل المزود متاح"""
        provider = self.providers.get(provider_name)
        if not provider:
            return False
        if not provider.api_key:
            return False
        # لو في cooldown، نشوف هل خلص
        if provider.cooldown_until > time.time():
            return False
        return True

    def _set_provider_cooldown(self, provider_name: str, error: str, cooldown_seconds: int = 60):
        """تعيين فترة تبريد للمزود بعد خطأ"""
        provider = self.providers.get(provider_name)
        if provider:
            provider.last_error = error
            provider.last_error_time = time.time()
            provider.cooldown_until = time.time() + cooldown_seconds
            logger.warning(f"⏳ Provider {provider_name} on cooldown for {cooldown_seconds}s: {error[:80]}")

    def _clear_provider_cooldown(self, provider_name: str):
        """إزالة فترة التبريد بعد نجاح"""
        provider = self.providers.get(provider_name)
        if provider:
            provider.cooldown_until = 0
            provider.last_error = None

    def get_model_routes(self, task_type: str) -> List[ModelRoute]:
        """
        الحصول على مسارات النماذج لنوع مهمة معين
        task_type: "chat", "simple", "deep_search", "coding", "summary", "vision"
        """
        routes_map = {
            "chat": CHAT_MODELS,
            "simple": SIMPLE_MODELS,
            "deep_search": DEEP_SEARCH_MODELS,
            "coding": CODING_MODELS,
            "summary": SUMMARY_MODELS,
            "vision": VISION_MODELS,
        }

        model_list = routes_map.get(task_type, CHAT_MODELS)
        routes = []
        for i, model_config in enumerate(model_list):
            provider_name = model_config["provider"]
            model_id = model_config["model"]
            if self._is_provider_available(provider_name):
                routes.append(ModelRoute(
                    provider_name=provider_name,
                    model_id=model_id,
                    priority=i,
                ))
            else:
                logger.debug(f"Skipping unavailable provider {provider_name} for model {model_id}")

        return routes

    # ═══════════════════════════════════════
    # استدعاء API - API Calls
    # ═══════════════════════════════════════

    def _call_openai_compatible_sync(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = 30,
    ) -> Optional[str]:
        """استدعاء مزود متوافق مع OpenAI API (متزامن)"""
        provider = self.providers.get(provider_name)
        if not provider:
            return None

        url = f"{provider.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        if provider_name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/ziadamr45/ai-news-bot"
            headers["X-Title"] = "My Bro AI Bot"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.info(f"🤖 Calling {provider_name}/{model}")
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()

            data = response.json()

            # معالجة الأخطاء في الاستجابة
            if "error" in data:
                error_msg = data.get("error", {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                logger.warning(f"❌ API error from {provider_name}/{model}: {error_msg[:100]}")

                # لو rate limit، نحط cooldown
                if "429" in str(error_msg) or "rate limit" in str(error_msg).lower():
                    self._set_provider_cooldown(provider_name, f"Rate limited: {error_msg}", 120)
                return None

            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content", "")
                if content:
                    # شيل thinking/reasoning tags من نماذج Qwen3
                    content = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL)
                    content = content.strip()
                    if content:
                        self._clear_provider_cooldown(provider_name)
                        logger.info(f"✅ Response from {provider_name}/{model} ({len(content)} chars)")
                        return content

            logger.warning(f"⚠️ Empty response from {provider_name}/{model}")
            return None

        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Timeout ({timeout}s) for {provider_name}/{model}")
            self._set_provider_cooldown(provider_name, "Timeout", 30)
            return None

        except requests.exceptions.RequestException as e:
            error_str = str(e)
            if "403" in error_str or "401" in error_str:
                logger.warning(f"🔒 Auth/region error for {provider_name}/{model}")
                self._set_provider_cooldown(provider_name, f"Auth error: {error_str[:80]}", 300)
            elif "429" in error_str:
                logger.warning(f"🚫 Rate limited for {provider_name}/{model}")
                self._set_provider_cooldown(provider_name, "Rate limit", 120)
            else:
                logger.warning(f"❌ Request error for {provider_name}/{model}: {error_str[:100]}")
                self._set_provider_cooldown(provider_name, f"Request error: {error_str[:80]}", 60)
            return None

        except Exception as e:
            logger.warning(f"❌ Unexpected error for {provider_name}/{model}: {str(e)[:100]}")
            return None

    def _call_cohere_sync(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """استدعاء Cohere API (متزامن)"""
        client = self._get_cohere_client()
        if not client:
            return None

        try:
            logger.info(f"🤖 Calling cohere/{model}")

            # Cohere V2 API يستخدم نفس تنسيق messages
            response = client.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if response and response.message and response.message.content:
                # استخراج النص من الرد
                content_blocks = response.message.content
                if isinstance(content_blocks, list):
                    text_parts = []
                    for block in content_blocks:
                        if hasattr(block, 'text'):
                            text_parts.append(block.text)
                        elif isinstance(block, dict) and 'text' in block:
                            text_parts.append(block['text'])
                    content = "".join(text_parts)
                elif isinstance(content_blocks, str):
                    content = content_blocks
                else:
                    content = str(content_blocks)

                if content:
                    content = content.strip()
                    self._clear_provider_cooldown("cohere")
                    logger.info(f"✅ Response from cohere/{model} ({len(content)} chars)")
                    return content

            logger.warning(f"⚠️ Empty response from cohere/{model}")
            return None

        except Exception as e:
            error_str = str(e)
            logger.warning(f"❌ Cohere error for {model}: {error_str[:100]}")
            if "429" in error_str or "rate" in error_str.lower():
                self._set_provider_cooldown("cohere", f"Rate limit: {error_str[:80]}", 120)
            else:
                self._set_provider_cooldown("cohere", f"Error: {error_str[:80]}", 60)
            return None

    def call_sync(
        self,
        messages: List[Dict[str, str]],
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = None,
    ) -> Optional[str]:
        """
        استدعاء AI مع تبديل تلقائي بين المزودين (متزامن)
        يجرب كل مسار بالترتيب لحد ما ينجح واحد
        """
        routes = self.get_model_routes(task_type)
        if not routes:
            logger.error("🚨 No available providers!")
            return None

        if timeout is None:
            timeout = FAST_TIMEOUT if task_type == "simple" else REQUEST_TIMEOUT

        for route in routes:
            provider = self.providers.get(route.provider_name)
            if not provider:
                continue

            if provider.provider_type == "openai_compatible":
                result = self._call_openai_compatible_sync(
                    provider_name=route.provider_name,
                    model=route.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            elif provider.provider_type == "cohere":
                result = self._call_cohere_sync(
                    model=route.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                continue

            if result:
                return result

        logger.error(f"🚨 All providers failed for task type: {task_type}")
        return None

    async def call_async(
        self,
        messages: List[Dict[str, str]],
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = None,
    ) -> Optional[str]:
        """استدعاء AI (غير متزامن - لا يحجب event loop)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.call_sync(
                messages=messages,
                task_type=task_type,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        )

    def call_with_system_prompt_sync(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = None,
    ) -> Optional[str]:
        """استدعاء AI مع system prompt منفصل (متزامن)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.call_sync(
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    async def call_with_system_prompt_async(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = None,
    ) -> Optional[str]:
        """استدعاء AI مع system prompt منفصل (غير متزامن)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.call_async(
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    # ═══════════════════════════════════════
    # Vision - معالجة الصور
    # ═══════════════════════════════════════

    def _call_vision_sync(
        self,
        provider_name: str,
        model: str,
        text_prompt: str,
        image_url: str = None,
        image_base64: str = None,
        temperature: float = 0.5,
        max_tokens: int = 1500,
    ) -> Optional[str]:
        """استدعاء نموذج رؤية (متزامن)"""
        provider = self.providers.get(provider_name)
        if not provider:
            return None

        # بناء رسالة المستخدم مع الصورة
        user_message: Dict[str, Any] = {
            "role": "user",
            "content": [],
        }

        user_message["content"].append({
            "type": "text",
            "text": text_prompt,
        })

        if image_url:
            user_message["content"].append({
                "type": "image_url",
                "image_url": {"url": image_url},
            })
        elif image_base64:
            user_message["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
            })

        messages = [user_message]

        return self._call_openai_compatible_sync(
            provider_name=provider_name,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=REQUEST_TIMEOUT,
        )

    async def analyze_image_async(
        self,
        text_prompt: str,
        image_url: str = None,
        image_base64: str = None,
        temperature: float = 0.5,
        max_tokens: int = 1500,
    ) -> Optional[str]:
        """تحليل صورة (غير متزامن)"""
        routes = self.get_model_routes("vision")
        if not routes:
            logger.error("🚨 No vision providers available!")
            return None

        loop = asyncio.get_event_loop()

        for route in routes:
            provider = self.providers.get(route.provider_name)
            if not provider or provider.provider_type != "openai_compatible":
                continue

            result = await loop.run_in_executor(
                None,
                lambda: self._call_vision_sync(
                    provider_name=route.provider_name,
                    model=route.model_id,
                    text_prompt=text_prompt,
                    image_url=image_url,
                    image_base64=image_base64,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            if result:
                return result

        logger.error("🚨 All vision providers failed")
        return None

    # ═══════════════════════════════════════
    # معلومات الحالة - Status Info
    # ═══════════════════════════════════════

    def get_status(self) -> str:
        """الحصول على حالة المزودين"""
        status_parts = []
        for name, provider in self.providers.items():
            available = "✅" if self._is_provider_available(name) else "❌"
            cooldown = ""
            if provider.cooldown_until > time.time():
                remaining = int(provider.cooldown_until - time.time())
                cooldown = f" (cooldown: {remaining}s)"
            status_parts.append(f"{available} {name}{cooldown}")

        return "\n".join(status_parts)

    def get_available_routes(self, task_type: str = "chat") -> str:
        """الحصول على المسارات المتاحة لنوع مهمة"""
        routes = self.get_model_routes(task_type)
        if not routes:
            return f"❌ No routes available for {task_type}"

        parts = []
        for r in routes:
            parts.append(f"  {r.priority + 1}. {r.provider_name}/{r.model_id}")
        return "\n".join(parts)


# ═══════════════════════════════════════
# Singleton Instance - نسخة واحدة من المدير
# ═══════════════════════════════════════

_manager_instance: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """الحصول على نسخة Provider Manager الوحيدة"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ProviderManager()
    return _manager_instance


# ═══════════════════════════════════════
# Helper Functions - دوال مساعدة
# ═══════════════════════════════════════

async def call_ai(
    prompt,
    system_prompt: str = "",
    task_type: str = "chat",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    prefer_arabic: bool = False,
) -> Optional[str]:
    """
    استدعاء AI عبر Provider Manager (غير متزامن)
    يدعم نص عادي أو قائمة رسائل (messages list)
    - لو prompt هو string: يتعامل كرسالة مستخدم عادية
    - لو prompt هو list: يتعامل كقائمة رسائل كاملة (مع سياق المحادثة)
    """
    if prefer_arabic and not system_prompt:
        system_prompt = "أنت 'My Bro' - مساعد ذكي شخصي. اسمك الوحيد My Bro ومفيش اسم تاني. لما حد يسألك مين أنت قول أنا My Bro. ماتقولش owo أو uwu أبداً. تجيب بالعربية الفصحى دائماً. اكتب كلام طبيعي وواضح من غير رموز غريبة. ماتستخدمش Markdown أبداً (لا *, **, #, |, ~). استخدم <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط بس."

    manager = get_provider_manager()

    # لو prompt قائمة رسائل (مع سياق المحادثة)
    if isinstance(prompt, list):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(prompt)
        return await manager.call_async(
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # لو prompt نص عادي
    return await manager.call_with_system_prompt_async(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type=task_type,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def call_ai_sync(
    prompt: str,
    system_prompt: str = "",
    task_type: str = "chat",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    prefer_arabic: bool = False,
) -> Optional[str]:
    """
    استدعاء AI عبر Provider Manager (متزامن)
    Compatible with the old ai_engine._call_ai_sync interface
    """
    if prefer_arabic and not system_prompt:
        system_prompt = "أنت 'My Bro' - مساعد ذكي شخصي. اسمك الوحيد My Bro ومفيش اسم تاني. لما حد يسألك مين أنت قول أنا My Bro. ماتقولش owo أو uwu أبداً. تجيب بالعربية الفصحى دائماً. اكتب كلام طبيعي وواضح من غير رموز غريبة. ماتستخدمش Markdown أبداً (لا *, **, #, |, ~). استخدم <b>عريض</b> <i>مائل</i> <code>كود</code> • نقاط بس."

    manager = get_provider_manager()
    return manager.call_with_system_prompt_sync(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type=task_type,
        temperature=temperature,
        max_tokens=max_tokens,
    )
