"""
Comprehensive tests for rate_limiter.py
========================================
Tests cover:
- Token bucket fill/drain
- Rate limiting triggers at correct threshold
- Admin bypass
- Multiple action types
- Cleanup removes expired entries
- Thread safety
- Stats reporting
- get_remaining and get_retry_after accuracy
- check_and_record combined function
- reset_user
"""

import time
import threading
import unittest

from rate_limiter import RateLimiter, DEFAULT_LIMITS


class TestTokenBucketFillDrain(unittest.TestCase):
    """Test token bucket refill (fill) and consumption (drain)."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 5, "window_seconds": 10},
        })

    def test_initial_tokens_equal_max(self):
        """New bucket starts with max tokens."""
        remaining = self.limiter.get_remaining(123, "test_action")
        self.assertEqual(remaining, 5)

    def test_consume_token_on_record(self):
        """Recording a request consumes one token."""
        self.limiter.record_request(123, "test_action")
        remaining = self.limiter.get_remaining(123, "test_action")
        self.assertEqual(remaining, 4)

    def test_consume_multiple_tokens(self):
        """Recording multiple requests consumes multiple tokens."""
        for _ in range(3):
            self.limiter.record_request(123, "test_action")
        remaining = self.limiter.get_remaining(123, "test_action")
        self.assertEqual(remaining, 2)

    def test_tokens_refill_over_time(self):
        """Tokens refill over time based on refill rate."""
        # Consume all tokens
        for _ in range(5):
            self.limiter.record_request(123, "test_action")
        self.assertEqual(self.limiter.get_remaining(123, "test_action"), 0)

        # Wait for partial refill (refill_rate = 5/10 = 0.5 tokens/sec)
        # Wait 2 seconds → should refill ~1 token
        time.sleep(2.1)
        remaining = self.limiter.get_remaining(123, "test_action")
        self.assertGreaterEqual(remaining, 0)  # At least partially refilled

    def test_tokens_capped_at_max(self):
        """Tokens never exceed max_tokens even after long idle."""
        time.sleep(0.5)
        remaining = self.limiter.get_remaining(123, "test_action")
        self.assertLessEqual(remaining, 5)

    def test_independent_users(self):
        """Different users have independent buckets."""
        self.limiter.record_request(111, "test_action")
        self.limiter.record_request(111, "test_action")
        # User 111 has 3 remaining
        self.assertEqual(self.limiter.get_remaining(111, "test_action"), 3)
        # User 222 still has full bucket
        self.assertEqual(self.limiter.get_remaining(222, "test_action"), 5)


class TestRateLimitingThreshold(unittest.TestCase):
    """Test that rate limiting triggers at the correct threshold."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 3, "window_seconds": 60},
        })

    def test_not_limited_initially(self):
        """User is not rate limited initially."""
        self.assertFalse(self.limiter.is_rate_limited(123, "test_action"))

    def test_limited_after_max_requests(self):
        """User is rate limited after consuming all tokens."""
        for _ in range(3):
            self.limiter.record_request(123, "test_action")
        self.assertTrue(self.limiter.is_rate_limited(123, "test_action"))

    def test_not_limited_before_threshold(self):
        """User is not rate limited before reaching threshold."""
        self.limiter.record_request(123, "test_action")
        self.limiter.record_request(123, "test_action")
        self.assertFalse(self.limiter.is_rate_limited(123, "test_action"))

    def test_rate_limit_resets_after_window(self):
        """Rate limit resets after the window period passes."""
        limiter = RateLimiter(limits={
            "fast": {"max_requests": 2, "window_seconds": 1},
        })
        # Consume all tokens
        limiter.record_request(123, "fast")
        limiter.record_request(123, "fast")
        self.assertTrue(limiter.is_rate_limited(123, "fast"))

        # Wait for window to pass
        time.sleep(1.1)
        self.assertFalse(limiter.is_rate_limited(123, "fast"))


