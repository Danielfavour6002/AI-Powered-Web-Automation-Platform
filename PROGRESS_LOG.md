# QA Platform — Progress Log
> **Purpose:** Track every change made, current state, and what is left. Any future AI session MUST read this file first before scanning code.

---

## Architecture Quick Reference

| Layer | Key Files |
|---|---|
| Config/DB | `core/config.py`, `core/database.py`, `core/models.py`, `core/security.py` |
| Recording | `engine/recorder.py`, `engine/generate_auth.py`, `engine/parser.py` |
| Runner | `engine/runner.py`, `engine/context.py`, `engine/reporter.py` |
| AI Studio | `engine/llm.py`, `engine/agent.py`, `web/routes/ai_studio.py` |
| Login | `fusion/login_page.py`, `fusion/base_page.py`, `fusion/locators.py` |
| Web UI | `web/routes/`, `web/templates/`, `web/static/css/app.css` |
| Reports | `reports/excel_report.py`, `reports/html_report.py`, `reports/docx_report.py`, `reports/packager.py` |

---

## Completed Fixes (Chronological)

### Session 1–3 (Prior)
- [x] **SQLite live column migrations** — `core/database.py` `init_db()` adds `client_id` and `run_params` to runs table via `ALTER TABLE` if missing
- [x] **Password resolution fallback** — `core/config.py` `resolve_password()` pulls from env vars with fallback chain
- [x] **Settings tab blanking** — removed overriding `display:none` on `[data-tab-content]`; added `.hidden { display: none !important; }` to `app.css`
- [x] **Reports path crash** — `web/routes/reports.py` changed `config.output_dir` → `config.output_root`
- [x] **Premium UI/UX overhaul** — `web/static/css/app.css` full redesign (dark obsidian, glassmorphism, micro-animations)
- [x] **Client Profiles UI** — toggle switch, app types (Oracle/SAP/PeopleSoft/Workday/Generic/Custom), export/import JSON, per-client export endpoint
- [x] **AI Studio enhancements** — client dropdown auto-populates URL (`data-url` attribute), `test_description` field added, description passed to `create_test()`
- [x] **Video/FPS settings** — `VIDEO_WIDTH`, `VIDEO_HEIGHT`, `VIDEO_FPS` fields in Settings → General
- [x] **Default report format** — `REPORT_FORMAT` select (excel/html) in Settings → General

### Session 4 (2026-06-03)
- [x] **generate_auth.py critical bug** — File used `sync_playwright` but `LoginPage.full_login()` is `async`. The `await` was missing, so the coroutine was NEVER executed → auth state saved as an empty session → every rerun landed on Oracle `/signin` block page. **Fixed:** converted entire file to `async_playwright` + `asyncio.run()`.
- [x] **Gemini 404 (v1beta API)** — `gemini-1.5-flash` and `gemini-1.5-pro` removed from `v1beta` API that litellm routes to. Updated to `gemini/gemini-2.0-flash` in:
  - `engine/llm.py` default model map
  - `web/templates/settings.html` `updateLlmDefaults()` JS
  - `core/database.py` auto-migration query (now matches `LIKE '%gemini-1.5%'` → upgrades to `gemini/gemini-2.0-flash`)
- [x] **Anthropic model date typo** — `claude-3-5-sonnet-20260620` (impossible future date) → `claude-3-5-sonnet-20241022` in `settings.html`
- [x] **IDCS two-step login** — `fusion/locators.py` was missing the `next_btn` locator. `fusion/login_page.py` `full_login()` went straight from username → password without clicking "Next". Added IDCS-aware step: after entering username, waits up to 4 s for a "Next" button, clicks it if visible, then continues to password. Falls back silently if no Next button (single-page environments).

