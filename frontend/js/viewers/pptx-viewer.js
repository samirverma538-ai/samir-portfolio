const PPTX_CDN = {
  jquery: "https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js",
  jszip: "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js",
  d3: "https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.17/d3.min.js",
  nvD3: "https://cdnjs.cloudflare.com/ajax/libs/nvd3/1.8.6/nv.d3.min.js",
  nvD3Css: "https://cdnjs.cloudflare.com/ajax/libs/nvd3/1.8.6/nv.d3.min.css",
  pptxjs: "https://cdn.jsdelivr.net/gh/meshesha/PPTXjs@master/js/pptxjs.js",
  divs2slides: "https://cdn.jsdelivr.net/gh/meshesha/PPTXjs@master/js/divs2slides.js",
};

let pptxScriptsLoaded = false;

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

function loadStylesheet(href) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`link[href="${href}"]`)) {
      resolve();
      return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.onload = resolve;
    link.onerror = () => reject(new Error(`Failed to load ${href}`));
    document.head.appendChild(link);
  });
}

async function ensurePptxLibs() {
  if (pptxScriptsLoaded && window.jQuery && window.$ && window.$().pptxToHtml) return;

  await loadScript(PPTX_CDN.jquery);
  await loadScript(PPTX_CDN.jszip);
  await loadScript(PPTX_CDN.d3);
  await loadStylesheet(PPTX_CDN.nvD3Css);
  await loadScript(PPTX_CDN.nvD3);
  await loadScript(PPTX_CDN.pptxjs);
  await loadScript(PPTX_CDN.divs2slides);
  pptxScriptsLoaded = true;
}

export async function renderPptx(container, url) {
  await ensurePptxLibs();
  container.innerHTML = "";
  const wrapper = document.createElement("div");
  wrapper.id = "pptx-preview-" + Date.now();
  wrapper.className = "pptx-wrapper";
  container.appendChild(wrapper);

  return new Promise((resolve, reject) => {
    try {
      window.jQuery(`#${wrapper.id}`).pptxToHtml({
        pptxFileUrl: url,
        slideMode: true,
        keyBoardShortCut: true,
        slidesScale: "50%",
        success: () => resolve(),
        error: (err) => reject(err || new Error("PPTX render failed")),
      });
    } catch (err) {
      reject(err);
    }
  });
}
