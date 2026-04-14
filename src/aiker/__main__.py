from pathlib import Path
from dotenv import load_dotenv

# Search upward from this file to find .env at the project root
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from aiker.cli import app

if __name__ == "__main__":
    app()