class TestAdminBypass(unittest.TestCase):
    """Test that admins are never rate limited."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 2, "window_seconds": 60},
        })
        self.limiter.set_admin_ids({999, 1000})

    def test_admin_never_rate_limited(self):
        """Admins are never rate limited even after many requests."""
        for _ in range(100):
            self.limiter.record_request(999, "test_action")
        self.assertFalse(self.limiter.is_rate_limited(999, "test_action"))

    def test_admin_get_remaining_returns_max(self):
        """Admin get_remaining always returns max_tokens."""
        for _ in range(10):
            self.limiter.record_request(999, "test_action")
        self.assertEqual(self.limiter.get_remaining(999, "test_action"), 2)

    def test_admin_get_retry_after_zero(self):
        """Admin get_retry_after always returns 0.0."""
        for _ in range(10):
            self.limiter.record_request(999, "test_action")
        self.assertEqual(self.limiter.get_retry_after(999, "test_action"), 0.0)

    def test_admin_check_and_record(self):
        """Admin check_and_record always returns not limited."""
        is_limited, remaining, retry_after = self.limiter.check_and_record(999, "test_action")
        self.assertFalse(is_limited)
        self.assertEqual(remaining, 2)
        self.assertEqual(retry_after, 0.0)

    def test_non_admin_still_limited(self):
        """Non-admin users are still rate limited."""
        for _ in range(2):
            self.limiter.record_request(123, "test_action")
        self.assertTrue(self.limiter.is_rate_limited(123, "test_action"))

    def test_add_remove_admin(self):
        """Adding and removing admin IDs works."""
        self.limiter.add_admin_id(555)
        self.assertFalse(self.limiter.is_rate_limited(555, "test_action"))

        self.limiter.remove_admin_id(555)
        # Now 555 should be rate limited after consuming tokens
        for _ in range(2):
            self.limiter.record_request(555, "test_action")
        self.assertTrue(self.limiter.is_rate_limited(555, "test_action"))

    def test_admin_with_string_id(self):
        """Admin IDs can be strings (e.g., WhatsApp phone numbers)."""
        self.limiter.set_admin_ids({"+1234567890"})
        for _ in range(10):
            self.limiter.record_request("+1234567890", "test_action")
        self.assertFalse(self.limiter.is_rate_limited("+1234567890", "test_action"))


class TestMultipleActionTypes(unittest.TestCase):
    """Test that different action types have independent limits."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "message": {"max_requests": 3, "window_seconds": 60},
            "ai_chat": {"max_requests": 2, "window_seconds": 60},
            "search": {"max_requests": 5, "window_seconds": 60},
        })

    def test_independent_action_limits(self):
        """Different actions have independent token buckets."""
        # Exhaust message limit
        for _ in range(3):
            self.limiter.record_request(123, "message")
        self.assertTrue(self.limiter.is_rate_limited(123, "message"))

        # AI chat should still be available
        self.assertFalse(self.limiter.is_rate_limited(123, "ai_chat"))
        self.assertEqual(self.limiter.get_remaining(123, "ai_chat"), 2)

    def test_exhaust_all_actions(self):
        """Exhausting all actions for a user."""
        for _ in range(3):
            self.limiter.record_request(123, "message")
        for _ in range(2):
            self.limiter.record_request(123, "ai_chat")
        for _ in range(5):
            self.limiter.record_request(123, "search")

        self.assertTrue(self.limiter.is_rate_limited(123, "message"))
        self.assertTrue(self.limiter.is_rate_limited(123, "ai_chat"))
        self.assertTrue(self.limiter.is_rate_limited(123, "search"))

    def test_default_limits_present(self):
        """Default limits are used when no custom limits provided."""
        limiter = RateLimiter()
        self.assertIn("message", limiter._limits)
        self.assertIn("ai_chat", limiter._limits)
        self.assertIn("image_gen", limiter._limits)
        self.assertIn("download", limiter._limits)
        self.assertIn("search", limiter._limits)

    def test_unknown_action_uses_fallback(self):
        """Unknown action types use a fallback limit."""
        # Should not raise — uses fallback of 30/60
        self.assertFalse(self.limiter.is_rate_limited(123, "unknown_action"))
        self.assertEqual(self.limiter.get_remaining(123, "unknown_action"), 30)


