import { sendChatMessage } from "./api.js";

const chatHistory = [];

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function appendBubble(container, role, text, extraClass = "") {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role} ${extraClass}`.trim();
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function setChatOpen(open) {
  const panel = document.getElementById("chat-panel");
  const toggle = document.getElementById("chat-toggle");
  if (!panel || !toggle) return;

  panel.classList.toggle("hidden", !open);
  toggle.classList.toggle("chat-toggle-active", open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close AI chat" : "Open AI chat");

  if (open) {
    document.getElementById("chat-input")?.focus();
  }
}

export function openChat() {
  setChatOpen(true);
}

export function initChat() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const messages = document.getElementById("chat-messages");
  const toggle = document.getElementById("chat-toggle");
  const closeBtn = document.getElementById("chat-close");
  const navLink = document.getElementById("chat-nav-link");

  toggle?.addEventListener("click", () => {
    const panel = document.getElementById("chat-panel");
    setChatOpen(panel?.classList.contains("hidden") ?? true);
  });

  closeBtn?.addEventListener("click", () => setChatOpen(false));

  navLink?.addEventListener("click", (e) => {
    e.preventDefault();
    openChat();
  });

  if (!form || !input || !messages) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.disabled = true;
    form.querySelector("button")?.setAttribute("disabled", "true");

    appendBubble(messages, "user", text);
    chatHistory.push({ role: "user", content: text });

    const typing = appendBubble(messages, "assistant", "Thinking…", "typing");

    try {
      const { reply } = await sendChatMessage(text, chatHistory.slice(0, -1));
      typing.remove();
      appendBubble(messages, "assistant", reply);
      chatHistory.push({ role: "assistant", content: reply });
    } catch (err) {
      typing.remove();
      appendBubble(messages, "assistant", `Sorry, something went wrong: ${err.message}`);
    } finally {
      input.disabled = false;
      form.querySelector("button")?.removeAttribute("disabled");
      input.focus();
    }
  });
}
