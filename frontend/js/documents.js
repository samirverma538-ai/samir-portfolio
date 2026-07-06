import { fetchDocuments, deleteDocument, API_BASE } from "./api.js";
import { renderDocx } from "./viewers/docx-viewer.js";
import { renderPptx } from "./viewers/pptx-viewer.js";

let currentViewerGroup = null;
let documentsGridEl = null;
let zoomMode = "manual";
let manualZoomLevel = 0.7;
const DEFAULT_ZOOM = 0.7;
const ZOOM_STEP = 0.15;
const ZOOM_MIN = 0.25;
const ZOOM_MAX = 3;

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getFileUrl(file) {
  return `${API_BASE}/uploads/${file.filename}`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getPrimaryFile(group) {
  return group.files[0];
}

function getGroupTitle(group) {
  if (group.description) return group.description;
  return group.files.length > 1 ? `Document set (${group.files.length} files)` : "Document";
}

function getViewerCanvas() {
  return document.getElementById("viewer-canvas");
}

function getCurrentFitScale() {
  const stage = document.getElementById("viewer-stage");
  const canvas = getViewerCanvas();
  if (!stage || !canvas) return 1;

  const pad = 16;
  const stageW = Math.max(stage.clientWidth - pad, 1);
  const stageH = Math.max(stage.clientHeight - pad, 1);
  const naturalW = Math.max(canvas.offsetWidth, 1);
  const naturalH = Math.max(canvas.offsetHeight, 1);

  const scale = Math.min(stageW / naturalW, stageH / naturalH, 1);
  return Number.isFinite(scale) && scale > 0 ? scale : 1;
}

function applyViewerZoom() {
  const stage = document.getElementById("viewer-stage");
  const shell = document.getElementById("viewer-zoom-shell");
  const canvas = getViewerCanvas();
  const label = document.getElementById("viewer-zoom-label");
  if (!stage || !shell || !canvas) return;

  const naturalW = Math.max(canvas.offsetWidth, 1);
  const naturalH = Math.max(canvas.offsetHeight, 1);
  const scale = zoomMode === "fit" ? getCurrentFitScale() : manualZoomLevel;

  shell.style.width = `${naturalW * scale}px`;
  shell.style.height = `${naturalH * scale}px`;
  canvas.style.transform = `scale(${scale})`;
  canvas.style.transformOrigin = "top left";

  if (label) {
    label.textContent = zoomMode === "fit" ? `Fit (${Math.round(scale * 100)}%)` : `${Math.round(scale * 100)}%`;
  }
}

function scheduleViewerZoom() {
  requestAnimationFrame(applyViewerZoom);
  setTimeout(applyViewerZoom, 200);
  setTimeout(applyViewerZoom, 800);
  setTimeout(applyViewerZoom, 2000);
}

function resetViewerZoom() {
  zoomMode = "manual";
  manualZoomLevel = DEFAULT_ZOOM;
}

function fitViewerToWindow() {
  zoomMode = "fit";
  applyViewerZoom();
}

function zoomViewerIn() {
  if (zoomMode === "fit") {
    manualZoomLevel = getCurrentFitScale();
  }
  zoomMode = "manual";
  manualZoomLevel = Math.min(manualZoomLevel + ZOOM_STEP, ZOOM_MAX);
  applyViewerZoom();
}

function zoomViewerOut() {
  if (zoomMode === "fit") {
    manualZoomLevel = getCurrentFitScale();
  }
  zoomMode = "manual";
  manualZoomLevel = Math.max(manualZoomLevel - ZOOM_STEP, ZOOM_MIN);
  applyViewerZoom();
}

function downloadFile(file) {
  const a = document.createElement("a");
  a.href = getFileUrl(file);
  a.download = file.original_filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function downloadAllFiles(group) {
  group.files.forEach((file, index) => {
    setTimeout(() => downloadFile(file), index * 300);
  });
}

function renderViewerDownloads(container, group) {
  if (!container) return;

  const rows = group.files
    .map(
      (file, index) => `
    <div class="viewer-file-row">
      <span class="viewer-file-name">${escapeHtml(file.original_filename)}</span>
      <button type="button" class="btn btn-secondary btn-xs file-download-btn" data-file-index="${index}">Download</button>
    </div>
  `
    )
    .join("");

  container.innerHTML = rows;
  container.classList.remove("hidden");

  container.querySelectorAll(".file-download-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const file = group.files[Number(btn.dataset.fileIndex)];
      if (file) downloadFile(file);
    });
  });
}

async function promptDeleteGroup(group) {
  const password = prompt("Enter admin password to delete this document:");
  if (password === null || password === "") return false;

  const label = getGroupTitle(group);
  if (!confirm(`Delete "${label}" and all ${group.files.length} file(s) permanently?`)) return false;

  try {
    await deleteDocument(group.id, password);
    closeViewer();
    if (documentsGridEl) await loadDocumentsGrid(documentsGridEl);
    return true;
  } catch (err) {
    alert(err.message);
    return false;
  }
}

