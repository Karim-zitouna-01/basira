"""Generate the required French synthesis note (≤ 2 pages), with no invented evaluation results.

Every figure comes from a pipeline output: scores/evaluation.json, scores/modele.json,
scores/simulation_boucle.json, signaux/rapport_execution.json and docs/team_stack.json.
Style: plain French for a non-specialist jury, short sentences, no semicolons in paragraphs.
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

NOMS_METHODES = {  # nom dans evaluation.json → libellé lisible
    "Basira": "Basira",
    "Règle statique (type SAR)": "Règle fixe, proche des pratiques actuelles",
    "Sélection aléatoire": "Tirage au hasard",
}


def _lire(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _dt(montant):
    if montant >= 1_000_000:
        return f"{montant / 1_000_000:.1f}".replace(".", ",") + " million de DT"
    return f"{montant:,.0f}".replace(",", " ") + " DT"


def _pct(x):
    return f"{100 * x:.0f} %"


def _nb(x):
    return str(x).replace(".", ",")


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
    styles.add(ParagraphStyle(name="BodyFR", fontName="Helvetica", fontSize=8.7, leading=11.2, spaceAfter=4))
    styles.add(ParagraphStyle(name="PuceFR", parent=styles["BodyFR"], leftIndent=10, bulletIndent=0, spaceAfter=2.5))
    styles.add(ParagraphStyle(name="CelluleFR", parent=styles["BodyFR"], fontSize=7.8, leading=9.6, spaceAfter=0))
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

    def cellule(text, gras=False):
        return Paragraph(f"<b>{text}</b>" if gras else text, styles["CelluleFR"])

    def tableau(lignes, largeurs, gras_ligne=None):
        t = Table(lignes, colWidths=[w * cm for w in largeurs], repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce7f3")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        if gras_ligne is not None:
            style.append(("BACKGROUND", (0, gras_ligne), (-1, gras_ligne), colors.HexColor("#f3f7fc")))
        t.setStyle(TableStyle(style))
        story.append(t)
        story.append(Spacer(1, 4))

    nb_ent = f"{run['entreprises']:,}".replace(",", " ") if run else "5 250"
    nb_ctl = modele.get("nb_exemples", 276)
    story.append(Paragraph("BASIRA — Note de synthèse", styles["TitreFR"]))
    story.append(Paragraph(
        "Défi principal <b>T20 : score de risque dynamique de la conformité des entreprises</b>. Défi complémentaire T7 : "
        "croisement des données fiscales, douanières et financières. Hackathon « IA &amp; Finances publiques », septembre 2026."
        + (f"<br/>Code source : <link href=\"{escape(stack['depot'])}\" color=\"#174a7e\">{escape(stack['depot'])}</link>" if stack.get("depot") else ""),
        styles["SousTitreFR"]))
    if not final:
        paragraph("<b>Version de travail.</b> Les résultats et l'inventaire final restent à compléter. "
                  "Aucun chiffre d'exemple n'est présenté comme un résultat mesuré.")

    heading("1. Le défi")
    paragraph(
        "L'administration dispose déjà de nombreuses informations sur les entreprises, mais elles sont réparties entre plusieurs "
        "systèmes : les déclarations fiscales, la douane (SINDA), les paiements de l'État aux entreprises (ADEB) et les annexes de "
        "l'employeur, où chaque entreprise déclare ce qu'elle a payé à ses fournisseurs. Les contrôles sont aujourd'hui choisis par "
        "des règles fixes, qui visent surtout les grandes entreprises. Or la fraude se voit souvent en comparant ces sources entre "
        "elles. Par exemple, une entreprise qui importe trois fois plus sans que son chiffre d'affaires déclaré augmente."
    )
    paragraph(
        "<b>Basira</b> attribue chaque mois à chaque entreprise un <b>score de risque de 0 à 100</b>, estime le montant d'impôt en jeu "
        "et propose la liste des entreprises à contrôler en priorité. Chaque score est expliqué par des faits chiffrés et par les "
        "pièces qui les prouvent. L'inspecteur garde toujours la décision."
    )

    heading("2. Les données")
    paragraph(
        f"Aucune donnée réelle n'a été fournie ni utilisée. Nous avons généré des données fictives réalistes, au format des "
        f"documents officiels : <b>{nb_ent} entreprises suivies sur 24 mois</b> (septembre 2024 à août 2026), avec leurs déclarations "
        f"fiscales, leurs importations, les paiements publics reçus, ce que leurs clients déclarent leur avoir payé, et les résultats "
        f"de {nb_ctl} contrôles passés. Nous y avons caché 7 types de fraude connus (chiffre d'affaires minoré, fausses factures, "
        "sous-évaluation en douane, sociétés écrans…), ainsi que des entreprises honnêtes au comportement trompeur, comme une forte "
        "croissance correctement déclarée. La liste des vraies fraudes reste cachée. Elle sert uniquement à mesurer les résultats, "
        "jamais à entraîner le modèle. Chaque calcul n'utilise que les informations disponibles à la date concernée."
    )
    paragraph(
        "<b>Conformité (loi organique n° 2004-63, INPDP).</b> Aucune donnée personnelle ou confidentielle n'est utilisée, et aucun "
        "système de l'administration n'est sollicité. Les identifiants, les noms et les montants sont fictifs. Les données et "
        "l'assistant restent sur le réseau local, et rien n'est envoyé à un service en ligne."
    )

    heading("3. L'approche IA, en trois étapes")
    puce(
        "<b>Détecter.</b> Basira calcule 16 indicateurs d'alerte pour chaque entreprise et chaque mois. Ils comparent ce que "
        "l'entreprise déclare avec ce que les autres administrations observent, avec son propre passé et avec les entreprises du "
        "même secteur et de même taille. D'autres repèrent les liens suspects entre entreprises, comme des fournisseurs communs "
        "apparus en même temps ou des sociétés écrans. Chaque alerte est accompagnée d'une phrase explicative et des pièces qui la justifient."
    )
    puce(
        f"<b>Évaluer le risque.</b> Un modèle d'apprentissage automatique (régression logistique) apprend, à partir des {nb_ctl} "
        "contrôles passés, l'importance de chaque indicateur. Il produit un score de 0 à 100 que l'on peut décomposer : chaque point "
        "du score est rattaché à un indicateur précis. On sait donc toujours pourquoi une entreprise est jugée risquée. Le score est "
        "ensuite combiné au montant estimé en jeu pour classer les entreprises à contrôler."
    )
    puce(
        "<b>Assister l'inspecteur.</b> Un assistant conversationnel, le modèle de langage Qwen installé en local, répond aux questions "
        "de l'inspecteur à partir des seules données du dossier. Il peut par exemple remonter une chaîne de fournisseurs jusqu'à une "
        "entreprise déjà sanctionnée et l'afficher en direct sur le graphe des relations, ou rédiger une demande d'information. "
        "Si une réponse contient un chiffre absent des données, elle est bloquée et remplacée par une réponse préparée à l'avance. "
        "L'assistant ne prend aucune décision."
    )
    paragraph(
        "<b>Souveraineté.</b> Lors de la table ronde douane et fiscalité, l'administration a rappelé qu'elle ne peut pas utiliser "
        "d'IA générative publique : les serveurs, les modèles et les données doivent rester au sein de l'institution. Basira est "
        "conçu sur ce principe. Le modèle de langage Qwen est un modèle à poids ouverts, téléchargé une fois puis exécuté sur une "
        "machine locale, sans aucun appel à un service en ligne ni à un fournisseur étranger. Le score de risque est calculé par un "
        "modèle entraîné par l'équipe, que l'administration peut réentraîner sur place avec ses propres contrôles. L'ensemble repose "
        "sur des logiciels libres et fonctionne hors connexion : pendant le hackathon, l'assistant tournait sur un ordinateur de "
        "l'équipe, relié par un simple réseau local."
    )
    k = boucle.get("decisions_ajoutees") if boucle else None
    paragraph(
        "<b>Le prototype</b> est une application web : liste des entreprises classées par priorité, fiche de chaque entreprise avec "
        "l'explication de son score et les pièces, graphe de ses relations, assistant et formulaire de décision motivée. Les décisions "
        "des inspecteurs deviennent de nouveaux exemples pour réentraîner le modèle"
        + (f", ce que nous avons simulé sur {k} décisions." if k else ".")
    )

    heading("4. Les résultats")
    if evaluation:
        n = evaluation.get("top_n", 50)
        m = {x["nom"]: x for x in evaluation.get("methodes", [])}
        b, r, h = m.get("Basira", {}), m.get("Règle statique (type SAR)", {}), m.get("Sélection aléatoire", {})
        paragraph(
            f"<b>Comment nous avons mesuré.</b> Nous avons rejoué une année de contrôles, de septembre 2025 à août 2026. Chaque mois, "
            f"trois méthodes choisissent chacune <b>{n} entreprises à contrôler</b> parmi les {nb_ent}, ce qui correspond à une capacité "
            "de contrôle réaliste : Basira, une règle fixe proche des pratiques actuelles (elle privilégie les grandes entreprises et "
            "quelques indicateurs classiques), et un tirage au hasard. On compare ensuite leurs choix à la liste cachée des vraies fraudes. "
            "Les chiffres sont des moyennes sur les 12 mois."
        )
        lignes = [[cellule("Méthode de sélection", True), cellule("Part des entreprises choisies qui fraudent réellement", True),
                   cellule("Montant éludé retrouvé en moyenne par contrôle", True),
                   cellule("Entreprises honnêtes en forte croissance choisies à tort, par mois", True)]]
        for nom in ("Basira", "Règle statique (type SAR)", "Sélection aléatoire"):
            if nom in m:
                x = m[nom]
                gras = nom == "Basira"
                lignes.append([cellule(NOMS_METHODES[nom], gras), cellule(_pct(x["taux_detection_top_n"]), gras),
                               cellule(_dt(x["montant_moyen_par_controle"]), gras), cellule(_nb(x["fausses_alertes_croissance_legitime"]), gras)])
        tableau(lignes, [5.0, 4.0, 4.1, 4.7], gras_ligne=1)
        if b and r and h:
            vrais = lambda x: _nb(round(x["taux_detection_top_n"] * n, 1)).replace(",0", "")  # noqa: E731  moyenne mensuelle
            facteur = b["montant_moyen_par_controle"] / max(r["montant_moyen_par_controle"], 1)
            paragraph(
                f"<b>Lecture.</b> Sur les {n} entreprises proposées chaque mois par Basira, {vrais(b)} en moyenne fraudent réellement "
                f"({_pct(b['taux_detection_top_n'])}), contre {vrais(r)} avec la règle fixe et {vrais(h)} avec un tirage au hasard. "
                f"Chaque contrôle proposé par Basira porte en moyenne sur {_dt(b['montant_moyen_par_controle'])} d'impôt éludé, "
                f"soit {facteur:.0f} fois plus qu'avec la règle fixe. Basira écarte aussi beaucoup mieux les entreprises honnêtes en forte "
                f"croissance ({_nb(b['fausses_alertes_croissance_legitime'])} par mois contre {_nb(r['fausses_alertes_croissance_legitime'])})."
            )
        v = evaluation.get("validation_modele", {})
        if v:
            paragraph(
                f"En août 2026, {v['prioritaires_mois_courant']} entreprises sur {nb_ent} sont classées prioritaires, et "
                f"{_pct(v['precision_prioritaires_mois_courant'])} d'entre elles fraudent réellement. Le résultat ne dépend pas des "
                f"contrôles utilisés pour l'apprentissage : un modèle entraîné uniquement sur les contrôles antérieurs à l'année de test "
                f"obtient le même taux ({_pct(v['detection_top_n_modele_sans_controles_periode_test'])})."
            )
    else:
        paragraph("<b>Résultats non encore mesurés.</b> Le fichier d'évaluation est absent. Aucun gain chiffré n'est revendiqué.")

    heading("5. Les limites")
    puce("Les données sont fictives et ont été conçues en même temps que les indicateurs. Les résultats montrent que l'approche "
         "fonctionne et que le croisement des sources est utile, mais pas son efficacité sur des données réelles.")
    if evaluation and evaluation.get("validation_modele"):
        v = evaluation["validation_modele"]
        det = evaluation.get("details", {}).get("Basira", {})
        sc = v.get("part_prioritaire_par_scenario", {})
        puce(f"Avec seulement {v['nb_controles']} contrôles passés, le modèle appris ne fait pas mieux qu'une simple moyenne des "
             f"indicateurs ({_pct(evaluation['methodes'][0]['taux_detection_top_n'])} contre {_pct(v['detection_top_n_poids_egaux'])}). "
             "Le gain vient surtout du croisement des sources. L'apprentissage deviendra utile avec les décisions des inspecteurs.")
        puce(f"Basira ne repère pas les fraudes plus tôt que la règle fixe. Une fraude est proposée au contrôle "
             f"{_nb(det.get('delai_moyen_detection_mois', '?'))} mois après son début, en moyenne.")
        if {"E", "F", "CROISSANCE_LEGITIME"} <= set(sc):
            puce(f"Deux types de fraude sont mal détectés : l'entreprise dormante qui reprend soudain une activité "
                 f"({_pct(sc['E']['part'])} classées prioritaires) et la marge qui se réduit progressivement ({_pct(sc['F']['part'])}). "
                 f"Par ailleurs, {_pct(sc['CROISSANCE_LEGITIME']['part'])} des entreprises honnêtes en forte croissance sont classées "
                 "prioritaires à tort.")
    puce("Le montant en jeu est une estimation, fondée en partie sur des données annuelles, et ses taux doivent être validés avec "
         "les inspecteurs.")

    heading("6. Modèles, bibliothèques et ressources utilisés")
    composants = stack.get("composants", [])
    if composants:
        lignes = [[cellule("Élément", True), cellule("Rôle dans Basira", True), cellule("Nature", True)]]
        for c in composants:
            lignes.append([cellule(escape(c["element"])), cellule(escape(c["usage"])), cellule(escape(c["type"]))])
        tableau(lignes, [6.0, 7.0, 4.8])
    paragraph("Aucune API externe ni aucun service en ligne n'est utilisé : tout fonctionne hors connexion. "
              + escape(stack.get("precision_versions", "")))

    heading("7. Recommandations pour une mise en production")
    paragraph(
        "Relier Basira aux systèmes réels, notamment le lac de données SADEC 2 et SINDA, en conservant la date à laquelle chaque "
        "information devient disponible. Unifier les identifiants et le référentiel des activités entre administrations. Valider les "
        "indicateurs et l'estimation des montants avec les inspecteurs. Héberger les données, le modèle de langage et l'application "
        "sur les serveurs de l'administration, dans le cadre de la stratégie nationale d'IA et sans dépendre d'aucun service "
        "extérieur, avec une gestion des droits d'accès et la traçabilité des consultations. Avant tout usage de données "
        "réelles, réaliser une analyse d'impact et accomplir les formalités auprès de l'INPDP (loi organique n° 2004-63). Enfin, "
        "réentraîner régulièrement le modèle avec les résultats réels des contrôles, surveiller les écarts de traitement selon le "
        "secteur, la taille et la région, et garder la décision humaine."
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
