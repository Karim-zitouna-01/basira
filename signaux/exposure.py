"""Contract §4.2 estimates: these are prototype assumptions, not tax assessments."""

import numpy as np
import pandas as pd

from .statistics import ratio


def estimate_exposure(
    ids,
    month,
    declared,
    imports,
    clients_ttc,
    annual_ttc,
    annual_ht,
    annual_complete,
    public_ht,
    import_vat,
    customs_vat,
    local_vat,
    shell_share,
    peer_margin,
    history_count,
    source_count,
):
    # Convert TTC to HT at the company's observed effective annual rate.
    clients_ht = clients_ttc * ratio(annual_ht, annual_ttc, zero_positive=0.0)
    # Without a complete observed annual tax mix, use the stated prototype 19% rate.
    clients_ht = np.where(annual_complete & (annual_ttc > 0), clients_ht, clients_ttc / 1.19)
    observed_receipts = clients_ht + public_ht
    observed_imports = imports * (1.0 + peer_margin)
    observed = np.maximum(observed_receipts, observed_imports)
    omitted = np.maximum(observed - declared, 0.0)
    overdeducted = np.maximum(import_vat - customs_vat, 0.0) + local_vat * shell_share
    agreement = np.where(
        (observed_receipts > 0) & (observed_imports > 0),
        1 - ratio(np.abs(observed_receipts - observed_imports), observed),
        0.0,
    )
    confidence = (np.clip(history_count / 24, 0, 1) + source_count / 4 + agreement) / 3
    confidence = np.clip(confidence, 0, 1)
    estimate = omitted * (0.19 + peer_margin * 0.20) + overdeducted
    width = 0.30 + 0.40 * (1.0 - confidence)
    frame = pd.DataFrame(
        {
            "mf": ids,
            "mois": str(month),
            "ca_observe_12m": observed,
            "ca_declare_12m": declared,
            "base_omise_12m": omitted,
            "tva_surdeduite_12m": overdeducted,
            "enjeu_estime": estimate,
            "enjeu_bas": estimate * (1 - width),
            "enjeu_haut": estimate * (1 + width),
            "confiance": confidence,
        }
    )
    money = frame.columns.difference(["mf", "mois", "confiance"])
    frame[money] = frame[money].round(3)
    return frame