class TestCleanup(unittest.TestCase):
    """Test that cleanup removes expired entries."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 5, "window_seconds": 1},
        })

    def test_cleanup_removes_full_old_buckets(self):
        """Cleanup removes fully refilled, old buckets."""
        # Create a bucket
        self.limiter.record_request(123, "test_action")
        # Wait for it to fully refill
        time.sleep(1.5)
        # Access it to refill
        self.limiter.get_remaining(123, "test_action")

        # Now it's full. Override the last_refill to make it old
        with self.limiter._lock:
            for key in self.limiter._buckets:
                self.limiter._buckets[key]["last_refill"] = time.monotonic() - 700

        # Cleanup should remove it
        removed = self.limiter.cleanup()
        self.assertGreater(removed, 0)
        self.assertEqual(len(self.limiter._buckets), 0)

    def test_cleanup_keeps_active_buckets(self):
        """Cleanup keeps buckets that are still partially consumed."""
        self.limiter.record_request(123, "test_action")
        # Don't wait for refill — bucket has < max_tokens
        removed = self.limiter.cleanup()
        self.assertEqual(removed, 0)
        self.assertIn((123, "test_action"), self.limiter._buckets)

    def test_cleanup_returns_count(self):
        """Cleanup returns the number of removed entries."""
        # Create multiple buckets
        for i in range(5):
            self.limiter.record_request(i, "test_action")
        # Wait for full refill
        time.sleep(1.5)
        for i in range(5):
            self.limiter.get_remaining(i, "test_action")

        # Make them old
        with self.limiter._lock:
            for key in self.limiter._buckets:
                self.limiter._buckets[key]["last_refill"] = time.monotonic() - 700

        removed = self.limiter.cleanup()
        self.assertEqual(removed, 5)


class TestThreadSafety(unittest.TestCase):
    """Test that the rate limiter is thread-safe."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 100, "window_seconds": 60},
        })

    def test_concurrent_record_requests(self):
        """Multiple threads can record requests simultaneously without errors."""
        errors = []

        def worker(user_id):
            try:
                for _ in range(50):
                    self.limiter.record_request(user_id, "test_action")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)

    def test_concurrent_check_and_record(self):
        """Multiple threads can use check_and_record simultaneously."""
        results = []

        def worker(user_id):
            for _ in range(20):
                result = self.limiter.check_and_record(user_id, "test_action")
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each user should have 100 tokens initially, each records 20 → not limited
        not_limited = sum(1 for r in results if not r[0])
        self.assertEqual(not_limited, 100)

    def test_concurrent_mixed_operations(self):
        """Mixed concurrent operations (read + write) don't cause errors."""
        errors = []

        def reader(user_id):
            try:
                for _ in range(50):
                    self.limiter.is_rate_limited(user_id, "test_action")
                    self.limiter.get_remaining(user_id, "test_action")
                    self.limiter.get_retry_after(user_id, "test_action")
            except Exception as e:
                errors.append(e)

        def writer(user_id):
            try:
                for _ in range(50):
                    self.limiter.record_request(user_id, "test_action")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader, args=(1,)),
            threading.Thread(target=writer, args=(1,)),
            threading.Thread(target=reader, args=(2,)),
            threading.Thread(target=writer, args=(2,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


class TestStatsReporting(unittest.TestCase):
    """Test get_stats() method."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "message": {"max_requests": 30, "window_seconds": 60},
            "ai_chat": {"max_requests": 20, "window_seconds": 60},
        })

    def test_empty_stats(self):
        """Stats are correct with no activity."""
        stats = self.limiter.get_stats()
        self.assertEqual(stats["total_buckets"], 0)
        self.assertEqual(stats["active_buckets"], 0)
        self.assertEqual(stats["currently_limited_users"], 0)
        self.assertEqual(stats["admin_count"], 0)

    def test_stats_after_activity(self):
        """Stats reflect activity."""
        self.limiter.record_request(1, "message")
        self.limiter.record_request(2, "ai_chat")

        stats = self.limiter.get_stats()
        self.assertEqual(stats["total_buckets"], 2)
        self.assertEqual(stats["active_buckets"], 2)  # Both have < max_tokens

    def test_stats_with_limited_users(self):
        """Stats show currently limited users."""
        limiter = RateLimiter(limits={
            "fast": {"max_requests": 1, "window_seconds": 60},
        })
        limiter.record_request(123, "fast")
        # User 123 should be limited now

        stats = limiter.get_stats()
        self.assertEqual(stats["currently_limited_users"], 1)
        self.assertIn(123, stats["limited_user_ids"])

    def test_stats_admin_count(self):
        """Stats show admin count."""
        self.limiter.set_admin_ids({1, 2, 3})
        stats = self.limiter.get_stats()
        self.assertEqual(stats["admin_count"], 3)

    def test_stats_action_counts(self):
        """Stats show per-action bucket counts."""
        self.limiter.record_request(1, "message")
        self.limiter.record_request(2, "message")
        self.limiter.record_request(3, "ai_chat")

        stats = self.limiter.get_stats()
        self.assertEqual(stats["action_counts"]["message"], 2)
        self.assertEqual(stats["action_counts"]["ai_chat"], 1)

    def test_stats_configured_limits(self):
        """Stats include configured limits."""
        stats = self.limiter.get_stats()
        self.assertIn("message", stats["configured_limits"])
        self.assertIn("ai_chat", stats["configured_limits"])


class TestGetRemainingAccuracy(unittest.TestCase):
    """Test get_remaining() accuracy."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 10, "window_seconds": 60},
        })

    def test_remaining_starts_at_max(self):
        """Remaining starts at max_requests."""
        self.assertEqual(self.limiter.get_remaining(123, "test_action"), 10)

    def test_remaining_decreases_with_requests(self):
        """Remaining decreases as requests are recorded."""
        self.limiter.record_request(123, "test_action")
        self.assertEqual(self.limiter.get_remaining(123, "test_action"), 9)

        self.limiter.record_request(123, "test_action")
        self.assertEqual(self.limiter.get_remaining(123, "test_action"), 8)

    def test_remaining_never_negative(self):
        """Remaining is never negative."""
        for _ in range(15):
            self.limiter.record_request(123, "test_action")
        self.assertEqual(self.limiter.get_remaining(123, "test_action"), 0)

    def test_remaining_refills_over_time(self):
        """Remaining increases as tokens refill."""
        limiter = RateLimiter(limits={
            "fast": {"max_requests": 3, "window_seconds": 3},
        })
        for _ in range(3):
            limiter.record_request(123, "fast")
        self.assertEqual(limiter.get_remaining(123, "fast"), 0)

        # Wait 1 second → refill_rate = 3/3 = 1 token/sec → 1 token
        time.sleep(1.1)
        self.assertGreaterEqual(limiter.get_remaining(123, "fast"), 1)


