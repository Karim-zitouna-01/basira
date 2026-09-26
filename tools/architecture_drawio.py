"""Génère docs/architecture.drawio (architecture complète de Basira, format draw.io / diagrams.net).

Usage : uv run python tools/architecture_drawio.py docs/architecture.drawio
"""
import sys
import xml.etree.ElementTree as ET

SORTIE = sys.argv[1] if len(sys.argv) > 1 else "architecture.drawio"

COUL = {  # (remplissage, contour)
    "A": ("#dae8fc", "#6c8ebf"), "B": ("#d5e8d4", "#82b366"), "C": ("#ffe6cc", "#d79b00"),
    "API": ("#e1d5e7", "#9673a6"), "D": ("#f8cecc", "#b85450"), "LLM": ("#fff2cc", "#d6b656"),
    "DATA": ("#f5f5f5", "#666666"), "NOTE": ("#ffffff", "#999999"),
}

racine = ET.Element("mxfile", host="Basira", version="24.0.0")
diag = ET.SubElement(racine, "diagram", id="basira-architecture", name="Architecture Basira")
modele = ET.SubElement(diag, "mxGraphModel", dx="1900", dy="1100", grid="1", gridSize="10", guides="1", tooltips="1",
                       connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth="1960", pageHeight="1080",
                       math="0", shadow="0", background="#ffffff")
root = ET.SubElement(modele, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")
_n = [0]


def _id(p="c"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def texte(titre, *lignes, taille=11):
    corps = "<br>".join(lignes)
    return f"<b>{titre}</b>" + (f"<br><span style=\"font-size:{taille - 1}px\">{corps}</span>" if lignes else "")


def cellule(valeur, style, x, y, w, h, parent="1", ident=None):
    ident = ident or _id()
    c = ET.SubElement(root, "mxCell", id=ident, value=valeur, style=style, vertex="1", parent=parent)
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})
    return ident


def conteneur(titre, lot, x, y, w, h):
    f, s = COUL[lot]
    style = (f"swimlane;html=1;startSize=34;rounded=1;arcSize=4;fillColor={f};strokeColor={s};swimlaneFillColor=#ffffff;"
             f"fontStyle=1;fontSize=14;fontColor=#1f2937;strokeWidth=2;")
    return cellule(titre, style, x, y, w, h)


def boite(parent, valeur, lot, x, y, w, h, tirets=False, gras=False):
    f, s = COUL[lot]
    style = (f"rounded=1;whiteSpace=wrap;html=1;arcSize=10;fillColor={f};strokeColor={s};fontSize=11;fontColor=#111827;"
             f"align=center;verticalAlign=middle;spacing=4;" + ("dashed=1;" if tirets else "") + ("strokeWidth=2.5;" if gras else ""))
    return cellule(valeur, style, x, y, w, h, parent)


def cylindre(parent, valeur, x, y, w, h, lot="DATA", tirets=False):
    f, s = COUL[lot]
    style = (f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=7;fillColor={f};strokeColor={s};"
             f"fontSize=10;fontColor=#111827;" + ("dashed=1;" if tirets else ""))
    return cellule(valeur, style, x, y, w, h, parent)


def note(parent, valeur, x, y, w, h, taille=10):
    return cellule(valeur, f"text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize={taille};fontColor=#4b5563;",
                   x, y, w, h, parent)


def fleche(src, tgt, libelle="", couleur="#374151", tirets=False, points=(), deux_sens=False, epais=1.6, extra=""):
    style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;html=1;strokeColor={couleur};strokeWidth={epais};"
             f"fontSize=10;fontColor={couleur};labelBackgroundColor=#ffffff;endArrow=block;endFill=1;"
             + ("dashed=1;" if tirets else "") + ("startArrow=block;startFill=1;" if deux_sens else "") + extra)
    e = ET.SubElement(root, "mxCell", id=_id("e"), value=libelle, style=style, edge="1", parent="1", source=src, target=tgt)
    g = ET.SubElement(e, "mxGeometry", relative="1", attrib={"as": "geometry"})
    if points:
        arr = ET.SubElement(g, "Array", attrib={"as": "points"})
        for px, py in points:
            ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
    return e


def interne(a, b):  # petite flèche verticale dans un conteneur
    return fleche(a, b, couleur="#9ca3af", epais=1.2, extra="edgeStyle=none;")


# ------------------------------------------------------------------ titre
cellule("<b>Basira</b> — architecture technique", "text;html=1;fontSize=24;fontColor=#111827;align=left;verticalAlign=middle;",
        40, 14, 900, 36)
