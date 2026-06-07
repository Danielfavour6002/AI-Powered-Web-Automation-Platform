# AI-Powered Web Automation Platform

> **Note:** This repository is a customized version of an open‑source automation platform. It has been adapted and extended to meet the specific needs of the client while preserving the original architecture. The codebase is fully owned and maintained here.

The platform enables AI‑driven test automation for Oracle Fusion Cloud, offering recording, replay, AI‑generated test scripts, and comprehensive reporting via a modern, responsive web dashboard.

---


# <h1>🔬 ████████</h1>
<p><strong>AI-powered Test Automation for Oracle Fusion Cloud</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white" />
</p>

Record browser sessions, replay them against Oracle Fusion Cloud, generate AI‑driven test scripts, and export beautiful reports, all from a modern, responsive web dashboard.

---

## ✨ What's New & Core Improvements

Since the initial release, we have added several architectural, security, and user‑experience enhancements:

### 🔒 1. Advanced Secure Vault (AES‑256‑GCM)
- **Master Password Key Derivation** – Secure vault in **Settings → Security (Vault)**. The master password derives an encryption key using **PBKDF2‑SHA256 (600 k iterations)**.
- **AES‑256‑GCM Encryption** – Client passwords and LLM API keys are encrypted at rest. The derived key lives only in memory during a session.

