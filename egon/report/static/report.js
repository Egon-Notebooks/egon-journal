/* Egon report runtime: theme handling, chart embedding, responsive concat widths. */
(function () {
  "use strict";

  const specs = JSON.parse(document.getElementById("egon-specs").textContent);
  const darkMap = JSON.parse(document.getElementById("egon-dark-map").textContent);
  const root = document.documentElement;
  const STORAGE_KEY = "egon-report-theme";
  const views = new Map();

  // --- Theme ------------------------------------------------------------------

  function prefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function isDark() {
    const t = root.getAttribute("data-theme");
    return t === "dark" || (t === "auto" && prefersDark());
  }

  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* file:// in some browsers */ }

  document.querySelectorAll(".theme-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* ignore */ }
      renderAll();
    });
  });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (root.getAttribute("data-theme") === "auto") renderAll();
    });
  }

  // Charts are authored in light colors; dark mode swaps each hex for its pair.
  const darkPattern = new RegExp(Object.keys(darkMap).join("|"), "gi");
  function themed(spec) {
    let json = JSON.stringify(spec);
    if (isDark()) {
      const lower = Object.fromEntries(Object.entries(darkMap).map(([k, v]) => [k.toLowerCase(), v]));
      json = json.replace(darkPattern, (m) => lower[m.toLowerCase()] || m);
    }
    return JSON.parse(json);
  }

  // --- Responsive concatenations ------------------------------------------------
  // Vega-Lite only sizes single views to their container.  For hconcat specs,
  // sub-views with width "container" share whatever the fixed-width views leave.

  function resolveConcatWidths(spec, available) {
    // Stacked small multiples: every "container" panel takes the full width,
    // minus the y-axis and the right-hand label gutter.
    if (Array.isArray(spec.vconcat)) {
      const right = (spec.padding && spec.padding.right) || 12;
      spec.vconcat.forEach((v) => {
        if (v.width === "container") v.width = Math.max(available - right - 64, 200);
      });
      return spec;
    }
    // Wrapped grids (small multiples): equal columns, one column on small screens.
    if (Array.isArray(spec.concat)) {
      const cols = available < 640 ? 1 : spec.columns || 2;
      const spacing = spec.spacing != null ? spec.spacing : 20;
      const each = Math.floor((available - spacing * (cols - 1)) / cols) - 64; // y-axis + title
      spec.columns = cols;
      spec.concat.forEach((v) => { if (v.width === "container") v.width = Math.max(each, 200); });
      return spec;
    }
    if (!Array.isArray(spec.hconcat)) return spec;
    const spacing = spec.spacing != null ? spec.spacing : 20;
    const fixed = spec.hconcat.reduce((sum, v) => sum + (typeof v.width === "number" ? v.width : 0), 0);
    const flexible = spec.hconcat.filter((v) => v.width === "container");
    if (available < 640) {
      // Stack side-by-side views vertically on small screens.
      spec.vconcat = spec.hconcat.map((v) => ({ ...v, width: Math.max(available - 72, 200) }));
      delete spec.hconcat;
      return spec;
    }
    const gutter = spacing * (spec.hconcat.length - 1) + 110; // y-axis labels, legend, padding
    const each = Math.max(Math.floor((available - fixed - gutter) / Math.max(flexible.length, 1)), 220);
    flexible.forEach((v) => { v.width = each; });
    return spec;
  }

  // --- Embedding ----------------------------------------------------------------

  const tooltipOptions = { theme: "custom", offsetX: 14, offsetY: 14 };

  function render(el) {
    const key = el.getAttribute("data-chart");
    const base = specs[key];
    if (!base) return;
    let spec = themed(base);
    spec = resolveConcatWidths(spec, el.clientWidth);
    const previous = views.get(key);
    if (previous) previous.finalize();
    vegaEmbed(el, spec, { actions: false, renderer: "svg", tooltip: tooltipOptions, logLevel: vega.Error })
      .then((res) => views.set(key, res))
      .catch((err) => {
        el.innerHTML = '<p class="chart-error">This chart could not be drawn: ' + String(err.message || err) + "</p>";
      });
  }

  function renderAll() {
    document.querySelectorAll("[data-chart]").forEach(render);
  }

  // Re-layout concatenated charts when the card width changes.
  let lastWidth = window.innerWidth;
  let timer = null;
  window.addEventListener("resize", () => {
    if (Math.abs(window.innerWidth - lastWidth) < 24) return;
    lastWidth = window.innerWidth;
    clearTimeout(timer);
    timer = setTimeout(() => {
      document.querySelectorAll("[data-chart]").forEach((el) => {
        const sp = specs[el.getAttribute("data-chart")];
        if (sp.hconcat || sp.vconcat || sp.concat) render(el);
      });
    }, 150);
  });

  // Print: always light, and lay concat charts out for A4 width.
  window.addEventListener("beforeprint", () => {
    root.setAttribute("data-print", "1");
    const saved = root.getAttribute("data-theme");
    root.dataset.themeBeforePrint = saved;
    root.setAttribute("data-theme", "light");
    renderAll();
  });
  window.addEventListener("afterprint", () => {
    root.removeAttribute("data-print");
    root.setAttribute("data-theme", root.dataset.themeBeforePrint || "auto");
    renderAll();
  });

  renderAll();
})();
