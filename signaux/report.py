"""Generate the required French synthesis note (≤ 2 pages), with no invented evaluation results.

Every figure comes from a pipeline output: scores/evaluation.json, scores/modele.json,
scores/simulation_boucle.json, signaux/rapport_execution.json and docs/team_stack.json.
"""

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT = Path(__file__).resolve().parents[1]


def _lire(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _dt(montant):
    return f"{montant:,.0f}".replace(",", " ") + " DT"


def _pct(x):
    return f"{100 * x:.0f} %"


def generate_report(data_dir, output, stack_path, final=False):
    stack = json.loads(stack_path.read_text(encoding="utf-8"))
    evaluation = _lire(data_dir / "scores" / "evaluation.json")
    if final and (evaluation is None or not stack.get("confirmed_by_c_and_d")):
        raise ValueError(
            "Version finale impossible : fournir evaluation.json de C et confirmer docs/team_stack.json avec C et D."
        )
    modele = _lire(data_dir / "scores" / "modele.json") or {}
    boucle = _lire(data_dir / "scores" / "simulation_boucle.json")
    run = _lire(data_dir / "signaux" / "rapport_execution.json")

    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyFR", fontName="Helvetica", fontSize=8.6, leading=11, spaceAfter=4))
    styles.add(ParagraphStyle(name="PuceFR", parent=styles["BodyFR"], leftIndent=9, bulletIndent=0, spaceAfter=2))
    styles.add(ParagraphStyle(name="TitreFR", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="SousTitreFR", parent=styles["BodyFR"], alignment=TA_CENTER, textColor=colors.HexColor("#4d5563"), spaceAfter=6))
    styles.add(ParagraphStyle(name="H2FR", fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=5, spaceAfter=3, keepWithNext=1,
                              textColor=colors.HexColor("#174a7e")))
    story = []

    def paragraph(text):
        story.append(Paragraph(text, styles["BodyFR"]))

    def puce(text):
        story.append(Paragraph(text, styles["PuceFR"], bulletText="•"))

    def heading(text):
        story.append(Paragraph(text, styles["H2FR"]))

    nb_ent = f"{run['entreprises']:,}".replace(",", " ") if run else "5 250"
    story.append(Paragraph("BASIRA — Note de synthèse", styles["TitreFR"]))
    story.append(Paragraph(
        "Défi principal <b>T20 — Risk scoring dynamique de la conformité des entreprises</b> · défi complémentaire T7 "
        "(croisement des données fiscales, douanières et de paiement). Hackathon « IA &amp; Finances publiques », septembre 2026."
        + (f"<br/>Code source : <link href=\"{escape(stack['depot'])}\" color=\"#174a7e\">{escape(stack['depot'])}</link>" if stack.get("depot") else ""),
        styles["SousTitreFR"]))
    if not final:
        paragraph("<b>Version de travail.</b> Les résultats d'impact et l'inventaire final restent à compléter s'ils ne sont pas "
                  "fournis. Aucun chiffre d'exemple du contrat n'est présenté comme un résultat mesuré.")

    heading("1. Problème traité")
    paragraph(
        "Les informations utiles au contrôle existent déjà mais restent en silos : déclarations fiscales, douane (SINDA), "
        "paiements publics (ADEB), annexes de l'employeur. La sélection des contrôles repose sur des règles statiques qui "
        "favorisent les grandes entreprises et les secteurs « classiques », pour une couverture de l'ordre de 2,5 % des "
        "contribuables. <b>Basira</b> classe chaque mois tout le portefeuille par <b>risque × enjeu</b>, explique chaque score "
        "par des faits chiffrés et les pièces sources, et laisse la décision à l'inspecteur : aucune sanction n'est automatique."
    )

    heading("2. Données utilisées")
    paragraph(
        f"Données <b>entièrement synthétiques</b> (aucune donnée réelle) : {nb_ent} entreprises sur 24 mois (2024-09 → 2026-08), "
        "au format du dossier fiscal, de la déclaration mensuelle, des annexes I, II et V, des déclarations et liquidations "
        "douanières, des paiements ADEB et des contrôles passés. Le générateur injecte 7 schémas de fraude (minoration du CA, "
        "réseaux de fausses factures, sous-évaluation en douane, recettes publiques non déclarées, dormante réactivée, compression "
        "de marge, sociétés coquilles) et des témoins trompeurs (croissance légitime, citoyens modèles, sosies sans fraude). "
        "La vérité terrain n'est lue que par l'évaluation, jamais par l'entraînement ni pour fixer un seuil. Un calcul à fin M "
        "ne lit que ce qui était disponible à cette date (déclaration de M connue en M+1, annexes de l'exercice N en mars N+1)."
    )
    paragraph(
        "<b>Conformité (loi organique n° 2004-63, INPDP).</b> Aucune donnée réelle, personnelle ou confidentielle n'est utilisée ni "
        "requise, et aucun système de l'administration n'est sollicité : identifiants, raisons sociales et montants sont fictifs. "
        "Les données et l'assistant restent sur le réseau local ; aucune donnée n'est envoyée à un service en ligne."
    )

    heading("3. Approche IA")
    puce(
        "<b>16 signaux explicables</b>, 4 lentilles : <i>cohérence</i> entre sources indépendantes (imports ou paiements reçus vs CA "
        "déclaré, TVA import, prix de référence en douane), <i>changement</i> (EWMA sur l'historique propre), <i>pairs</i> (écart robuste "
        "médiane/MAD, distance de Mahalanobis régularisée par secteur × taille), <i>réseau</i> (fournisseurs partagés, coquilles, "
        "proximité d'entreprises redressées). Statistiques déterministes ; chaque signal actif porte un fait en français et "
        "jusqu'à 50 pièces sources."
    )
    nb_ex, nb_pos = modele.get("nb_exemples", "?"), modele.get("nb_positifs", "?")
    puce(
        f"<b>Score appris</b> : régression logistique L2 sur {nb_ex} contrôles passés ({nb_pos} redressements), caractéristiques au "
        "mois précédant l'avis, poids ≥ 0 (un signal d'alerte ne baisse jamais le risque). Les signaux jamais observés en "
        "contrôle ou à coefficient négatif — effet du biais de sélection de la règle statique — reçoivent un poids a priori "
        "(médiane des poids appris). Échelle fixée par la capacité de contrôle (1 % des couples entreprise × mois ≥ 70) ; un "
        "écart très marqué entre deux sources indépendantes suffit à rendre l'entreprise prioritaire ; plafond 99. Chaque point "
        "est attribué à un signal (somme des points = score − score de base) : l'explication est exacte par construction."
    )
    puce(
        "<b>Priorité</b> = score × enjeu (droits éludés reconstitués à partir des écarts entre sources). Segments PRIORITAIRE, "
        "SURVEILLANCE, NORMAL et CONFIANCE (voie de facilitation) ; action suggérée (demande d'information, vérification, "
        "signalement à la douane)."
    )
    puce(
        "<b>Assistant</b> : Qwen 3.5 9B hébergé en local, 6 outils (dossier, preuves, réseau, lettre de demande d'information, "
        "liens d'une contrepartie, chemin vers une entreprise redressée). Les outils de réseau mettent à jour le graphe de l'écran "
        "en direct, avant la réponse écrite ; le graphe ne montre que des relations déclarées. Tout chiffre de la réponse doit "
        "provenir des outils, sinon Basira renvoie une réponse déterministe ; l'assistant ne décide jamais."
    )
    k = boucle.get("decisions_ajoutees") if boucle else None
    puce(
        "<b>Prototype</b> : application web de l'inspecteur (liste priorisée, fiche « Pourquoi ce score ? » avec pièces sources, "
        "graphe du réseau déployable de proche en proche, copilote, décision motivée et journalisée). Les décisions deviennent de "
        "nouveaux exemples étiquetés : <b>boucle d'apprentissage</b>"
        + (f" (simulation avant/après sur {k} décisions, sans réentraînement en direct)." if k else ".")
    )

    heading("4. Résultats (données synthétiques)")
    if evaluation:
        paragraph(
            f"Chaque mois de la période de test ({escape(str(evaluation.get('periode_test', '?')))}), chaque méthode choisit "
            f"{evaluation.get('top_n', '?')} entreprises à contrôler. Moyennes mensuelles :"
        )
        rows = [["Méthode", "Fraudes dans la sélection", "Droits éludés / contrôle", "Croissances légitimes retenues"]]
        for m in evaluation.get("methodes", []):
            rows.append([m["nom"], _pct(m["taux_detection_top_n"]), _dt(m["montant_moyen_par_controle"]),
                         str(m["fausses_alertes_croissance_legitime"]).replace(".", ",")])
        table = Table(rows, colWidths=[5.2 * cm, 3.8 * cm, 3.8 * cm, 4.8 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce7f3")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(table)
        story.append(Spacer(1, 4))
        v = evaluation.get("validation_modele", {})
        if v:
            paragraph(
                f"En 2026-08, {v['prioritaires_mois_courant']} entreprises sont PRIORITAIRE, dont "
                f"<b>{_pct(v['precision_prioritaires_mois_courant'])} de fraudes actives</b>. Robustesse : un modèle entraîné "
                f"uniquement sur les {v['nb_controles_avant_periode_test']} contrôles antérieurs à la période de test garde "
                f"{_pct(v['detection_top_n_modele_sans_controles_periode_test'])} de fraudes dans sa sélection."
            )
    else:
        paragraph(
            "<b>Impact non encore mesuré :</b> data/scores/evaluation.json de C est absent. La comparaison avec une règle statique "
            "et le hasard sera reprise automatiquement de ce fichier. Aucun gain chiffré n'est revendiqué."
        )

    heading("5. Limites identifiées")
    puce("Les données et les signaux sont conçus à partir de la même spécification : ces résultats montrent la faisabilité et "
         "l'intérêt du croisement des sources, pas l'efficacité en production.")
    if evaluation and evaluation.get("validation_modele"):
        v = evaluation["validation_modele"]
        det = evaluation.get("details", {}).get("Basira", {})
        basira = next((m for m in evaluation.get("methodes", []) if m["nom"] == "Basira"), {})
        sc = v.get("part_prioritaire_par_scenario", {})
        puce(f"Avec {v['nb_controles']} contrôles passés, rares, bruités et biaisés par leur sélection, les poids appris ne font pas "
             f"mieux que des poids égaux (AUC en validation croisée {str(v['auc_validation_croisee_poids_appris']).replace('.', ',')} "
             f"contre {str(v['auc_validation_croisee_poids_egaux']).replace('.', ',')} ; sélection {_pct(basira.get('taux_detection_top_n', 0))} "
             f"contre {_pct(v['detection_top_n_poids_egaux'])}). La performance vient du croisement des sources ; l'apprentissage "
             "prendra son sens avec les décisions des inspecteurs.")
        puce(f"Pas d'avance de détection mesurée sur la règle statique ({str(basira.get('avance_detection_mois')).replace('.', ',')} mois) ; "
             f"une fraude entre dans la sélection {str(det.get('delai_moyen_detection_mois', '?')).replace('.', ',')} mois après son début "
             f"en moyenne, et {det.get('entreprises_frauduleuses_detectees', '?')} fraudes sur {det.get('sur', '?')} y entrent au moins une fois.")
        if {"E", "F", "CROISSANCE_LEGITIME"} <= set(sc):
            puce(f"Schémas mal couverts : dormante réactivée ({_pct(sc['E']['part'])} PRIORITAIRE), compression de marge "
                 f"({_pct(sc['F']['part'])}) ; {_pct(sc['CROISSANCE_LEGITIME']['part'])} des croissances légitimes sont PRIORITAIRE.")
    puce("L'enjeu est une estimation (données annuelles, double compte possible clients/ADEB, taux de prototype à valider). "
         "Le référentiel d'activités n'est pas unifié entre administrations ; SAR et SADEC 2 ne sont connus que par la conférence.")

    heading("6. Modèles, bibliothèques, API tierces et ressources citées")
    for model in stack.get("models", []):
        puce(escape(f"{model['owner']} — {model['name']} ; pré-entraîné : {'oui' if model['pretrained'] else 'non'} ; {model['status']}."))
    paragraph(escape(" · ".join(f"{owner} : {', '.join(libs)}" for owner, libs in stack.get("libraries", {}).items()))
              + ". Aucune API externe ni service en ligne : tout fonctionne hors connexion.")
    if stack.get("ressources_externes"):
        paragraph("<b>Code et ressources externes cités :</b> " + escape(" ; ".join(stack["ressources_externes"])) + ".")

    heading("7. Recommandations pour une mise en production")
    paragraph(
        "Brancher les sources au data lake SADEC 2 et à SINDA en conservant les dates de disponibilité ; unifier identifiants et "
        "référentiel d'activités ; valider les signaux et l'enjeu avec les métiers. Héberger données et assistant dans le périmètre "
        "de l'administration, avec habilitations, journalisation et minimisation ; avant tout traitement de données réelles, analyse "
        "d'impact et formalités auprès de l'INPDP (loi organique n° 2004-63). Réentraîner sur les "
        "résultats réels et les décisions des inspecteurs, suivre les biais par secteur, taille et région, et garder la décision humaine."
    )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(19.4 * cm, 0.8 * cm, f"Basira · Note de synthèse · {doc.page}")

    doc = SimpleDocTemplate(
        str(output),
        pagesize=(21 * cm, 29.7 * cm),
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.3 * cm,
        title="Basira — Note de synthèse",
        author="Équipe Basira",
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
