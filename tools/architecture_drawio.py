"""Génère docs/architecture.drawio (architecture générale de Basira, format draw.io / diagrams.net).

Usage : uv run python tools/architecture_drawio.py docs/architecture.drawio
"""
import sys
import xml.etree.ElementTree as ET

SORTIE = sys.argv[1] if len(sys.argv) > 1 else "architecture.drawio"

racine = ET.Element("mxfile", host="Basira")
diag = ET.SubElement(racine, "diagram", id="basira-architecture", name="Architecture générale")
modele = ET.SubElement(diag, "mxGraphModel", grid="1", gridSize="10", guides="1", connect="1", arrows="1", page="1",
                       pageWidth="1500", pageHeight="620", background="#ffffff")
root = ET.SubElement(modele, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")
_n = [0]


def cellule(valeur, style, x, y, w, h, parent="1"):
    _n[0] += 1
    ident = f"c{_n[0]}"
    c = ET.SubElement(root, "mxCell", id=ident, value=valeur, style=style, vertex="1", parent=parent)
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})
    return ident


def cadre(titre, x, y, w, h):
    return cellule(titre, "rounded=1;arcSize=3;html=1;whiteSpace=wrap;fillColor=none;strokeColor=#9ca3af;dashed=1;"
                          "verticalAlign=top;align=left;spacingLeft=14;spacingTop=8;fontSize=13;fontStyle=1;fontColor=#6b7280;",
                   x, y, w, h)


def bloc(titre, detail, fond, contour, x, y, w=210, h=110, forme="rounded=1;arcSize=12;"):
    valeur = f"<b style=\"font-size:15px\">{titre}</b><br><span style=\"font-size:12px;color:#374151\">{detail}</span>"
    return cellule(valeur, f"{forme}whiteSpace=wrap;html=1;fillColor={fond};strokeColor={contour};strokeWidth=2;"
                           "fontColor=#111827;spacing=8;", x, y, w, h)


def fleche(src, tgt, libelle="", couleur="#374151", tirets=False, deux_sens=False, extra="", points=()):
    _n[0] += 1
    style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor={couleur};strokeWidth=2;fontSize=12;"
             f"fontColor={couleur};labelBackgroundColor=#ffffff;endArrow=block;endFill=1;"
             + ("dashed=1;" if tirets else "") + ("startArrow=block;startFill=1;" if deux_sens else "") + extra)
    e = ET.SubElement(root, "mxCell", id=f"e{_n[0]}", value=libelle, style=style, edge="1", parent="1", source=src, target=tgt)
    g = ET.SubElement(e, "mxGeometry", relative="1", attrib={"as": "geometry"})
    if points:
        arr = ET.SubElement(g, "Array", attrib={"as": "points"})
        for px, py in points:
            ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))


cellule("<b>Basira</b> — architecture générale", "text;html=1;fontSize=24;fontColor=#111827;align=left;", 40, 16, 700, 36)

cadre("Pipeline de données (calcul par lots, hors ligne)", 30, 80, 790, 240)
cadre("Application de l'inspecteur", 850, 80, 620, 480)

src = bloc("Sources de données", "Déclarations DGI · Douane SINDA<br>Paiements ADEB · Annexes employeur<br>Contrôles passés<br><i>(simulées)</i>",
           "#dae8fc", "#6c8ebf", 50, 150, 250, 130, forme="shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=12;")
sig = bloc("Moteur de signaux", "16 signaux explicables<br>cohérence · changement<br>pairs · réseau", "#d5e8d4", "#82b366", 330, 160)
sco = bloc("Score IA", "régression logistique<br>score explicable × enjeu<br>→ priorité des contrôles", "#ffe6cc", "#d79b00", 580, 160)
api = bloc("API", "FastAPI<br>scores · preuves · réseau<br>assistant + garde-fou", "#e1d5e7", "#9673a6", 880, 160)
web = bloc("Interface web", "portefeuille · fiche<br>graphe du réseau · copilote<br>décision", "#f8cecc", "#b85450", 1180, 160)
llm = bloc("LLM local", "Qwen 3.5 9B<br>aucune donnée ne sort", "#fff2cc", "#d6b656", 880, 410)
insp = cellule("<b style=\"font-size:14px\">Inspecteur</b><br><span style=\"font-size:12px\">décide</span>",
               "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor=#ffffff;"
               "strokeColor=#1f2937;strokeWidth=2;", 1267, 405, 36, 70)

fleche(src, sig)
fleche(sig, sco)
fleche(sco, api)
fleche(api, web, deux_sens=True)
fleche(api, llm, "questions · outils", couleur="#a16207", deux_sens=True)
fleche(web, insp, deux_sens=True)
fleche(web, sco, "décisions → réentraînement", couleur="#b45309", tirets=True,
       extra="exitX=0.5;exitY=0;entryX=0.5;entryY=0;", points=((1285, 128), (685, 128)))

ET.ElementTree(racine).write(SORTIE, encoding="utf-8", xml_declaration=False)
print("écrit", SORTIE)
