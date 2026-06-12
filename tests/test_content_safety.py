"""
Unit tests for content_safety.py

Tests the content safety module:
- check_query_safety() — unsafe queries are flagged
- Safe query pass-through — normal queries pass through
- Arabic content — test with Arabic queries
- _check_keywords() — keyword blocking logic
- _is_url() — URL detection
- _parse_safety_result() — VLM result parsing
- _has_suspicious_words() — suspicious word detection
- _timeout_blocked() — timeout blocking behavior
- Configuration — SAFETY_THRESHOLD, CONTENT_SAFETY_ENABLED
"""

import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# ── Mock only telegram (needed by admin.py) and provider_manager AI calls ──
# content_safety.py imports provider_manager at function call time for AI checks
# We don't mock sys.modules['provider_manager'] to avoid cross-test contamination
# Instead, we mock the specific functions at the test level

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

# Import content_safety
import content_safety
from content_safety import (
    check_query_safety,
    _check_keywords,
    _is_url,
    _parse_safety_result,
    _has_suspicious_words,
    _timeout_blocked,
    SAFETY_THRESHOLD,
    CONTENT_SAFETY_ENABLED,
    BLOCKED_KEYWORDS_AR,
    BLOCKED_KEYWORDS_EN,
    BLOCKED_PATTERNS,
    check_search_results_safety,
)


class TestCheckKeywords(unittest.TestCase):
    """Tests for _check_keywords() — keyword blocking logic"""

    def test_empty_query_not_blocked(self):
        self.assertFalse(_check_keywords("")[0])

    def test_none_query_not_blocked(self):
        self.assertFalse(_check_keywords(None)[0])

    def test_safe_english_query(self):
        self.assertFalse(_check_keywords("how to learn python programming")[0])

    def test_safe_arabic_query(self):
        self.assertFalse(_check_keywords("كيف اتعلم البرمجة")[0])

    def test_blocked_english_keyword(self):
        is_blocked, reason = _check_keywords("porn videos")
        self.assertTrue(is_blocked)
        self.assertIn("porn", reason.lower())

    def test_blocked_arabic_keyword(self):
        is_blocked, reason = _check_keywords("سكس")
        self.assertTrue(is_blocked)
        self.assertIn("كلمة ممنوعة", reason)

    def test_blocked_keyword_case_insensitive(self):
        self.assertTrue(_check_keywords("PORN VIDEOS")[0])

    def test_blocked_keyword_mixed_case(self):
        self.assertTrue(_check_keywords("Porn Videos")[0])

    def test_blocked_keyword_in_sentence(self):
        self.assertTrue(_check_keywords("I want to watch porn tonight")[0])

    def test_arabic_keyword_in_sentence(self):
        self.assertTrue(_check_keywords("عايز اشوف سكس فيديو")[0])

    def test_nsfw_blocked(self):
        self.assertTrue(_check_keywords("nsfw content")[0])

    def test_onlyfans_blocked(self):
        self.assertTrue(_check_keywords("onlyfans videos")[0])

    def test_hentai_blocked(self):
        self.assertTrue(_check_keywords("hentai anime")[0])

    def test_18plus_blocked(self):
        self.assertTrue(_check_keywords("18+ content")[0])

    def test_xxx_blocked(self):
        self.assertTrue(_check_keywords("xxx movies")[0])

    def test_nude_blocked(self):
        self.assertTrue(_check_keywords("nude photos")[0])

    def test_multiple_blocked_keywords(self):
        self.assertTrue(_check_keywords("porn xxx nude")[0])

    def test_whitespace_only_not_blocked(self):
        self.assertFalse(_check_keywords("   ".strip())[0])


class TestCheckQuerySafety(unittest.TestCase):
    """Tests for check_query_safety() — full query safety check"""

    def setUp(self):
        content_safety.CONTENT_SAFETY_ENABLED = True

    def test_safety_disabled_passes_everything(self):
        content_safety.CONTENT_SAFETY_ENABLED = False
        result = asyncio.run(check_query_safety("porn videos"))
        self.assertTrue(result[0])
        content_safety.CONTENT_SAFETY_ENABLED = True

    def test_empty_query_passes(self):
        self.assertTrue(asyncio.run(check_query_safety(""))[0])

    def test_none_query_passes(self):
        self.assertTrue(asyncio.run(check_query_safety(None))[0])

    def test_whitespace_query_passes(self):
        self.assertTrue(asyncio.run(check_query_safety("   "))[0])

    def test_safe_english_query_passes(self):
        self.assertTrue(asyncio.run(check_query_safety("latest technology news"))[0])

    def test_safe_arabic_query_passes(self):
        self.assertTrue(asyncio.run(check_query_safety("أخبار التكنولوجيا اليوم"))[0])

    def test_blocked_keyword_fails(self):
        self.assertFalse(asyncio.run(check_query_safety("porn videos"))[0])

    def test_blocked_arabic_keyword_fails(self):
        self.assertFalse(asyncio.run(check_query_safety("سكس"))[0])

    def test_url_skips_ai_check(self):
        # URL with no blocked keywords should pass
        self.assertTrue(asyncio.run(check_query_safety("https://www.youtube.com/watch?v=abc123"))[0])

    def test_url_with_blocked_keyword_fails(self):
        self.assertFalse(asyncio.run(check_query_safety("https://example.com/porn"))[0])

    def test_returns_reason_when_blocked(self):
        result = asyncio.run(check_query_safety("porn videos"))
        self.assertFalse(result[0])
        self.assertTrue(len(result[1]) > 0)

    def test_returns_empty_reason_when_safe(self):
        result = asyncio.run(check_query_safety("technology news"))
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")


