/* ============================================
   SHL Assessment Recommender — Client Logic
   ============================================ */

const chatMessages = document.getElementById("chat-messages");
const userInput    = document.getElementById("user-input");
const sendBtn      = document.getElementById("send-btn");
const recList      = document.getElementById("rec-list");

// Full conversation history (sent to API every call)
const history = [];

// Type code → human-readable label
const TYPE_LABELS = {
  A: "Ability",
  B: "Behavioral",
  C: "Competency",
  D: "Development",
  E: "Evaluation",
  K: "Knowledge",
  P: "Personality",
  S: "Simulation",
};

function typeLabel(codes) {
  return codes
    .split("")
    .map((c) => TYPE_LABELS[c] || c)
    .join(", ");
}

// ---- Render helpers ----

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "You" : "AI";

  const body = document.createElement("div");
  body.className = "message-body";

  // Split on double newlines for paragraphs
  const paragraphs = text.split(/\n{2,}/);
  paragraphs.forEach((p) => {
    const pe = document.createElement("p");
    pe.textContent = p.trim();
    if (pe.textContent) body.appendChild(pe);
  });

  div.appendChild(avatar);
  div.appendChild(body);
  chatMessages.appendChild(div);
  scrollToBottom();
}

function showLoading() {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = "loading-msg";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "AI";

  const body = document.createElement("div");
  body.className = "message-body typing-indicator";
  body.innerHTML = "<span></span><span></span><span></span>";

  div.appendChild(avatar);
  div.appendChild(body);
  chatMessages.appendChild(div);
  scrollToBottom();
}

function hideLoading() {
  const el = document.getElementById("loading-msg");
  if (el) el.remove();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderRecommendations(recs) {
  recList.innerHTML = "";

  if (!recs || recs.length === 0) {
    recList.innerHTML = `
      <div class="rec-empty">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.35">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        <p>No recommendations yet.</p>
        <p class="rec-empty-sub">Start a conversation to get assessment suggestions.</p>
      </div>`;
    return;
  }

  recs.forEach((rec) => {
    const card = document.createElement("div");
    card.className = "rec-card";
    card.innerHTML = `
      <div class="rec-card-name">${escapeHtml(rec.name)}</div>
      <div class="rec-card-meta">
        <span class="rec-type-badge">${escapeHtml(typeLabel(rec.test_type))}</span>
        <a class="rec-card-link" href="${escapeHtml(rec.url)}" target="_blank" rel="noopener">
          View in catalog &rarr;
        </a>
      </div>`;
    recList.appendChild(card);
  });
}

function showEndBanner() {
  const banner = document.createElement("div");
  banner.className = "eoc-banner";
  banner.textContent = "Conversation complete — recommendations are ready above.";
  chatMessages.appendChild(banner);
  scrollToBottom();
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

function sendSample(text) {
  const sampleBtns = document.querySelectorAll(".sample-btn");
  sampleBtns.forEach(btn => btn.style.display = "none");
  userInput.value = text;
  sendMessage();
}

// ---- API call ----

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  // Disable input
  userInput.value = "";
  sendBtn.disabled = true;
  userInput.disabled = true;

  // Add user message
  history.push({ role: "user", content: text });
  addMessage("user", text);
  showLoading();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    hideLoading();

    if (!res.ok) {
      addMessage("assistant", "Something went wrong. Please try again.");
      history.pop(); // remove failed user message
      return;
    }

    const data = await res.json();

    // Add assistant reply to history
    history.push({ role: "assistant", content: data.reply });
    addMessage("assistant", data.reply);

    // Update recommendations
    if (data.recommendations && data.recommendations.length > 0) {
      renderRecommendations(data.recommendations);
    }

    // End of conversation
    if (data.end_of_conversation) {
      showEndBanner();
    }
  } catch (err) {
    hideLoading();
    addMessage("assistant", "Network error — please check your connection and try again.");
    history.pop();
  } finally {
    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();
  }
}

// ---- Event listeners ----

sendBtn.addEventListener("click", sendMessage);

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Focus input on load
userInput.focus();
