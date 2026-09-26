// ============================================================
// Tea Pot Transcription Bot — Landing Page Interactive Engine
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  initRetentionSimulator();
  initSetupTabs();
  initLiveTranscriptSimulation();
  initMobileMenu();
});

// 1. Interactive Retention & Tier Simulator
function initRetentionSimulator() {
  const slider = document.getElementById('tierRangeSlider');
  const toggle = document.getElementById('retention-toggle');
  const toggleStatusLabel = document.getElementById('toggle-status-label');
  const badge = document.getElementById('resultTierBadge');
  const desc = document.getElementById('resultTierDesc');
  const perk = document.getElementById('resultTierPerk');
  const demoBadge = document.getElementById('demo-retention-badge');

  if (!slider) return;

  const tierData = {
    1: {
      name: "Chamomile (Free Tier)",
      badgeColor: "#10B981",
      duration: "24 Hours",
      desc: "Transcripts are stored in Discord threads for <strong>24 Hours</strong>, then automatically purged by the bot to keep server storage clean and preserve privacy.",
      downloads: "Disabled (In-Discord viewing only)",
      demoText: "24h Auto-Purge (Free Tier)"
    },
    2: {
      name: "Chamomile Extended (Free Tier + Toggle)",
      badgeColor: "#34D399",
      duration: "48 Hours",
      desc: "Transcripts remain accessible in Discord threads for <strong>48 Hours</strong> with the server retention toggle enabled.",
      downloads: "Disabled (In-Discord viewing only)",
      demoText: "48h Auto-Purge (Free Tier Toggle)"
    },
    3: {
      name: "Earl Grey (Pro Tier)",
      badgeColor: "#F59E0B",
      duration: "Up to 7 Days (Configurable)",
      desc: "Transcripts stay for <strong>7 Days</strong> (or obey a 24h/48h toggle). Includes full export to <strong>.txt & .md meeting files</strong>!",
      downloads: "✓ Enabled (.txt / .md meeting files)",
      demoText: "7-Day Retention (Pro Tier)"
    },
    4: {
      name: "Matcha Imperial (Premium Tier)",
      badgeColor: "#A855F7",
      duration: "Indefinite / Permanent Archive",
      desc: "Transcripts are <strong>archived permanently</strong> and never deleted automatically. The auto-purge toggle is <strong>100% optional</strong> for full admin compliance.",
      downloads: "✓ Enabled (Unlimited instant downloads & export API)",
      demoText: "Permanent Archive (Premium Tier)"
    }
  };

  function updateSimulation() {
    const val = slider.value;
    const isToggleOn = toggle.checked;
    const data = tierData[val];

    if (val === "1" && isToggleOn) {
      // Toggle switched to 48h
      badge.textContent = data.name;
      desc.innerHTML = data.desc;
      perk.innerHTML = `⬇️ File Downloads: <em>${data.downloads}</em>`;
      if (demoBadge) demoBadge.textContent = data.demoText;
    } else if (val === "4") {
      badge.textContent = data.name;
      desc.innerHTML = isToggleOn
        ? "Transcripts are <strong>archived permanently</strong>. (Auto-delete toggle is currently active if you wish to enforce compliance)."
        : data.desc;
      perk.innerHTML = `⬇️ File Downloads: <strong>${data.downloads}</strong>`;
      if (demoBadge) demoBadge.textContent = data.demoText;
    } else {
      badge.textContent = data.name;
      desc.innerHTML = data.desc;
      perk.innerHTML = `⬇️ File Downloads: ${data.downloads.includes('Enabled') ? '<strong>' + data.downloads + '</strong>' : '<em>' + data.downloads + '</em>'}`;
      if (demoBadge) demoBadge.textContent = data.demoText;
    }

    toggleStatusLabel.innerHTML = `Auto-Purge Toggle: <strong>${isToggleOn ? 'ON' : 'OFF'}</strong>`;
  }

  slider.addEventListener('input', updateSimulation);
  toggle.addEventListener('change', updateSimulation);

  updateSimulation();
}

// 2. Setup Tabs
function initSetupTabs() {
  const buttons = document.querySelectorAll('.setup-tab-btn');
  const panels = document.querySelectorAll('.setup-tab-panel');

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });
}

// 3. Live Simulated Discord Stream Animations
function initLiveTranscriptSimulation() {
  const transcriptStream = document.getElementById('transcript-stream');
  if (!transcriptStream) return;

  const sampleQuotes = [
    { user: "Emma", color: "#EC4899", text: "I just reviewed the retention policy, 48 hours is perfect for our standups." },
    { user: "David", color: "#3B82F6", text: "Can we run `/export` after this session to download the minutes?" },
    { user: "Alex", color: "#6366F1", text: "Yes! Pro and Premium tiers get instant .txt file attachments in the thread." },
    { user: "Sarah", color: "#10B981", text: "And the audio chime at the beginning alerted everyone in the channel." }
  ];

  let quoteIdx = 0;

  setInterval(() => {
    const q = sampleQuotes[quoteIdx % sampleQuotes.length];
    quoteIdx++;

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const newMsg = document.createElement('div');
    newMsg.className = 'chat-msg';
    newMsg.style.animation = 'fadeInUp 0.4s ease forwards';
    newMsg.innerHTML = `
      <div class="avatar" style="background: ${q.color};">${q.user[0]}</div>
      <div class="msg-body">
        <div class="msg-header">
          <span class="user-name">${q.user}</span>
          <span class="timestamp">${timeStr}</span>
        </div>
        <div class="msg-text">
          <span class="stt-clock">🕒 <code>${timeStr}</code></span> | 🗣️ <strong>${q.user}</strong>: "${q.text}"
        </div>
      </div>
    `;

    // Append and keep max 4 entries
    transcriptStream.appendChild(newMsg);
    if (transcriptStream.children.length > 4) {
      transcriptStream.removeChild(transcriptStream.children[0]);
    }
  }, 4500);
}

// 4. Mobile Menu
function initMobileMenu() {
  const toggle = document.getElementById('mobile-toggle');
  const nav = document.querySelector('.nav-links');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.style.display === 'flex';
    nav.style.display = isOpen ? 'none' : 'flex';
    if (!isOpen) {
      nav.style.flexDirection = 'column';
      nav.style.position = 'absolute';
      nav.style.top = '100%';
      nav.style.left = '0';
      nav.style.right = '0';
      nav.style.background = '#07090E';
      nav.style.padding = '20px';
      nav.style.borderBottom = '1px solid rgba(255, 255, 255, 0.1)';
    }
  });
}
