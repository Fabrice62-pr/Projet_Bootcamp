import os
import sys
from pathlib import Path

# La cle doit exister avant l'import de app.main, qui refuse de demarrer sans.
os.environ.setdefault('ENGINE_API_KEY', 'test-key')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
