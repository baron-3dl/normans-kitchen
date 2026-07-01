/* Poppa's Recipes — instant search & category filter.
   Progressive enhancement: cards are already in the HTML; we just filter them.
   Works with the file:// protocol and needs no network. */
(function () {
  "use strict";
  var search = document.getElementById("search");
  var grid = document.getElementById("recipe-grid");
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var meta = document.getElementById("result-meta");
  var noResults = document.getElementById("no-results");
  var activeCat = "";

  function norm(s) { return (s || "").toLowerCase(); }

  function apply() {
    var q = norm(search ? search.value : "").trim();
    var terms = q.split(/\s+/).filter(Boolean);
    var shown = 0;
    cards.forEach(function (card) {
      var hay = card.getAttribute("data-search") || "";
      var cats = (card.getAttribute("data-categories") || "").split("|");
      var okCat = !activeCat || cats.indexOf(activeCat) !== -1;
      var okText = terms.every(function (t) { return hay.indexOf(t) !== -1; });
      var visible = okCat && okText;
      card.style.display = visible ? "" : "none";
      if (visible) shown++;
    });
    if (noResults) noResults.style.display = shown === 0 ? "" : "none";
    if (meta) {
      if (!q && !activeCat) meta.textContent = cards.length + " recipes in the collection";
      else meta.textContent = shown + (shown === 1 ? " recipe" : " recipes") +
        (activeCat ? " in " + activeCat : "") + (q ? ' matching “' + q + '”' : "");
    }
  }

  if (search) {
    search.addEventListener("input", apply);
    // "/" focuses search
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== search) { e.preventDefault(); search.focus(); }
    });
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var cat = chip.getAttribute("data-cat") || "";
      if (activeCat === cat) { activeCat = ""; } else { activeCat = cat; }
      chips.forEach(function (c) {
        c.setAttribute("aria-pressed", c.getAttribute("data-cat") === activeCat ? "true" : "false");
      });
      apply();
    });
  });

  // support ?c=Category and #Category deep links from other pages.
  // Guard against malformed URLs so a bad hash never disables search.
  try {
    var params = new URLSearchParams(window.location.search);
    var hash = (window.location.hash || "").replace(/^#/, "");
    var initCat = params.get("c") || (hash ? decodeURIComponent(hash) : "");
    if (initCat) {
      var match = chips.filter(function (c) { return c.getAttribute("data-cat") === initCat; })[0];
      if (match) match.click();
    }
  } catch (e) { /* ignore malformed deep-link */ }
  apply();
})();
