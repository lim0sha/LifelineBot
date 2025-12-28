# Lifeline Bot 💬

A Telegram bot for the **ART Lichnost'** team that enables anonymous messaging, AI-powered support, meeting scheduling,
and personal development tracking synced with Google Sheets.

Powered by:

- [**Telegram Bot API**](https://core.telegram.org/bots/api)
- [**OpenRouter**](https://openrouter.ai) (free LLM access)
- [**Google Sheets API**](https://developers.google.com/sheets) for real-time profile management

---
## 🧰 Technologies Used

### Core Frameworks & Libraries
- **Python 3.11+**: Main programming language
- **aiogram 3.x**: Asynchronous Telegram Bot framework with FSM support
- **Motor**: Async driver for MongoDB
- **Google Client Libraries**: Official Python APIs for Sheets and Auth
- **aiohttp**: Async HTTP client for OpenRouter integration
- **Jinja2**: Template engine for email rendering

### Infrastructure & DevOps
- **MongoDB Community Edition**: Lightweight, document-based database for user profiles and audit logs
- **Docker & Docker Compose**: Containerization for consistent local and cloud environments
- **Google Sheets API**: Real-time, structured data storage for personal development profiles
- **Gmail SMTP**: Reliable email delivery for notifications and requests

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

## How It Works

The ART Lifeline Bot operates as a **central orchestrator**, connecting Telegram users with external services for a
seamless experience (for example, AI-powered advice, the bot queries OpenRouter to generate a thoughtful reply):

---
![scheme.png](docs%2Fsrc%2Fscheme.png)

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
    - Share your access of the Google Sheet with the Service Account email

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

Absolutely! Here's the **English version** of that instruction, perfectly aligned with your README's tone and structure:

---

### 3. Prepare Your Google Sheet

Before the first launch, you **must** create and configure a Google Sheet with the correct structure:

1. Create a **new Google Sheet**.
2. In the **first row (header row)**, add the following column headers **exactly as defined
   in `config/constants.py` → `ALL_PROFILE_FIELDS`**:

   ```
   telegram_id	username	profile_name	Career Growth	Current Direction	Current Age	Current Role	Additional Comment	Goal: Where? Why?	How? Understanding the path to the goal	What? Ways to achieve the goal
   ```

   > ⚠️ **Order and spelling must match** `ALL_PROFILE_FIELDS` exactly.  
   > The `telegram_id` column is **required** — the bot uses it to locate user profiles.

3. Ensure your **Google Service Account** (from `google_credentials.json`) has **"Editor"** access to this sheet.

> [!TIP]
> On first use, the bot will automatically create a new row with your `telegram_id` and `profile_name` if it doesn’t
> exist. All other fields can be updated via the **"✏ Update My Path"** menu option (note: `username` is read-only).

### 4. Run with Docker (recommended)

```bash
# Build & start
docker-compose build --no-cache
docker-compose up -d

# View logs
docker-compose logs -f

# To stop services
docker-compose down
```

### 5. Local development (MongoDB in Docker, bot locally)

```bash
# Start MongoDB only
docker-compose up -d mongo

# Run bot locally
python src/main.py
```

### 6. Test the bot

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

This project is licensed under the MIT License - see the [LICENSE.md](docs/src/LICENSE.md) file for details.

---

## Contact

For questions or feedback: [limosha@inbox.ru](mailto:limosha@inbox.ru)

---

Feel free to customize this further to better fit your needs!