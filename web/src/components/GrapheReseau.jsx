// Graphe de réseau (D3 force) : l'entreprise au centre, ses contreparties, et les
// autres entreprises du portefeuille qui partagent ces contreparties.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as d3 from "d3";
import { entreprisesLiees } from "../lib/donnees.js";
import { fmtDT } from "../lib/format.js";

const H = 440;
const court = (t, n = 20) => (t.length > n ? `${t.slice(0, n - 1)}…` : t);

function construire(entreprise, L) {
  const noeuds = new Map();
  const liens = [];
  noeuds.set(entreprise.mf, { id: entreprise.mf, label: entreprise.company_name, genre: "centre", segment: entreprise.segment });
  for (const n of entreprise.network_nodes) {
    if (!noeuds.has(n.id)) noeuds.set(n.id, { id: n.id, label: n.label, genre: "contrepartie", type: n.type, signalee: n.risk_flag });
    liens.push({ source: entreprise.mf, target: n.id, niveau: 1 });
    // API : liens de niveau 2 calculés côté serveur (le portefeuille complet n'est pas chargé avec ses réseaux)
    const liees = entreprise.liens_portefeuille ? (entreprise.liens_portefeuille[n.id] ?? []) : entreprisesLiees(n.id, entreprise.mf);
    for (const autre of liees) {
      if (autre.mf === n.id) continue; // la contrepartie est elle-même une entreprise du portefeuille
      if (!noeuds.has(autre.mf)) noeuds.set(autre.mf, { id: autre.mf, label: autre.company_name, genre: "entreprise", segment: autre.segment });
      liens.push({ source: n.id, target: autre.mf, niveau: 2 });
    }
  }
  const tous = [...noeuds.values()];
  const centre = noeuds.get(entreprise.mf);
  centre.fx = L / 2; centre.fy = H / 2;
  d3.forceSimulation(tous)
    .force("lien", d3.forceLink(liens).id((d) => d.id).distance((l) => (l.niveau === 1 ? 130 : 85)).strength(0.9))
    .force("charge", d3.forceManyBody().strength(-620))
    // Rayon de collision : la largeur du libellé (centré sous le nœud) compte plus que le cercle
    .force("collision", d3.forceCollide((d) => Math.max(26, court(d.label).length * 3.4)).strength(1))
    .force("x", d3.forceX(L / 2).strength(0.03))
    .force("y", d3.forceY(H / 2).strength(0.12))
    .stop()
    .tick(320);
  for (const n of tous) { n.x = Math.max(80, Math.min(L - 80, n.x)); n.y = Math.max(24, Math.min(H - 40, n.y)); }
  return { noeuds: tous, liens };
}

export default function GrapheReseau({ entreprise, montants, contrepartiesFiltrees, onClicContrepartie, palette }) {
  const navigate = useNavigate();
  // palette : force le recalcul des couleurs lues dans les variables CSS
  // Mise en page calculée à la largeur réelle de la carte : les libellés gardent leur taille
  const conteneur = useRef(null);
  const [L, setL] = useState(640);
  useEffect(() => {
    const el = conteneur.current;
    const obs = new ResizeObserver(() => { const l = Math.round(el.clientWidth); if (l && Math.abs(l - L) > 20) setL(l); });
    obs.observe(el);
    return () => obs.disconnect();
  }, [L]);
  const { noeuds, liens } = useMemo(() => construire(entreprise, L), [entreprise, L]);
  const max = d3.max([...montants.values()]) || 1;
  const rayon = d3.scaleSqrt().domain([0, max]).range([5, 22]);
  const filtreActif = contrepartiesFiltrees.length > 0;

  const couleur = (n) => {
    if (n.genre !== "contrepartie") return `var(--seg-${{ PRIORITAIRE: "prio", SURVEILLANCE: "surv", NORMAL: "norm", CONFIANCE: "conf" }[n.segment]})`;
    return n.signalee ? "var(--seg-prio)" : "var(--carte)";
  };

  return (
    <div ref={conteneur} className="flex flex-col gap-2" data-palette={palette}>
      <svg viewBox={`0 0 ${L} ${H}`} role="img" aria-label={`Réseau de contreparties de ${entreprise.company_name}`} className="w-full">
        <g>
          {liens.map((l, i) => (
            <line key={i} x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
              stroke="var(--bordure)" strokeWidth={l.niveau === 1 ? 1.5 : 1} strokeDasharray={l.niveau === 2 ? "4 3" : undefined} />
          ))}
        </g>
        {noeuds.map((n) => {
          const montant = montants.get(n.id) ?? 0;
          const estContrepartie = n.genre === "contrepartie";
          const selectionnee = contrepartiesFiltrees.includes(n.label);
          const estompe = estContrepartie && (filtreActif ? !selectionnee : montant === 0);
          const r = n.genre === "centre" ? 18 : estContrepartie ? rayon(montant) : 9;
          const cliquable = n.genre !== "centre";
          const action = () => (estContrepartie ? onClicContrepartie(n.label) : navigate(`/entreprise/${n.id}`));
          return (
            <g
              key={n.id}
              transform={`translate(${n.x},${n.y})`}
              opacity={estompe ? 0.3 : 1}
              className={cliquable ? "cursor-pointer" : ""}
              onClick={cliquable ? action : undefined}
              onKeyDown={cliquable ? (e) => (e.key === "Enter" || e.key === " ") && action() : undefined}
              tabIndex={cliquable ? 0 : undefined}
              role={cliquable ? "button" : undefined}
            >
              <title>{`${n.label}${n.type ? ` · ${n.type}` : ""}${n.signalee ? " · signalée" : ""}${estContrepartie ? ` · ${fmtDT(montant)} dans la sélection` : ""}`}</title>
              <circle r={r + 8} fill="transparent" />
              <circle r={r} fill={couleur(n)}
                stroke={selectionnee ? "var(--encre)" : estContrepartie && !n.signalee ? "var(--attenue)" : "var(--carte)"}
                strokeWidth={selectionnee ? 2.5 : 1.5} />
              <text x={0} y={r + 13} textAnchor="middle" fontSize={n.genre === "centre" ? 12.5 : 11} fontWeight={n.genre === "centre" ? 700 : 500}
                fill="var(--encre)" stroke="var(--carte)" strokeWidth={3} paintOrder="stroke">
                {court(n.label)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-4 text-[12px] text-encre-2">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: "var(--seg-prio)" }} />Contrepartie signalée</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full border border-attenue bg-carte" />Contrepartie</span>
        <span className="inline-flex items-center gap-1.5"><svg width="22" height="6" aria-hidden="true"><line x1="0" y1="3" x2="22" y2="3" stroke="var(--attenue)" strokeDasharray="4 3" /></svg>Autre entreprise du portefeuille (couleur de son statut)</span>
      </div>
    </div>
  );
}