export async function loadDocumentsGrid(gridEl) {
  documentsGridEl = gridEl;
  try {
    const groups = await fetchDocuments();
    if (!groups.length) {
      gridEl.innerHTML =
        '<p class="empty-state">No documents uploaded yet. Use the Admin dashboard to add documents.</p>';
      return;
    }

    gridEl.innerHTML = groups
      .map((group) => {
        const primary = getPrimaryFile(group);
        const description = group.description || "No description provided.";
        const fileCountLabel = group.files.length > 1 ? ` · ${group.files.length} files` : "";
        const thumb = primary.thumbnail_path
          ? `<img src="${primary.thumbnail_path.startsWith("http") ? primary.thumbnail_path : (API_BASE + primary.thumbnail_path)}" alt="" loading="lazy">`
          : `<div class="doc-thumb-fallback">Preview</div>`;

        return `
      <article class="doc-card" data-group-id="${group.id}">
        <div class="doc-card-body">
          <div class="doc-thumb">${thumb}</div>
          <div class="doc-desc-scroll">${escapeHtml(description)}</div>
          <p class="doc-meta">${formatDate(group.upload_date)}${fileCountLabel}</p>
        </div>
      </article>
    `;
      })
      .join("");

    gridEl.querySelectorAll(".doc-card").forEach((card) => {
      const groupId = Number(card.dataset.groupId);
      const group = groups.find((g) => g.id === groupId);
      if (!group) return;

      card.querySelector(".doc-card-body")?.addEventListener("click", () => openViewer(group));
    });
  } catch (err) {
    gridEl.innerHTML = `<p class="empty-state error">Failed to load documents: ${escapeHtml(err.message)}</p>`;
  }
}

function onViewerResize() {
  const modal = document.getElementById("viewer-modal");
  if (modal && !modal.classList.contains("hidden") && zoomMode === "fit") {
    applyViewerZoom();
  }
}

export function initViewerModal() {
  const modal = document.getElementById("viewer-modal");
  if (!modal) return;

  modal.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeViewer);
  });

  document.getElementById("viewer-zoom-in")?.addEventListener("click", zoomViewerIn);
  document.getElementById("viewer-zoom-out")?.addEventListener("click", zoomViewerOut);
  document.getElementById("viewer-zoom-fit")?.addEventListener("click", fitViewerToWindow);

  document.getElementById("viewer-download-all")?.addEventListener("click", () => {
    if (currentViewerGroup) downloadAllFiles(currentViewerGroup);
  });

  document.getElementById("viewer-delete")?.addEventListener("click", async () => {
    if (currentViewerGroup) await promptDeleteGroup(currentViewerGroup);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeViewer();
    }
  });

  window.addEventListener("resize", onViewerResize);
}

function closeViewer() {
  const modal = document.getElementById("viewer-modal");
  const canvas = getViewerCanvas();
  const downloads = document.getElementById("viewer-downloads");
  const description = document.getElementById("viewer-description");
  const downloadAllBtn = document.getElementById("viewer-download-all");
  const shell = document.getElementById("viewer-zoom-shell");
  currentViewerGroup = null;
  resetViewerZoom();
  if (modal) modal.classList.add("hidden");
  if (canvas) canvas.innerHTML = "";
  if (shell) {
    shell.style.width = "";
    shell.style.height = "";
  }
  if (description) description.textContent = "";
  if (downloads) {
    downloads.innerHTML = "";
    downloads.classList.add("hidden");
  }
  if (downloadAllBtn) downloadAllBtn.classList.add("hidden");
  document.body.classList.remove("viewer-open");
}

async function openViewer(group) {
  const modal = document.getElementById("viewer-modal");
  const canvas = getViewerCanvas();
  const description = document.getElementById("viewer-description");
  const downloads = document.getElementById("viewer-downloads");
  const downloadAllBtn = document.getElementById("viewer-download-all");

  if (!modal || !canvas) return;

  const doc = getPrimaryFile(group);
  currentViewerGroup = group;
  resetViewerZoom();
  canvas.innerHTML = '<p class="viewer-loading">Loading preview…</p>';
  if (description) {
    description.textContent = group.description || "No description provided.";
  }
  modal.classList.remove("hidden");
  document.body.classList.add("viewer-open");
  document.getElementById("viewer-scroll")?.scrollTo(0, 0);

  renderViewerDownloads(downloads, group);

  if (group.files.length > 1) {
    downloadAllBtn?.classList.remove("hidden");
  } else {
    downloadAllBtn?.classList.add("hidden");
  }

  const url = getFileUrl(doc);
  const ext = doc.file_type.toLowerCase();

  try {
    canvas.innerHTML = "";

    if (ext === ".pdf") {
      const iframe = document.createElement("iframe");
      iframe.src = url;
      iframe.title = doc.original_filename;
      iframe.className = "pdf-preview-frame";
      canvas.appendChild(iframe);
      iframe.addEventListener("load", scheduleViewerZoom);
    } else if (ext === ".docx" || ext === ".doc") {
      await renderDocx(canvas, url);
      scheduleViewerZoom();
    } else if (ext === ".pptx" || ext === ".ppt") {
      await renderPptx(canvas, url);
      scheduleViewerZoom();
    } else if ([".jpg", ".jpeg", ".png"].includes(ext)) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = doc.original_filename;
      img.addEventListener("load", scheduleViewerZoom);
      canvas.appendChild(img);
    } else if (ext === ".txt") {
      const response = await fetch(url);
      const text = await response.text();
      const pre = document.createElement("pre");
      pre.className = "txt-preview";
      pre.textContent = text;
      canvas.appendChild(pre);
      scheduleViewerZoom();
    } else {
      canvas.innerHTML = `<p style="padding:2rem;">Preview not available for this file type. <a href="${url}" download="${escapeHtml(doc.original_filename)}">Download file</a></p>`;
      scheduleViewerZoom();
    }
  } catch (err) {
    canvas.innerHTML = `<p style="padding:2rem;color:#c00;">Failed to render preview: ${escapeHtml(err.message)}. <a href="${url}" download="${escapeHtml(doc.original_filename)}">Download instead</a></p>`;
    scheduleViewerZoom();
  }
}
