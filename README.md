# simplehuman Release Bot

A modern, fast, and interactive Slack Release Bot built with **Python FastAPI** and **Slack Block Kit** to trigger, abort, and monitor **Bitrise** mobile application builds.

---

## 📁 Project Structure

```
simplehuman-release-bot/
│
├── app.py                  # Main entry point containing FastAPI routes
├── .env                    # Environment variables file (secrets and configurations)
├── requirements.txt        # Python package dependencies
│
├── services/
│   ├── bitrise.py          # Wrapper for the Bitrise REST API
│   ├── slack.py            # Formats Slack Block Kit layouts and sends API calls
│   ├── parser.py           # Extracts command actions, arguments, and state data
│   └── auth.py             # Middleware to verify Slack signatures in constant time
│
├── config.py               # Settings manager (loads and validates .env variables)
└── README.md               # Setup and usage documentation
```

---

## 🛠️ Prerequisites

- **Python 3.8+**
- **pip** (Python package installer)
- A **Slack workspace** where you have permission to install apps.
- A **Bitrise account** with an application set up for iOS or Android.

---

## 🚀 Setup & Local Installation

### 1. Clone & Install Dependencies
Navigate into the bot directory and install required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy or create the `.env` file in the root of the project. Fill in the placeholders:
```ini
# Server configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Slack configuration
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
DEFAULT_SLACK_CHANNEL=#releases

# Bitrise configuration
BITRISE_API_TOKEN=your-bitrise-api-token
BITRISE_APP_SLUG=your-bitrise-app-slug
```

---

## 🤖 Slack App Configuration

To wire this bot up to your Slack App:

1. **Create a Slack App** in the [Slack API Console](https://api.slack.com/apps).
2. **Retrieve Credentials**:
   - Get the **Signing Secret** from the *Basic Information* page and put it in `.env` as `SLACK_SIGNING_SECRET`.
   - Go to *OAuth & Permissions*, request the `chat:write` and `chat:write.public` scopes, install the app in your workspace, and copy the **Bot User OAuth Token** (starts with `xoxb-`) into `.env` as `SLACK_BOT_TOKEN`.
3. **Configure Slash Command**:
   - Go to *Slash Commands* -> *Create New Command*.
   - Command: `/release`
   - Request URL: `https://your-domain.com/slack/commands` (or your local ngrok URL during development).
   - Usage Hint: `[trigger|status|abort|help]`
4. **Configure Interactivity**:
   - Go to *Interactivity & Shortcuts* -> Enable Interactivity.
   - Request URL: `https://your-domain.com/slack/actions`.

---

## 📲 Bitrise Webhook Configuration

To receive build progress (e.g. Success/Failure cards) in Slack:

1. Log in to **Bitrise** and navigate to your App settings.
2. Select **Webhooks** from the side menu.
3. Click **Add webhook** and specify your endpoint URL:
   `https://your-domain.com/webhooks/bitrise`
4. Set the event triggers (e.g., Build Started, Build Finished). The bot will automatically parse and publish status updates to the configured `DEFAULT_SLACK_CHANNEL`.

---

## 🏃 Running the Application

Start the development server using **Uvicorn**:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- Open your browser to `http://localhost:8000/health` to confirm it is running.
- Access automated API docs at `http://localhost:8000/docs`.

---

## 📝 Slash Commands Reference

| Command | Action | Example |
| :--- | :--- | :--- |
| `/release` | Opens the interactive release form inside Slack | `/release` |
| `/release trigger <platform> <ref>` | Directly starts a build for platform/ref | `/release trigger android main` |
| `/release status <build_slug>` | Inspect status of a specific build slug | `/release status d3b4f621a...` |
| `/release status` | Lists status of the last 5 builds | `/release status` |
| `/release abort <build_slug>` | Cancels an ongoing build on Bitrise | `/release abort d3b4f621a...` |
| `/release help` | Explains bot commands and capabilities | `/release help` |
