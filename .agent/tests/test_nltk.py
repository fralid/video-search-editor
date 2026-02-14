
# Script to verify NLTK WordNet expansion
import logging
import sys
import os
import traceback

# Add project root to sys.path to allow running script directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- NUMPY 2.0 HOTFIX START ---
# Fix for "AttributeError: np.float_ was removed" in local environment
try:
    import numpy as np
    if not hasattr(np, 'float_'):
        np.float_ = np.float64
except ImportError:
    pass
# --- NUMPY 2.0 HOTFIX END ---

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_expansion():
    print("🚀 Testing NLTK Expansion...")
    
    try:
        from app.config import AppConfig
        from app.query import _expand_queries_wordnet
        
        test_words = [
            "server",
            "database",
            "algorithm",
            "network",
            "computer"
        ]
        
        for word in test_words:
            print(f"\nQUERY: {word}")
            try:
                results = _expand_queries_wordnet(word)
                print(f" -> {results}")
            except Exception as e:
                print(f"FAILED: {e}")
                
        print("\n✅ Verification complete.")

    except ImportError as e:
        print(f"\n❌ ERROR: Missing libraries (ImportError).")
        print(f"Details: {e}")
        print("\nTo run this script locally (outside Docker), you need to install dependencies:")
        print("pip install nltk pydantic PyYAML")
        print("Or verify that you are running in the correct virtual environment.")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR:\n{traceback.format_exc()}")

    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    test_expansion()