cellule("Risque de conformité des entreprises, dynamique et explicable · défi T20 (+T7) · données entièrement synthétiques · "
        "tout fonctionne hors connexion", "text;html=1;fontSize=12;fontColor=#4b5563;align=left;verticalAlign=middle;",
        40, 44, 1400, 22)

# ------------------------------------------------------------------ ① données synthétiques (A)
A = conteneur("① Données synthétiques — generation/ (A)", "A", 40, 90, 280, 780)
a1 = boite(A, texte("Générateur du monde", "5 250 entreprises × 24 mois", "flux cohérents entre sources", "7 schémas de fraude + témoins"), "A", 20, 46, 240, 78)
a2 = boite(A, texte("Contrôles passés", "sélection biaisée (règle type SAR)", "résultats bruités"), "A", 20, 136, 240, 60)
a3 = boite(A, texte("Graphe des relations", "NetworkX · métriques mensuelles", "partages · coquilles · distance"), "A", 20, 208, 240, 62)
boite(A, "84 contrôles de cohérence (checks.py)", "A", 20, 282, 240, 30, tirets=True)
interne(a1, a2)
interne(a2, a3)
cylindre(A, "<b>Déclarations DGI</b><br>mensuelles · IS", 20, 330, 115, 66)
cylindre(A, "<b>Douane SINDA</b><br>décl. · articles · liquid.", 145, 330, 115, 66)
cylindre(A, "<b>Paiements ADEB</b><br>marchés publics", 20, 408, 115, 66)
cylindre(A, "<b>Annexes employeur</b><br>I · II · V", 145, 408, 115, 66)
cylindre(A, "<b>Registre</b><br>+ référentiels", 20, 486, 115, 66)
ctl = cylindre(A, "<b>Contrôles passés</b><br>276 (étiquettes)", 145, 486, 115, 66)
cylindre(A, "<b>Graphe</b><br>arêtes · métriques", 20, 564, 115, 66)
vt = cylindre(A, "<b>Vérité terrain</b><br>(cachée)", 145, 564, 115, 66, lot="D", tirets=True)
note(A, "data/raw · data/graphe — 20 tables CSV", 20, 636, 240, 22)
boite(A, texte("Qwen local, hors ligne", "vocabulaire des noms d'entreprises fictives", "(la génération n'appelle pas le modèle)"), "LLM", 20, 668, 240, 60, tirets=True)
note(A, "numpy · pandas · networkx · vis-network", 20, 738, 240, 22)

# ------------------------------------------------------------------ ② signaux (B)
B = conteneur("② Signaux et enjeu — signaux/ (B)", "B", 380, 90, 300, 780)
boite(B, texte("Disponibilité à date", "calcul à fin M sur les seuls dépôts reçus", "déclaration M → M+1 · annexes N → mars N+1"), "B", 20, 46, 260, 60, tirets=True)
b1 = boite(B, texte("Cohérence entre sources · 5 COH_*", "imports / CA · clients / CA · ADEB / CA", "TVA import · prix de référence douane"), "B", 20, 120, 260, 64)
b2 = boite(B, texte("Changement · 6 CHG_*", "EWMA α = 0,3 vs 10 mois de référence (z-score)"), "B", 20, 196, 260, 48)
b3 = boite(B, texte("Pairs · 2 PAI_*", "marge vs médiane (MAD) · Mahalanobis robuste", "division NAT × taille (≥ 30 pairs)"), "B", 20, 256, 260, 64)
b4 = boite(B, texte("Réseau · 3 RES_*", "fournisseur nouveau partagé · coquilles", "proximité d'entreprises redressées"), "B", 20, 332, 260, 64)
b5 = boite(B, texte("Preuves", "≤ 50 pièces par signal (table:identifiant)", "+ phrase en français (fait_fr)"), "B", 20, 412, 260, 58)
b6 = boite(B, texte("Enjeu estimé", "CA reconstitué − CA déclaré", "→ TVA + IS éludés · fourchette de confiance"), "B", 20, 482, 260, 62)
sig = cylindre(B, "<b>data/signaux</b><br>signaux.parquet · 2 016 000 lignes<br>enjeux · pairs_stats · groupes_pairs", 20, 562, 260, 84)
note(B, "16 signaux normalisés 0–1, chacun avec valeur brute, phrase et pièces", 20, 656, 260, 34)
note(B, "numpy · pandas · pyarrow · reportlab (note de synthèse)", 20, 700, 260, 22)
interne(b5, b6)
interne(b6, sig)

