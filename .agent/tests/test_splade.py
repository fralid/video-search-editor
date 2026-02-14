"""
Test SPLADE encoder functionality.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NumPy 2.0 hotfix
try:
    import numpy as np
    if not hasattr(np, 'float_'):
        np.float_ = np.float64
except ImportError:
    pass

def test_splade():
    print("🧪 Testing SPLADE Encoder...")
    
    try:
        from app.splade import SpladeEncoder, encode_sparse, SPLADE_DIM
        
        print(f"SPLADE vocabulary size: {SPLADE_DIM}")
        
        # Test encoding
        test_texts = [
            "машинное обучение и нейронные сети",
            "Putin announced new economic reforms",
            "алгоритмы поиска в базах данных"
        ]
        
        for text in test_texts:
            print(f"\n📝 Query: {text}")
            sparse_str = encode_sparse(text)
            
            # Parse to count non-zero elements
            if sparse_str.startswith("{") and "/" in sparse_str:
                parts = sparse_str.split("/")
                inner = parts[0][1:-1]  # Remove { }
                if inner:
                    tokens = inner.split(",")
                    print(f"   Non-zero tokens: {len(tokens)}")
                    # Show top 5 tokens
                    print(f"   Sample: {tokens[:5]}...")
                else:
                    print("   [Empty sparse vector]")
            
        print("\n✅ SPLADE test complete!")
        
    except Exception as e:
        import traceback
        print(f"\n❌ SPLADE test failed:\n{traceback.format_exc()}")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    test_splade()
