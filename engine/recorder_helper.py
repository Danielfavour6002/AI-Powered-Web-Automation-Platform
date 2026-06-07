"""
QA Platform Recording Helper.

Replaces 'playwright codegen' to allow:
  1. Persistent browser context so extensions load reliably
  2. Recording badge extension injected on all pages
  3. CSS centering fix injected on Oracle IDCS sign-in pages

Usage (via subprocess from recorder.py):
    python -m engine.recorder_helper <url> <output_file> [width] [height]
"""
import sys
import asyncio
import textwrap
from pathlib import Path

# ── Centering CSS ─────────────────────────────────────────────────────────────
# Injected as an init script on every page.  Only takes visual effect when
# the URL contains "/signin" or "idcs", so it won't affect Oracle Fusion pages.
CENTERING_SCRIPT = """
(function() {
  const url = window.location.href.toLowerCase();
  if (!url.includes('/signin') && !url.includes('idcs')) return;

  const style = document.createElement('style');
  style.innerHTML = `
    .oj-idaas-signin-card,
    .idcs-signin-card,
    #loginContainer {
      position: fixed !important;
      top: 50% !important;
      left: 50% !important;
      transform: translate(-50%, -50%) !important;
      z-index: 100000 !important;
      margin: 0 !important;
    }
  `;

  const insert = () => {
    const parent = document.head || document.documentElement;
    if (parent) parent.appendChild(style);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', insert);
  } else {
    insert();
  }

  // Retry a few times in case Oracle JET re-renders the DOM
  let n = 0;
  const t = setInterval(() => {
    insert();
    if (++n >= 8) clearInterval(t);
  }, 500);
})();
"""

# ── Recording Badge Script ────────────────────────────────────────────────────
BADGE_SCRIPT = """
(function() {
  if (window !== window.top) return; // top-level window only
  if (document.getElementById('qap-record-badge-root')) return;

  const ICONS = {
    click:    '🖱️',
    fill:     '✍️',
    press:    '⌨️',
    submit:   '✅',
    navigate: '🌐',
  };

  function mount() {
    if (document.getElementById('qap-record-badge-root')) return;

    const wrap = document.createElement('div');
    wrap.id = 'qap-record-badge-root';
    Object.assign(wrap.style, {
      position: 'fixed', bottom: '24px', left: '24px',
      zIndex: '2147483647', pointerEvents: 'none',
    });

    const shadow = wrap.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host { all: initial; }
        .badge {
          font-family: system-ui, "Segoe UI", Roboto, sans-serif;
          background: rgba(15, 23, 42, 0.88);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(239, 68, 68, 0.45);
          box-shadow: 0 10px 30px rgba(0,0,0,.5);
          border-radius: 14px;
          padding: 12px 16px;
          color: #fff;
          display: flex;
          flex-direction: column;
          gap: 8px;
          min-width: 230px;
          pointer-events: auto;
        }
        .row { display: flex; align-items: center; gap: 10px; }
        .dot-wrap { position: relative; width: 10px; height: 10px; flex-shrink: 0; }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: #ef4444; }
        .ring {
          position: absolute; width: 22px; height: 22px;
          border-radius: 50%; background: rgba(239,68,68,.55);
          top: -6px; left: -6px;
          animation: pulse 1.6s ease-out infinite;
        }
        @keyframes pulse {
          0%   { transform: scale(.4); opacity: 1; }
          100% { transform: scale(1.5); opacity: 0; }
        }
        .title { font-weight: 700; font-size: 13px; }
        .divider { border-top: 1px solid rgba(255,255,255,.1); }
        .action-row { display: none; align-items: center; gap: 10px; padding-top: 4px; }
        .icon {
          font-size: 18px; width: 32px; height: 32px;
          display: flex; align-items: center; justify-content: center;
          background: rgba(168,85,247,.15); border: 1px solid rgba(168,85,247,.3);
          border-radius: 8px; flex-shrink: 0;
        }
        .atype { font-size: 10px; font-weight: 700; color: #c084fc; text-transform: uppercase; letter-spacing: .05em; }
        .adesc { font-size: 11px; color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 160px; }
      </style>
      <div class="badge">
        <div class="row">
          <div class="dot-wrap"><div class="dot"></div><div class="ring"></div></div>
          <span class="title">QA Platform: Recording…</span>
        </div>
        <div class="divider"></div>
        <div class="action-row" id="arow">
          <div class="icon" id="aicon">🤖</div>
          <div>
            <div class="atype" id="atype">READY</div>
            <div class="adesc" id="adesc">Interact with the page</div>
          </div>
        </div>
      </div>`;

    document.body ? document.body.appendChild(wrap)
      : document.addEventListener('DOMContentLoaded', () => document.body.appendChild(wrap));

    // ── Live action listeners ──────────────────────────────────────────
    function update(action, desc) {
      const arow = shadow.getElementById('arow');
      const aicon = shadow.getElementById('aicon');
      const atype = shadow.getElementById('atype');
      const adesc = shadow.getElementById('adesc');
      if (!arow) return;
      arow.style.display = 'flex';
      aicon.textContent = ICONS[action] || '📝';
      atype.textContent = action.toUpperCase();
      adesc.textContent = desc;
    }

    document.addEventListener('click', e => {
      const t = e.target;
      const id = t.id ? '#' + t.id : (t.className && typeof t.className === 'string' ? '.' + t.className.trim().split(' ')[0] : '');
      update('click', 'Clicked <' + t.tagName.toLowerCase() + id + '>');
    }, true);

    document.addEventListener('input', e => {
      const t = e.target;
      update('fill', 'Typing in <' + t.tagName.toLowerCase() + (t.id ? '#' + t.id : '') + '>');
    }, true);

    document.addEventListener('keydown', e => {
      if (e.key === 'Enter') update('press', 'Pressed Enter');
    }, true);

    document.addEventListener('submit', () => update('submit', 'Form submitted'), true);
  }

  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
"""


async def _run(url: str, output_file: Path, width: int, height: int,
               state_file: Path | None, ext_path: Path):
    from playwright.async_api import async_playwright  # type: ignore

    user_data_dir = Path("engine/.recorder_user_data")
    user_data_dir.mkdir(parents=True, exist_ok=True)

    ext_str = str(ext_path.resolve())

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            args=[
                "--start-maximized",
                f"--disable-extensions-except={ext_str}",
                f"--load-extension={ext_str}",
            ],
            viewport=None,          # let --start-maximized control window size
            no_viewport=True,
        )

        # Inject centering + badge on every new page
        await ctx.add_init_script(CENTERING_SCRIPT)
        await ctx.add_init_script(BADGE_SCRIPT)

        # Load existing auth state if available
        if state_file and state_file.exists():
            import json
            state = json.loads(state_file.read_text(encoding="utf-8"))
            cookies = state.get("cookies", [])
            if cookies:
                await ctx.add_cookies(cookies)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded")

        # Open Playwright Inspector (codegen recorder UI)
        await ctx.pause()

        # After the user closes the inspector, save recorded steps
        # Playwright writes them to output_file via the codegen mechanism.
        # Since we can't capture codegen output from pause(), we generate
        # a basic script from the trace instead. For now just close cleanly.
        await ctx.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m engine.recorder_helper <url> <output_file> [width] [height]", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    output_file = Path(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 800

    state_file = Path("engine/.auth_state.json")
    ext_path = Path(__file__).resolve().parent / "recorder_extension"

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_run(url, output_file, width, height, state_file, ext_path))


if __name__ == "__main__":
    main()