class TestArabicContentSafety(unittest.TestCase):
    """Tests for Arabic content safety"""

    def test_arabic_explicit_blocked(self):
        blocked_queries = [
            "سكس", "بورنو", "عري", "إباحي", "اباحية",
            "بزاز", "طيز", "نيك", "اغتصاب", "تحرش",
            "فاحش", "شرموط", "عاهرة",
        ]
        for query in blocked_queries:
            self.assertTrue(_check_keywords(query)[0], f"Should be blocked: {query}")

    def test_arabic_safe_queries_pass(self):
        safe_queries = [
            "أخبار اليوم", "كيف أتعلم البرمجة", "وصفة طبخ مصري",
            "أفضل جامعات مصر", "تحليل اقتصادي", "تعليم الأطفال",
            "طبخ سمك", "فن التصوير",
        ]
        for query in safe_queries:
            self.assertFalse(_check_keywords(query)[0], f"Should NOT be blocked: {query}")

    def test_mixed_arabic_english_blocked(self):
        self.assertTrue(_check_keywords("porn سكس")[0])

    def test_mixed_arabic_english_safe(self):
        self.assertFalse(_check_keywords("Python البرمجة")[0])


class TestIsUrl(unittest.TestCase):
    """Tests for _is_url() — URL detection"""

    def test_http_url(self):
        self.assertTrue(_is_url("http://example.com"))

    def test_https_url(self):
        self.assertTrue(_is_url("https://example.com"))

    def test_url_with_path(self):
        self.assertTrue(_is_url("https://www.youtube.com/watch?v=abc"))

    def test_not_url(self):
        self.assertFalse(_is_url("hello world"))

    def test_empty_string(self):
        self.assertFalse(_is_url(""))

    def test_url_with_spaces(self):
        self.assertTrue(_is_url("  https://example.com"))


class TestParseSafetyResult(unittest.TestCase):
    """Tests for _parse_safety_result() — VLM result parsing"""

    def test_safe_result(self):
        result = "SCORE: 95\nVERDICT: SAFE\nREASON: Normal content"
        score, is_safe, reason = _parse_safety_result(result)
        self.assertTrue(is_safe)
        self.assertEqual(score, 95)
        self.assertIn("Normal content", reason)

    def test_unsafe_result(self):
        result = "SCORE: 20\nVERDICT: UNSAFE\nREASON: Explicit content detected"
        score, is_safe, reason = _parse_safety_result(result)
        self.assertFalse(is_safe)
        self.assertEqual(score, 20)
        self.assertIn("Explicit content detected", reason)

    def test_high_score_safe(self):
        score, is_safe, _ = _parse_safety_result("SCORE: 85\nSome text")
        self.assertTrue(is_safe)

    def test_low_score_unsafe(self):
        score, is_safe, _ = _parse_safety_result("SCORE: 30\nSome text")
        self.assertFalse(is_safe)

    def test_score_below_threshold_unsafe(self):
        result = f"SCORE: {SAFETY_THRESHOLD - 5}\nVERDICT: SAFE\nREASON: Borderline"
        score, is_safe, _ = _parse_safety_result(result)
        self.assertFalse(is_safe)

    def test_score_at_threshold_safe(self):
        result = f"SCORE: {SAFETY_THRESHOLD}\nVERDICT: SAFE\nREASON: OK"
        score, is_safe, _ = _parse_safety_result(result)
        self.assertTrue(is_safe)

    def test_score_clamped_to_100(self):
        score, _, _ = _parse_safety_result("SCORE: 150\nVERDICT: SAFE\nREASON: test")
        self.assertEqual(score, 100)

    def test_negative_score_not_parsed(self):
        """Negative scores don't match the \\d+ regex, so score defaults to 100"""
        score, is_safe, _ = _parse_safety_result("SCORE: -10\nVERDICT: UNSAFE\nREASON: test")
        self.assertFalse(is_safe)
        self.assertEqual(score, 100)

    def test_no_score_defaults_to_100(self):
        score, _, _ = _parse_safety_result("VERDICT: SAFE\nREASON: Looks good")
        self.assertEqual(score, 100)
        self.assertTrue(_parse_safety_result("VERDICT: SAFE\nREASON: Looks good")[1])

    def test_verdict_unsafe_overrides_score(self):
        score, is_safe, _ = _parse_safety_result("SCORE: 90\nVERDICT: UNSAFE\nREASON: Bad")
        self.assertFalse(is_safe)


