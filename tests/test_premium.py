"""
Unit tests for premium.py

Tests the premium subscription system:
- PLAN_LIMITS dict structure and values
- check_limit() — free users have daily limits, premium users have higher/no limits
- increment_usage() — usage counter incrementing
- is_premium() — premium status detection
- premium_required_message() — message generation for premium-gated features
- Expiry logic — premium expiration detection
- get_user_plan() — plan detection with caching
- limit_reached_message() — daily limit reached message
- get_remaining_usage() — remaining usage display
"""

import sys
import time as _time
import unittest
from unittest.mock import MagicMock, patch

# ── Mock only telegram (needed by admin.py) ──
# All other mocking is done per-test with @patch to avoid cross-test contamination
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

# Import premium
import premium
from premium import (
    PLAN_LIMITS,
    check_limit,
    increment_usage,
    is_premium,
    premium_required_message,
    limit_reached_message,
    get_user_plan,
    get_remaining_usage,
    get_premium_info,
    grant_premium,
    revoke_premium,
    _plan_cache,
    _usage_cache,
    CAIRO_TZ,
)


class TestPlanLimitsStructure(unittest.TestCase):
    """Tests for PLAN_LIMITS dict structure and values"""

    def test_has_three_plans(self):
        self.assertIn("free", PLAN_LIMITS)
        self.assertIn("premium", PLAN_LIMITS)
        self.assertIn("premium_plus", PLAN_LIMITS)

    def test_free_plan_has_daily_limits(self):
        free = PLAN_LIMITS["free"]
        self.assertGreater(free["ai_messages_per_day"], 0)
        self.assertGreater(free["pdf_analyses_per_day"], 0)
        self.assertGreater(free["image_analyses_per_day"], 0)
        self.assertGreater(free["youtube_summaries_per_day"], 0)
        self.assertGreater(free["searches_per_day"], 0)

    def test_free_plan_premium_features_zero(self):
        free = PLAN_LIMITS["free"]
        self.assertEqual(free["deep_searches_per_day"], 0)
        self.assertEqual(free["image_generations_per_day"], 0)
        self.assertEqual(free["image_edits_per_day"], 0)
        self.assertEqual(free["downloads_per_day"], 0)
        self.assertEqual(free["video_searches_per_day"], 0)
        self.assertEqual(free["audio_searches_per_day"], 0)

    def test_free_plan_boolean_features_false(self):
        free = PLAN_LIMITS["free"]
        self.assertFalse(free["study_mode"])
        self.assertFalse(free["long_term_memory"])
        self.assertFalse(free["voice_assistant"])
        self.assertFalse(free["premium_models"])
        self.assertFalse(free["workspace"])
        self.assertFalse(free["smart_alerts"])
        self.assertFalse(free["image_gen"])
        self.assertFalse(free["image_edit"])

    def test_premium_plan_unlimited(self):
        premium_plan = PLAN_LIMITS["premium"]
        numeric_keys = [
            "ai_messages_per_day", "pdf_analyses_per_day",
            "image_analyses_per_day", "youtube_summaries_per_day",
            "searches_per_day", "deep_searches_per_day",
            "image_generations_per_day", "image_edits_per_day",
            "downloads_per_day", "video_searches_per_day",
            "audio_searches_per_day", "photo_searches_per_day",
        ]
        for key in numeric_keys:
            self.assertEqual(premium_plan[key], -1, f"Premium plan {key} should be -1")

    def test_premium_plan_boolean_features_true(self):
        premium_plan = PLAN_LIMITS["premium"]
        self.assertTrue(premium_plan["study_mode"])
        self.assertTrue(premium_plan["long_term_memory"])
        self.assertTrue(premium_plan["voice_assistant"])
        self.assertTrue(premium_plan["premium_models"])
        self.assertTrue(premium_plan["workspace"])
        self.assertTrue(premium_plan["smart_alerts"])
        self.assertTrue(premium_plan["image_gen"])
        self.assertTrue(premium_plan["image_edit"])

    def test_premium_plus_same_as_premium(self):
        p = PLAN_LIMITS["premium"]
        pp = PLAN_LIMITS["premium_plus"]
        for key in p:
            self.assertEqual(pp[key], p[key], f"premium_plus {key} should match premium")

    def test_all_plans_have_same_keys(self):
        free_keys = set(PLAN_LIMITS["free"].keys())
        premium_keys = set(PLAN_LIMITS["premium"].keys())
        plus_keys = set(PLAN_LIMITS["premium_plus"].keys())
        self.assertEqual(free_keys, premium_keys)
        self.assertEqual(free_keys, plus_keys)


