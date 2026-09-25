"""Stable peer mapping and monthly robust peer comparisons."""

import numpy as np
import pandas as pd

from .catalogue import INDICATORS
from .statistics import normalize_z, ratio, robust_distances


def division_of(companies):
    return companies.code_nat.str.replace(".", "", regex=False).str[:2]


def sizes_of(companies):
    return pd.cut(
        companies.effectif_declare, [-1, 2, 9, 49, np.inf], labels=["0-2", "3-9", "10-49", "50+"]
    ).astype(str)


def peer_members(companies, group):
    """Fallback groups include ALL division/section peers, even fine-group members."""
    division = division_of(companies)
    if group.startswith("SECTION|"):
        return (companies.section_nat == group.split("|")[1]).to_numpy()
    if "|" in group:
        return ((division + "|" + sizes_of(companies)) == group).to_numpy()
    return (division == group).to_numpy()


def build_groups(companies):
    division = division_of(companies)
    fine = division + "|" + sizes_of(companies)
    fine_count = fine.map(fine.value_counts())
    division_count = division.map(division.value_counts())
    group = fine.where(fine_count >= 30, division).where(
        (fine_count >= 30) | (division_count >= 30), "SECTION|" + companies.section_nat
    )
    counts = {name: int(peer_members(companies, name).sum()) for name in group.unique()}
    return pd.DataFrame(
        {
            "mf": companies.index,
            "groupe": group.to_numpy(),
            "libelle_groupe": group.str.replace("|", " × ", regex=False).to_numpy(),
            "nb_pairs": group.map(counts).to_numpy(dtype=int),
        }
    )


def compute_peers(
    groups, month, ca, imports, local_vat, total_vat, collected, staff, complete, companies
):
    margin = np.where(ca > 0, ratio(ca - imports - local_vat / 0.19, ca), np.nan)
    indicators = np.column_stack(
        (
            margin,
            np.where(collected > 0, ratio(total_vat, collected), np.nan),
            np.where(staff > 0, ratio(ca, staff), np.nan),
            np.where(ca > 0, ratio(imports, ca), np.nan),
        )
    )
    exists = (companies.date_debut_activite <= month.end_time).to_numpy()
    indicators[~(complete & exists)] = np.nan
    n = len(groups)
    margin_z, distance, peer_margin = np.zeros(n), np.zeros(n), np.zeros(n)
    dominant = np.full(n, "MARGE", dtype=object)
    stats = []
    for group, target_index in groups.groupby("groupe", sort=True).groups.items():
        target_index = np.asarray(target_index)
        reference = indicators[peer_members(companies, group)]
        targets = indicators[target_index]
        for j, name in enumerate(INDICATORS):
            valid = reference[np.isfinite(reference[:, j]), j]
            quantiles = np.quantile(valid, [0.1, 0.5, 0.9]) if len(valid) else np.zeros(3)
            stats.append(
                {
                    "groupe": group,
                    "mois": str(month),
                    "indicateur": name,
                    "mediane": quantiles[1],
                    "p10": quantiles[0],
                    "p90": quantiles[2],
                    "nb": len(valid),
                }
            )
        margins = reference[np.isfinite(reference[:, 0]), 0]
        target_valid = np.isfinite(targets[:, 0])
        if len(margins):
            median = np.median(margins)
            peer_margin[target_index] = np.clip(median, 0, 1)
            if len(margins) >= 3:
                scale = max(1.4826 * np.median(np.abs(margins - median)), abs(median) * 0.05, 0.01)
                margin_z[target_index[target_valid]] = np.maximum(
                    (median - targets[target_valid, 0]) / scale, 0
                )
        valid_reference = reference[np.isfinite(reference).all(axis=1)]
        valid_target = np.isfinite(targets).all(axis=1)
        if len(valid_reference) >= 5 and valid_target.any():
            d, contributions, _ = robust_distances(valid_reference, targets[valid_target])
            distance[target_index[valid_target]] = d
            dominant[target_index[valid_target]] = np.asarray(INDICATORS)[
                contributions.argmax(axis=1)
            ]
    return (
        {
            "PAI_MARGE": (margin_z, normalize_z(margin_z)),
            "PAI_MAHALANOBIS": (distance, np.clip((distance - 2) / 4, 0, 1)),
        },
        pd.DataFrame(stats),
        peer_margin,
        dominant,
        indicators,
    )
