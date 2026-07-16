"""Local and Gunicorn application entrypoint."""
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402

Config.validate()
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
