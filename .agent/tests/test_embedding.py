"""
Unit tests for embedding cache functionality.
"""
import pytest
from app.embedding import (
    embed_query,
    get_cache_stats,
    clear_query_cache,
    _make_cache_key,
)


class TestEmbeddingCache:
    """Tests for embedding cache functionality."""
    
    def test_cache_key_consistent(self):
        """Same input should produce same cache key."""
        key1 = _make_cache_key("model-name", "test query")
        key2 = _make_cache_key("model-name", "test query")
        assert key1 == key2
    
    def test_cache_key_differs_for_different_text(self):
        """Different text should produce different cache keys."""
        key1 = _make_cache_key("model", "query1")
        key2 = _make_cache_key("model", "query2")
        assert key1 != key2
    
    def test_cache_key_differs_for_different_model(self):
        """Different model should produce different cache keys."""
        key1 = _make_cache_key("model1", "query")
        key2 = _make_cache_key("model2", "query")
        assert key1 != key2
    
    def test_cache_stats_returns_dict(self):
        """Cache stats should return dictionary with expected keys."""
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "query_cache" in stats
        assert "model_cache" in stats
    
    def test_clear_cache(self):
        """Clearing cache should not raise errors."""
        # This is a smoke test - just ensure it doesn't crash
        clear_query_cache()
