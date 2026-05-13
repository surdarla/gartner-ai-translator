import os
import sys

# Add the project root to sys.path so we can import from back/src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "back", "src"))

from api.main import app

# Set root_path to handle Vercel's /api prefix correctly
app.root_path = "/api"

# This is the entry point for Vercel
handler = app