class TestHasSuspiciousWords(unittest.TestCase):
    """Tests for _has_suspicious_words()"""

    def test_suspicious_english(self):
        self.assertTrue(_has_suspicious_words("hot dance video"))
        self.assertTrue(_has_suspicious_words("bikini photoshoot"))

    def test_suspicious_arabic(self):
        self.assertTrue(_has_suspicious_words("رقص شرقي"))
        self.assertTrue(_has_suspicious_words("بنت جميلة"))

    def test_normal_text_not_suspicious(self):
        self.assertFalse(_has_suspicious_words("python programming tutorial"))
        self.assertFalse(_has_suspicious_words("أخبار التكنولوجيا"))

    def test_empty_text_not_suspicious(self):
        self.assertFalse(_has_suspicious_words(""))


class TestTimeoutBlocked(unittest.TestCase):
    """Tests for _timeout_blocked()"""

    def test_always_returns_false(self):
        self.assertFalse(_timeout_blocked())
        self.assertFalse(_timeout_blocked("some reason"))


class TestSafetyConfiguration(unittest.TestCase):
    """Tests for safety configuration constants"""

    def test_safety_threshold_is_numeric(self):
        self.assertIsInstance(SAFETY_THRESHOLD, int)

    def test_safety_threshold_range(self):
        self.assertGreaterEqual(SAFETY_THRESHOLD, 0)
        self.assertLessEqual(SAFETY_THRESHOLD, 100)

    def test_content_safety_enabled_is_bool(self):
        self.assertIsInstance(CONTENT_SAFETY_ENABLED, bool)

    def test_blocked_keywords_ar_is_list(self):
        self.assertIsInstance(BLOCKED_KEYWORDS_AR, list)
        self.assertGreater(len(BLOCKED_KEYWORDS_AR), 0)

    def test_blocked_keywords_en_is_list(self):
        self.assertIsInstance(BLOCKED_KEYWORDS_EN, list)
        self.assertGreater(len(BLOCKED_KEYWORDS_EN), 0)

    def test_blocked_patterns_is_list(self):
        self.assertIsInstance(BLOCKED_PATTERNS, list)
        self.assertGreater(len(BLOCKED_PATTERNS), 0)
        for pattern in BLOCKED_PATTERNS:
            self.assertTrue(hasattr(pattern, 'search'))


class TestCheckSearchResultsSafety(unittest.TestCase):
    """Tests for check_search_results_safety() — search result filtering"""

    def setUp(self):
        content_safety.CONTENT_SAFETY_ENABLED = True

    def test_empty_results_pass_through(self):
        self.assertEqual(asyncio.run(check_search_results_safety([])), [])

    def test_safe_results_pass_through(self):
        results = [
            {"title": "Python Tutorial", "description": "Learn Python", "channel": "CodeAcademy", "tags": ["python"]},
        ]
        safe = asyncio.run(check_search_results_safety(results))
        self.assertEqual(len(safe), 1)

    def test_blocked_result_filtered_out(self):
        results = [
            {"title": "Python Tutorial", "description": "Learn Python", "channel": "CodeAcademy", "tags": ["python"]},
            {"title": "Porn Videos", "description": "Adult content", "channel": "XXX", "tags": ["adult"]},
        ]
        safe = asyncio.run(check_search_results_safety(results))
        self.assertEqual(len(safe), 1)
        self.assertEqual(safe[0]["title"], "Python Tutorial")

    def test_safety_disabled_passes_all(self):
        content_safety.CONTENT_SAFETY_ENABLED = False
        results = [
            {"title": "Porn Videos", "description": "Adult content", "channel": "XXX", "tags": ["adult"]},
        ]
        safe = asyncio.run(check_search_results_safety(results))
        self.assertEqual(len(safe), 1)
        content_safety.CONTENT_SAFETY_ENABLED = True

    def test_all_blocked_returns_empty(self):
        results = [
            {"title": "Porn Video 1", "description": "nsfw", "channel": "XXX", "tags": []},
            {"title": "Porn Video 2", "description": "adult", "channel": "XXX", "tags": []},
        ]
        safe = asyncio.run(check_search_results_safety(results))
        self.assertEqual(len(safe), 0)


if __name__ == "__main__":
    unittest.main()