### ⚙️ 2. Execution Toggles (General Config)
- **Media & Trace Controls** – Toggle Playwright traces, video captures, and step screenshots **individually** via **Settings → General Config**.
- **Granular Log Levels** – Choose logging detail (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

### 🤖 3. Intelligent Action Normalization (Auto‑Healing)
- **Database CHECK Constraint Fixes** – Auto‑mapper normalizes synonyms like `"hover"`, `"open"`, `"type"` to SQLite‑valid fields (`"click"`, `"navigate"`, `"fill"`).
- **On‑The‑Fly Healing** – Replays analyze a simplified DOM tree to locate correct elements, reducing brittleness from CSS/ID changes.

### 🌐 4. Windows Compatibility (ProactorEventLoop Threading)
- **Playwright Subprocess Fix** – Resolved `NotImplementedError` caused by uvicorn’s `SelectorEventLoop` spawning Playwright browsers.
- **Dedicated Worker Threads** – Autonomous agent now runs a background thread with `asyncio.ProactorEventLoop`, streaming live logs to the main thread via thread‑safe SSE queues.

### 💅 5. Responsive UI & Alignments
- **Collapsible Sidebar** – Fixed bug where toggling hid the collapse button; the button now stays visible and centered.
- **Monitor Alignment** – AI Studio Live Agent Monitor uses proper flexbox for clean vertical logs and screenshot overlays.
- **Button Spacing** – Standardized icon spacing with flex `gap` to eliminate layout misalignment.

---

## What Can This Do?

| Feature | Description |
|---|---|
| 🎥 **Record** | Capture manual browser clicks into a replayable test |
| ▶️ **Replay** | Run recorded tests against Oracle Fusion Cloud automatically |
| 🤖 **AI Studio** | Upload a manual test case file and let the AI generate and run the test |
| 📊 **Reports** | Export beautiful Excel or self‑contained HTML reports with embedded screenshots |
| 🛡️ **Credential Vault** | Securely encrypt client passwords and API keys with a master key |
| 🌐 **Web Dashboard** | Manage everything from a modern dark‑mode UI |

---

## 📋 Prerequisites

### 1. Python 3.11 or higher
- Download from [python.org/downloads](https://www.python.org/downloads/)
- Run the installer and **check “Add Python to PATH”**
- Verify: `python --version`

### 2. Git
- Install from [git‑scm.com/downloads](https://git-scm.com/downloads)

---

## 🚀 Setup Instructions (Step by Step)

### Step 1: Clone the Repository
```bash
git clone https://github.com/Danielfavour6002/AI-Powered-Web-Automation-Platform.git
cd AI-Powered-Web-Automation-Platform
```

### Step 2: Create a Virtual Environment
**On Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```
**On macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 4: Configure the Environment
Copy the example env file and edit your values:
```bash
copy .env.example .env   # Windows
# or
cp .env.example .env   # macOS/Linux
```
- `FUSION_URL` – Oracle Fusion instance URL
- `DB_PATH` – Path for local SQLite DB (default `data/qap.db`)
- `OUTPUT_ROOT` – Directory for traces/videos (default `output`)

### Step 5: Initialise the Database
```bash
python scripts/init_db.py
```

### Step 6: Run the Application
```bash
python main.py serve
```
Open **http://127.0.0.1:8001** in your browser.

---

## 📖 How to Use

### 🎥 Recording a Test
1. Click **“Quick Record”** in the top navigation bar.
2. Enter the target URL and click **“Start Recording”**.
3. Perform manual steps in the opened browser window.
4. Click **“Stop Recording”** when finished.

### ▶️ Replaying a Test
1. Navigate to **Tests**, select a test, and click **“Run”**.
2. Choose a **Client Profile** to run against a specific instance.
3. Monitor progress on the **Runs** page.

### 🤖 AI Studio (AI‑Powered Test Generation)
1. Open **AI Studio** from the navigation bar.
2. Select your LLM provider (Gemini, OpenAI, Anthropic) and load the API key from the vault.
3. Upload a test case file (`.xlsx`, `.csv`, `.txt`) and click **“Translate to NLP”**.
4. Press **“Generate & Record (Agent)”** to let the AI autonomously execute steps and record them.

---

## 📁 Project Structure
```
testcase/
├─ core/                 # Core models, DB, config, security
│   ├─ config.py
│   ├─ database.py
│   └─ security.py
├─ engine/               # Test execution engine
│   ├─ runner.py
│   ├─ agent.py
│   └─ llm.py
├─ fusion/               # Oracle Fusion Cloud selectors & hooks
├─ reports/              # Excel & HTML report generators
├─ web/                  # Dashboard UI, templates, REST routes
├─ scripts/              # Helper scripts (e.g., init_db.py)
└─ main.py               # FastAPI entry point
```
---

## 🛡️ Security Notes
- **Zero Plaintext Storage** – All credentials are encrypted with AES‑256‑GCM and never stored in plaintext.
- **Dynamic Parameterisation** – Use `{{Date}}` or `{{Random}}` in step values for unique runtime strings.
- **Sensitive Steps** – Steps marked `is_sensitive` are automatically redacted from logs and reports.

---

*Enjoy fast, reliable, and AI‑enhanced test automation!*

<h1>🔬 ████████</h1>
<p><strong>AI-powered Test Automation for Oracle Fusion Cloud</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white" />
</p>

<p>Record browser sessions, replay them against Oracle Fusion Cloud, generate AI-driven test scripts, and export beautiful reports, all from a modern, responsive web dashboard.</p>

</div>

---

## ✨ What's New & Core Improvements

Since the initial release, we have upgraded the platform with several key architectural, security, and user experience enhancements:

### 🔒 1. Advanced Secure Vault (AES-256-GCM)
* **Master Password Key Derivation**: Added a secure vault in **Settings → Security (Vault)**. Setting a master password derives an encryption key using **PBKDF2-SHA256 with 600,000 iterations**.
* **AES-256-GCM Encryption**: Stored client passwords and LLM API keys are encrypted at rest. The derived key is stored strictly in-memory during the session, meaning credentials cannot be read if the server restarts or the vault is locked.

### ⚙️ 2. Execution Toggles (General Config)
* **Media & Trace Controls**: Added new configurations under **Settings → General Config** to turn Playwright traces, video captures, and step screenshots **on or off** individually.
* **Granular Log Levels**: Added a dropdown to control logging detail levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

### 🤖 3. Intelligent Action Normalization (Auto-Healing)
* **Database CHECK Constraint Fixes**: Implemented an automated action mapper. If an LLM (e.g. Gemini, GPT-4) or file importer produces synonyms like `"hover"`, `"open"`, or `"type"`, the system automatically maps them to SQLite-valid schema fields (`"click"`, `"navigate"`, `"fill"`) on the fly, preventing database insertion crashes.
* **On-The-Fly Healing**: Replays analyze the simplified DOM tree dynamically to locate the correct elements based on description and text value, mitigating issues with changing CSS paths or element IDs.

### 🌐 4. Windows Compatibility (ProactorEventLoop Threading)
* **Playwright Subprocess Fix**: Fixed the `NotImplementedError` raised when uvicorn (which runs on a `SelectorEventLoop`) spawned background Playwright browsers.
* **Dedicated Worker Threads**: The autonomous agent now initializes a dedicated background thread running `asyncio.ProactorEventLoop` directly, communicating live logs to the main thread via thread-safe SSE event queues.

### 💅 5. Responsive UI & Alignments
* **Collapsible Sidebar**: Fixed a bug where toggling the sidebar closed hid the collapse button, locking the UI. The button remains visible and centered at the top of the collapsed 72px sidebar for easy expansion.
* **Monitor Alignment**: Configured the AI Studio Live Agent Monitor as a proper flexbox panel for clean vertical logs and screenshot overlays.
* **Button Spacing**: Standardized button icons using the flex `gap` system to eliminate layout misalignment.

---

## What Can This Do?

| Feature | Description |
|---|---|
| 🎥 **Record** | Capture your manual browser clicks into a replayable test |
| ▶️ **Replay** | Run recorded tests against Oracle Fusion Cloud automatically |
| 🤖 **AI Studio** | Upload a manual test case file and let the AI generate and run the test |
| 📊 **Reports** | Download a beautiful Excel report or self-contained HTML report with embedded screenshots |
| 🛡️ **Credential Vault**| Securely encrypt client login passwords and API keys with a master key |
| 🌐 **Web Dashboard** | Manage everything from a modern dark-mode web UI |

---

## 📋 Prerequisites

Before you start, make sure you have the following installed:

### 1. Python 3.11 or higher
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer and check **"Add Python to PATH"** before clicking install.
3. Verify it worked:
   ```bash
   python --version
   ```

### 2. Git
1. Go to [git-scm.com/downloads](https://git-scm.com/downloads) and install it.

---

## 🚀 Setup Instructions (Step by Step)

### Step 1: Download the Project
```bash
git clone https://github.com/pvsairam/testcase.git
cd testcase
```

### Step 2: Create a Virtual Environment
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

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 4: Configure Your Environment
Copy `.env.example` to `.env` and fill in your basic details:
* `FUSION_URL` - Oracle Fusion instance URL
* `DB_PATH` - path for local SQLite database (default: `data/qap.db`)
* `OUTPUT_ROOT` - directory for execution traces/videos (default: `output`)

### Step 5: Initialize the Database
```bash
python scripts/init_db.py
```

### Step 6: Start the Application
```bash
python main.py serve
```
Open **[http://127.0.0.1:8001](http://127.0.0.1:8001)** in your browser!

---

## 📖 How to Use

### 🎥 Recording a Test
1. Click **"Quick Record"** in the top navigation bar.
2. Enter the URL you want to test and click **"Start Recording"**.
3. A browser window will open - perform your test steps manually (clicking, typing, etc.).
4. When done, click **"Stop Recording"** in the dashboard.

### ▶️ Replaying a Test
1. Go to the **Tests** page, select a test, and click **"Run"**.
2. Select the target **Client Profile** from the dropdown to run it against a specific client instance with their credentials.
3. Watch the progress in the **Runs** page.

### 🤖 AI Studio (AI-Powered Test Generation)
1. Click **"AI Studio"** in the navigation bar.
2. Select your LLM Provider (Google Gemini, OpenAI, or Anthropic) and load your API key from the vault.
3. Upload your test case file (`.xlsx`, `.csv`, `.txt`) and click **"Translate to NLP"** for structured step generation.
4. Click **"Generate & Record (Agent)"** to have the AI autonomously execute steps in the browser and record them.

---

## 📁 Project Structure

```
testcase/
|
+-- core/                   # Core models, database, config, security
|   +-- config.py           # Config schema and parser
|   +-- database.py         # DB CRUD, migrations, and action normalizer
|   +-- security.py         # AES-256-GCM Vault encryption logic
|
+-- engine/                 # Test execution engine
|   +-- runner.py           # Replay loop with trace/video/screenshot toggles
|   +-- agent.py            # Background autonomous driving agent (Proactor thread)
|   +-- llm.py              # LLM completion adapter
|
+-- fusion/                 # Oracle Fusion Cloud page selectors & wait hooks
+-- reports/                # Excel & self-contained HTML report generators
+-- web/                    # Dashboard views, templates, and REST routes
+-- main.py                 # Fast API entrypoint
```

---

## 🛡️ Security Notes
* **Zero Plaintext Storage**: No client passwords or LLM API keys are stored in plaintext. They are encrypted using AES-256-GCM and decrypted strictly in memory when the vault is unlocked.
* **Dynamic Parameterization**: Use double braces `{{Date}}` or `{{Random}}` in step values to automatically substitute unique runtime strings and avoid duplicate data errors.
* **Sensitive Steps**: Steps marked `is_sensitive` are automatically redacted from execution logs and report screenshots.
