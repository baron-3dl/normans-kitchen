/* Poppa's Recipes — Original / Enhanced view mode.
   Global toggle (header) sets the default and drives the index; each recipe has
   its own Enhanced/Original tabs that start from the global mode but can flip
   locally. Persisted in localStorage. Head has an inline snippet that sets the
   mode before paint to avoid a flash. */
(function () {
  "use strict";
  var KEY = "nk-mode";
  var root = document.documentElement;

  function mode() { return root.getAttribute("data-mode") === "enhanced" ? "enhanced" : "original"; }

  function syncToggle(m) {
    document.querySelectorAll(".mode-toggle [data-mode]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false");
    });
  }
  function syncTabs(article, v) {
    article.querySelectorAll(".view-tab").forEach(function (t) {
      t.setAttribute("aria-selected", t.getAttribute("data-view") === v ? "true" : "false");
    });
  }

  function setGlobal(m) {
    root.setAttribute("data-mode", m);
    try { localStorage.setItem(KEY, m); } catch (e) {}
    syncToggle(m);
    document.querySelectorAll(".recipe[data-view]").forEach(function (a) {
      a.setAttribute("data-view", m); syncTabs(a, m);
    });
  }

  var saved = mode();
  try { saved = localStorage.getItem(KEY) || saved; } catch (e) {}
  root.setAttribute("data-mode", saved);
  syncToggle(saved);

  document.querySelectorAll(".mode-toggle [data-mode]").forEach(function (b) {
    b.addEventListener("click", function () { setGlobal(b.getAttribute("data-mode")); });
  });

  document.querySelectorAll(".recipe[data-view]").forEach(function (a) {
    a.setAttribute("data-view", saved); syncTabs(a, saved);
    a.querySelectorAll(".view-tab").forEach(function (t) {
      t.addEventListener("click", function (e) {
        e.preventDefault();
        var v = t.getAttribute("data-view");
        a.setAttribute("data-view", v); syncTabs(a, v);
      });
    });
  });
})();
