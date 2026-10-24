"""Model-only transformations and descriptive area clustering."""

import json
from functools import lru_cache

import data_store


@lru_cache(maxsize=1)
def clustering():
    """Separate model copy; model values never enter user suitability scores."""
    report_path = data_store.DB.with_name("cluster_report.json")
    cells, manifest = data_store.dataset()
    saved = data_store.read_report("cluster_report.json")
    if isinstance(saved, dict) and saved.get("data_version") == manifest["built_at"]:
        return saved
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering, KMeans
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import adjusted_rand_score, silhouette_score
    from sklearn.preprocessing import StandardScaler

    cats = ["bus_stop", "metro_station", "school", "hospital", "park", "gym", "mall", "ev"]
    names = [f"{c}_{kind}" for c in cats for kind in ("count", "distance")]
    X = []
    for cell in cells:
        row = []
        for c in cats:
            f = cell["features"]["2"][c]
            row.extend(
                [
                    f["count"] if f["coverage"] else np.nan,
                    min(f["nearest_km"], 10)
                    if f["coverage"] and f["nearest_km"] is not None
                    else np.nan,
                ]
            )
        X.append(row)
    X = np.array(X, dtype=float)
    keep = (np.mean(np.isnan(X), axis=0) <= 0.2) & (np.nanstd(X, axis=0) > 0)
    X = X[:, keep]
    names = [n for n, k in zip(names, keep) if k]
    if len(X) < 100 or X.shape[1] < 4:
        return dict(
            available=False,
            reason="Not enough usable cells or varying features.",
            labels={},
            trials=[],
        )

    def pipeline(values):
        imputed = SimpleImputer(strategy="median", add_indicator=True).fit_transform(values)
        return StandardScaler().fit_transform(imputed)

    Z = pipeline(X)
    trials = []
    candidates = []
    for method in ("K-Means", "Hierarchical"):
        for k in range(2, 7):
            model = (
                KMeans(n_clusters=k, n_init=10, random_state=7)
                if method == "K-Means"
                else AgglomerativeClustering(n_clusters=k)
            )
            labels = model.fit_predict(Z)
            if min(np.bincount(labels)) < 10:
                continue
            silhouette = float(
                silhouette_score(Z, labels, sample_size=min(1000, len(Z)), random_state=7)
            )
            trials.append(dict(method=method, k=k, silhouette=round(silhouette, 3)))
            candidates.append((silhouette, method, k, labels))
    if not candidates:
        return dict(
            available=False,
            reason="No cluster configuration met the minimum group size.",
            labels={},
            trials=trials,
        )
    silhouette, method, k, labels = max(candidates, key=lambda a: a[0])
    rng = np.random.default_rng(7)
    stability = []
    for repeat in range(5):
        idx = np.sort(rng.choice(len(X), int(0.8 * len(X)), replace=False))
        Zsub = pipeline(X[idx])
        model = (
            KMeans(n_clusters=k, n_init=10, random_state=repeat)
            if method == "K-Means"
            else AgglomerativeClustering(n_clusters=k)
        )
        sublabels = model.fit_predict(Zsub)
        stability.append(float(adjusted_rand_score(labels[idx], sublabels)))
    profiles = []
    for label in range(k):
        subset = np.array(X)[labels == label]
        medians = np.nanmedian(subset, axis=0)
        profiles.append(
            dict(
                group=label + 1,
                size=int(sum(labels == label)),
                indicators={n: round(float(v), 2) for n, v in zip(names, medians)},
            )
        )
    result = dict(
        available=True,
        method=method,
        k=k,
        silhouette=round(silhouette, 3),
        stability=round(sum(stability) / len(stability), 3),
        labels={c["id"]: int(label) + 1 for c, label in zip(cells, labels)},
        trials=trials,
        profiles=profiles,
        features=names,
        sample_count=len(cells),
        stability_repeats=5,
        data_version=manifest["built_at"],
    )
    try:
        report_path.write_text(json.dumps(result, indent=2))
    except OSError:
        pass
    return result