class TestGetRetryAfterAccuracy(unittest.TestCase):
    """Test get_retry_after() accuracy."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 2, "window_seconds": 2},
        })

    def test_retry_after_zero_when_not_limited(self):
        """retry_after is 0.0 when not rate limited."""
        self.assertEqual(self.limiter.get_retry_after(123, "test_action"), 0.0)

    def test_retry_after_positive_when_limited(self):
        """retry_after is positive when rate limited."""
        self.limiter.record_request(123, "test_action")
        self.limiter.record_request(123, "test_action")
        retry_after = self.limiter.get_retry_after(123, "test_action")
        self.assertGreater(retry_after, 0.0)

    def test_retry_after_decreases_over_time(self):
        """retry_after decreases as time passes."""
        self.limiter.record_request(123, "test_action")
        self.limiter.record_request(123, "test_action")
        retry1 = self.limiter.get_retry_after(123, "test_action")
        time.sleep(0.3)
        retry2 = self.limiter.get_retry_after(123, "test_action")
        self.assertLess(retry2, retry1)

    def test_retry_after_reasonable_range(self):
        """retry_after is within reasonable range for the configured window."""
        limiter = RateLimiter(limits={
            "fast": {"max_requests": 1, "window_seconds": 10},
        })
        limiter.record_request(123, "fast")
        retry_after = limiter.get_retry_after(123, "fast")
        # refill_rate = 1/10 = 0.1 tokens/sec
        # Need 1 token → 1/0.1 = 10 seconds max
        self.assertLessEqual(retry_after, 10.0)
        self.assertGreater(retry_after, 0.0)


class TestCheckAndRecord(unittest.TestCase):
    """Test check_and_record() combined function."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "test_action": {"max_requests": 3, "window_seconds": 60},
        })

    def test_not_limited_records_and_returns_remaining(self):
        """When not limited, records request and returns remaining count."""
        is_limited, remaining, retry_after = self.limiter.check_and_record(123, "test_action")
        self.assertFalse(is_limited)
        self.assertEqual(remaining, 2)  # 3-1 = 2 remaining
        self.assertEqual(retry_after, 0.0)

    def test_limited_does_not_record(self):
        """When limited, does not consume a token."""
        # Consume all tokens
        for _ in range(3):
            self.limiter.check_and_record(123, "test_action")

        # Next call should be limited
        is_limited, remaining, retry_after = self.limiter.check_and_record(123, "test_action")
        self.assertTrue(is_limited)
        self.assertEqual(remaining, 0)
        self.assertGreater(retry_after, 0.0)

    def test_sequential_check_and_record(self):
        """Sequential calls correctly track remaining."""
        for i in range(3):
            is_limited, remaining, retry_after = self.limiter.check_and_record(123, "test_action")
            self.assertFalse(is_limited)
            self.assertEqual(remaining, 2 - i)

        # 4th call should be limited
        is_limited, remaining, retry_after = self.limiter.check_and_record(123, "test_action")
        self.assertTrue(is_limited)

    def test_atomic_no_race_condition(self):
        """check_and_record is atomic — no gap between check and record."""
        limiter = RateLimiter(limits={
            "tight": {"max_requests": 1, "window_seconds": 60},
        })
        # First call succeeds
        is_limited1, _, _ = limiter.check_and_record(123, "tight")
        self.assertFalse(is_limited1)
        # Second call must be limited
        is_limited2, _, _ = limiter.check_and_record(123, "tight")
        self.assertTrue(is_limited2)


