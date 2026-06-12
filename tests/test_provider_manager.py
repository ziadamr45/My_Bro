"""
Unit tests for provider_manager.py

Tests the AI provider fallback system:
- Provider selection — picks the right provider based on model config
- Fallback chain — when one provider fails, falls back to the next
- Model configuration — FREE_CHAT_MODELS and PREMIUM_CHAT_MODELS have expected structure
- API key lookup — each model has the right API key
- ModelRoute dataclass
- Cooldown system
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# ── Mock only telegram (needed by admin.py which is imported at runtime) ──
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

# Set API keys in environment so ProviderManager can configure providers
os.environ.setdefault("MISTRAL_API_KEY", "test-mistral-key")
os.environ.setdefault("SAMBANOVA_API_KEY", "test-sambanova-key")

import config

# Ensure keys are set on config module
if not config.MISTRAL_API_KEY:
    config.MISTRAL_API_KEY = "test-mistral-key"
if not config.SAMBANOVA_API_KEY:
    config.SAMBANOVA_API_KEY = "test-sambanova-key"

# Set NVIDIA keys for route availability tests
_nvidia_key_map = {
    "NVIDIA_DEEPSEEK_V4_FLASH_KEY": "test-nvidia-ds-flash-key",
    "NVIDIA_DEEPSEEK_V4_PRO_KEY": "test-nvidia-ds-pro-key",
    "NVIDIA_KIMI_K26_KEY": "test-nvidia-kimi-key",
    "NVIDIA_MINIMAX_M27_KEY": "test-nvidia-minimax-key",
    "NVIDIA_GLM_51_KEY": "test-nvidia-glm-key",
    "NVIDIA_LLAMA_33_70B_KEY": "test-nvidia-llama-key",
    "NVIDIA_STEP_37_FLASH_KEY": "test-nvidia-step-key",
    "NVIDIA_LLAMA_32_90B_VISION_KEY": "test-nvidia-vision-key",
    "NVIDIA_NEMOTRON_NANO_VL_KEY": "test-nvidia-nemotron-key",
    "NVIDIA_SD35_LARGE_KEY": "test-nvidia-sd-key",
    "NVIDIA_FLUX_KONTEXT_KEY": "test-nvidia-flux-key",
    "NVIDIA_QWEN_IMAGE_KEY": "test-nvidia-qwen-img-key",
    "NVIDIA_QWEN_IMAGE_EDIT_KEY": "test-nvidia-qwen-edit-key",
}
for attr, val in _nvidia_key_map.items():
    if not getattr(config, attr, ""):
        setattr(config, attr, val)

# Rebuild model lists with the test keys
def _rebuild_model_lists_with_test_keys():
    key_map = {
        "deepseek-ai/deepseek-v4-flash": config.NVIDIA_DEEPSEEK_V4_FLASH_KEY,
        "deepseek-ai/deepseek-v4-pro": config.NVIDIA_DEEPSEEK_V4_PRO_KEY,
        "moonshotai/kimi-k2.6": config.NVIDIA_KIMI_K26_KEY,
        "minimaxai/minimax-m2.7": config.NVIDIA_MINIMAX_M27_KEY,
        "thudm/glm-5.1": config.NVIDIA_GLM_51_KEY,
        "meta/llama-3.3-70b-instruct": config.NVIDIA_LLAMA_33_70B_KEY,
        "stepfun-ai/step-3.7-flash": config.NVIDIA_STEP_37_FLASH_KEY,
        "meta/llama-3.2-90b-vision-instruct": config.NVIDIA_LLAMA_32_90B_VISION_KEY,
        "nvidia/nemotron-nano-12b-v2-vl": config.NVIDIA_NEMOTRON_NANO_VL_KEY,
        "stabilityai/stable-diffusion-3.5-large": config.NVIDIA_SD35_LARGE_KEY,
        "black-forest-labs/flux.1-kontext-dev": config.NVIDIA_FLUX_KONTEXT_KEY,
        "black-forest-labs/flux.1-dev": config.NVIDIA_QWEN_IMAGE_KEY,
    }

    def _patch_list(model_list):
        result = []
        for entry in model_list:
            entry = dict(entry)
            model_id = entry.get("model", "")
            if entry.get("provider") in ("nvidia", "nvidia_genai") and model_id in key_map:
                entry["api_key"] = key_map[model_id]
            result.append(entry)
        return result

    config.FREE_CHAT_MODELS = _patch_list(config.FREE_CHAT_MODELS)
    config.PREMIUM_CHAT_MODELS = _patch_list(config.PREMIUM_CHAT_MODELS)
    config.FREE_SIMPLE_MODELS = _patch_list(config.FREE_SIMPLE_MODELS)
    config.PREMIUM_SIMPLE_MODELS = _patch_list(config.PREMIUM_SIMPLE_MODELS)
    config.FREE_DEEP_SEARCH_MODELS = _patch_list(config.FREE_DEEP_SEARCH_MODELS)
    config.PREMIUM_DEEP_SEARCH_MODELS = _patch_list(config.PREMIUM_DEEP_SEARCH_MODELS)
    config.FREE_CODING_MODELS = _patch_list(config.FREE_CODING_MODELS)
    config.PREMIUM_CODING_MODELS = _patch_list(config.PREMIUM_CODING_MODELS)
    config.FREE_SUMMARY_MODELS = _patch_list(config.FREE_SUMMARY_MODELS)
    config.PREMIUM_SUMMARY_MODELS = _patch_list(config.PREMIUM_SUMMARY_MODELS)
    config.FREE_VISION_MODELS = _patch_list(config.FREE_VISION_MODELS)
    config.PREMIUM_VISION_MODELS = _patch_list(config.PREMIUM_VISION_MODELS)
    config.PREMIUM_IMAGE_GEN_MODELS = _patch_list(config.PREMIUM_IMAGE_GEN_MODELS)
    config.PREMIUM_IMAGE_EDIT_MODELS = _patch_list(config.PREMIUM_IMAGE_EDIT_MODELS)
    config.CHAT_MODELS = config.PREMIUM_CHAT_MODELS
    config.SIMPLE_MODELS = config.PREMIUM_SIMPLE_MODELS
    config.DEEP_SEARCH_MODELS = config.PREMIUM_DEEP_SEARCH_MODELS
    config.CODING_MODELS = config.PREMIUM_CODING_MODELS
    config.SUMMARY_MODELS = config.PREMIUM_SUMMARY_MODELS
    config.VISION_MODELS = config.PREMIUM_VISION_MODELS

_rebuild_model_lists_with_test_keys()

# Import provider_manager
import provider_manager
from provider_manager import ProviderManager, ModelRoute

# Also patch provider_manager's own references to the model lists
# since it does `from config import FREE_CHAT_MODELS, ...` at import time
provider_manager.FREE_CHAT_MODELS = config.FREE_CHAT_MODELS
provider_manager.PREMIUM_CHAT_MODELS = config.PREMIUM_CHAT_MODELS
provider_manager.FREE_SIMPLE_MODELS = config.FREE_SIMPLE_MODELS
provider_manager.PREMIUM_SIMPLE_MODELS = config.PREMIUM_SIMPLE_MODELS
provider_manager.FREE_DEEP_SEARCH_MODELS = config.FREE_DEEP_SEARCH_MODELS
provider_manager.PREMIUM_DEEP_SEARCH_MODELS = config.PREMIUM_DEEP_SEARCH_MODELS
provider_manager.FREE_CODING_MODELS = config.FREE_CODING_MODELS
provider_manager.PREMIUM_CODING_MODELS = config.PREMIUM_CODING_MODELS
provider_manager.FREE_SUMMARY_MODELS = config.FREE_SUMMARY_MODELS
provider_manager.PREMIUM_SUMMARY_MODELS = config.PREMIUM_SUMMARY_MODELS
provider_manager.FREE_VISION_MODELS = config.FREE_VISION_MODELS
provider_manager.PREMIUM_VISION_MODELS = config.PREMIUM_VISION_MODELS
provider_manager.PREMIUM_IMAGE_GEN_MODELS = config.PREMIUM_IMAGE_GEN_MODELS
provider_manager.PREMIUM_IMAGE_EDIT_MODELS = config.PREMIUM_IMAGE_EDIT_MODELS
provider_manager.CHAT_MODELS = config.CHAT_MODELS
provider_manager.SIMPLE_MODELS = config.SIMPLE_MODELS
provider_manager.DEEP_SEARCH_MODELS = config.DEEP_SEARCH_MODELS
provider_manager.CODING_MODELS = config.CODING_MODELS
provider_manager.SUMMARY_MODELS = config.SUMMARY_MODELS
provider_manager.VISION_MODELS = config.VISION_MODELS


class TestModelRoute(unittest.TestCase):
    """Tests for ModelRoute dataclass"""

    def test_create_model_route(self):
        route = ModelRoute(
            provider_name="nvidia",
            model_id="meta/llama-3.3-70b-instruct",
            api_key="nvapi-test-key",
            priority=0,
        )
        self.assertEqual(route.provider_name, "nvidia")
        self.assertEqual(route.model_id, "meta/llama-3.3-70b-instruct")
        self.assertEqual(route.api_key, "nvapi-test-key")
        self.assertEqual(route.priority, 0)

    def test_default_api_key_empty(self):
        route = ModelRoute(provider_name="mistral", model_id="mistral-small-latest", priority=1)
        self.assertEqual(route.api_key, "")

    def test_default_priority_zero(self):
        route = ModelRoute(provider_name="mistral", model_id="test-model")
        self.assertEqual(route.priority, 0)


class TestFreeChatModelsStructure(unittest.TestCase):
    """Tests for FREE_CHAT_MODELS configuration"""

    def test_is_list(self):
        self.assertIsInstance(config.FREE_CHAT_MODELS, list)

    def test_not_empty(self):
        self.assertGreater(len(config.FREE_CHAT_MODELS), 0)

    def test_each_entry_has_provider(self):
        for model_config in config.FREE_CHAT_MODELS:
            self.assertIn("provider", model_config)

    def test_each_entry_has_model(self):
        for model_config in config.FREE_CHAT_MODELS:
            self.assertIn("model", model_config)

    def test_valid_providers(self):
        valid_providers = {"nvidia", "mistral", "sambanova", "nvidia_genai"}
        for model_config in config.FREE_CHAT_MODELS:
            self.assertIn(model_config["provider"], valid_providers)

    def test_nvidia_models_have_api_key(self):
        for model_config in config.FREE_CHAT_MODELS:
            if model_config["provider"] == "nvidia":
                self.assertIn("api_key", model_config)


class TestPremiumChatModelsStructure(unittest.TestCase):
    """Tests for PREMIUM_CHAT_MODELS configuration"""

    def test_is_list(self):
        self.assertIsInstance(config.PREMIUM_CHAT_MODELS, list)

    def test_not_empty(self):
        self.assertGreater(len(config.PREMIUM_CHAT_MODELS), 0)

    def test_each_entry_has_provider(self):
        for model_config in config.PREMIUM_CHAT_MODELS:
            self.assertIn("provider", model_config)

    def test_each_entry_has_model(self):
        for model_config in config.PREMIUM_CHAT_MODELS:
            self.assertIn("model", model_config)

    def test_nvidia_models_have_api_key(self):
        for model_config in config.PREMIUM_CHAT_MODELS:
            if model_config["provider"] == "nvidia":
                self.assertIn("api_key", model_config)

    def test_different_from_free(self):
        if config.FREE_CHAT_MODELS and config.PREMIUM_CHAT_MODELS:
            free_first = config.FREE_CHAT_MODELS[0]["model"]
            premium_first = config.PREMIUM_CHAT_MODELS[0]["model"]
            self.assertNotEqual(free_first, premium_first)


class TestAllModelListsStructure(unittest.TestCase):
    """Tests for all model list configurations"""

    def _validate_model_list(self, model_list, name):
        self.assertIsInstance(model_list, list, f"{name} should be a list")
        for i, model_config in enumerate(model_list):
            self.assertIn("provider", model_config, f"{name}[{i}] missing 'provider'")
            self.assertIn("model", model_config, f"{name}[{i}] missing 'model'")

    def test_free_simple_models(self):
        self._validate_model_list(config.FREE_SIMPLE_MODELS, "FREE_SIMPLE_MODELS")

    def test_premium_simple_models(self):
        self._validate_model_list(config.PREMIUM_SIMPLE_MODELS, "PREMIUM_SIMPLE_MODELS")

    def test_free_deep_search_models(self):
        self._validate_model_list(config.FREE_DEEP_SEARCH_MODELS, "FREE_DEEP_SEARCH_MODELS")

    def test_premium_deep_search_models(self):
        self._validate_model_list(config.PREMIUM_DEEP_SEARCH_MODELS, "PREMIUM_DEEP_SEARCH_MODELS")

    def test_free_coding_models(self):
        self._validate_model_list(config.FREE_CODING_MODELS, "FREE_CODING_MODELS")

    def test_premium_coding_models(self):
        self._validate_model_list(config.PREMIUM_CODING_MODELS, "PREMIUM_CODING_MODELS")

    def test_free_summary_models(self):
        self._validate_model_list(config.FREE_SUMMARY_MODELS, "FREE_SUMMARY_MODELS")

    def test_premium_summary_models(self):
        self._validate_model_list(config.PREMIUM_SUMMARY_MODELS, "PREMIUM_SUMMARY_MODELS")

    def test_vision_models(self):
        self._validate_model_list(config.FREE_VISION_MODELS, "FREE_VISION_MODELS")
        self._validate_model_list(config.PREMIUM_VISION_MODELS, "PREMIUM_VISION_MODELS")

    def test_image_gen_models(self):
        self._validate_model_list(config.PREMIUM_IMAGE_GEN_MODELS, "PREMIUM_IMAGE_GEN_MODELS")

    def test_image_edit_models(self):
        self._validate_model_list(config.PREMIUM_IMAGE_EDIT_MODELS, "PREMIUM_IMAGE_EDIT_MODELS")


class TestProviderManagerInit(unittest.TestCase):
    """Tests for ProviderManager initialization"""

    def test_creates_instance(self):
        pm = ProviderManager()
        self.assertIsNotNone(pm)

    def test_has_providers_dict(self):
        pm = ProviderManager()
        self.assertIsInstance(pm.providers, dict)

    def test_has_nvidia_provider(self):
        pm = ProviderManager()
        self.assertIn("nvidia", pm.providers)

    def test_nvidia_base_url(self):
        pm = ProviderManager()
        self.assertEqual(pm.providers["nvidia"]["base_url"], config.NVIDIA_BASE_URL)

    def test_has_cooldowns_dict(self):
        pm = ProviderManager()
        self.assertIsInstance(pm._model_cooldowns, dict)

    def test_mistral_provider_with_key(self):
        pm = ProviderManager()
        self.assertIn("mistral", pm.providers)

    def test_sambanova_provider_with_key(self):
        pm = ProviderManager()
        self.assertIn("sambanova", pm.providers)


class TestProviderManagerApiKeys(unittest.TestCase):
    """Tests for API key lookup logic"""

    def setUp(self):
        self.pm = ProviderManager()

    def test_per_model_api_key_priority(self):
        model_config = {"api_key": "model-specific-key"}
        key = self.pm._get_api_key("nvidia", model_config)
        self.assertEqual(key, "model-specific-key")

    def test_provider_level_key_fallback(self):
        self.pm.providers["test_provider"] = {"api_key": "provider-key", "base_url": "https://test.com"}
        key = self.pm._get_api_key("test_provider")
        self.assertEqual(key, "provider-key")

    def test_mistral_provider_has_key(self):
        key = self.pm._get_api_key("mistral")
        self.assertTrue(key)

    def test_sambanova_provider_has_key(self):
        key = self.pm._get_api_key("sambanova")
        self.assertTrue(key)

    def test_empty_model_config_falls_back(self):
        key = self.pm._get_api_key("mistral", {})
        self.assertTrue(key)

    def test_nvidia_no_provider_key(self):
        key = self.pm._get_api_key("nvidia")
        self.assertEqual(key, "")


class TestProviderAvailability(unittest.TestCase):
    """Tests for provider and model availability checks"""

    def setUp(self):
        self.pm = ProviderManager()

    def test_nvidia_is_available(self):
        self.assertTrue(self.pm._is_provider_available("nvidia"))

    def test_mistral_is_available(self):
        self.assertTrue(self.pm._is_provider_available("mistral"))

    def test_nonexistent_provider_not_available(self):
        self.assertFalse(self.pm._is_provider_available("nonexistent_provider"))

    def test_model_available_when_no_cooldown(self):
        self.assertTrue(self.pm._is_model_available("test-model"))

    def test_model_not_available_on_cooldown(self):
        self.pm._set_model_cooldown("test-model", "error", cooldown_seconds=300)
        self.assertFalse(self.pm._is_model_available("test-model"))

    def test_model_available_after_cooldown_expires(self):
        self.pm._model_cooldowns["test-model"] = time.time() - 1
        self.assertTrue(self.pm._is_model_available("test-model"))

    def test_ignore_cooldown_flag(self):
        self.pm._set_model_cooldown("test-model", "error", cooldown_seconds=300)
        self.assertTrue(self.pm._is_model_available("test-model", ignore_cooldown=True))


class TestCooldownSystem(unittest.TestCase):
    """Tests for model cooldown system"""

    def setUp(self):
        self.pm = ProviderManager()

    def test_set_cooldown(self):
        self.pm._set_model_cooldown("model-1", "test error", cooldown_seconds=30)
        self.assertIn("model-1", self.pm._model_cooldowns)

    def test_rate_limit_cooldown_longer(self):
        self.pm._set_model_cooldown("model-1", "429 rate limit exceeded", cooldown_seconds=10)
        self.assertGreater(self.pm._model_cooldowns["model-1"], time.time() + 50)

    def test_auth_error_cooldown_longer(self):
        self.pm._set_model_cooldown("model-1", "401 unauthorized", cooldown_seconds=10)
        self.assertGreater(self.pm._model_cooldowns["model-1"], time.time() + 100)

    def test_clear_cooldown(self):
        self.pm._set_model_cooldown("model-1", "error", cooldown_seconds=30)
        self.pm._clear_model_cooldown("model-1")
        self.assertNotIn("model-1", self.pm._model_cooldowns)

    def test_clear_nonexistent_cooldown(self):
        self.pm._clear_model_cooldown("nonexistent-model")


class TestGetModelRoutes(unittest.TestCase):
    """Tests for get_model_routes() — provider selection"""

    def setUp(self):
        self.pm = ProviderManager()
        self.pm._model_cooldowns.clear()

    def test_free_user_gets_free_routes(self):
        routes = self.pm.get_model_routes("chat", user_plan="free")
        self.assertGreater(len(routes), 0)
        for route in routes:
            self.assertIsInstance(route, ModelRoute)

    def test_premium_user_gets_premium_routes(self):
        routes = self.pm.get_model_routes("chat", user_plan="premium")
        self.assertGreater(len(routes), 0)

    def test_admin_gets_premium_routes(self):
        routes = self.pm.get_model_routes("chat", user_plan="admin")
        self.assertGreater(len(routes), 0)

    def test_routes_have_increasing_priority(self):
        routes = self.pm.get_model_routes("chat", user_plan="premium")
        for i, route in enumerate(routes):
            self.assertEqual(route.priority, i)

    def test_cooldown_models_excluded(self):
        first_model = config.PREMIUM_CHAT_MODELS[0]["model"]
        self.pm._set_model_cooldown(first_model, "test", cooldown_seconds=300)
        routes = self.pm.get_model_routes("chat", user_plan="premium")
        for route in routes:
            self.assertNotEqual(route.model_id, first_model)

    def test_cooldown_models_included_with_flag(self):
        first_model = config.PREMIUM_CHAT_MODELS[0]["model"]
        self.pm._set_model_cooldown(first_model, "test", cooldown_seconds=300)
        routes = self.pm.get_model_routes("chat", ignore_cooldown=True, user_plan="premium")
        model_ids = [r.model_id for r in routes]
        self.assertIn(first_model, model_ids)

    def test_nvidia_models_without_api_key_excluded(self):
        routes = self.pm.get_model_routes("chat", user_plan="free")
        for route in routes:
            if route.provider_name == "nvidia":
                self.assertTrue(route.api_key)

    def test_default_plan_is_free(self):
        routes = self.pm.get_model_routes("chat")
        self.assertGreater(len(routes), 0)
        self.assertEqual(routes[0].model_id, "mistral-small-latest")

    def test_unknown_task_type_defaults_to_chat(self):
        routes = self.pm.get_model_routes("unknown_task", user_plan="premium")
        self.assertGreater(len(routes), 0)

    def test_free_routes_contain_mistral_small(self):
        routes = self.pm.get_model_routes("chat", user_plan="free")
        model_ids = [r.model_id for r in routes]
        self.assertIn("mistral-small-latest", model_ids)

    def test_premium_routes_contain_mistral_large(self):
        routes = self.pm.get_model_routes("chat", user_plan="premium")
        model_ids = [r.model_id for r in routes]
        self.assertIn("mistral-large-latest", model_ids)


class TestGetModelListForTask(unittest.TestCase):
    """Tests for _get_model_list_for_task() — verifies correct list selection by task and plan"""

    def setUp(self):
        self.pm = ProviderManager()

    def _validate_returned_list(self, result, expected_first_model):
        """Helper: validate that returned model list is non-empty and starts with expected model"""
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["model"], expected_first_model)

    def test_chat_task_free(self):
        """Free chat should return a list starting with mistral-small-latest"""
        result = self.pm._get_model_list_for_task("chat", "free")
        self._validate_returned_list(result, "mistral-small-latest")

    def test_chat_task_premium(self):
        """Premium chat should return a list starting with mistral-large-latest"""
        result = self.pm._get_model_list_for_task("chat", "premium")
        self._validate_returned_list(result, "mistral-large-latest")

    def test_simple_task_free(self):
        """Free simple should return a list starting with mistral-small-latest"""
        result = self.pm._get_model_list_for_task("simple", "free")
        self._validate_returned_list(result, "mistral-small-latest")

    def test_simple_task_premium(self):
        """Premium simple should return a list starting with mistral-large-latest"""
        result = self.pm._get_model_list_for_task("simple", "premium")
        self._validate_returned_list(result, "mistral-large-latest")

    def test_deep_search_task_free(self):
        """Free deep search should return a list with nvidia models"""
        result = self.pm._get_model_list_for_task("deep_search", "free")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_coding_task_free(self):
        """Free coding should return a non-empty list"""
        result = self.pm._get_model_list_for_task("coding", "free")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_summary_task_free(self):
        """Free summary should return a non-empty list"""
        result = self.pm._get_model_list_for_task("summary", "free")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_vision_task_free(self):
        """Free vision should return a non-empty list with nvidia_genai models"""
        result = self.pm._get_model_list_for_task("vision", "free")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_image_gen_always_premium(self):
        """Image gen should always return premium models regardless of plan"""
        result_free = self.pm._get_model_list_for_task("image_gen", "free")
        result_premium = self.pm._get_model_list_for_task("image_gen", "premium")
        # Both should be the same (premium-only feature)
        self.assertEqual(result_free, result_premium)
        # Should contain nvidia_genai provider
        providers = [m["provider"] for m in result_free]
        self.assertIn("nvidia_genai", providers)

    def test_image_edit_always_premium(self):
        """Image edit should always return premium models regardless of plan"""
        result_free = self.pm._get_model_list_for_task("image_edit", "free")
        result_premium = self.pm._get_model_list_for_task("image_edit", "premium")
        self.assertEqual(result_free, result_premium)
        providers = [m["provider"] for m in result_free]
        self.assertIn("nvidia_genai", providers)

    def test_admin_gets_premium_routes(self):
        """Admin should get the same models as premium for chat"""
        result_admin = self.pm._get_model_list_for_task("chat", "admin")
        result_premium = self.pm._get_model_list_for_task("chat", "premium")
        self.assertEqual(result_admin, result_premium)

    def test_free_and_premium_chat_differ(self):
        """Free and premium chat model lists should be different"""
        result_free = self.pm._get_model_list_for_task("chat", "free")
        result_premium = self.pm._get_model_list_for_task("chat", "premium")
        self.assertNotEqual(result_free, result_premium)


class TestFallbackChain(unittest.TestCase):
    """Tests for provider fallback behavior"""

    def setUp(self):
        self.pm = ProviderManager()
        self.pm._model_cooldowns.clear()

    def test_call_sync_returns_none_when_all_fail(self):
        with patch.object(self.pm, '_call_provider_sync', return_value=None):
            result = self.pm.call_sync(
                messages=[{"role": "user", "content": "test"}],
                task_type="chat",
                user_plan="premium",
            )
            self.assertIsNone(result)

    def test_call_sync_returns_first_success(self):
        with patch.object(self.pm, '_call_provider_sync', return_value="Hello!"):
            result = self.pm.call_sync(
                messages=[{"role": "user", "content": "test"}],
                task_type="chat",
                user_plan="premium",
            )
            self.assertEqual(result, "Hello!")

    def test_call_sync_fallback_on_failure(self):
        call_count = 0

        def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return None if call_count <= 2 else "success"

        with patch.object(self.pm, '_try_parallel_routes', return_value=(None, None)), \
             patch.object(self.pm, '_call_provider_sync', side_effect=mock_call):
            result = self.pm.call_sync(
                messages=[{"role": "user", "content": "test"}],
                task_type="chat",
                user_plan="premium",
            )
            self.assertEqual(result, "success")

    def test_call_sync_ignores_cooldown_on_all_fail(self):
        with patch.object(self.pm, '_call_provider_sync', return_value=None):
            with patch.object(self.pm, 'get_model_routes') as mock_routes:
                route1 = ModelRoute(provider_name="mistral", model_id="test", api_key="key", priority=0)
                mock_routes.side_effect = [[], [route1]]
                result = self.pm.call_sync(
                    messages=[{"role": "user", "content": "test"}],
                    task_type="chat",
                    user_plan="premium",
                )
                self.assertIsNone(result)
                self.assertEqual(mock_routes.call_count, 2)


class TestGetUserPlan(unittest.TestCase):
    """Tests for _get_user_plan() — user plan resolution"""

    def setUp(self):
        self.pm = ProviderManager()

    @patch('admin.is_admin', return_value=True)
    @patch('premium.is_premium', return_value=True)
    def test_admin_user(self, mock_premium, mock_admin):
        self.assertEqual(self.pm._get_user_plan(1), "admin")

    @patch('admin.is_admin', return_value=False)
    @patch('premium.is_premium', return_value=True)
    def test_premium_user(self, mock_premium, mock_admin):
        self.assertEqual(self.pm._get_user_plan(123), "premium")

    @patch('admin.is_admin', return_value=False)
    @patch('premium.is_premium', return_value=False)
    def test_free_user(self, mock_premium, mock_admin):
        self.assertEqual(self.pm._get_user_plan(999), "free")

    @patch('admin.is_admin', return_value=True)
    @patch('premium.is_premium', return_value=True)
    def test_admin_takes_priority_over_premium(self, mock_premium, mock_admin):
        self.assertEqual(self.pm._get_user_plan(1), "admin")


if __name__ == "__main__":
    unittest.main()
