
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Hotfix for NumPy 2.0
try:
    import numpy as np
    if not hasattr(np, 'float_'):
        np.float_ = np.float64
except ImportError:
    pass

import nltk
from nltk.corpus import wordnet as wn

print("Checking available languages...")
try:
    langs = wn.langs()
    print(f"Supported languages: {langs}")
    if 'rus' in langs:
        print("✅ Russian is supported!")
    else:
        print("❌ Russian is NOT supported.")
except Exception as e:
    print(f"Error checking langs: {e}")

input("Press Enter...")
