(() => {
  "use strict";
  window.addEventListener("message", function (event) {
    const frame = document.querySelector("#combined-map iframe");
    if (
      !frame ||
      event.source !== frame.contentWindow ||
      event.data?.type !== "localytics:selection" ||
      typeof event.data.html !== "string"
    )
      return;
    const target = document.getElementById("selection-details");
    if (target) target.innerHTML = event.data.html;
  });

  document.getElementById("filters").addEventListener("submit", () => {
    const b = document.getElementById("submit");
    b.disabled = true;
    b.textContent = "Loading…";
    document.getElementById("progress").textContent =
      "Fetching all pages and building your map. Please keep this page open.";
  });
})();
