/* Poppa's Recipes — version switcher for dishes with multiple versions.
   Progressive enhancement: without JS, every version is visible and stacked;
   with JS, the pills switch between them and only one shows at a time. */
(function () {
  "use strict";
  var bar = document.querySelector(".versions");
  if (!bar) return;
  var article = bar.closest(".recipe");
  var pills = Array.prototype.slice.call(bar.querySelectorAll(".ver-pill"));
  var sections = Array.prototype.slice.call(article.querySelectorAll(".version"));
  if (sections.length < 2) return;

  function show(id) {
    sections.forEach(function (s) { s.hidden = s.id !== id; });
    pills.forEach(function (p) {
      p.setAttribute("aria-selected", p.getAttribute("href") === "#" + id ? "true" : "false");
    });
  }

  var ids = sections.map(function (s) { return s.id; });
  pills.forEach(function (p) {
    p.addEventListener("click", function (e) {
      e.preventDefault();
      var id = p.getAttribute("href").slice(1);
      show(id);
      if (history.replaceState) history.replaceState(null, "", "#" + id);
    });
  });

  var fromHash = (location.hash || "").slice(1);
  show(ids.indexOf(fromHash) >= 0 ? fromHash : ids[0]);
})();
