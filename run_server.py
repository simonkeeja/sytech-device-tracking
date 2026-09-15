"""Launch the local SYTECH prototype. Demo data must be seeded explicitly."""
import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000)
