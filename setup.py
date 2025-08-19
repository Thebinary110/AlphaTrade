# setup.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PROJECT_STRUCTURE = {
    "src": {
        "client": ["binance_client.py", "validator.py"],
        "orders": {
            "advanced": ["oco.py", "twap.py"],
            "__files__": ["market_orders.py", "limit_orders.py"],
        },
        "utils": ["config.py", "logger.py"],
        "__files__": ["main.py"],
    },
    "tests": ["test_orders.py"],
    "__files__": [
        "requirements.txt",
        "config.json",
        ".env.example",
        "README.md",
        "setup.sh",
        "setup.bat",
    ],
    "__touch__": [".env", "bot.log"],
    "logs": [],
}


def create_structure(base, structure):
    for name, content in structure.items():
        if name == "__files__":
            for file in content:
                path = base / file
                if not path.exists():
                    path.touch()
                    print(f"[+] Created file: {path}")
        elif name == "__touch__":
            for file in content:
                path = base / file
                if not path.exists():
                    path.touch()
                    print(f"[+] Touched file: {path}")
        elif isinstance(content, dict):
            folder = base / name
            folder.mkdir(parents=True, exist_ok=True)
            print(f"[+] Ensured directory: {folder}")
            create_structure(folder, content)
        elif isinstance(content, list):
            folder = base / name
            folder.mkdir(parents=True, exist_ok=True)
            print(f"[+] Ensured directory: {folder}")
            for file in content:
                path = folder / file
                if not path.exists():
                    path.touch()
                    print(f"[+] Created file: {path}")


def main():
    print("🔧 Building Binance Trading Bot project structure...")
    create_structure(BASE_DIR, PROJECT_STRUCTURE)
    print("✅ Project structure ready.")


if __name__ == "__main__":
    main()
