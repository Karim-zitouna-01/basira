"""CLI: python -m signaux.run [--data-dir data]."""

import argparse
import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .engine import Engine
from .io import COLUMNS, SIGNAL_SCHEMA, InputError, load_tables

LOG = logging.getLogger(__name__)


def run(
    data_dir: Path,
    output_dir: Path | None = None,
    start="2024-09",
    end="2026-08",
    allow_missing=False,
):
    started = time.perf_counter()
    months = pd.period_range(start, end, freq="M")
    if not len(months):
        raise InputError("La date de début doit précéder la date de fin.")
    tables, warnings = load_tables(data_dir, allow_missing)
    if tables["contribuables"].empty:
        raise InputError("contribuables.csv est vide")
    for warning in warnings:
        LOG.warning(warning)
    engine = Engine(tables, end)
    output_dir = output_dir or data_dir / "signaux"
    output_dir.mkdir(parents=True, exist_ok=True)
    exposures, peer_stats, audits, issues = [], [], [], []
    active_count = 0
    # Failed calculations never replace a previously valid delivery.
    with tempfile.TemporaryDirectory(prefix=".signaux-", dir=output_dir) as temporary:
        staging = Path(temporary)
        with pq.ParquetWriter(
            staging / "signaux.parquet", SIGNAL_SCHEMA, compression="zstd"
        ) as writer:
            for month in months:
                signals, exposure, peers, audit, problems = engine.calculate(month)
                validate_signals(signals)
                active_count += int((signals.valeur_norm >= 0.5).sum())
                writer.write_table(
                    pa.Table.from_pandas(signals, schema=SIGNAL_SCHEMA, preserve_index=False)
                )
                exposures.append(exposure)
                peer_stats.append(peers)
                audits.extend(audit)
                issues.extend(problems)
                LOG.info("%s : %s signaux, %s actifs", month, len(signals), len(audit))
        pd.concat(exposures, ignore_index=True).to_parquet(staging / "enjeux.parquet", index=False)
        pd.concat(peer_stats, ignore_index=True).to_parquet(
            staging / "pairs_stats.parquet", index=False
        )
        engine.groups.to_parquet(staging / "groupes_pairs.parquet", index=False)
        with (staging / "audit_signaux.jsonl").open("w", encoding="utf-8") as stream:
            for row in audits:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        inputs = {}
        for name in COLUMNS:
            path = data_dir / ("graphe" if name == "metriques_noeuds" else "raw") / f"{name}.csv"
            if path.exists():
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                inputs[str(path.relative_to(data_dir))] = digest.hexdigest()
        report = {
            "entreprises": len(engine.data.ids),
            "mois": len(months),
            "lignes_signaux": len(engine.data.ids) * len(months) * 16,
            "signaux_actifs": active_count,
            "duree_secondes": round(time.perf_counter() - started, 3),
            "avertissements": warnings,
            "problemes_preuves": issues,
            "entrees_sha256": inputs,
            "debut": start,
            "fin": end,
            "mode_disponibilite": "fin de mois; dernière période fiscale échue = mois précédent",
        }
        (staging / "rapport_execution.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        for path in staging.iterdir():
            os.replace(path, output_dir / path.name)
    return report


def validate_signals(frame):
    if frame.duplicated(["mf", "mois", "code_signal"]).any():
        raise RuntimeError("Clés de signaux dupliquées")
    if not frame.valeur_norm.between(0, 1).all():
        raise RuntimeError("Signal hors de [0,1]")
    if frame.loc[frame.valeur_norm < 0.5, "fait_fr"].ne("").any():
        raise RuntimeError("Un signal inactif ne doit pas avoir de fait")
    if frame.preuves.map(len).gt(50).any():
        raise RuntimeError("Plus de 50 preuves")


def main():
    parser = argparse.ArgumentParser(description="Lot B Basira : signaux déterministes et enjeux.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--start", default="2024-09")
    parser.add_argument("--end", default="2026-08")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Accepter les sources absentes avec avertissements (échantillon seulement).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report = run(args.data_dir, args.output_dir, args.start, args.end, args.allow_missing)
    except (InputError, ValueError) as exc:
        parser.exit(2, f"Erreur de données : {exc}\n")
    LOG.info("Terminé : %s lignes en %.1f s", report["lignes_signaux"], report["duree_secondes"])


if __name__ == "__main__":
    main()
