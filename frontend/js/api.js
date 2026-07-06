export const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "https://YOUR_BACKEND_RENDER_URL.onrender.com"; // TODO: Replace with your actual deployed Render backend URL

function normalizeDocumentGroups(data) {
  if (!Array.isArray(data) || !data.length) return [];
  if (data[0].files) return data;
  return data.map((doc) => ({
    id: doc.id,
    group_id: String(doc.id),
    description: doc.description || "",
    upload_date: doc.upload_date,
    files: [
      {
        id: doc.id,
        filename: doc.filename,
        original_filename: doc.original_filename,
        file_type: doc.file_type,
        group_order: 0,
        thumbnail_path: doc.thumbnail_path || null,
      },
    ],
  }));
}

export async function fetchConfig() {
  const res = await fetch(`${API_BASE}/api/config`);
  if (!res.ok) throw new Error("Failed to load site configuration");
  return res.json();
}

export async function updateConfig(data) {
  const res = await fetch(`${API_BASE}/api/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update configuration");
  }
  return res.json();
}

export async function uploadProfilePicture(file, adminPassword) {
  const form = new FormData();
  form.append("file", file);
  form.append("admin_password", adminPassword);
  const res = await fetch(`${API_BASE}/api/config/profile-picture`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload profile picture");
  }
  return res.json();
}

export async function fetchDocuments() {
  const res = await fetch(`${API_BASE}/api/documents`);
  if (!res.ok) throw new Error("Failed to load documents");
  const data = await res.json();
  return normalizeDocumentGroups(data);
}

export async function uploadDocuments(files, description, adminPassword) {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  form.append("description", description);
  form.append("admin_password", adminPassword);
  const res = await fetch(`${API_BASE}/api/documents`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload documents");
  }
  return res.json();
}

export async function updateDocument(id, description, adminPassword) {
  const res = await fetch(`${API_BASE}/api/documents/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, admin_password: adminPassword }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update document");
  }
  return res.json();
}

export async function deleteDocument(id, adminPassword) {
  const res = await fetch(`${API_BASE}/api/documents/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ admin_password: adminPassword }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete document");
  }
  return res.json();
}

export async function sendChatMessage(message, history) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Chat request failed");
  }
  return res.json();
}
