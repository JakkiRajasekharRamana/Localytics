(() => {
  "use strict";
  // Loads the school profile of the pincode containing a point into a sidebar box.
  const latest = new WeakMap();
  window.LocalyticsSchools = Object.freeze({
    load(box, lat, lon) {
      if (!box) return;
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        box.innerHTML = "";
        return;
      }
      const id = (latest.get(box) || 0) + 1; // ignore replies that arrive after a newer click
      latest.set(box, id);
      box.innerHTML = "<hr><small>Loading school profile…</small>";
      fetch("/schools/lookup?" + new URLSearchParams({ lat, lon }))
        .then((r) => r.text())
        .then((html) => {
          if (latest.get(box) === id) box.innerHTML = html;
        })
        .catch(() => {
          if (latest.get(box) === id)
            box.innerHTML = "<hr><small>School profile unavailable.</small>";
        });
    },
  });
})();