# ------------------------------------------------------------------ ③ score (C)
C = conteneur("③ Score, priorité, évaluation — scoring/ (C)", "C", 740, 90, 320, 780)
c1 = boite(C, texte("Apprentissage · train.py", "régression logistique L2 · poids ≥ 0", "signaux au mois précédant l'avis de contrôle",
                    "poids a priori : jamais observés / négatifs"), "C", 20, 46, 280, 82)
c2 = boite(C, texte("Calibrage par la capacité", "sans signal = 5 · top 1 % des couples = 70", "plancher preuve forte (COH ≥ 0,8) · plafond 99"), "C", 20, 142, 280, 64)
c3 = boite(C, texte("Score explicable · score.py", "100·σ(b0 + Σ wᵢxᵢ) + bonus « nouveau schéma »", "points par signal : somme = score − base"), "C", 20, 220, 280, 64)
c4 = boite(C, texte("Enjeu complété · enjeux.py", "douane sous-évaluée · imports excédentaires"), "C", 20, 298, 280, 48)
c5 = boite(C, texte("Priorité = score × enjeu", "PRIORITAIRE · SURVEILLANCE · NORMAL · CONFIANCE", "action suggérée · résumé en français"), "C", 20, 360, 280, 64)
c6 = boite(C, texte("Évaluation · evaluate.py", "top 50 / mois : Basira vs règle SAR vs hasard", "validation croisée · modèle hors période de test"), "C", 20, 438, 280, 64)
c7 = boite(C, texte("Boucle d'apprentissage · boucle.py", "décisions → exemples étiquetés → réentraînement", "(hors démo, validé avant mise en service)"), "C", 20, 516, 280, 64, tirets=True)
sco = cylindre(C, "<b>data/scores</b><br>scores.parquet · modele.json<br>evaluation.json · enjeux.parquet", 20, 596, 280, 80)
note(C, "87 % de fraudes dans le top 50 (SAR 23 %, hasard 5 %) · précision PRIORITAIRE 73 %", 20, 684, 280, 34)
note(C, "scikit-learn · pandas", 20, 724, 280, 22)
for a, b in ((c1, c2), (c2, c3), (c3, c5), (c4, c5), (c5, c6)):
    interne(a, b)

# ------------------------------------------------------------------ ④ API (C)
P = conteneur("④ API — api/ (C · FastAPI + Uvicorn)", "API", 1120, 90, 360, 580)
boite(P, texte("Chargement en mémoire au démarrage (~11 s)", "lit data/scores, data/signaux, data/raw · aucun recalcul"), "API", 20, 46, 320, 48, tirets=True)
p1 = boite(P, texte("Routes de l'interface · front.py", "/api/front/portefeuille · /entreprises/{mf}", "/voisins/{id} (déploiement du réseau)"), "API", 20, 106, 320, 62)
p2 = boite(P, texte("Routes du contrat", "/entreprises · /preuves · /reseau · /evaluation · /sante"), "API", 20, 180, 320, 48)
p3 = boite(P, texte("Explications chiffrées · explications.py", "phrases avec chiffres · chemin vers une entreprise redressée"), "API", 20, 240, 320, 50)
p4 = boite(P, texte("Assistant · assistant.py", "6 outils : fiche · preuves · réseau · lettre", "liens d'une contrepartie · chemin vers entreprise redressée",
                    "outils évidents · garde-fou sur les chiffres · repli déterministe"), "API", 20, 302, 320, 84, gras=True)
p5 = boite(P, texte("POST /api/assistant/flux (SSE)", "étape → action sur le graphe → réponse"), "API", 20, 398, 320, 50)
p6 = boite(P, texte("Décisions · decisions.py", "POST /decision → decisions.csv (journal)"), "API", 20, 460, 320, 48)
note(P, "pydantic · client openai (API compatible OpenAI)", 20, 520, 320, 22)
interne(p4, p5)

# ------------------------------------------------------------------ ⑤ LLM
L = boite("1", texte("⑤ LLM local — Qwen 3.5 9B", "poids ouverts · quantification Q4_K_M", "llama.cpp (llama-server) · API compatible OpenAI",
                     "PC du réseau local · aucune donnée ne sort"), "LLM", 1160, 730, 280, 96, gras=True)

