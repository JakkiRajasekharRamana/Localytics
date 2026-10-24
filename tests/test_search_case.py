import air_client as client


def test_uppercase_state(monkeypatch):
    calls = []

    def fetch(state, city):
        calls.append((state, city))
        return [{"city": "Pune"}] if state == "Maharashtra" else []

    monkeypatch.setattr(client, "_fetch_records", fetch)
    assert client.fetch_records("MAHARASHTRA", "Pune") == [{"city": "Pune"}]
    assert calls == [("MAHARASHTRA", "Pune"), ("Maharashtra", "Pune")]


def test_city_case_fallback_does_not_mix_cities(monkeypatch):
    def fetch(state, city):
        return [] if city else [{"city": "Pune"}, {"city": "Mumbai"}]

    monkeypatch.setattr(client, "_fetch_records", fetch)
    assert client.fetch_records("Maharashtra", "PUNE") == [{"city": "Pune"}]
    assert client.fetch_records("Maharashtra", "Unknown") == []