class TestCheckLimit(unittest.TestCase):
    """Tests for check_limit() — limit checking logic"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 5, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_under_limit(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertTrue(result["allowed"])
        self.assertGreater(result["remaining"], 0)
        self.assertEqual(result["plan"], "free")

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 20, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_at_limit(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["remaining"], 0)

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 25, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_over_limit(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["remaining"], 0)

    @patch.object(premium, 'get_user_plan', return_value='premium')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 100, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_premium_user_unlimited(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["remaining"], -1)
        self.assertEqual(result["limit"], -1)

    @patch.object(premium, 'get_user_plan', return_value='premium')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_premium_user_deep_search_allowed(self, mock_usage, mock_plan):
        result = check_limit(123, "deep_searches_per_day")
        self.assertTrue(result["allowed"])

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_deep_search_not_allowed(self, mock_usage, mock_plan):
        result = check_limit(123, "deep_searches_per_day")
        self.assertFalse(result["allowed"])

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_boolean_feature_free(self, mock_usage, mock_plan):
        result = check_limit(123, "study_mode")
        self.assertFalse(result["allowed"])

    @patch.object(premium, 'get_user_plan', return_value='premium')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_boolean_feature_premium(self, mock_usage, mock_plan):
        result = check_limit(123, "study_mode")
        self.assertTrue(result["allowed"])

    @patch('admin.is_admin', return_value=True)
    def test_admin_bypass(self, mock_is_admin):
        result = check_limit(1, "ai_messages_per_day")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["remaining"], -1)
        self.assertEqual(result["plan"], "admin")

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_remaining_calculation(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertEqual(result["limit"], 20)
        self.assertEqual(result["remaining"], 20)

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 15, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_remaining_with_usage(self, mock_usage, mock_plan):
        result = check_limit(123, "ai_messages_per_day")
        self.assertEqual(result["remaining"], 5)


class TestIncrementUsage(unittest.TestCase):
    """Tests for increment_usage() — usage counter incrementing"""

    def setUp(self):
        _usage_cache.clear()

    @patch.object(premium, '_ensure_usage_row')
    @patch.object(premium, '_get_today_key', return_value='2024-01-15')
    @patch.object(premium, '_execute')
    def test_increment_valid_feature(self, mock_execute, mock_key, mock_ensure):
        increment_usage(123, "ai_messages")
        mock_execute.assert_called_once()
        query = mock_execute.call_args[0][0]
        self.assertIn("UPDATE usage_tracking", query)
        self.assertIn("ai_messages", query)

    @patch.object(premium, '_ensure_usage_row')
    @patch.object(premium, '_get_today_key', return_value='2024-01-15')
    @patch.object(premium, '_execute')
    def test_increment_invalid_feature_ignored(self, mock_execute, mock_key, mock_ensure):
        increment_usage(123, "invalid_feature_xyz")
        mock_execute.assert_not_called()

    @patch.object(premium, '_ensure_usage_row')
    @patch.object(premium, '_get_today_key', return_value='2024-01-15')
    @patch.object(premium, '_execute')
    def test_increment_clears_usage_cache(self, mock_execute, mock_key, mock_ensure):
        _usage_cache[123] = ({"ai_messages": 5}, _time.time() + 100)
        increment_usage(123, "ai_messages")
        self.assertNotIn(123, _usage_cache)

    @patch.object(premium, '_ensure_usage_row')
    @patch.object(premium, '_get_today_key', return_value='2024-01-15')
    @patch.object(premium, '_execute')
    def test_increment_with_custom_count(self, mock_execute, mock_key, mock_ensure):
        increment_usage(123, "pdf_analyses", count=3)
        mock_execute.assert_called_once()
        query = mock_execute.call_args[0][0]
        self.assertIn("pdf_analyses = pdf_analyses + 3", query)

    @patch.object(premium, '_ensure_usage_row')
    @patch.object(premium, '_get_today_key', return_value='2024-01-15')
    @patch.object(premium, '_execute')
    def test_all_valid_features(self, mock_execute, mock_key, mock_ensure):
        valid_features = [
            "ai_messages", "pdf_analyses", "image_analyses",
            "youtube_summaries", "searches", "deep_searches",
            "image_generations", "image_edits",
        ]
        for feature in valid_features:
            mock_execute.reset_mock()
            increment_usage(123, feature)
            mock_execute.assert_called_once()


class TestIsPremium(unittest.TestCase):
    """Tests for is_premium() — premium status detection"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, 'get_user_plan', return_value='free')
    def test_free_user_is_not_premium(self, mock_plan):
        self.assertFalse(is_premium(123))

    @patch.object(premium, 'get_user_plan', return_value='premium')
    def test_premium_user_is_premium(self, mock_plan):
        self.assertTrue(is_premium(123))

    @patch.object(premium, 'get_user_plan', return_value='premium_plus')
    def test_premium_plus_is_premium(self, mock_plan):
        self.assertTrue(is_premium(123))

    @patch.object(premium, 'get_user_plan', return_value='unknown_plan')
    def test_unknown_plan_not_premium(self, mock_plan):
        self.assertFalse(is_premium(123))


