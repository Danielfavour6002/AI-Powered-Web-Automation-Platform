(function() {
  function injectBadge() {
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
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(12px) saturate(180%);
          -webkit-backdrop-filter: blur(12px) saturate(180%);
          border: 1px solid rgba(239, 68, 68, 0.4);
          box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.25), 0 8px 10px -6px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1);
          border-radius: 9999px;
          padding: 10px 18px;
          color: #ffffff;
          display: flex;
          align-items: center;
          gap: 10px;
          font-weight: 600;
          font-size: 13px;
          pointer-events: auto;
          letter-spacing: -0.01em;
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
      </style>
      <div class="badge">
        <div class="dot-container">
          <div class="dot"></div>
          <div class="dot-pulse"></div>
        </div>
        <span>QA Platform: Recording...</span>
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
  }

  // Inject early
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectBadge);
  } else {
    injectBadge();
  }
})();
