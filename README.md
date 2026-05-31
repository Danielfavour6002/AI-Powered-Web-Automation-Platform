<div align="center">

<h1>🔬 ████████</h1>
<p><strong>AI-powered Test Automation for Oracle Fusion Cloud</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
</p>

<p>Record browser sessions, replay them against Oracle Fusion Cloud, generate AI-driven test scripts, and export beautiful Excel reports, all from a single web dashboard.</p>

</div>

---

## What Can This Do?

| Feature | Description |
|---|---|
| 🎥 **Record** | Capture your manual browser clicks into a replayable test |
| ▶️ **Replay** | Run recorded tests against Oracle Fusion Cloud automatically |
| 🤖 **AI Studio** | Upload an Excel test case file and let the AI generate and run the test |
| 📊 **Reports** | Download a beautiful Excel report with screenshots for every step |
| 🌐 **Web Dashboard** | Manage everything from a modern dark-mode web UI |

---

## 📋 Prerequisites

Before you start, make sure you have the following installed on your computer. Each one is explained clearly below.

### 1. Python 3.11 or higher

> **What is Python?** Python is the programming language this project is built with.

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click **"Download Python 3.11.x"** (or newer)
3. Run the installer
4. ⚠️ **IMPORTANT:** On the first screen of the installer, check **"Add Python to PATH"** before clicking Install!
5. Verify it worked by opening a terminal (Command Prompt on Windows) and typing:
   ```
   python --version
   ```
   You should see something like `Python 3.11.9`

### 2. Git

> **What is Git?** Git is a tool that lets you download code from the internet.

