/*
 * Stage switching for the matrix.
 *
 * A progressive enhancement over a page that is already complete: the markup
 * ships all five stage panels visible and the control hidden, and this script
 * reverses that. If it fails to load, a reader scrolls five captioned tables
 * instead of clicking between them, which is a worse experience and not a
 * broken one.
 *
 * No stage id appears in this file. The vocabulary lives in data/registry/ and
 * reaches here only through the data attributes build.py rendered, so a stage
 * added or renamed upstream cannot leave a stale copy behind.
 */

(function () {
  "use strict";

  const strip = document.querySelector("[data-stage-strip]");
  const panels = Array.from(document.querySelectorAll("[data-stage-panel]"));
  if (!strip || panels.length === 0) {
    return;
  }

  const buttons = Array.from(strip.querySelectorAll("button[data-stage]"));
  if (buttons.length === 0) {
    return;
  }

  function show(stageId) {
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.stagePanel !== stageId;
    });
    buttons.forEach(function (button) {
      button.setAttribute(
        "aria-pressed",
        button.dataset.stage === stageId ? "true" : "false"
      );
    });
  }

  function stageFromHash() {
    const requested = window.location.hash.replace(/^#stage-/, "");
    return buttons.some(function (button) {
      return button.dataset.stage === requested;
    })
      ? requested
      : buttons[0].dataset.stage;
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const stageId = button.dataset.stage;
      show(stageId);
      // replaceState, not a hash assignment: assigning scrolls the panel under
      // the sticky header, and it fills the back button with stage switches.
      window.history.replaceState(null, "", "#stage-" + stageId);
    });
  });

  window.addEventListener("hashchange", function () {
    show(stageFromHash());
  });

  strip.hidden = false;
  show(stageFromHash());
})();
