"""Paginated data.gov.in client using curl without exposing its API key."""

import json
import os
import shutil
import subprocess
from urllib.parse import urlencode

BASE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"


class FetchError(Exception):
    pass


def _fetch_records(state, city):
    key = os.environ.get("DATA_GOV_API_KEY", "").strip()
    if not key:
        raise FetchError("Set DATA_GOV_API_KEY in your .env file, then restart the app.")
    if not shutil.which("curl"):
        raise FetchError("curl is required. Install it on the computer running Flask.")
    params = {"api-key": key, "format": "json", "limit": 100, "offset": 0, "filters[state]": state}
    if city:
        params["filters[city]"] = city
    records, seen_pages = [], set()
    for _ in range(200):
        # Pass URL via stdin configuration so the key is not a process argument.
        config = "url = " + json.dumps(BASE_URL + "?" + urlencode(params)) + "\n"
        try:
            result = subprocess.run(
                [
                    "curl",
                    "--config",
                    "-",
                    "--silent",
                    "--show-error",
                    "--fail",
                    "--connect-timeout",
                    "15",
                    "--max-time",
                    "120",
                    "-H",
                    "accept: application/json",
                ],
                input=config,
                capture_output=True,
                text=True,
                timeout=125,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise FetchError("The API connection failed or timed out. Please try again.") from None
        if result.returncode:
            raise FetchError(
                "The API request failed (possibly a timeout or HTTP 502). Please try again."
            )
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or not isinstance(data.get("records"), list):
                raise ValueError
            batch = data["records"]
            if any(not isinstance(row, dict) for row in batch):
                raise ValueError
            total = int(data["total"]) if data.get("total") is not None else None
            if total is not None and total < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise FetchError("The API returned an unexpected response. Please try again.") from None
        if not batch:
            if total is not None and len(records) < total:
                raise FetchError("The API stopped before returning all records. Please try again.")
            return records
        signature = json.dumps(batch, sort_keys=True)
        if signature in seen_pages:
            raise FetchError("The API repeated a page. Fetch stopped to avoid duplicate data.")
        seen_pages.add(signature)
        records.extend(batch)
        params["offset"] += len(batch)
        if total is not None and len(records) >= total:
            return records
    raise FetchError("The query exceeded 200 pages. Please narrow it to a city.")


def fetch_records(state, city):
    """Use exact filters first, then tolerate user-entered capitalisation."""
    state = " ".join(state.split())
    city = " ".join(city.split())
    records = _fetch_records(state, city)
    if records:
        return records
    canonical_state = state.title()
    if canonical_state != state:
        records = _fetch_records(canonical_state, city)
        if records:
            return records
    if city:
        # Resolve city spelling/case against returned data, never substitute another city.
        state_records = _fetch_records(canonical_state, "")
        wanted = city.casefold()
        return [
            r
            for r in state_records
            if " ".join(str(r.get("city", "")).split()).casefold() == wanted
        ]
    return []
