# 🚀 PRIME Trading Bot

A modular Python crypto trading bot for Binance.  
It supports **Grid Trading, OCO (One Cancels the Other), TWAP (Time-Weighted Average Price), and Limit Orders**.  
The bot is extendable — you can add new strategies inside `src/orders/advanced/`.

---

## 📦 Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/Thebinary110/AlphaTrade
cd <your-repo>

# Create virtual environment
python -m venv venv

# Activate (Linux / MacOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate


pip install --upgrade pip
pip install -r requirements.txt


cp .env.example .env


Then open .env and set:

BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

Run the main entrypoint:

python src/main.py

