import sys
import os
import json
import logging
import numpy as np
from typing import List
from dataclasses import dataclass

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Mocking before import if possible, or patching after
import app.chunking

# Mock the model to avoid download
class MockModel:
    def encode(self, sentences, **kwargs):
        # Return random embeddings
        return np.random.rand(len(sentences), 384)

# Patch the cache
app.chunking._MODELS["paraphrase-MiniLM-L6-v2"] = MockModel()

from app.chunking import semantic_chunking
from app.models import Segment
from app.config import AppConfig, ChunkConfig

def test_strict_timestamps():
    logging.basicConfig(level=logging.INFO)
    
    # Configure strict settings
    cfg = AppConfig(
        chunk=ChunkConfig(
            min_chars=10,
            max_chars=100,
            semantic_threshold=0.5,
            semantic_model_name="paraphrase-MiniLM-L6-v2" 
        )
    )
    
    # Create segments with WORDS
    words1 = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": " world.", "start": 0.5, "end": 1.0}
    ]
    
    words2 = [
        {"word": " This", "start": 1.0, "end": 1.2},
        {"word": " is", "start": 1.2, "end": 1.4},
        {"word": " a", "start": 1.4, "end": 1.6},
        {"word": " test.", "start": 1.6, "end": 2.0}
    ]
    
    seg1 = Segment(
        segment_id="1", video_id="v1", 
        start_sec=0.0, end_sec=1.0, 
        text="Hello world.", 
        words=json.dumps(words1)
    )
    
    seg2 = Segment(
        segment_id="2", video_id="v1", 
        start_sec=1.0, end_sec=2.0, 
        text=" This is a test.", 
        words=json.dumps(words2)
    )
    
    print("Running semantic_chunking with MockModel...")
    chunks = semantic_chunking(cfg, [seg1, seg2])
    
    print(f"Generated {len(chunks)} chunks")
    for c in chunks:
        suffix, start, end, text = c
        print(f"Chunk: '{text}' ({start:.2f}-{end:.2f})")
        
        # Verify timestamps logic
        # Note: Semantic chunking might merge or split based on random embeddings.
        # But IF it splits, the timestamps must effectively align with words.
        
        # Check that start/end correspond to SOME word boundary in our input
        valid_starts = {0.0, 0.5, 1.0, 1.2, 1.4, 1.6}
        valid_ends = {0.5, 1.0, 1.2, 1.4, 1.6, 2.0}
        
        assert any(abs(start - vs) < 0.01 for vs in valid_starts), f"Invalid start {start}"
        assert any(abs(end - ve) < 0.01 for ve in valid_ends), f"Invalid end {end}"

    print("✅ Test passed!")

if __name__ == "__main__":
    test_strict_timestamps()
