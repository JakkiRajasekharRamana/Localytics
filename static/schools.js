(() => {
  "use strict";
  const table = document.getElementById("profiles");
  if (!table) return;
  const body = table.tBodies[0];
  const dataRows = () => [...body.rows].filter((r) => !r.dataset.fixed);

  document.getElementById("filter").addEventListener("input", (e) => {
    const q = e.target.value.trim();
    for (const tr of dataRows())
      tr.hidden = q !== "" && !tr.cells[0].textContent.includes(q);
  });

  table.tHead.rows[0].querySelectorAll("th.sortable").forEach((th, col) => {
    let ascending = true;
    th.addEventListener("click", () => {
      const numeric = th.dataset.type === "num";
      // -1 marks pincodes with too few schools for a range: keep them last either way.
      const value = (row) => {
        const v = row.cells[col].dataset.sort;
        return numeric ? (v === "-1" ? null : parseFloat(v)) : v;
      };
      const rows = dataRows().sort((a, b) => {
        const x = value(a);
        const y = value(b);
        if (x === null || y === null) return (x === null) - (y === null);
        return (numeric ? x - y : x.localeCompare(y)) * (ascending ? 1 : -1);
      });
      ascending = !ascending;
      rows.forEach((r) => body.appendChild(r));
    });
  });
})();
