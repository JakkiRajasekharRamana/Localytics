"use strict";
window.Localytics = Object.freeze({
  escape(value, fallback = "Unavailable") {
    return String(value ?? fallback).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  },
  formatNumber(value) {
    return value === null || value === undefined
      ? "Unavailable"
      : Number(value).toFixed(2);
  },
});
