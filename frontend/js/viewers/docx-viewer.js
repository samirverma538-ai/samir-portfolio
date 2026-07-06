const DOCX_CDN = {
  jszip: "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  docxPreview: "https://cdn.jsdelivr.net/npm/docx-preview@0.3.3/dist/docx-preview.min.js",
};

let docxScriptsLoaded = false;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

async function ensureDocxLibs() {
  if (docxScriptsLoaded && window.JSZip && window.docx) return;
  await loadScript(DOCX_CDN.jszip);
  await loadScript(DOCX_CDN.docxPreview);
  docxScriptsLoaded = true;
}

export async function renderDocx(container, url) {
  await ensureDocxLibs();
  container.innerHTML = "";
  const wrapper = document.createElement("div");
  wrapper.className = "docx-wrapper";
  container.appendChild(wrapper);

  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch document");
  const blob = await response.blob();

  await window.docx.renderAsync(blob, wrapper, null, {
    className: "docx",
    inWrapper: true,
    ignoreWidth: false,
    ignoreHeight: false,
    breakPages: true,
  });
}