1. Go to [git-scm.com/downloads](https://git-scm.com/downloads)
2. Download and install for your operating system (use all default settings)
3. Verify it worked:
   ```
   git --version
   ```

### 3. A Chromium Browser

The test recorder uses a special version of Chromium that gets installed automatically in the setup steps below.

---

## 🚀 Setup Instructions (Step by Step)

Follow these steps carefully. Each command should be typed into your terminal (Command Prompt or PowerShell on Windows, Terminal on Mac/Linux).

### Step 1: Download the Project

```bash
git clone https://github.com/pvsairam/testcase.git
cd testcase
```

### Step 2: Create a Virtual Environment

> **What is this?** A virtual environment is like a clean, isolated room for Python. It keeps this project's dependencies separate from everything else on your computer.

**On Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**On Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

✅ When it's active, you'll see `(.venv)` at the start of your terminal prompt.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> This will download all the required libraries. It may take 2-5 minutes on first run.

### Step 4: Install Playwright Browsers

```bash
playwright install chromium
```

> This downloads a special version of Chromium that Playwright uses for automation. Roughly 150 MB download.

### Step 5: Configure Your Environment

Copy the example configuration file:

**On Windows:**
```bash
copy .env.example .env
```

**On Mac/Linux:**
```bash
cp .env.example .env
```

Now open the `.env` file in any text editor (Notepad works fine) and fill in your details:

```ini
# The full URL of your Oracle Fusion Cloud instance
FUSION_URL=https://your-instance.fa.ap1.oraclecloud.com

# Your Oracle Fusion Cloud login username
FUSION_USER=your.username@company.com

# A short name for your pod/instance (used in reports)
FUSION_POD=MY-POD

# Your initials (used to organise output folders)
CONSULTANT=ABC

# Server settings - leave these as-is unless you have a port conflict
HOST=127.0.0.1
PORT=8001

# Where to store the database and test output
DB_PATH=data/qap.db
OUTPUT_ROOT=output
```

### Step 6: Store Your Password Securely

Instead of putting your password in a plain text file, this project uses your operating system's secure keyring (Windows Credential Manager, macOS Keychain, or Linux Secret Service). Run:

```bash
python scripts/setup_keyring.py
```

You will be prompted to type your Oracle Fusion Cloud password. It will be stored securely and never written to a file.

### Step 7: Initialize the Database

```bash
python scripts/init_db.py
```

This creates the local database file that stores your tests and run history.

### Step 8: Start the Application

```bash
python main.py serve
```

You will see:
```
QA Platform started on http://127.0.0.1:8001
```

Open your browser and go to **[http://127.0.0.1:8001](http://127.0.0.1:8001)** 🎉

---

## 📖 How to Use

### 🎥 Recording a Test

1. Click **"Quick Record"** in the top navigation bar
2. Enter the URL you want to test and click **"Start Recording"**
3. A browser window will open - perform your test steps manually (clicking, typing, etc.)
4. When done, click **"Stop Recording"** in the dashboard
5. Your steps are saved and ready to replay

### ▶️ Replaying a Test

1. Go to the **Tests** page
2. Find your test and click **"Run"**
3. The system will automatically log in to Oracle Fusion Cloud and replay every step
4. Watch the progress in the **Runs** page
5. Download the **Excel Report** when complete - it includes screenshots of every step

### 🤖 AI Studio (AI-Powered Test Generation)

> Requires an OpenAI API Key. Get one at [platform.openai.com](https://platform.openai.com).

1. Click **"AI Studio"** in the navigation
2. Select your LLM Provider (OpenAI recommended)
3. Enter your API Key
4. Upload your test case file (Excel `.xlsx`, CSV, or plain text `.txt`)
5. Enter a Test Name and the Target URL
6. Click **"Translate to NLP"** for a fast conversion of your steps into structured JSON
7. Or click **"Generate & Record (Agent)"** to have the AI autonomously perform the steps in a real browser and record them

---

## 📁 Project Structure

```
testcase/
|
+-- core/                   # Core models, database, config, security
|   +-- config.py           # Loads settings from .env
|   +-- database.py         # All database read/write operations
|   +-- models.py           # Data models (Test, Step, Run, etc.)
|   +-- security.py         # Password handling via OS keyring
|
+-- engine/                 # Test execution engine
|   +-- runner.py           # Runs tests step-by-step in Playwright
|   +-- recorder.py         # Captures manual browser interactions
|   +-- parser.py           # Translates recorded Playwright code to steps
|   +-- agent.py            # AI agent wrapper for autonomous recording
|   +-- llm.py              # LLM adapter (OpenAI, Gemini, Anthropic)
|
+-- fusion/                 # Oracle Fusion Cloud specific helpers
|   +-- ...                 # Login flow, wait helpers, etc.
|
+-- reports/                # Report generation
|   +-- excel_report.py     # Generates Excel reports with screenshots
|
+-- web/                    # Web dashboard (FastAPI + Jinja2)
|   +-- app.py              # FastAPI application factory
|   +-- routes/             # URL handlers for each page
|   +-- templates/          # HTML templates for the UI
|
+-- scripts/                # Utility scripts
|   +-- init_db.py          # Creates the database schema
|   +-- setup_keyring.py    # Stores password in OS keyring
|   +-- cleanup_traces.py   # Deletes old Playwright traces/videos
|
+-- data/                   # Database lives here (git-ignored)
+-- output/                 # Test run output (git-ignored)
+-- main.py                 # Application entry point
+-- requirements.txt        # Python dependencies
+-- .env.example            # Template for your .env config file
+-- docker-compose.yml      # Docker deployment (optional)
```

---

## 🐳 Docker (Optional)

If you prefer to use Docker instead of installing Python locally:

```bash
docker-compose up --build
```

Then open **[http://localhost:8001](http://localhost:8001)**

---

## ❓ Troubleshooting

### "python is not recognized as an internal or external command"
Python was not added to your PATH. Uninstall Python and re-install it, making sure to check **"Add Python to PATH"** during installation.

### "ModuleNotFoundError: No module named '...'"
Your virtual environment might not be active. Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux) and try again.

### "playwright: command not found"
Make sure your virtual environment is active, then run `pip install playwright` followed by `playwright install chromium`.

### The browser opens but the test fails immediately
Check that your `.env` file has the correct `FUSION_URL` and `FUSION_USER`. Also make sure you have run `python scripts/setup_keyring.py` to save your password.

### "Address already in use" when starting the server
Another app is using port 8001. Change `PORT=8002` in your `.env` file.

---

## 🛡️ Security Notes

- **Your password is NEVER stored in a file.** It uses the operating system's secure credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service).
- **Your `.env` file is in `.gitignore`** and will never be accidentally uploaded to GitHub.
- **API keys** (OpenAI, etc.) are entered in the UI at runtime and are not stored in the database.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

This project is for internal Oracle Fusion Cloud QA automation use. All rights reserved.
