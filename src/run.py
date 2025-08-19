#!/usr/bin/env python3
"""
Simple bot runner that handles import issues
Run this instead of src/main.py if you have import problems
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set working directory to src
os.chdir(src_path)

# Now import and run main
try:
    from main import main
    main()
except ImportError as e:
    print(f"Import Error: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)