(function () {
  "use strict";

  const htmlCache = new Map();
  const inFlightLoads = new Map();
  const networkFetchCounts = new Map();
  const seenNetworkForKey = new Set();

  const perfNow = () => (
    window.performance && typeof window.performance.now === "function"
      ? window.performance.now()
      : Date.now()
  );

  const perfLog = (name, startMs, meta) => {
    const durationMs = perfNow() - startMs;
    if (meta) {
      console.log(`[perf][loader] ${name} ${durationMs.toFixed(2)}ms`, meta);
    } else {
      console.log(`[perf][loader] ${name} ${durationMs.toFixed(2)}ms`);
    }
  };

  const parseScopes = (container) =>
    String(container?.dataset?.scope || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

  const buildCacheKey = (container) => {
    const endpoint = container.dataset.endpoint || "";
    const customKey = container.dataset.cacheKey || "";
    return customKey || endpoint;
  };

  const fetchHtml = async (container) => {
    const endpoint = container.dataset.endpoint;
    if (!endpoint) return "";
    const response = await fetch(endpoint, {
      method: "GET",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error(`Failed to load component from ${endpoint}`);
    }
    return response.text();
  };

  const registerNetworkFetch = (key) => {
    if (!key) return;
    const nextCount = (networkFetchCounts.get(key) || 0) + 1;
    networkFetchCounts.set(key, nextCount);
    console.log("[perf][acceptance] component.network_fetch", { key, count: nextCount });
    if (seenNetworkForKey.has(key)) {
      console.warn("[perf][acceptance] duplicate_network_fetch_detected", { key, count: nextCount });
    } else {
      seenNetworkForKey.add(key);
    }
  };

  const setContainerHtml = (container, html) => {
    container.innerHTML = html;
    container.dataset.loaded = "1";
    container.dispatchEvent(
      new CustomEvent("dashboard:component-loaded", {
        bubbles: true,
        detail: {
          endpoint: container.dataset.endpoint || "",
          scope: parseScopes(container),
        },
      })
    );
  };

  const loadComponentOnce = async (container) => {
    if (!container) return;
    if (container.dataset.loaded === "1" && container.dataset.invalidated !== "1") {
      return;
    }
    const started = perfNow();
    const key = buildCacheKey(container);
    const allowCache = (container.dataset.cache || "on") !== "off";
    if (inFlightLoads.has(key)) {
      await inFlightLoads.get(key);
      return;
    }

    if (allowCache && key && htmlCache.has(key)) {
      setContainerHtml(container, htmlCache.get(key));
      container.dataset.invalidated = "0";
      perfLog("load_component.cached", started, { key });
      return;
    }

    const loadPromise = (async () => {
      registerNetworkFetch(key);
      const html = await fetchHtml(container);
      if (allowCache && key) {
        htmlCache.set(key, html);
      }
      setContainerHtml(container, html);
      container.dataset.invalidated = "0";
      perfLog("load_component.network", started, { key });
    })();
    inFlightLoads.set(key, loadPromise);
    try {
      await loadPromise;
    } finally {
      inFlightLoads.delete(key);
    }
  };

  const refreshComponent = async (container) => {
    if (!container) return;
    const started = perfNow();
    const key = buildCacheKey(container);
    registerNetworkFetch(key);
    const html = await fetchHtml(container);
    const allowCache = (container.dataset.cache || "on") !== "off";
    if (allowCache && key) {
      htmlCache.set(key, html);
    }
    setContainerHtml(container, html);
    container.dataset.invalidated = "0";
    perfLog("refresh_component.network", started, { key });
  };

  const invalidateComponentsByScope = (scopeKey) => {
    if (!scopeKey) return;
    const started = perfNow();
    document.querySelectorAll("[data-component-slot][data-scope]").forEach((container) => {
      const scopes = parseScopes(container);
      if (!scopes.includes(scopeKey)) return;
      container.dataset.invalidated = "1";
      container.dataset.loaded = "0";
      const key = buildCacheKey(container);
      if (key) {
        htmlCache.delete(key);
        seenNetworkForKey.delete(key);
        networkFetchCounts.delete(key);
      }
    });
    perfLog("invalidate.scope", started, { scope: scopeKey });
  };

  const bindRefreshButtons = () => {
    document.addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-action='refresh-component']");
      if (!trigger) return;
      event.preventDefault();
      const targetSelector = trigger.dataset.target;
      if (!targetSelector) return;
      const container = document.querySelector(targetSelector);
      if (!container) return;
      refreshComponent(container).catch((error) => console.error(error));
    });
  };

  bindRefreshButtons();

  window.DashboardLoader = {
    loadComponentOnce,
    refreshComponent,
    invalidateComponentsByScope,
  };
})();