### Session 5 (2026-06-03)
- [x] **assert_login_form_visible timeout on IDCS** — Was waiting for username + password + submit all at once. On IDCS two-step login, password field is hidden until "Next" is clicked → 10s timeout before login even started. **Fixed:** now only waits for username field; waits for password field separately AFTER Next button is clicked.
- [x] **auto-login skipped for IDCS-recorded tests** — `runner.py` had `if "idcs" not in first_step_url` condition which SKIPPED auto-login exactly when it was most needed (when test was recorded without being logged in). **Fixed:** always attempt auto-login for Oracle tests; fail-fast with clear error message if login fails.
- [x] **Recorded /signin NAVIGATE steps now skipped** — After auto-login, `runner.py` now also skips NAVIGATE steps pointing to `/signin` URLs (not just `idcs`/`oauth2`).
- [x] **assert_logged_in false negative** — Used `wait_for_url(lambda: "signin" not in url)` which would timeout if already on home page with a URL containing "signin" accidentally. **Fixed:** checks home landmarks first (fast path), then waits for URL change, then re-checks landmarks. Falls back to clear error.
- [x] **429 rate limit — no retry logic** — `engine/llm.py` and `engine/agent.py` had no retry on quota errors. **Fixed:** added 3-attempt exponential backoff (10s → 30s → 60s) for any error containing 429/quota/rate in both files.
- [x] **subprocess CWD missing in replay.py** — `subprocess.Popen` spawning the background runner had no `cwd`, so aiosqlite and other modules were not found when launched from different directories. **Fixed:** `cwd=Path(__file__).resolve().parents[2]` (project root).

---

## Current Known Issues / Next Steps

### 🔴 High Priority
- [ ] **Gemini API key in DB** — After the server restarts the `init_db()` migration will update the model_name. But **the user must still manually re-activate or update the existing Gemini LLM provider** in Settings → LLM Providers if it still shows the old model (the migration updates `model_name` column but the user's API key must still be valid).
- [ ] **Gemini free tier quota** — The `gemini/gemini-2.0-flash` free-tier quota is very low (~1 RPM on free). Consider upgrading to a paid API key or switching to another provider (OpenAI/Anthropic) to avoid persistent 429 errors during AI Studio use.
- [ ] **Test replay re-run** — After fixing auth state, validate a full replay passes Steps 1–12 without timeout.
- [ ] **Reports download** — Verify Excel/HTML/ZIP download works from run detail page.
- [ ] **DOCX background error** — Non-fatal DOCX generation failure appears in logs. Not blocking but worth investigating `reports/docx_report.py`.

### 🟢 Low Priority / Spec Items Not Yet Done
- [ ] Drag-and-drop step reorder on review screen (Section 04)
- [ ] Batch run queuing (Section 06)
- [ ] Scheduled future runs with date/time picker (Section 06)
- [ ] Screenshot ZIP download from run detail (Section 08)
- [ ] Video player HTML5 embed on run detail page (Section 08)
- [ ] Master test protection from accidental deletion (Section 05)
- [ ] Test parameter token preview in Run dialog (Section 05)
- [ ] First-run setup wizard (Section 10)

---

## Key Design Decisions (Do Not Change)

1. **Zero Hardcoding** — No URLs, credentials, paths, or API keys in source code. Everything via DB/config.
2. **Model string format** — litellm requires `provider/model` prefix e.g. `gemini/gemini-2.0-flash`, NOT bare `gemini-2.0-flash`.
3. **Auth state** — `engine/.auth_state.json` is generated by `engine/generate_auth.py` (async, uses `LoginPage.full_login()`). Must be regenerated whenever the Oracle session expires.
4. **"Browser use" prohibited** — UI and docs must say "AI-guided recording" or "autonomous test generation". Never "browser use".
5. **Passwords** — Never in DB, logs, or files. OS keyring first, encrypted file fallback.
6. **Runner OAuth skip logic** — NAVIGATE to `idcs`/`oauth2` URLs is only skipped if `did_auto_login == True`. Manual replay keeps those steps.

---

## File Change Summary (Session 4, 2026-06-03)

| File | Change |
|---|---|
| `engine/generate_auth.py` | Full rewrite — async_playwright + asyncio.run, await added to full_login |
| `engine/llm.py` | Default gemini model: `gemini-1.5-flash` → `gemini-2.0-flash` |
| `engine/runner.py` | Added /signin redirect detection after NAVIGATE step |
| `core/database.py` | Migration now catches all `gemini-1.5-*` → `gemini-2.0-flash` |
| `web/templates/settings.html` | Gemini default: `1.5-flash` → `2.0-flash`; Anthropic date fix |

---

*Last updated: 2026-06-03 by AI session. Restart server after these changes.*
