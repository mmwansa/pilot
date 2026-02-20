(function () {
  "use strict";

  if (window.DashboardTabs && window.DashboardTabs.__initialized) return;

  const shellState = new Map();
  const storagePrefix = "dashboard-tabs:v1";

  const perfNow = () => (
    window.performance && typeof window.performance.now === "function"
      ? window.performance.now()
      : Date.now()
  );

  const perfLog = (name, startMs, meta) => {
    const durationMs = perfNow() - startMs;
    if (meta) {
      console.log(`[perf][tabs] ${name} ${durationMs.toFixed(2)}ms`, meta);
    } else {
      console.log(`[perf][tabs] ${name} ${durationMs.toFixed(2)}ms`);
    }
  };

  const getLoader = () => window.DashboardLoader || null;

  const storageKeyForShell = (shell) => {
    const shellName = shell?.dataset?.shell || "unknown";
    return `${storagePrefix}:${window.location.pathname}:${shellName}`;
  };

  const readSessionState = (shell) => {
    if (!window.sessionStorage) return null;
    try {
      const raw = window.sessionStorage.getItem(storageKeyForShell(shell));
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return typeof parsed === "object" && parsed ? parsed : null;
    } catch (_error) {
      return null;
    }
  };

  const writeSessionState = (shell, state) => {
    if (!window.sessionStorage || !state) return;
    try {
      window.sessionStorage.setItem(storageKeyForShell(shell), JSON.stringify(state));
    } catch (_error) {
      // no-op
    }
  };

  const discoverTabLinks = (shell) => Array.from(shell.querySelectorAll("[data-tab]"));
  const discoverPanels = (shell) => Array.from(shell.querySelectorAll(".dashboard-tab-panel[data-tab-panel]"));

  const parseScopes = (container) =>
    String(container?.dataset?.scope || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

  const setPanelVisibility = (panel, isActive) => {
    panel.classList.toggle("active", isActive);
    panel.classList.toggle("show", isActive);
    panel.setAttribute("aria-hidden", isActive ? "false" : "true");
  };

  const emitComponentRefreshes = (shell, panel, tabKey) => {
    const shellName = shell.dataset.shell || "unknown";
    const components = Array.from(panel.querySelectorAll("[data-component]"));
    components.forEach((el) => {
      const componentName = el.dataset.component || "unknown";
      el.dispatchEvent(
        new CustomEvent("dashboard:refresh-component", {
          bubbles: true,
          detail: {
            shell: shellName,
            tab: tabKey,
            component: componentName,
          },
        })
      );
    });
    return components.length;
  };

  const hydratePanelComponents = async (panel) => {
    const loader = getLoader();
    if (!loader || typeof loader.loadComponentOnce !== "function") return;
    const slots = Array.from(panel.querySelectorAll("[data-component-slot]"));
    if (!slots.length) return;
    await Promise.all(slots.map((slot) => loader.loadComponentOnce(slot)));
  };

  const getInitialTab = (shell, links) => {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && links.some((link) => link.dataset.tab === urlTab)) return urlTab;
    const activeLink = links.find((link) => link.classList.contains("active"));
    if (activeLink?.dataset?.tab) return activeLink.dataset.tab;
    const fromSession = readSessionState(shell)?.lastTab || "";
    if (fromSession && links.some((link) => link.dataset.tab === fromSession)) return fromSession;
    return links[0]?.dataset?.tab || null;
  };

  const pushTabToUrl = (tabKey, mode) => {
    if (!tabKey) return;
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tabKey);
    if (mode === "replace") {
      window.history.replaceState({ tab: tabKey }, "", url.toString());
      return;
    }
    window.history.pushState({ tab: tabKey }, "", url.toString());
  };

  const activateTab = async (shell, tabKey, options) => {
    const started = perfNow();
    const opts = options || {};
    const state = shellState.get(shell);
    if (!state) return;

    const selectedLink = state.links.find((link) => link.dataset.tab === tabKey) || state.links[0];
    if (!selectedLink) return;
    const activeTab = selectedLink.dataset.tab;

    state.links.forEach((link) => {
      const isActive = link.dataset.tab === activeTab;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    let activePanel = null;
    state.panels.forEach((panel) => {
      const isActive = panel.dataset.tabPanel === activeTab;
      setPanelVisibility(panel, isActive);
      if (isActive) activePanel = panel;
    });
    if (!activePanel) return;

    const firstLoad = !state.loadedTabs.has(activeTab);
    if (firstLoad) {
      await hydratePanelComponents(activePanel);
      state.loadedTabs.add(activeTab);
    }
    state.activeTab = activeTab;

    writeSessionState(shell, {
      lastTab: activeTab,
      loadedTabs: Array.from(state.loadedTabs),
    });

    if (opts.pushState) {
      pushTabToUrl(activeTab, "push");
    } else if (opts.replaceState) {
      pushTabToUrl(activeTab, "replace");
    }

    const componentCount = emitComponentRefreshes(shell, activePanel, activeTab);
    document.dispatchEvent(
      new CustomEvent("dashboard:refresh-tab", {
        detail: {
          shell: shell.dataset.shell || "unknown",
          tab: activeTab,
          componentCount,
          firstLoad,
        },
      })
    );
    perfLog("tab.activate", started, {
      shell: shell.dataset.shell || "unknown",
      tab: activeTab,
      firstLoad,
      pushState: !!opts.pushState,
    });
  };

  const invalidateComponentsByScope = (scopeKey) => {
    if (!scopeKey) return;
    const loader = getLoader();
    if (loader && typeof loader.invalidateComponentsByScope === "function") {
      loader.invalidateComponentsByScope(scopeKey);
    }

    shellState.forEach((state, shell) => {
      state.panels.forEach((panel) => {
        const hasScope = Array.from(panel.querySelectorAll("[data-component-slot][data-scope]"))
          .some((slot) => parseScopes(slot).includes(scopeKey));
        if (hasScope) {
          state.loadedTabs.delete(panel.dataset.tabPanel || "");
        }
      });
      writeSessionState(shell, {
        lastTab: state.activeTab,
        loadedTabs: Array.from(state.loadedTabs),
      });
    });
  };

  const refreshComponent = async (container) => {
    const loader = getLoader();
    if (!loader || typeof loader.refreshComponent !== "function") return;
    await loader.refreshComponent(container);
  };

  const loadComponentOnce = async (container) => {
    const loader = getLoader();
    if (!loader || typeof loader.loadComponentOnce !== "function") return;
    await loader.loadComponentOnce(container);
  };

  const initShell = (shell) => {
    const links = discoverTabLinks(shell);
    const panels = discoverPanels(shell);
    if (!links.length || !panels.length) return;

    const restoredLoadedTabs = new Set(
      (readSessionState(shell)?.loadedTabs || [])
        .map((tab) => String(tab || ""))
        .filter((tab) => panels.some((panel) => panel.dataset.tabPanel === tab))
    );

    const state = {
      links,
      panels,
      loadedTabs: restoredLoadedTabs,
      activeTab: "",
    };
    shellState.set(shell, state);

    const initialTab = getInitialTab(shell, links);
    if (initialTab) {
      activateTab(shell, initialTab, { pushState: false, replaceState: false }).catch((error) => console.error(error));
    }

    links.forEach((link) => {
      link.addEventListener("click", (event) => {
        const tab = link.dataset.tab;
        if (!tab) return;
        event.preventDefault();
        activateTab(shell, tab, { pushState: true }).catch((error) => console.error(error));
      });
    });
  };

  const init = () => {
    const started = perfNow();
    Array.from(document.querySelectorAll(".dashboard-shell[data-shell]")).forEach(initShell);
    window.addEventListener("popstate", () => {
      const queryTab = new URLSearchParams(window.location.search).get("tab");
      shellState.forEach((_state, shell) => {
        const fallbackTab = discoverTabLinks(shell)[0]?.dataset?.tab || null;
        const targetTab = queryTab && shell.querySelector(`[data-tab="${queryTab}"]`)
          ? queryTab
          : fallbackTab;
        if (targetTab) {
          activateTab(shell, targetTab, { pushState: false, replaceState: false }).catch((error) => console.error(error));
        }
      });
    });
    perfLog("dashboard_tabs.init", started, { shellCount: shellState.size });
  };

  window.DashboardTabs = {
    __initialized: true,
    activateTab,
    invalidateComponentsByScope,
    refreshComponent,
    loadComponentOnce,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
