import {
  fetchConfig,
  updateConfig,
  uploadProfilePicture,
  fetchDocuments,
  uploadDocuments,
  updateDocument,
  deleteDocument,
  API_BASE,
} from "./api.js";

const MAX_UPLOAD_FILES = 4;
const FILE_ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png,.txt";

function getSelectedUploadFiles() {
  const container = document.getElementById("file-upload-slots");
  if (!container) return [];
  return Array.from(container.querySelectorAll(".file-slot-input"))
    .map((input) => input.files?.[0])
    .filter(Boolean);
}

function addUploadSlot() {
  const container = document.getElementById("file-upload-slots");
  if (!container) return;

  const existing = container.querySelectorAll(".file-upload-slot").length;
  if (existing >= MAX_UPLOAD_FILES) return;

  const slot = document.createElement("div");
  slot.className = "file-upload-slot";
  slot.innerHTML = `
    <label class="file-slot-label">File ${existing + 1}</label>
    <input type="file" class="file-slot-input" accept="${FILE_ACCEPT}">
    <span class="file-slot-name"></span>
  `;

  const input = slot.querySelector(".file-slot-input");
  input.addEventListener("change", () => handleUploadSlotChange(slot, input));
  container.appendChild(slot);
}

function handleUploadSlotChange(slot, input) {
  const container = document.getElementById("file-upload-slots");
  const nameEl = slot.querySelector(".file-slot-name");
  const file = input.files?.[0];

  if (file) {
    nameEl.textContent = file.name;
    const slots = container.querySelectorAll(".file-upload-slot");
    const isLastSlot = slot === slots[slots.length - 1];
    if (isLastSlot && slots.length < MAX_UPLOAD_FILES) {
      addUploadSlot();
    }
  } else {
    nameEl.textContent = "";
  }
}

function resetUploadSlots() {
  const container = document.getElementById("file-upload-slots");
  if (!container) return;
  container.innerHTML = "";
  addUploadSlot();
}

function setStatus(el, message, type = "") {
  if (!el) return;
  el.textContent = message;
  el.className = `form-status ${type}`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getGroupLabel(group) {
  if (group.title) return group.title;
  const primary = group.files[0];
  if (group.description) return group.description;
  if (group.files.length === 1) return primary.original_filename;
  return `${primary.original_filename} (+${group.files.length - 1} more)`;
}

async function loadConfigForm() {
  const config = await fetchConfig();
  const fields = [
    "header",
    "subheader",
    "owner_name",
    "role",
    "experience",
    "contact_email",
    "contact_phone",
    "contact_linkedin",
  ];
  fields.forEach((f) => {
    const el = document.getElementById(f);
    if (el) el.value = config[f] || "";
  });

  const preview = document.getElementById("admin-profile-preview");
  if (preview && config.profile_picture) {
    const src = config.profile_picture.startsWith("http") ? config.profile_picture : (API_BASE + config.profile_picture);
    preview.src = src + "?t=" + Date.now();
  }
}

async function loadAdminDocuments() {
  const list = document.getElementById("admin-documents-list");
  if (!list) return;

  try {
    const groups = await fetchDocuments();
    if (!groups.length) {
      list.innerHTML = '<p class="empty-state">No documents yet.</p>';
      return;
    }

    list.innerHTML = groups
      .map(
        (group) => `
      <div class="admin-doc-item" data-id="${group.id}">
        <div class="admin-doc-info">
          <h4>${escapeHtml(getGroupLabel(group))}</h4>
          <p>${group.files.length} file(s) · ${new Date(group.upload_date).toLocaleDateString()}</p>
          <ul class="admin-file-list">
            ${group.files
              .map((file) => `<li>${escapeHtml(file.original_filename)} (${file.file_type.toUpperCase().slice(1)})</li>`)
              .join("")}
          </ul>
        </div>
        <div class="admin-doc-actions">
          <input type="text" class="title-input" value="${escapeHtml(group.title || "")}" placeholder="Title / Header">
          <input type="text" class="desc-input" value="${escapeHtml(group.description || "")}" placeholder="Description">
          <input type="password" class="pw-input" placeholder="Admin password">
          <button class="btn btn-secondary save-desc-btn">Save</button>
          <button class="btn btn-danger delete-btn">Delete</button>
        </div>
      </div>
    `
      )
      .join("");

    list.querySelectorAll(".admin-doc-item").forEach((item) => {
      const id = Number(item.dataset.id);

      item.querySelector(".save-desc-btn")?.addEventListener("click", async () => {
        const title = item.querySelector(".title-input")?.value ?? "";
        const desc = item.querySelector(".desc-input")?.value ?? "";
        const pw = item.querySelector(".pw-input")?.value ?? "";
        try {
          await updateDocument(id, title, desc, pw);
          alert("Document details updated.");
          await loadAdminDocuments();
        } catch (err) {
          alert(err.message);
        }
      });

      item.querySelector(".delete-btn")?.addEventListener("click", async () => {
        const pw = item.querySelector(".pw-input")?.value ?? "";
        if (!confirm("Delete this upload and all its files permanently?")) return;
        try {
          await deleteDocument(id, pw);
          await loadAdminDocuments();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  } catch (err) {
    list.innerHTML = `<p class="empty-state error">${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("config-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("config-status");
  const form = e.target;
  const data = {
    header: form.header.value,
    subheader: form.subheader.value,
    owner_name: form.owner_name.value,
    role: form.role.value,
    experience: form.experience.value,
    contact_email: form.contact_email.value,
    contact_phone: form.contact_phone.value,
    contact_linkedin: form.contact_linkedin.value,
    admin_password: form.admin_password.value,
  };

  try {
    await updateConfig(data);
    setStatus(status, "Configuration saved successfully.", "success");
    form.admin_password.value = "";
  } catch (err) {
    setStatus(status, err.message, "error");
  }
});

document.getElementById("profile-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("profile-status");
  const form = e.target;
  const file = form.file.files[0];
  if (!file) return;

  try {
    const config = await uploadProfilePicture(file, form.admin_password.value);
    const preview = document.getElementById("admin-profile-preview");
    if (preview) {
      const src = config.profile_picture.startsWith("http") ? config.profile_picture : (API_BASE + config.profile_picture);
      preview.src = src + "?t=" + Date.now();
    }
    setStatus(status, "Profile picture updated.", "success");
    form.reset();
  } catch (err) {
    setStatus(status, err.message, "error");
  }
});

document.getElementById("upload-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("upload-status");
  const form = e.target;
  const files = getSelectedUploadFiles();
  if (!files.length) {
    setStatus(status, "Please select at least one file.", "error");
    return;
  }

  try {
    const result = await uploadDocuments(files, form.title.value, form.description.value, form.admin_password.value);
    setStatus(
      status,
      `${result.files.length} document(s) uploaded successfully.`,
      "success"
    );
    form.title.value = "";
    form.description.value = "";
    form.admin_password.value = "";
    resetUploadSlots();
    await loadAdminDocuments();
  } catch (err) {
    setStatus(status, err.message, "error");
  }
});

resetUploadSlots();
loadConfigForm();
loadAdminDocuments();
