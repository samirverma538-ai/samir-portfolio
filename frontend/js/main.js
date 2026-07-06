import { fetchConfig, API_BASE } from "./api.js";
import { loadDocumentsGrid, initViewerModal } from "./documents.js";
import { initChat } from "./chat.js";

async function applySiteConfig() {
  try {
    const config = await fetchConfig();

    setText("site-header", config.header);
    setText("site-subheader", config.subheader);
    setText("owner-name", config.owner_name);
    setText("owner-role", config.role);
    setText("owner-experience", config.experience);
    setText("footer-name", config.owner_name);

    const pic = document.getElementById("profile-picture");
    if (pic && config.profile_picture) {
      const src = config.profile_picture.startsWith("http") ? config.profile_picture : (API_BASE + config.profile_picture);
      pic.src = src + "?t=" + Date.now();
    }

    toggleContact("contact-email-row", "contact-email", config.contact_email, (el, val) => {
      el.href = `mailto:${val}`;
      el.textContent = val;
    });
    toggleContact("contact-phone-row", "contact-phone", config.contact_phone);
    toggleContact("contact-linkedin-row", "contact-linkedin", config.contact_linkedin, (el, val) => {
      el.href = val;
    });

    document.title = config.header;
  } catch (err) {
    console.error("Failed to load site config:", err);
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text || "";
}

function toggleContact(rowId, valueId, value, setup) {
  const row = document.getElementById(rowId);
  const el = document.getElementById(valueId);
  if (!row || !el) return;
  if (value) {
    row.classList.remove("hidden");
    if (setup) setup(el, value);
    else el.textContent = value;
  } else {
    row.classList.add("hidden");
  }
}

document.getElementById("footer-year").textContent = new Date().getFullYear();

applySiteConfig();
initViewerModal();
initChat();

const grid = document.getElementById("documents-grid");
if (grid) loadDocumentsGrid(grid);