# ------------------------------------------------------------------ ⑥ interface (D)
D = conteneur("⑥ Interface de l'inspecteur — web/ (D)", "D", 1540, 90, 300, 580)
d1 = boite(D, texte("Portefeuille", "indicateurs · tableau priorisé · filtres · pagination"), "D", 20, 46, 260, 50)
d2 = boite(D, texte("Fiche entreprise", "score · déclaré vs observé · trajectoire"), "D", 20, 108, 260, 50)
d3 = boite(D, texte("« Pourquoi ce score ? »", "points par signal · preuves · pairs"), "D", 20, 170, 260, 50)
d4 = boite(D, texte("Graphe du réseau", "React Flow + dagre · déploiement · focus", "suit le copilote en direct"), "D", 20, 232, 260, 62)
d5 = boite(D, texte("Copilote IA", "réponses en flux · étapes · sources citées"), "D", 20, 306, 260, 50)
d6 = boite(D, texte("Opérations", "pièces sources : SINDA · ADEB · annexe V"), "D", 20, 368, 260, 50)
d7 = boite(D, texte("Décision motivée", "action + justification obligatoire"), "D", 20, 430, 260, 50)
note(D, "React 19 · Vite · Mantine · Tailwind · dc.js · Crossfilter · D3 · react-markdown", 20, 492, 260, 36)

insp = cellule("<b>Inspecteur</b><br>décide", "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
               "fillColor=#ffffff;strokeColor=#1f2937;strokeWidth=2;fontSize=12;", 1885, 330, 36, 70)

# ------------------------------------------------------------------ flux principaux (libellés courts, dans les couloirs)
fleche(A, B, "CSV +<br>graphe", epais=2.2)
fleche(B, C, "signaux<br>preuves<br>enjeu", epais=2.2)
fleche(C, P, "scores<br>modèle<br>éval.", epais=2.2, extra="exitX=1;exitY=0.35;entryX=0;entryY=0.47;")
fleche(ctl, c1, "contrôles passés = étiquettes d'apprentissage", couleur="#b45309", points=((328, 78), (900, 78)),
       extra="exitX=1;exitY=0.5;entryX=0.5;entryY=0;")
fleche(vt, c6, "vérité terrain : mesure seulement, jamais d'apprentissage", couleur="#b91c1c", tirets=True,
       points=((372, 687), (372, 905), (1080, 905), (1080, 560)), extra="exitX=1;exitY=0.5;entryX=1;entryY=0.5;")
fleche(p6, c7, "décisions", couleur="#b45309", tirets=True, points=((1100, 574), (1100, 638)),
       extra="exitX=0;exitY=0.5;entryX=1;entryY=0.5;")
fleche(P, D, "JSON<br>flux", deux_sens=True, epais=2.2, extra="exitX=1;exitY=0.3;entryX=0;entryY=0.3;")
fleche(p5, d4, "actions<br>graphe", couleur="#7c3aed", tirets=True, extra="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
fleche(P, L, "assistant ⇄ Qwen (outils)", couleur="#a16207", deux_sens=True, extra="exitX=0.5;exitY=1;entryX=0.5;entryY=0;")
fleche(D, insp, "", deux_sens=True, epais=2)

# ------------------------------------------------------------------ légende et gouvernance
leg = cellule("", "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d1d5db;arcSize=6;", 40, 930, 980, 120)
note(leg, "<b>Légende</b>", 10, 6, 120, 20, taille=12)
for i, (lot, lib) in enumerate((("A", "A · génération des données"), ("B", "B · signaux et enjeu"), ("C", "C · score et évaluation"),
                                ("API", "C · API et assistant"), ("D", "D · interface"), ("LLM", "LLM local (Qwen)"))):
    f, s = COUL[lot]
    cellule(lib, f"rounded=1;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};fontSize=10;", 10 + (i % 3) * 160, 32 + (i // 3) * 40, 150, 30, leg)
note(leg, "── flux de données<br>- - boucle, mesure ou action en direct<br>▭ contour épais : cœur de l'IA générative",
     500, 30, 230, 72, taille=10)
cyl_l = cylindre(leg, "fichier / table", 760, 36, 90, 56)
note(leg, "fichiers produits<br>par le pipeline", 858, 40, 110, 48, taille=10)

gov = cellule(texte("Garde-fous", "données entièrement synthétiques · vérité terrain lue uniquement par l'évaluation",
                    "aucun calcul ne lit le futur · chaque point du score renvoie à des pièces",
                    "aucun chiffre non fondé dans les réponses du copilote · le graphe ne montre que des relations déclarées",
                    "tout fonctionne hors connexion · la décision reste humaine · 53 tests automatiques", taille=12),
              "rounded=1;whiteSpace=wrap;html=1;fillColor=#f0fdf4;strokeColor=#16a34a;strokeWidth=1.5;fontSize=12;align=left;spacingLeft=12;",
              1120, 930, 720, 120)

ET.ElementTree(racine).write(SORTIE, encoding="utf-8", xml_declaration=False)
print("écrit", SORTIE)
