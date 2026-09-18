import sys
from pathlib import Path

# Add backend directory to sys.path so app module is discoverable by pytest
sys.path.insert(0, str(Path(__file__).parent))
