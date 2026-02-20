(function () {
  "use strict";

  function perfNow() {
    return (window.performance && typeof window.performance.now === "function")
      ? window.performance.now()
      : Date.now();
  }

  function perfLog(name, startMs, meta) {
    const durationMs = perfNow() - startMs;
    if (meta) {
      console.log(`[perf][client] ${name} ${durationMs.toFixed(2)}ms`, meta);
    } else {
      console.log(`[perf][client] ${name} ${durationMs.toFixed(2)}ms`);
    }
  }

  function discoverComponents(panel) {
    return Array.from(panel.querySelectorAll("[data-component]"));
  }

  function refreshActiveComponents(shell, panel, tabKey) {
    const started = perfNow();
    const shellName = shell.dataset.shell || "unknown";
    const components = discoverComponents(panel);

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

    document.dispatchEvent(
      new CustomEvent("dashboard:refresh-tab", {
        detail: {
          shell: shellName,
          tab: tabKey,
          componentCount: components.length,
        },
      })
    );
    perfLog("tab.refresh_components", started, {
      shell: shellName,
      tab: tabKey,
      componentCount: components.length,
    });
  }

  function setPanelVisibility(panel, isActive) {
    panel.classList.toggle("active", isActive);
    panel.classList.toggle("show", isActive);
    panel.setAttribute("aria-hidden", isActive ? "false" : "true");
  }

  function activateTab(shell, tabKey, options) {
    const started = perfNow();
    const opts = options || {};
    const tabLinks = Array.from(shell.querySelectorAll("[data-tab]"));
    const tabPanels = Array.from(shell.querySelectorAll(".dashboard-tab-panel[data-tab-panel]"));

    const selectedLink = tabLinks.find((link) => link.dataset.tab === tabKey) || tabLinks[0];
    if (!selectedLink) return;

    const activeTab = selectedLink.dataset.tab;

    tabLinks.forEach((link) => {
      const isActive = link.dataset.tab === activeTab;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    let activePanel = null;
    tabPanels.forEach((panel) => {
      const isActive = panel.dataset.tabPanel === activeTab;
      setPanelVisibility(panel, isActive);
      if (isActive) activePanel = panel;
    });

    if (opts.pushState) {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", activeTab);
      window.history.pushState({ tab: activeTab }, "", url.toString());
    }

    if (activePanel) {
      refreshActiveComponents(shell, activePanel, activeTab);
    }
    perfLog("tab.activate", started, {
      shell: shell.dataset.shell || "unknown",
      tab: activeTab,
      pushState: !!opts.pushState,
    });
  }

  function getInitialTab(shell) {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && shell.querySelector("[data-tab='" + urlTab + "']")) {
      return urlTab;
    }

    const activeLink = shell.querySelector("[data-tab].active");
    if (activeLink) return activeLink.dataset.tab;

    const firstLink = shell.querySelector("[data-tab]");
    return firstLink ? firstLink.dataset.tab : null;
  }

  function initShell(shell) {
    const tabLinks = Array.from(shell.querySelectorAll("[data-tab]"));
    if (!tabLinks.length) return;

    const initialTab = getInitialTab(shell);
    if (initialTab) {
      activateTab(shell, initialTab, { pushState: false });
    }

    tabLinks.forEach((link) => {
      link.addEventListener("click", (event) => {
        const tabKey = link.dataset.tab;
        if (!tabKey) return;

        // Keep no-JS deep link behavior, but enhance with in-page switching when JS is available.
        event.preventDefault();
        activateTab(shell, tabKey, { pushState: true });
      });
    });

    window.addEventListener("popstate", () => {
      const targetTab = getInitialTab(shell);
      if (targetTab) {
        activateTab(shell, targetTab, { pushState: false });
      }
    });
  }

  function init() {
    const started = perfNow();
    const shells = Array.from(document.querySelectorAll(".dashboard-shell[data-shell]"));
    shells.forEach(initShell);
    perfLog("dashboard_shell.init", started, { shellCount: shells.length });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
