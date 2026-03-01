import sys
import os

# Ensure the root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase3_rest_api.app import app

# Export for Vercel
# Vercel's Python builder automatically picks up the "app" variable.
