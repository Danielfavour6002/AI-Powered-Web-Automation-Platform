(function() {
  function centerOracleSignin() {
    const url = window.location.href.toLowerCase();
    if (!url.includes('/signin') && !url.includes('idcs')) {
      return;
    }

    // Apply a global flexbox centering to the body
    const style = document.createElement('style');
    style.id = 'qap-center-signin-style';
    style.innerHTML = `
      html, body {
        height: 100% !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: hidden !important;
      }
      .oj-idaas-signin-card,
      .idcs-signin-card,
      #loginContainer,
      .login-container,
      .signin-container,
      .login-card,
      .login-panel,
      #login,
      .identity-portal,
      .loginContent,
      .sign-in {
        position: static !important;
        top: auto !important;
        left: auto !important;
        transform: none !important;
        margin: 0 auto !important;
        max-width: 100% !important;
      }
    `;
    const apply = () => {
      const parent = document.head || document.documentElement;
      if (parent && !document.getElementById('qap-center-signin-style')) {
        parent.appendChild(style);
      }
    };
    apply();
    // Re-apply a few times to catch dynamically loaded elements
    let count = 0;
    const interval = setInterval(() => {
      apply();
      if (++count >= 10) clearInterval(interval);
    }, 500);
    document.addEventListener('DOMContentLoaded', apply);
  }

  function injectBadge() {
    if (window !== window.top) return; // Only in top-level window
    if (document.getElementById('qap-record-badge-root')) return;

    const container = document.createElement('div');
    container.id = 'qap-record-badge-root';
    container.style.position = 'fixed';
    container.style.bottom = '24px';
    container.style.left = '24px';
    container.style.zIndex = '2147483647'; // absolute top priority overlay
    container.style.pointerEvents = 'none';

    const shadow = container.attachShadow({mode: 'open'});
    shadow.innerHTML = `
      <style>
          .badge {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(12px) saturate(180%);
            -webkit-backdrop-filter: blur(12px) saturate(180%);
            border: 1px solid rgba(100, 100, 100, 0.4);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(0, 0, 0, 0.1);
            border-radius: 12px;
            padding: 12px 16px;
            color: #111111;
            display: flex;
            flex-direction: column;
            gap: 10px;
            font-weight: 600;
            font-size: 13px;
            pointer-events: auto;
            letter-spacing: -0.01em;
            min-width: 220px;
          }
        .header {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .dot-container {
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          width: 10px;
          height: 10px;
        }
        .dot {
          width: 10px;
          height: 10px;
          background-color: #ef4444;
          border-radius: 50%;
          z-index: 2;
        }
        .dot-pulse {
          position: absolute;
          width: 22px;
          height: 22px;
          background-color: rgba(239, 68, 68, 0.6);
          border-radius: 50%;
          animation: pulse 1.6s ease-out infinite;
          z-index: 1;
        }
        @keyframes pulse {
          0% { transform: scale(0.4); opacity: 1; }
          100% { transform: scale(1.5); opacity: 0; }
        }
        .action-row {
          display: none; /* hidden until first action */
          align-items: center;
          gap: 10px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          padding-top: 8px;
          margin-top: 2px;
        }
        .icon {
          font-size: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 30px;
          height: 30px;
          background: rgba(168, 85, 247, 0.15);
          border: 1px solid rgba(168, 85, 247, 0.25);
          border-radius: 8px;
          flex-shrink: 0;
        }
        .action-info {
          flex: 1;
          min-width: 0;
        }
        .action-type {
          font-weight: 700;
          font-size: 11px;
          color: #c084fc;
          text-transform: uppercase;
          letter-spacing: 0.02em;
        }
        .description {
          font-size: 11.5px;
          color: #cbd5e1;
          margin: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      </style>
      <div class="badge">
        <div class="header">
          <div class="dot-container">
            <div class="dot"></div>
            <div class="dot-pulse"></div>
          </div>
          <span>QA Platform: Recording...</span>
        </div>
        <div class="action-row" id="action-row">
          <div class="icon" id="action-icon">🤖</div>
          <div class="action-info">
            <div class="action-type" id="action-title">Initializing</div>
            <p class="description" id="action-desc">Ready to record actions...</p>
          </div>
        </div>
      </div>
    `;
    
    // Support inserting into body even if DOM hasn't fully loaded
    if (document.body) {
      document.body.appendChild(container);
    } else {
      const observer = new MutationObserver(() => {
        if (document.body) {
          document.body.appendChild(container);
          observer.disconnect();
        }
      });
      observer.observe(document.documentElement, { childList: true });
    }

    // Set up interactive action logging listeners
    setupActionListeners();
  }

  function setupActionListeners() {
    const icons = {
      'navigate': '🌐',
      'click': '🖱️',
      'fill': '✍️',
      'press': '⌨️',
      'submit': '✅'
    };

    function updateBadgeAction(action, description) {
      const shadow = document.getElementById('qap-record-badge-root')?.shadowRoot;
      if (!shadow) return;
      
      const actionIcon = shadow.getElementById('action-icon');
      const actionTitle = shadow.getElementById('action-title');
      const actionDesc = shadow.getElementById('action-desc');
      const actionRow = shadow.getElementById('action-row');
      
      if (actionIcon && actionTitle && actionDesc && actionRow) {
        actionRow.style.display = 'flex';
        actionIcon.textContent = icons[action.toLowerCase()] || '📝';
        actionTitle.textContent = action.toUpperCase();
        actionDesc.textContent = description;
      }
    }

    // Click Listener
    document.addEventListener('click', (e) => {
      const target = e.target;
      let label = target.tagName.toLowerCase();
      if (target.id) label += `#${target.id}`;
      else if (target.className && typeof target.className === 'string') {
        const firstClass = target.className.trim().split(' ')[0];
        if (firstClass) label += `.${firstClass}`;
      }
      updateBadgeAction('click', `Clicked <${label}>`);
    }, true);

    // Input/Fill Listener
    document.addEventListener('input', (e) => {
      const target = e.target;
      let label = target.tagName.toLowerCase();
      if (target.id) label += `#${target.id}`;
      updateBadgeAction('fill', `Typing in <${label}>`);
    }, true);

    // Keydown Listener (Enter key)
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        updateBadgeAction('press', 'Pressed Enter');
      }
    }, true);

    // Submit Listener
    document.addEventListener('submit', () => {
      updateBadgeAction('submit', 'Form Submitted');
    }, true);
  }

  // Initialize early styling
  centerOracleSignin();

  // Inject early
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectBadge);
  } else {
    injectBadge();
  }
})();