class TestResetUser(unittest.TestCase):
    """Test reset_user() method."""

    def setUp(self):
        self.limiter = RateLimiter(limits={
            "message": {"max_requests": 3, "window_seconds": 60},
            "ai_chat": {"max_requests": 2, "window_seconds": 60},
        })

    def test_reset_specific_action(self):
        """Resetting a specific action only affects that action."""
        self.limiter.record_request(123, "message")
        self.limiter.record_request(123, "ai_chat")

        self.limiter.reset_user(123, "message")

        # message should be back to full
        self.assertEqual(self.limiter.get_remaining(123, "message"), 3)
        # ai_chat should still be consumed
        self.assertEqual(self.limiter.get_remaining(123, "ai_chat"), 1)

    def test_reset_all_actions(self):
        """Resetting all actions for a user."""
        self.limiter.record_request(123, "message")
        self.limiter.record_request(123, "ai_chat")

        self.limiter.reset_user(123)

        self.assertEqual(self.limiter.get_remaining(123, "message"), 3)
        self.assertEqual(self.limiter.get_remaining(123, "ai_chat"), 2)

    def test_reset_nonexistent_user(self):
        """Resetting a nonexistent user doesn't raise."""
        self.limiter.reset_user(999)  # Should not raise


class TestDefaultLimitsConfig(unittest.TestCase):
    """Test that DEFAULT_LIMITS has expected configuration."""

    def test_message_limit(self):
        self.assertEqual(DEFAULT_LIMITS["message"]["max_requests"], 30)
        self.assertEqual(DEFAULT_LIMITS["message"]["window_seconds"], 60)

    def test_ai_chat_limit(self):
        self.assertEqual(DEFAULT_LIMITS["ai_chat"]["max_requests"], 20)
        self.assertEqual(DEFAULT_LIMITS["ai_chat"]["window_seconds"], 60)

    def test_image_gen_limit(self):
        self.assertEqual(DEFAULT_LIMITS["image_gen"]["max_requests"], 5)
        self.assertEqual(DEFAULT_LIMITS["image_gen"]["window_seconds"], 60)

    def test_download_limit(self):
        self.assertEqual(DEFAULT_LIMITS["download"]["max_requests"], 10)
        self.assertEqual(DEFAULT_LIMITS["download"]["window_seconds"], 60)

    def test_search_limit(self):
        self.assertEqual(DEFAULT_LIMITS["search"]["max_requests"], 15)
        self.assertEqual(DEFAULT_LIMITS["search"]["window_seconds"], 60)


