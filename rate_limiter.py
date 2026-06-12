"""
Rate Limiter — Per-User, Per-Action Token Bucket Rate Limiting
================================================================
Provides in-memory rate limiting using the token bucket algorithm.

Features:
- Per-user, per-action-type rate limiting
- Configurable limits per action type
- Admin bypass (admins are never rate limited)
- Thread-safe (uses threading.Lock)
- Automatic periodic cleanup to prevent memory leaks
- No external dependencies — pure Python

Usage:
    from rate_limiter import rate_limiter

    # Check if rate limited
    if rate_limiter.is_rate_limited(user_id, "message"):
        # Reject the request
        pass

    # Combined check + record (recommended)
    is_limited, remaining, retry_after = rate_limiter.check_and_record(user_id, "ai_chat")
    if is_limited:
        # Reject with retry_after info
        pass
"""

import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# Default Limits Configuration
# ═══════════════════════════════════════

DEFAULT_LIMITS = {
    "message": {"max_requests": 30, "window_seconds": 60},
    "ai_chat": {"max_requests": 20, "window_seconds": 60},
    "image_gen": {"max_requests": 5, "window_seconds": 60},
    "download": {"max_requests": 10, "window_seconds": 60},
    "search": {"max_requests": 15, "window_seconds": 60},
}

# How often (seconds) the automatic cleanup runs
CLEANUP_INTERVAL = 300  # 5 minutes

# How old an entry must be (seconds) before it can be cleaned up
CLEANUP_MAX_AGE = 600  # 10 minutes