class TestPremiumRequiredMessage(unittest.TestCase):
    """Tests for premium_required_message() — message generation"""

    def test_arabic_message_contains_feature(self):
        msg = premium_required_message("Deep Search", lang="ar")
        self.assertIn("Deep Search", msg)
        self.assertIn("Premium", msg)

    def test_english_message_contains_feature(self):
        msg = premium_required_message("Deep Search", lang="en")
        self.assertIn("Deep Search", msg)
        self.assertIn("Premium", msg)

    def test_arabic_message_has_free_plan_info(self):
        msg = premium_required_message("Test Feature", lang="ar")
        self.assertIn("20", msg)

    def test_english_message_has_free_plan_info(self):
        msg = premium_required_message("Test Feature", lang="en")
        self.assertIn("20", msg)

    def test_arabic_message_has_developer_contact(self):
        msg = premium_required_message("Test", lang="ar")
        self.assertIn("wa.me", msg)

    def test_english_message_has_developer_contact(self):
        msg = premium_required_message("Test", lang="en")
        self.assertIn("wa.me", msg)

    def test_default_language_is_arabic(self):
        msg = premium_required_message("Test")
        self.assertIn("مشتركين", msg)


class TestLimitReachedMessage(unittest.TestCase):
    """Tests for limit_reached_message() — daily limit reached message"""

    def test_arabic_message(self):
        msg = limit_reached_message("AI Messages", remaining=0, limit=20, lang="ar")
        self.assertIn("AI Messages", msg)
        self.assertIn("20", msg)

    def test_english_message(self):
        msg = limit_reached_message("AI Messages", remaining=0, limit=20, lang="en")
        self.assertIn("AI Messages", msg)
        self.assertIn("20", msg)

    def test_message_contains_premium_cta(self):
        msg = limit_reached_message("AI Messages", remaining=0, limit=20, lang="en")
        self.assertIn("Premium", msg)


