# Lifeline Bot 💬

A Telegram bot for the **ART Lichnost'** team that enables anonymous messaging, AI-powered support, meeting scheduling, and personal development tracking synced with Google Sheets.

Powered by:
- [**Telegram Bot API**](https://core.telegram.org/bots/api)
- [**OpenRouter**](https://openrouter.ai) (free LLM access)
- [**Google Sheets API**](https://developers.google.com/sheets) for real-time profile management

---

## 🚀 Features
- **User onboarding**: auto-create profile on first use
- **Anonymous messaging**: send confidential notes to team leads
- **AI-powered advice**: get empathetic, free LLM responses via OpenRouter
- **Meeting requests**: schedule 1:1s with mentors
- **Personal development tracking**:
  - View your profile stored in Google Sheets
  - Edit fields like *Career Growth*, *Current Role*, *Goals*, and more
- **Secure & lightweight**:
  - No passwords — uses Telegram ID for auth
  - Data stored in MongoDB + Google Sheets
  - All secrets in `.env`
- **Intuitive menu**: button-driven UX with fallback handling
- **Docker-ready**: easy local dev or cloud deployment

---

## 📋 Setup Instructions

### 1. Clone the repository
```bash
git https://github.com/lim0sha/LifelineBot.git
cd LifelineBot
```

### 2. Create a virtual environment and install dependencies
```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

---

## 🔑 Getting Your API Keys

### 1. Create a Telegram bot via [BotFather](https://t.me/BotFather)
- Use `/newbot`, choose a name and username.
- Copy the **bot token** — you’ll add it to `.env`.
- No extra permissions needed — bot works in private chats.

### 2. Set up Gmail for email notifications
- Enable **2-Factor Authentication** on your Google account.
- Go to [Google Account → Security → App passwords](https://myaccount.google.com/apppasswords).
- Generate a 16-character **App Password** for "Mail".
- Use your Gmail address and this password in `.env`.

### 3. Get your OpenRouter API key
- Sign up at [OpenRouter](https://openrouter.ai/)
- Go to **Dashboard → API Keys**
- Create a key and add it to `.env`
- Free model: `meta-llama/llama-3.2-3b-instruct:free`

### 4. Configure Google Sheets
- Create a new **Google Sheet**
- Copy the **Sheet ID** from the URL (between `/d/` and `/edit`)
- In **Google Cloud Console**:
  - Create a project
  - Enable **Google Sheets API**
  - Create a **Service Account**
  - Download the JSON key → rename to `google_credentials.json`
  - Share your Google Sheet with the Service Account email (from JSON)

---

## ⚙️ Configuration and Running the Bot

### 1. Copy the environment file template
Rename `.env.example` to `.env` and fill in:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# MongoDB
MONGO_HOST=mongo
MONGO_PORT=27017
MONGO_DB_NAME=art_bot

# Gmail SMTP
GMAIL_EMAIL=your_service@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# OpenRouter
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=google_credentials.json
GOOGLE_SHEET_ID=your_google_sheet_id_here
```

### 2. Add team leads in `config/mentors.json`
```json
{
  "Mentor1": "someaddress1@gmail.com",
  "Mentor2": "someaddress2@gmail.com",
  "Mentor3": "someaddress3@gmail.com",
  "Mentor4": "someaddress4@gmail.com",
  "Mentor5": "someaddress5@gmail.com"
}
```

### 3. Run with Docker (recommended)
```bash
# Build & start
docker-compose build --no-cache
docker-compose up -d

# View logs
docker-compose logs -f

# To stop services
docker-compose down
```

### 4. Local development (MongoDB in Docker, bot locally)
```bash
# Start MongoDB only
docker-compose up -d mongo

# Run bot locally
python src/main.py
```

### 5. Test the bot
- Message your bot in Telegram
- Use the menu to:
  - Send anonymous notes
  - Get AI advice
  - Request meetings
  - View/edit your profile
---

## 📂 Project Structure
```bash
ArtLifelineBot/
│
├── config/
│   ├── constants.py        # Profile field definitions
│   └── mentors.json        # Team lead emails
├── src/
│   ├── bot/                # FSM states & bot init
│   ├── handlers/           # Command logic (advice, meeting, profile, etc.)
│   ├── services/           # External integrations
│   └── templates/email/    # HTML/TXT email templates
├── google_credentials.json # Google Service Account key
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## License
This project is licensed under the MIT License - see the [LICENSE.md](docs/LICENSE.md) file for details.

---

## Contact
For questions or feedback: [limosha@inbox.ru](mailto:limosha@inbox.ru)

---

Feel free to customize this further to better fit your needs!