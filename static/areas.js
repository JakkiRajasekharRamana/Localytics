(() => {
  "use strict";
  const config = JSON.parse(document.getElementById("area-config").textContent);
  const { geojson, factorNames, weights, facilityColors, airPoints } = config;
  const params = new URLSearchParams(config.preferences);
  const map = L.map("map").setView([28.61, 77.2], 10),
    layers = new Map(),
    comparison = new Map();
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);
  const esc = Localytics.escape;
  const fmt = Localytics.formatNumber;
  let mode = "score",
    choosing = false,
    workMarker = null,
    selected = null,
    controller = null;
  function color(p) {
    if (mode === "group")
      return [
        "#bbb",
        "#4178be",
        "#975bb5",
        "#d87e22",
        "#2b9a70",
        "#ce5577",
        "#6c7627",
      ][p.group || 0];
    return p.score === null
      ? "#a8afb7"
      : p.score >= 70
        ? "#16834a"
        : p.score >= 40
          ? "#e9a522"
          : "#cc4949";
  }
  function style(f) {
    return {
      color: "#fff",
      weight: 0.7,
      fillColor: color(f.properties),
      fillOpacity: 0.65,
    };
  }
  const grid = L.geoJSON(geojson, {
    style,
    onEachFeature: (f, layer) => {
      layers.set(f.properties.id, layer);
      layer.bindTooltip(
        esc(f.properties.label) +
          "<br>" +
          esc(f.properties.id) +
          " · " +
          (f.properties.score === null
            ? "Unranked"
            : f.properties.score.toFixed(1) + "/100"),
      );
      layer.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        if (choosing) {
          setWork(e.latlng);
          return;
        }
        inspect(f.properties.id);
      });
    },
  }).addTo(map);
  map.fitBounds(grid.getBounds());
  const facilityLayer = L.featureGroup().addTo(map),
    airLayer = L.featureGroup().addTo(map);

  for (const p of airPoints) {
    const v = p.pm,
      c = p.air.color;
    L.circleMarker([p.lat, p.lon], {
      radius: 6,
      color: "#333",
      weight: 1,
      fillColor: c,
      fillOpacity: 1,
    })
      .bindTooltip(esc(p.name) + " · PM2.5 " + esc(v) + "<br>" + esc(p.updated))
      .addTo(airLayer);
  }
  L.control
    .layers(null, {
      "Area scores / groups": grid,
      "Air monitors (indicative PM2.5)": airLayer,
      "Nearby services for selected area": facilityLayer,
    })
    .addTo(map);
  document.getElementById("map-mode").onchange = (e) => {
    mode = e.target.value;
    grid.setStyle(style);
    if (selected)
      layers.get(selected)?.setStyle({ color: "#172d40", weight: 3 });
  };
  const legend = L.control({ position: "bottomleft" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    d.innerHTML =
      '<b>Suitability / 100</b><br><span style="color:#16834a">● ≥70</span> · <span style="color:#e9a522">● 40–69</span> · <span style="color:#cc4949">● &lt;40</span><br>Grey: missing evidence / unmet requirement<br>Groups use separate categorical colours.';
    return d;
  };
  legend.addTo(map);
  function setWork(p) {
    document.getElementById("work_lat").value = p.lat.toFixed(6);
    document.getElementById("work_lon").value = p.lng.toFixed(6);
    if (workMarker) map.removeLayer(workMarker);
    workMarker = L.marker(p).addTo(map).bindTooltip("Workplace / college");
    choosing = false;
    document.getElementById("map-status").textContent =
      "Workplace selected. Give Workplace distance a positive importance and update recommendations.";
  }
  if (config.workplace)
    workMarker = L.marker(config.workplace)
      .addTo(map)
      .bindTooltip("Workplace / college");
  document.getElementById("choose-work").onclick = () => {
    choosing = true;
    document.getElementById("map-status").textContent =
      "Click the map to choose your workplace.";
    document
      .getElementById("map")
      .scrollIntoView({ behavior: "smooth", block: "center" });
  };
  map.on("click", (e) => {
    if (choosing) setWork(e.latlng);
  });
  async function getArea(id, signal) {
    const response = await fetch(
      "/api/areas/" + encodeURIComponent(id) + "?" + params,
      { signal },
    );
    if (!response.ok) throw Error("Area details could not be loaded.");
    return response.json();
  }
  async function inspect(id) {
    if (controller) controller.abort();
    controller = new AbortController();
    selected = id;
    grid.setStyle(style);
    layers.get(id)?.setStyle({ color: "#172d40", weight: 3 });
    const target = document.getElementById("insights");
    target.innerHTML = "<p>Loading area details…</p>";
    try {
      const r = await getArea(id, controller.signal);
      if (id !== selected) return;
      renderDetail(r);
    } catch (e) {
      if (e.name !== "AbortError") target.textContent = e.message;
    }
  }
  function renderDetail(r) {
    facilityLayer.clearLayers();

    for (const [category, f] of Object.entries(r.features))
      for (const p of f.nearby) {
        L.circleMarker([p.lat, p.lon], {
          radius: 5,
          color: facilityColors[category],
          fillOpacity: 0.9,
          weight: 2,
        })
          .bindTooltip(
            esc(category.replaceAll("_", " ")) +
              ": " +
              esc(p.name) +
              " · " +
              fmt(p.km) +
              " km",
          )
          .addTo(facilityLayer);
      }
    let h =
      "<h2>" +
      esc(r.label) +
      "</h2><small>" +
      esc(r.id) +
      " · " +
      r.lat.toFixed(5) +
      ", " +
      r.lon.toFixed(5) +
      '</small><p class="score">' +
      (r.score === null ? "Unranked" : r.score.toFixed(1) + " / 100") +
      '</p><button id="compare-current" type="button">Add to comparison</button>';
    if (r.missing.length)
      h +=
        "<p>Missing selected factors: " +
        r.missing.map((k) => esc(factorNames[k])).join(", ") +
        "</p>";
    if (r.checks.length)
      h +=
        "<h3>Must-have checks</h3><ul>" +
        r.checks
          .map(
            (c) =>
              "<li>" +
              esc(c.factor.replaceAll("_", " ")) +
              ": " +
              esc(c.status) +
              " (within " +
              c.limit +
              " km)</li>",
          )
          .join("") +
        "</ul>";
    h +=
      "<hr><h3>Factor scores</h3><table><tr><th>Factor</th><th>/ 100</th><th>Contribution</th></tr>" +
      Object.entries(r.scores)
        .map(
          ([k, v]) =>
            "<tr><td>" +
            esc(factorNames[k]) +
            (weights[k] > 0 ? "" : " <small>(ignored)</small>") +
            "</td><td>" +
            fmt(v === null ? null : v * 100) +
            "</td><td>" +
            (weights[k] > 0 ? fmt(r.contributions[k]) : "—") +
            "</td></tr>",
        )
        .join("") +
      "</table>";
    if (r.work_km !== null)
      h += "<p>Workplace: " + r.work_km + " km straight-line.</p>";
    h += "<hr><h3>Air-quality observations</h3>";
    if (r.air) {
      h +=
        "<p>" +
        esc(r.air.name) +
        " · " +
        r.air.distance_km +
        " km away<br>PM2.5 value: " +
        esc(r.air.pm) +
        "<br>Observation age: " +
        esc(r.air.age_hours) +
        " hours</p><p><small>" +
        esc(r.air.status) +
        ". Nearest-monitor context is not an area-wide measurement.</small></p>";
      if (r.air.scoring_monitor)
        h +=
          "<p>Ranking monitor: " +
          esc(r.air.scoring_monitor) +
          " · " +
          fmt(r.air.scoring_distance_km) +
          " km away<br>PM2.5 indicator input: " +
          esc(r.air.scoring_value) +
          "</p>";
      h +=
        '<div class="tablewrap"><table><tr><th>Pollutant</th><th>Avg</th><th>Updated</th></tr>' +
        r.air.readings
          .map(
            (v) =>
              "<tr><td>" +
              esc(v.pollutant_id) +
              "</td><td>" +
              esc(v.avg_value) +
              "</td><td>" +
              esc(v.last_update) +
              "</td></tr>",
          )
          .join("") +
        "</table></div>";
    } else
      h +=
        "<p>No Delhi air readings cached. Use Refresh Delhi air readings below; services can still be compared.</p>";
    h +=
      "<hr><h3>Mapped services</h3><small>Up to five nearest per type are marked on the map. Airports use a 25 km radius; other services use the selected local radius.</small>";
    for (const [key, f] of Object.entries(r.features)) {
      h +=
        "<details><summary>" +
        esc(key.replaceAll("_", " ")) +
        " · " +
        f.count +
        " nearby</summary><p>Nearest mapped feature: " +
        fmt(f.nearest_km) +
        " km.<br>Extract extent: " +
        (f.coverage ? "search radius covered" : "unavailable / partial") +
        ".</p><ul>" +
        f.nearby
          .map(
            (p) =>
              "<li>" +
              esc(p.name) +
              " · " +
              fmt(p.km) +
              " km<br><small>" +
              esc(p.method.replaceAll("_", " ")) +
              "; access " +
              esc(p.access) +
              "</small></li>",
          )
          .join("") +
        "</ul><small>Access and current service are not guaranteed.</small></details>";
    }
    document.getElementById("insights").innerHTML = h;
    document.getElementById("compare-current").onclick = () => addCompare(r);
  }
  function syncChecks() {
    document
      .querySelectorAll(".compare-check")
      .forEach((c) => (c.checked = comparison.has(c.dataset.id)));
  }
  function addCompare(r) {
    if (comparison.size >= 3 && !comparison.has(r.id)) {
      document.getElementById("map-status").textContent =
        "Compare at most three areas. Remove one first.";
      syncChecks();
      return;
    }
    comparison.set(r.id, r);
    syncChecks();
    renderCompare();
  }
  function renderCompare() {
    const out = document.getElementById("compare-output");
    if (!comparison.size) {
      out.textContent = "Select up to three areas from the map or shortlist.";
      return;
    }
    let h =
      '<div class="tablewrap"><table><tr><th>Factor</th>' +
      [...comparison.values()]
        .map(
          (r) =>
            "<th>" +
            esc(r.label) +
            "<br><small>" +
            esc(r.id) +
            '</small><br><button class="remove secondary" data-id="' +
            esc(r.id) +
            '">Remove</button></th>',
        )
        .join("") +
      "</tr><tr><td>Suitability / 100</td>" +
      [...comparison.values()]
        .map((r) => "<td>" + fmt(r.score) + "</td>")
        .join("") +
      "</tr>";
    for (const [key, label] of Object.entries(factorNames))
      h +=
        "<tr><td>" +
        esc(label) +
        " / 100</td>" +
        [...comparison.values()]
          .map(
            (r) =>
              "<td>" +
              fmt(r.scores[key] === null ? null : r.scores[key] * 100) +
              "</td>",
          )
          .join("") +
        "</tr>";
    out.innerHTML = h + "</table></div>";
    out.querySelectorAll(".remove").forEach(
      (b) =>
        (b.onclick = () => {
          comparison.delete(b.dataset.id);
          syncChecks();
          renderCompare();
        }),
    );
  }
  document.querySelectorAll(".inspect").forEach(
    (b) =>
      (b.onclick = () => {
        const layer = layers.get(b.dataset.id);
        map.fitBounds(layer.getBounds(), { maxZoom: 14 });
        inspect(b.dataset.id);
        document
          .getElementById("map")
          .scrollIntoView({ behavior: "smooth", block: "center" });
      }),
  );
  document.querySelectorAll(".compare-check").forEach(
    (c) =>
      (c.onchange = async () => {
        if (!c.checked) {
          comparison.delete(c.dataset.id);
          renderCompare();
          return;
        }
        try {
          addCompare(await getArea(c.dataset.id));
        } catch (e) {
          c.checked = false;
          document.getElementById("map-status").textContent = e.message;
        }
      }),
  );
  document.getElementById("export").href += "?" + params;
  document.getElementById("refresh-air").onsubmit = () => {
    const b = document.querySelector("#refresh-air button");
    b.disabled = true;
    b.textContent = "Refreshing…";
    document.getElementById("refresh-status").textContent =
      " Fetching all Delhi pages. Please keep this page open.";
  };
  document.getElementById("radius").onchange = (e) =>
    document
      .querySelectorAll('[id^="must_"]')
      .forEach((n) => (n.max = e.target.value));
})();
