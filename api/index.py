import os
import sys

# Add the project root and back/src to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
back_src = os.path.join(root_dir, "back", "src")

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if back_src not in sys.path:
    sys.path.insert(0, back_src)

# Import the app from back/src/api/main.py
# Since back/src is in path, 'api.main' should work if api folder has __init__.py
try:
    from api.main import app
except ImportError:
    # Fallback for different directory structures
    from back.src.api.main import app

handler = app
app.root_path = "/api"
