"""Generate the required French synthesis, with no invented evaluation results."""

import argparse
import json
from importlib.metadata import version
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT = Path(__file__).resolve().parents[1]


def generate_report(data_dir, output, stack_path, final=False):
    evaluation_path = data_dir / "scores" / "evaluation.json"
    stack = json.loads(stack_path.read_text(encoding="utf-8"))
    evaluation = (
        json.loads(evaluation_path.read_text(encoding="utf-8"))
        if evaluation_path.exists()
        else None
    )
    if final and (evaluation is None or not stack.get("confirmed_by_c_and_d")):
        raise ValueError(
            "Version finale impossible : fournir evaluation.json de C et confirmer docs/team_stack.json avec C et D."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="BodyFR", fontName="Helvetica", fontSize=9, leading=12, spaceAfter=7)
    )
    styles.add(
        ParagraphStyle(
            name="TitleFR",
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    story = []

    def paragraph(text):
        story.append(Paragraph(text, styles["BodyFR"]))

    def heading(text):
        story.append(Paragraph(text, styles["Heading2"]))

    story.append(Paragraph("BASIRA — Note de synthèse", styles["TitleFR"]))
    paragraph(
        "<b>Défi principal T20 · Défi secondaire T7.</b> Priorisation dynamique et explicable des contrôles par recoupement des déclarations fiscales, des importations et des paiements."
    )
    if not final:
        paragraph(
            "<b>Version de travail du lot B.</b> Les résultats d'impact et l'inventaire final de C/D restent à compléter s'ils ne sont pas fournis. Aucun chiffre d'exemple du contrat n'est présenté comme un résultat mesuré."
        )
    heading("1. Problème et approche")
    paragraph(
        "L'inspecteur dispose d'une capacité de contrôle limitée. Basira compare les déclarations aux observations des autres administrations, à l'historique et aux pairs. Quatre lentilles — cohérence, changement, pairs, réseau — produisent des signaux justifiés, puis C apprend une priorité risque × enjeu. La décision appartient à l'inspecteur; aucune sanction n'est automatique."
    )
    heading("2. Données et disponibilité")
    paragraph(
        "Les données sont entièrement synthétiques. Le format reproduit le dossier fiscal et la déclaration mensuelle DGI, les annexes I, II et V de l'employeur, les déclarations et liquidations douanières SINDA, les paiements ADEB et les contrôles passés. Le portefeuille cible comprend 5 250 entreprises; B livre 24 mois × 16 signaux, soit 2 016 000 lignes. Les fichiers de vérité terrain sont réservés à l'évaluation de C et ne sont jamais lus par B."
    )
    paragraph(
        "Un calcul à fin M ne lit que les dépôts effectivement reçus. La comparaison fiscale utilise les périodes échues jusqu'à M-1; la TVA importée est décalée d'un mois selon le dictionnaire. L'exercice N des annexes employeur n'est disponible qu'en mars N+1. Les données annuelles restent des approximations pour une reconstitution glissante."
    )
    heading("3. Technique et explicabilité")
    paragraph(
        "Le lot B utilise des agrégations déterministes, des fenêtres de 6/12 mois, un EWMA α=0,3 et une normalisation bornée. Les pairs sont définis par division NAT et taille, avec repli division puis section. La distance multivariée emploie une covariance régularisée robuste aux matrices singulières. Les métriques réseau mensuelles sont produites par A; B les normalise et relie les opérations disponibles."
    )
    paragraph(
        "Chaque signal actif fournit un fait en français et au plus 50 références brutes triées par montant. Les chiffres affichés citent une pièce vérifiable; les calculs utilisent toutes les opérations admissibles. Les quatre Parquet contractuels, un journal des calculs et les empreintes des entrées permettent de reproduire la livraison. L'enjeu est une estimation selon les coefficients du contrat, avec une fourchette élargie lorsque les sources ou l'historique manquent."
    )
    heading("4. Modèles et bibliothèques")
    paragraph(
        "<b>B :</b> aucun modèle pré-entraîné et aucun modèle de prédiction appris. Bibliothèques directes : "
        + escape(
            ", ".join(
                f"{name} {version(name)}" for name in ("numpy", "pandas", "pyarrow", "reportlab")
            )
        )
        + ". Tests et qualité : pytest, Ruff. Un inventaire complet des dépendances Python est livré dans requirements.lock.txt."
    )
    for model in stack.get("models", []):
        paragraph(
            escape(
                f"{model['owner']} — {model['name']}; pré-entraîné : {'oui' if model['pretrained'] else 'non'}; {model['status']}."
            )
        )
    for owner, libraries in stack.get("libraries", {}).items():
        paragraph(escape(f"{owner} — bibliothèques : {', '.join(libraries)}."))
    story.append(PageBreak())
    heading("5. Résultats et validation")
    if evaluation:
        paragraph(
            "Résultats fournis par C : "
            + escape(str(evaluation.get("periode_test", "période non renseignée")))
            + "; top N = "
            + escape(str(evaluation.get("top_n", "?")))
            + "."
        )
        rows = [["Méthode", "Détection", "DT / contrôle", "Fausses alertes", "Avance (mois)"]]
        for method in evaluation.get("methodes", []):
            rows.append(
                [
                    Paragraph(escape(str(method["nom"])), styles["BodyFR"]),
                    f"{100 * method['taux_detection_top_n']:.1f} %",
                    f"{method['montant_moyen_par_controle']:,.0f}",
                    str(method["fausses_alertes_croissance_legitime"]),
                    str(
                        method.get("avance_detection_mois")
                        if method.get("avance_detection_mois") is not None
                        else "n.d."
                    ),
                ]
            )
        table = Table(rows, colWidths=[5 * cm, 2.2 * cm, 3 * cm, 3 * cm, 2.6 * cm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce7f3")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))
        paragraph(escape(str(evaluation.get("note", "Évaluation sur données synthétiques."))))
    else:
        paragraph(
            "<b>Impact non encore mesuré :</b> data/scores/evaluation.json de C est absent. La comparaison avec une règle statique et le hasard, le taux de détection, la récupération moyenne, les faux positifs et l'avance de détection seront repris automatiquement de ce fichier. Aucun gain chiffré n'est revendiqué."
        )
    run_path = data_dir / "signaux" / "rapport_execution.json"
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        paragraph(
            escape(
                f"Dernière exécution B : {run['entreprises']} entreprises, {run['mois']} mois, {run['lignes_signaux']} lignes de signaux; durée {run['duree_secondes']} s. Il s'agit d'une mesure d'exécution, pas d'une validation de performance prédictive."
            )
        )
    paragraph(
        "La suite de tests vérifie les schémas, les délais de publication, l'invariance aux observations futures, les preuves, la stabilité des covariances et les identités financières. Le contrôle des héros vérifie les signaux attendus, dont l'absence d'alerte de cohérence pour Zeta. Les scores 28 → 76 et les segments restent du ressort de C."
    )
    heading("6. Limites")
    paragraph(
        "Les données synthétiques ne démontrent pas l'efficacité en production. Les contrôles historiques sont rares et biaisés par leur sélection; les labels sont partiels. Le référentiel d'activités n'est pas unifié. SAR et SADEC 2 ne sont connus que par la conférence. La couverture annuelle 2023 peut être partielle; les comparaisons annuelles incomplètes sont neutralisées. Les estimations clients + ADEB peuvent se recouvrir faute de clés de rapprochement. La TVA et l'IS du calcul sont des hypothèses de prototype, à valider métier."
    )
    paragraph(
        "Les caractéristiques statiques du registre sont supposées historiques et stables; les corrections des annexes sans date de publication ne peuvent pas être reconstituées dans le passé. A doit garantir que les métriques réseau sont calculées à date. Un groupe de section trop petit reste signalé comme peu documenté. La confiance mesure la couverture et l'accord des sources, pas une probabilité de fraude."
    )
    heading("7. Recommandations pour la production")
    paragraph(
        "Brancher les sources au data lake SADEC 2 et à SINDA 2, conserver les versions et dates de disponibilité, unifier les identifiants et référentiels, et valider les règles avec les métiers. Héberger les données et l'assistant dans le périmètre de l'administration. Prévoir habilitations, journalisation, minimisation et examen du cadre loi 2004-63 / INPDP. Réentraîner et évaluer le modèle de C à partir des décisions et résultats réels, avec contrôle des biais par secteur, taille et région; maintenir une validation humaine."
    )
    heading("Références documentaires transmises")
    for title, url in (
        (
            "Ministère des Finances — déclaration mensuelle 2023",
            "https://www.finances.gov.tn/sites/default/files/2023-04/MENSUELLE__2023.pdf",
        ),
        (
            "Ministère des Finances — cahier des charges employeur",
            "https://www.finances.gov.tn/sites/default/files/2023-04/EMPCCA_22-23.pdf",
        ),
        ("Douane tunisienne — valeur en douane", "https://www.douane.gov.tn/valeur-en-douane/"),
        (
            "CIMF — présentation ADEB",
            "http://www.cimf.tn/index.php/systeme-d-aide-a-la-decision-budgetaire",
        ),
    ):
        paragraph(
            f'<link href="{escape(url)}" color="#174a7e">{escape(title)}</link> (référence issue de modele_donnees.md).'
        )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(19 * cm, 1 * cm, f"Basira · Lot B · {doc.page}")

    doc = SimpleDocTemplate(
        str(output),
        pagesize=(21 * cm, 29.7 * cm),
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.5 * cm,
        title="Basira — Note de synthèse",
        author="Équipe Basira — lot B",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("docs/note_synthese.pdf"))
    parser.add_argument("--stack", type=Path, default=PROJECT / "docs/team_stack.json")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        print(generate_report(args.data_dir, args.output, args.stack, args.final))
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