class RateLimiter:
    """Token bucket rate limiter with per-user, per-action limits."""

    def __init__(self, limits: Optional[dict] = None):
        """Initialize with default or custom limits.

        Args:
            limits: Optional dict of action -> {max_requests, window_seconds}.
                    If None, DEFAULT_LIMITS is used.
        """
        self._limits = limits if limits is not None else dict(DEFAULT_LIMITS)
        self._buckets: dict = {}  # (user_id, action) -> {"tokens": float, "last_refill": float, "max_tokens": int, "refill_rate": float}
        self._admin_ids: set = set()
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False

        # Start automatic cleanup in background
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start the background cleanup thread."""
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="RateLimiter-Cleanup",
            daemon=True,
        )
        self._cleanup_thread.start()
        logger.info("✅ Rate limiter cleanup thread started")

    def _cleanup_loop(self):
        """Periodically remove expired entries."""
        while self._running:
            try:
                time.sleep(CLEANUP_INTERVAL)
                self.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Rate limiter cleanup error: {e}")

    def _get_bucket(self, user_id, action: str) -> dict:
        """Get or create a token bucket for user+action."""
        key = (user_id, action)
        if key not in self._buckets:
            limit_config = self._limits.get(action, {"max_requests": 30, "window_seconds": 60})
            max_tokens = limit_config["max_requests"]
            window_seconds = limit_config["window_seconds"]
            # refill_rate = tokens per second
            refill_rate = max_tokens / window_seconds
            self._buckets[key] = {
                "tokens": float(max_tokens),
                "last_refill": time.monotonic(),
                "max_tokens": max_tokens,
                "refill_rate": refill_rate,
            }
        return self._buckets[key]

    def _refill(self, bucket: dict) -> None:
        """Refill tokens based on elapsed time (token bucket algorithm)."""
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        # Add tokens proportional to elapsed time
        tokens_to_add = elapsed * bucket["refill_rate"]
        bucket["tokens"] = min(bucket["max_tokens"], bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now

    def is_rate_limited(self, user_id, action: str = "message") -> bool:
        """Check if user is rate limited for the given action.

        Returns True if rate limited (should reject), False if OK.
        Admins are never rate limited.
        """
        # Admin bypass
        if user_id in self._admin_ids:
            return False

        with self._lock:
            bucket = self._get_bucket(user_id, action)
            self._refill(bucket)
            return bucket["tokens"] < 1.0

    def get_remaining(self, user_id, action: str = "message") -> int:
        """Get remaining requests for user+action in current window.

        Returns the number of remaining requests (floor of tokens).
        Admins always return max_tokens.
        """
        if user_id in self._admin_ids:
            limit_config = self._limits.get(action, {"max_requests": 30, "window_seconds": 60})
            return limit_config["max_requests"]

        with self._lock:
            bucket = self._get_bucket(user_id, action)
            self._refill(bucket)
            return max(0, int(bucket["tokens"]))

    def get_retry_after(self, user_id, action: str = "message") -> float:
        """Get seconds until the rate limit resets (until at least 1 token is available).

        Returns 0.0 if not currently rate limited.
        Admins always return 0.0.
        """
        if user_id in self._admin_ids:
            return 0.0

        with self._lock:
            bucket = self._get_bucket(user_id, action)
            self._refill(bucket)
            if bucket["tokens"] >= 1.0:
                return 0.0
            # Time needed to get 1 token at current refill rate
            tokens_needed = 1.0 - bucket["tokens"]
            return tokens_needed / bucket["refill_rate"]

    def record_request(self, user_id, action: str = "message") -> None:
        """Record a request for rate limiting purposes.

        Consumes one token from the bucket. Does nothing for admins.
        """
        if user_id in self._admin_ids:
            return

        with self._lock:
            bucket = self._get_bucket(user_id, action)
            self._refill(bucket)
            if bucket["tokens"] > 0:
                bucket["tokens"] -= 1.0

    def check_and_record(self, user_id, action: str = "message") -> tuple:
        """Combined check + record. Returns (is_limited, remaining, retry_after).

        This is the recommended method to use — it atomically checks and records.
        If the user is rate limited, it does NOT consume a token.
        If the user is not rate limited, it DOES consume a token.

        Returns:
            is_limited (bool): True if rate limited (should reject)
            remaining (int): Number of remaining requests after this one
            retry_after (float): Seconds until rate limit resets (0.0 if not limited)
        """
        if user_id in self._admin_ids:
            limit_config = self._limits.get(action, {"max_requests": 30, "window_seconds": 60})
            return (False, limit_config["max_requests"], 0.0)

        with self._lock:
            bucket = self._get_bucket(user_id, action)
            self._refill(bucket)

            if bucket["tokens"] < 1.0:
                # Rate limited — don't consume a token
                tokens_needed = 1.0 - bucket["tokens"]
                retry_after = tokens_needed / bucket["refill_rate"]
                return (True, 0, retry_after)

            # Not rate limited — consume a token
            bucket["tokens"] -= 1.0
            remaining = max(0, int(bucket["tokens"]))
            return (False, remaining, 0.0)

    def set_admin_ids(self, admin_ids: set) -> None:
        """Set admin user IDs that bypass rate limiting.

        Args:
            admin_ids: Set of user IDs (int or str) that should never be rate limited.
        """
        with self._lock:
            self._admin_ids = set(admin_ids)
        logger.info(f"👑 Rate limiter: {len(self._admin_ids)} admin IDs set")

    def add_admin_id(self, user_id) -> None:
        """Add a single admin ID."""
        with self._lock:
            self._admin_ids.add(user_id)

    def remove_admin_id(self, user_id) -> None:
        """Remove a single admin ID."""
        with self._lock:
            self._admin_ids.discard(user_id)

    def cleanup(self) -> int:
        """Remove expired entries to prevent memory leaks.

        Removes buckets that haven't been accessed recently and are fully refilled.

        Returns:
            Number of entries removed.
        """
        now = time.monotonic()
        removed = 0

        with self._lock:
            keys_to_remove = []
            for key, bucket in self._buckets.items():
                # Remove if bucket is fully refilled and hasn't been used recently
                age = now - bucket["last_refill"]
                is_full = bucket["tokens"] >= bucket["max_tokens"]
                if age > CLEANUP_MAX_AGE and is_full:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._buckets[key]
                removed += 1

        if removed > 0:
            logger.debug(f"🧹 Rate limiter cleanup: removed {removed} expired entries")

        return removed

    def get_stats(self) -> dict:
        """Get rate limiter statistics for monitoring.

        Returns:
            Dict with stats including total buckets, active buckets, admin count, etc.
        """
        with self._lock:
            now = time.monotonic()
            total_buckets = len(self._buckets)
            active_buckets = 0  # buckets with < max_tokens
            limited_users = set()
            action_counts = {}

            for (user_id, action), bucket in self._buckets.items():
                self._refill(bucket)
                if bucket["tokens"] < bucket["max_tokens"]:
                    active_buckets += 1
                if bucket["tokens"] < 1.0:
                    limited_users.add(user_id)
                action_counts[action] = action_counts.get(action, 0) + 1

            return {
                "total_buckets": total_buckets,
                "active_buckets": active_buckets,
                "currently_limited_users": len(limited_users),
                "limited_user_ids": list(limited_users),
                "admin_count": len(self._admin_ids),
                "action_counts": action_counts,
                "configured_limits": dict(self._limits),
                "cleanup_interval_seconds": CLEANUP_INTERVAL,
                "cleanup_max_age_seconds": CLEANUP_MAX_AGE,
            }

    def reset_user(self, user_id, action: Optional[str] = None) -> None:
        """Reset rate limiting for a specific user+action or all actions.

        Args:
            user_id: The user ID to reset
            action: If provided, reset only this action. If None, reset all actions.
        """
        with self._lock:
            if action:
                key = (user_id, action)
                if key in self._buckets:
                    del self._buckets[key]
            else:
                keys_to_remove = [k for k in self._buckets if k[0] == user_id]
                for key in keys_to_remove:
                    del self._buckets[key]

    def shutdown(self) -> None:
        """Stop the cleanup thread."""
        self._running = False
        logger.info("🛑 Rate limiter shutdown")


# ═══════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════

rate_limiter = RateLimiter()
