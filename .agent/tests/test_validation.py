"""
Unit tests for the AGENT application.
Run with: pytest tests/ -v
"""
import pytest
from app.validation import (
    validate_youtube_url,
    validate_tags,
    validate_segment_ids,
    validate_search_query,
    sanitize_text,
)


class TestValidateYoutubeUrl:
    """Tests for YouTube URL validation."""
    
    def test_valid_full_url(self):
        is_valid, video_id, error = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"
        assert error == ""
    
    def test_valid_short_url(self):
        is_valid, video_id, error = validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"
    
    def test_valid_shorts_url(self):
        is_valid, video_id, error = validate_youtube_url("https://youtube.com/shorts/dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"
    
    def test_valid_video_id_only(self):
        is_valid, video_id, error = validate_youtube_url("dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"
    
    def test_invalid_empty(self):
        is_valid, video_id, error = validate_youtube_url("")
        assert is_valid is False
        assert video_id is None
        assert "пустым" in error.lower() or "empty" in error.lower()
    
    def test_invalid_random_text(self):
        is_valid, video_id, error = validate_youtube_url("hello world")
        assert is_valid is False
        assert video_id is None
    
    def test_invalid_non_youtube_url(self):
        is_valid, video_id, error = validate_youtube_url("https://vimeo.com/12345")
        assert is_valid is False


class TestValidateTags:
    """Tests for tag validation."""
    
    def test_valid_tags(self):
        is_valid, tags, error = validate_tags("tag1, tag2, tag3")
        assert is_valid is True
        assert tags == ["tag1", "tag2", "tag3"]
    
    def test_empty_tags_ok(self):
        is_valid, tags, error = validate_tags("")
        assert is_valid is True
        assert tags == []
    
    def test_strips_whitespace(self):
        is_valid, tags, error = validate_tags("  tag1  ,  tag2  ")
        assert is_valid is True
        assert tags == ["tag1", "tag2"]
    
    def test_removes_html(self):
        is_valid, tags, error = validate_tags("tag1, <script>alert('xss')</script>")
        assert is_valid is True
        assert "<script>" not in str(tags)
    
    def test_too_many_tags(self):
        many_tags = ",".join([f"tag{i}" for i in range(25)])
        is_valid, tags, error = validate_tags(many_tags)
        assert is_valid is False
        assert "много" in error.lower() or "many" in error.lower()


class TestValidateSegmentIds:
    """Tests for segment ID validation."""
    
    def test_valid_single_id(self):
        is_valid, ids, error = validate_segment_ids("dQw4w9WgXcQ-0")
        assert is_valid is True
        assert ids == ["dQw4w9WgXcQ-0"]
    
    def test_valid_multiple_ids(self):
        is_valid, ids, error = validate_segment_ids("dQw4w9WgXcQ-0, dQw4w9WgXcQ-1")
        assert is_valid is True
        assert len(ids) == 2
    
    def test_empty_fails(self):
        is_valid, ids, error = validate_segment_ids("")
        assert is_valid is False
    
    def test_invalid_format(self):
        is_valid, ids, error = validate_segment_ids("invalid-segment-id")
        assert is_valid is False


class TestValidateSearchQuery:
    """Tests for search query validation."""
    
    def test_valid_query(self):
        is_valid, query, error = validate_search_query("инфляция в России")
        assert is_valid is True
        assert query == "инфляция в России"
    
    def test_too_short(self):
        is_valid, query, error = validate_search_query("", min_length=1)
        assert is_valid is False
    
    def test_sanitizes_html(self):
        is_valid, query, error = validate_search_query("<script>alert('xss')</script>test")
        assert is_valid is True
        assert "<script>" not in query


class TestSanitizeText:
    """Tests for text sanitization."""
    
    def test_removes_html_tags(self):
        result = sanitize_text("<b>bold</b> text")
        assert "<b>" not in result
        assert "bold" in result
    
    def test_limits_length(self):
        long_text = "a" * 2000
        result = sanitize_text(long_text, max_length=100)
        assert len(result) == 100
    
    def test_handles_empty(self):
        result = sanitize_text("")
        assert result == ""
    
    def test_strips_whitespace(self):
        result = sanitize_text("  text  ")
        assert result == "text"