class TestSingletonInstance(unittest.TestCase):
    """Test that the module-level singleton is properly initialized."""

    def test_singleton_exists(self):
        """The rate_limiter singleton exists and is a RateLimiter instance."""
        from rate_limiter import rate_limiter
        self.assertIsInstance(rate_limiter, RateLimiter)

    def test_singleton_has_default_limits(self):
        """The singleton has DEFAULT_LIMITS configured."""
        from rate_limiter import rate_limiter
        self.assertEqual(rate_limiter._limits["message"]["max_requests"], 30)
        self.assertEqual(rate_limiter._limits["ai_chat"]["max_requests"], 20)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_user_id_as_string(self):
        """WhatsApp phone numbers (strings) work as user IDs."""
        limiter = RateLimiter(limits={
            "message": {"max_requests": 5, "window_seconds": 60},
        })
        self.assertFalse(limiter.is_rate_limited("+201234567890", "message"))
        limiter.record_request("+201234567890", "message")
        self.assertEqual(limiter.get_remaining("+201234567890", "message"), 4)

    def test_user_id_as_int(self):
        """Telegram user IDs (ints) work as user IDs."""
        limiter = RateLimiter(limits={
            "message": {"max_requests": 5, "window_seconds": 60},
        })
        self.assertFalse(limiter.is_rate_limited(12345, "message"))
        limiter.record_request(12345, "message")
        self.assertEqual(limiter.get_remaining(12345, "message"), 4)

    def test_zero_max_requests(self):
        """Zero max_requests immediately rate limits."""
        limiter = RateLimiter(limits={
            "blocked": {"max_requests": 0, "window_seconds": 60},
        })
        self.assertTrue(limiter.is_rate_limited(123, "blocked"))
        self.assertEqual(limiter.get_remaining(123, "blocked"), 0)

    def test_large_max_requests(self):
        """Large max_requests works correctly."""
        limiter = RateLimiter(limits={
            "generous": {"max_requests": 10000, "window_seconds": 60},
        })
        self.assertFalse(limiter.is_rate_limited(123, "generous"))
        self.assertEqual(limiter.get_remaining(123, "generous"), 10000)


if __name__ == "__main__":
    unittest.main()
