"""Human-readable hero report, with optional acceptance assertions."""

import argparse
from pathlib import Path

import pandas as pd

from .demo import HEROES, NAMES

EXPECTED = {
    HEROES[0]: [
        "COH_IMPORT_VS_CA",
        "CHG_IMPORTS",
        "CHG_NOUVEAUX_FOURNISSEURS",
        "RES_FOURNISSEUR_PARTAGE",
    ],
    HEROES[1]: ["COH_VALEUR_REF"],
    HEROES[2]: ["COH_ADEB_VS_CA"],
    HEROES[3]: ["CHG_DEPOTS", "CHG_IMPORTS"],
    HEROES[4]: ["PAI_MARGE", "PAI_MAHALANOBIS"],
    HEROES[7]: ["COH_CLIENTS_VS_CA"],
}


def hero_report(data_dir, month="2026-08"):
    signals = pd.read_parquet(
        data_dir / "signaux" / "signaux.parquet", filters=[("mois", "=", month)]
    )
    active = signals.loc[signals.valeur_norm >= 0.5]
    lines, failures = (
        [
            f"# Contrôle des héros — {month}",
            "",
            "Signaux du lot B uniquement. Les scores et segments appartiennent à C.",
            "",
        ],
        [],
    )
    for mf, name in zip(HEROES, NAMES):
        rows = active.loc[active.mf.eq(mf)]
        codes = set(rows.code_signal)
        absent = set(EXPECTED.get(mf, [])) - codes
        if not signals.mf.eq(mf).any():
            failures.append(f"{name}: entreprise absente")
        if absent:
            failures.append(f"{name}: signaux attendus inactifs : {', '.join(sorted(absent))}")
        if mf == HEROES[5] and any(code.startswith("COH_") for code in codes):
            failures.append("Zeta: signal de cohérence actif")
        if mf == HEROES[6] and codes:
            failures.append("Eta: signal actif")
        lines.extend(
            [f"## {name} ({mf})", "", ", ".join(sorted(codes)) or "Aucun signal actif.", ""]
        )
        for row in rows.itertuples():
            lines.append(f"- {row.code_signal} : {row.valeur_norm:.3f} — {row.fait_fr}")
        lines.append("")
    lines += ["## Écarts à examiner avec A", ""] + (
        failures or ["Aucun écart sur les signaux attendus."]
    )
    return "\n".join(lines) + "\n", failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--month", default="2026-08")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report, failures = hero_report(args.data_dir, args.month)
    output = args.data_dir / "signaux" / "controle_heros.md"
    output.write_text(report, encoding="utf-8")
    print(report)
    if args.strict and failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
