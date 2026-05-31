# QA Platform - Complete Tester's Guide

Welcome to the QA Platform! This guide covers all the powerful features of the tool (including New Tests and Quick Record) and provides a suite of Test Cases for validating the platform itself.

---

## Part 1: Feature Guide

### 1. Starting the Platform
1. Open a terminal and navigate to the `qap` folder.
2. Run `python main.py serve`
3. Open `http://localhost:8000` in your browser.

### 2. Creating a "New Test"
You can create powerful, human-readable tests using our NLP Engine.
1. Create a new Python file in your workspace (e.g., `test_my_feature.py`).
2. Write your test steps using simple instructions. Example:
   ```python
   instructions = [
       "Navigate to https://example.com",
       "Click on 'Login'",
       "Fill 'Username' with 'myuser'",
       "Fill 'Password' with 'mypassword'",
       "Click on 'Submit'"
   ]
   ```
3. Use the Engine to run it:
   ```python
   from qap.engine.runner import Engine
   
   engine = Engine()
   engine.execute(instructions)
   ```
4. The test will automatically appear in your dashboard runs!

### 3. Quick Record (Codegen)
Don't want to type out steps? Use the Quick Record feature to automatically generate instructions by interacting with the browser.
1. Run the recorder script (e.g., `mock_recording.py` or Playwright Codegen).
2. A browser will open. Perform your actions (clicking, typing) naturally.
3. The platform will translate your actions into plain-text instructions that you can directly paste into a New Test!

### 4. Analyzing Results
Once a test finishes, click on it in the **Runs** tab to access:
- **Screenshots:** View visual evidence for every single step.
- **Video:** Watch a full video playback of the test execution.
- **Trace Viewer:** Open the time-travel debugger to inspect network requests, console logs, and the DOM at every millisecond.

### 5. Generating Reports
At the bottom of the run details page, you can export your results:
- **Download Excel:** For tabular data analysis.
- **Download DOCX:** A beautiful, stakeholder-ready document with embedded screenshots.
- **View Allure:** Interactive HTML reporting (if integrated).

---

## Part 2: Platform Validation (QA Test Cases)

If you are a QA tester tasked with testing **this QA tool itself**, run through the following test cases to ensure the platform is functioning perfectly:

### TC-01: End-to-End Test Execution
- **Action:** Go to the dashboard, click "Play" on an existing test.
- **Expected Result:** The run status changes to "Running" with a progress bar. Once completed, the status changes to "Passed" or "Failed" and execution time is logged.

### TC-02: New Test Script Parsing
- **Action:** Create a `test_new.py` with custom plain-English instructions (e.g., "Click on 'Save'"). Execute it via the Engine.
- **Expected Result:** The Fusion Locator successfully interprets the English command, finds the element via Playwright, and records the step in the dashboard.

### TC-03: Quick Record Accuracy
- **Action:** Start Quick Record, navigate to a site, click a button, and stop recording.
- **Expected Result:** The recorded output generates valid instruction strings (e.g., `"Click on 'Button Name'"`) that perfectly match the actions taken.

### TC-04: Trace Viewer Integration
- **Action:** Open a completed run, go to the "Trace" tab, and click "Open in Trace Viewer".
- **Expected Result:** Playwright's Trace Viewer opens in a new tab, successfully loading the `.zip` trace without network errors, showing action timelines.

### TC-05: Report Generation Integrity
- **Action:** Click "Download DOCX" on a completed run that has screenshots.
- **Expected Result:** A `.docx` file is downloaded. When opened, it contains formatting, tables of all steps, and correctly embeds the screenshots.

### TC-06: UI/UX Redesign Validation
- **Action:** Navigate through the Home, Tests, and Runs tabs. Hover over buttons and cards.
- **Expected Result:** The new Glassmorphism UI renders correctly. Cards have blurred backgrounds, buttons have neon gradients with smooth hover animations, and the sidebar highlights active routes accurately.