class TestGetUserPlan(unittest.TestCase):
    """Tests for get_user_plan() — plan detection with caching"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, '_execute', return_value=None)
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_returns_free_by_default(self, mock_ensure, mock_pg, mock_exec):
        plan = get_user_plan(999)
        self.assertEqual(plan, "free")

    @patch.object(premium, '_execute', return_value=("premium",))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_returns_plan_from_db(self, mock_ensure, mock_pg, mock_exec):
        plan = get_user_plan(123)
        self.assertEqual(plan, "premium")

    @patch.object(premium, '_execute', return_value=("premium",))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_caches_result(self, mock_ensure, mock_pg, mock_exec):
        plan1 = get_user_plan(123)
        plan2 = get_user_plan(123)
        self.assertEqual(plan1, "premium")
        self.assertEqual(plan2, "premium")
        self.assertEqual(mock_exec.call_count, 1)

    @patch.object(premium, '_execute', return_value=("custom_plan",))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_unknown_plan_returns_from_db(self, mock_ensure, mock_pg, mock_exec):
        plan = get_user_plan(456)
        self.assertEqual(plan, "custom_plan")


class TestPremiumExpiryLogic(unittest.TestCase):
    """Tests for premium expiration detection"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, '_execute', return_value=("free", None, None, None))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_get_premium_info_free_user(self, mock_ensure, mock_pg, mock_exec):
        info = get_premium_info(123)
        self.assertFalse(info["is_premium"])
        self.assertEqual(info["remaining_days"], -1)
        self.assertEqual(info["plan"], "free")

    @patch.object(premium, '_execute', return_value=("premium", "2024-01-01T00:00:00", None, "admin"))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_get_premium_info_premium_no_expiry(self, mock_ensure, mock_pg, mock_exec):
        info = get_premium_info(123)
        self.assertTrue(info["is_premium"])
        self.assertEqual(info["remaining_days"], 0)  # lifetime
        self.assertIsNone(info["premium_expires"])

    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_get_premium_info_premium_with_future_expiry(self, mock_ensure, mock_pg, mock_exec):
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(CAIRO_TZ) + timedelta(days=30)).isoformat()
        mock_exec.return_value = ("premium", "2024-01-01T00:00:00", future, "admin")
        info = get_premium_info(123)
        self.assertTrue(info["is_premium"])
        self.assertGreater(info["remaining_days"], 0)

    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_get_premium_info_premium_with_past_expiry(self, mock_ensure, mock_pg, mock_exec):
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(CAIRO_TZ) - timedelta(days=5)).isoformat()
        mock_exec.return_value = ("premium", "2024-01-01T00:00:00", past, "admin")
        info = get_premium_info(123)
        self.assertTrue(info["is_premium"])
        self.assertEqual(info["remaining_days"], 0)

    @patch.object(premium, '_execute', return_value=("free", None, None, None))
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_get_premium_info_contains_all_expected_keys(self, mock_ensure, mock_pg, mock_exec):
        info = get_premium_info(123)
        for key in ["plan", "is_premium", "premium_since", "premium_expires",
                     "granted_by", "expires_display", "remaining_days"]:
            self.assertIn(key, info, f"Missing key: {key}")


class TestGetRemainingUsage(unittest.TestCase):
    """Tests for get_remaining_usage() — remaining usage display"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, 'get_user_plan', return_value='premium')
    def test_premium_user_unlimited_display(self, mock_plan):
        result = get_remaining_usage(123, lang="ar")
        self.assertIn("غير محدود", result)

    @patch.object(premium, 'get_user_plan', return_value='premium')
    def test_premium_user_unlimited_english(self, mock_plan):
        result = get_remaining_usage(123, lang="en")
        self.assertIn("unlimited", result)

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 5, 'pdf_analyses': 1, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_shows_remaining(self, mock_usage, mock_plan):
        result = get_remaining_usage(123, lang="en")
        self.assertIn("15", result)

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, 'get_usage', return_value={'ai_messages': 0, 'pdf_analyses': 0, 'image_analyses': 0, 'youtube_summaries': 0, 'searches': 0, 'deep_searches': 0})
    def test_free_user_arabic_display(self, mock_usage, mock_plan):
        result = get_remaining_usage(123, lang="ar")
        self.assertIn("20", result)


class TestGrantRevokePremium(unittest.TestCase):
    """Tests for grant_premium() and revoke_premium()"""

    def setUp(self):
        _plan_cache.clear()
        _usage_cache.clear()

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_grant_premium_clears_cache(self, mock_ensure, mock_pg, mock_exec, mock_plan):
        _plan_cache[123] = ("free", _time.time() + 60)
        grant_premium(123, granted_by="admin")
        self.assertNotIn(123, _plan_cache)

    @patch.object(premium, 'get_user_plan', return_value='premium')
    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    def test_revoke_premium_clears_cache(self, mock_pg, mock_exec, mock_plan):
        _plan_cache[123] = ("premium", _time.time() + 60)
        revoke_premium(123)
        self.assertNotIn(123, _plan_cache)

    @patch.object(premium, 'get_user_plan', return_value='free')
    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    @patch('memory._ensure_user_in_db')
    def test_grant_premium_calls_execute(self, mock_ensure, mock_pg, mock_exec, mock_plan):
        mock_exec.return_value = None
        grant_premium(123, granted_by="admin")
        self.assertGreater(mock_exec.call_count, 0)

    @patch.object(premium, 'get_user_plan', return_value='premium')
    @patch.object(premium, '_execute')
    @patch.object(premium, '_is_postgres', return_value=False)
    def test_revoke_premium_calls_execute(self, mock_pg, mock_exec, mock_plan):
        revoke_premium(123)
        self.assertGreater(mock_exec.call_count, 0)


if __name__ == "__main__":
    unittest.main()
