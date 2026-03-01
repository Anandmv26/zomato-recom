import sys
import os

# Ensure the root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase3_rest_api.app import app
from phase1_data_pipeline import pipeline

# Defensive bootstrap for Vercel
# If the FastAPI lifespan isn't triggered quickly enough, ensure we start loading here.
if not pipeline.app_state.is_loaded:
    pipeline.bootstrap()

# Export for Vercel
app = app
