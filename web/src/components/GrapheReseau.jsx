// Réseau de contreparties en flux d'argent (React Flow + dagre) : les payeurs à gauche, ceux qu'ils paient à droite.
// - Mise en page automatique en couches (dagre) : le réseau reste lisible quand on « déploie » des contreparties
//   (croisements minimisés, boucles gérées).
// - Mode focus : survoler ou choisir un nœud estompe le reste ; la chaîne qui le relie à l'entreprise étudiée est
//   animée dans le sens du paiement. Les montants ne s'affichent que sur les relations en focus quand le réseau est grand.
// - Filtre « Signalées » appliqué à tout le réseau, y compris les réseaux déployés.
// - Panneau d'explication compact en onglets (Pourquoi · Relation · Liens), motifs dépliables un par un.
import { memo, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import dagre from "@dagrejs/dagre";
import { Background, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import {
  Accordion, ActionIcon, Anchor, Avatar, Badge, Button, CloseButton, Group, Modal, Paper, ScrollArea, SegmentedControl,
  Stack, Tabs, Text, ThemeIcon, Tooltip, UnstyledButton
} from "@mantine/core";
import { AlertTriangle, ArrowRight, ArrowUpRight, Filter, GitBranchPlus, GitBranchMinus, History, Link2, Maximize2, Minimize2, Network, Scale, Sparkles } from "lucide-react";
import { chargerVoisins, entreprisesLiees, modeApi } from "../lib/donnees.js";
import { SEGMENTS } from "../lib/palettes.js";
import { COULEURS_SEGMENT } from "../lib/theme.js";
import { fmtCompact, fmtDate, fmtDT, fmtMoisIso } from "../lib/format.js";

const PAR_COTE = 6;           // contreparties visibles par côté avant regroupement
const L_CARTE = 236, H_CARTE = 58, L_CENTRE = 200;
const ENTRANTS = new Set(["Client", "Client (honoraires)", "Acheteur public", "Importateur"]);
const EST_MF = /^\d{7}[A-Z]{3}\d{3}$/;
const ROUGE = "#dc2626", GRIS = "#94a3b8", VIOLET = "#7c3aed";
const COURT = {
  "Achat · annexe V": "Achat", "Vente · annexe V": "Vente", "Paiement public": "Paiement public", "Honoraires reçus": "Honoraires",
  "Fournisseur étranger": "Import", "Fournisseur local": "Achat", Client: "Vente", "Acheteur public": "Paiement public"
};
const SOURCE_RELATION = {
  Import: "déclarations en douane (SINDA)", "Achat · annexe V": "annexe V de la déclaration employeur 2025",
  "Vente · annexe V": "annexe V des clients (exercice 2025)", Honoraires: "annexe II (honoraires, loyers)",
  "Honoraires reçus": "annexe II des clients", "Paiement public": "ordonnances de paiement ADEB"
};
const initiales = (nom) => nom.replace(/^(Société|Ste|Sté)\s+/i, "").split(/[\s-]+/).filter(Boolean).slice(0, 2).map((m) => m[0]).join("").toUpperCase();

// ---------------------------------------------------------------- nœuds
const CarteContrepartie = memo(function CarteContrepartie({ data }) {
  const n = data.n;
  const signalee = n.risk_flag;
  const badge = n.agregat ? null : n.coquille ? ["Coquille", ROUGE] : signalee ? ["Signalée", ROUGE] : n.nouvelle ? ["Nouvelle", "#b45309"] : null;
  const couleur = signalee ? ROUGE : n.segment ? COULEURS_SEGMENT[n.segment] : "#64748b";
  return (
    <div className={`flex items-center gap-2 rounded-xl border bg-white px-2.5 transition-all duration-200 ${data.selectionnee ? "ring-2 ring-[var(--mantine-color-basira-5)] ring-offset-1" : ""} ${n.agregat ? "border-dashed" : ""}`}
      style={{ width: L_CARTE, height: H_CARTE, borderColor: signalee ? "#fca5a5" : "var(--bordure)",
               boxShadow: `${data.deploye ? `inset 3px 0 0 ${VIOLET},` : ""} 0 1px 2px rgba(15,23,42,.06), 0 4px 12px -6px rgba(15,23,42,.14)`,
               opacity: data.estompe ? 0.22 : n.horsSelection && !n.agregat ? 0.6 : 1, cursor: "pointer" }}>
      <Handle id="tl" type="target" position={Position.Left} className="!opacity-0" />
      <Handle id="sl" type="source" position={Position.Left} className="!opacity-0" />
      <Handle id="tr" type="target" position={Position.Right} className="!opacity-0" />
      <Handle id="sr" type="source" position={Position.Right} className="!opacity-0" />
      {!n.agregat && (
        <span className="grid size-8 shrink-0 place-items-center rounded-lg text-[11px] font-bold" style={{ background: `${couleur}1a`, color: couleur }}>
          {signalee ? <AlertTriangle size={14} /> : initiales(n.label)}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-encre" title={n.label}>{n.label}</span>
          {badge && <Badge size="xs" variant="light" color={badge[1]} className="shrink-0">{badge[0]}</Badge>}
        </div>
        <div className="mt-0.5 flex items-center gap-1 text-[11px] text-attenue">
          <span className="chiffres font-semibold text-encre-2">{n.montant ? fmtCompact(n.montant) : "—"}</span>
          <span className="truncate">· {n.agregat ? "cliquer pour afficher" : n.type}</span>
        </div>
      </div>
    </div>
  );
});

const CarteEntreprise = memo(function CarteEntreprise({ data }) {
  const { e, nG, nD } = data;
  const couleur = COULEURS_SEGMENT[e.segment];
  const poignees = (n, type, pos, prefixe) => Array.from({ length: Math.max(1, n) }, (_, i) => (
    <Handle key={`${prefixe}${i}`} id={`${prefixe}${i}`} type={type} position={pos} className="!opacity-0"
      style={{ top: `${((i + 1) / (Math.max(1, n) + 1)) * 100}%` }} />
  ));
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border-2 bg-white px-3 text-center shadow-[0_10px_30px_-12px_rgba(15,23,42,.35)]"
      style={{ width: L_CENTRE, height: data.hauteur, borderColor: couleur }}>
      {poignees(nG, "target", Position.Left, "g")}
      {poignees(nD, "source", Position.Right, "d")}
      <span className="line-clamp-2 text-[13.5px] font-bold leading-tight text-encre">{e.company_name}</span>
      <span className="mt-1 text-[11.5px] text-attenue">score {e.current_risk_score}/100</span>
      <Badge mt={6} size="sm" variant="light" color={couleur}>{SEGMENTS[e.segment]?.libelle}</Badge>
    </div>
  );
});

const TYPES_NOEUDS = { contrepartie: CarteContrepartie, entreprise: CarteEntreprise };

// ---------------------------------------------------------------- données
function preparer(entreprise, montants) {
  const noeuds = entreprise.network_nodes.map((n) => {
    const selection = montants.get(n.id) ?? 0;
    return { ...n, sens: n.sens ?? (ENTRANTS.has(n.type) ? "entrant" : "sortant"), relation: n.relation ?? n.type,
             montant: selection || n.montant_dt || 0, horsSelection: !selection };
  });
  const tri = (a, b) => (b.risk_flag - a.risk_flag) || (a.horsSelection - b.horsSelection) || (b.montant - a.montant);
  return { gauche: noeuds.filter((n) => n.sens === "entrant").sort(tri), droite: noeuds.filter((n) => n.sens === "sortant").sort(tri) };
}

function regrouper(liste, cote, tout) {
  if (tout || liste.length <= PAR_COTE + 1) return liste;
  const reste = liste.slice(PAR_COTE);
  return [...liste.slice(0, PAR_COTE), {
    id: `__autres_${cote}`, agregat: true, label: `+ ${reste.length} autres contreparties`, type: "", relation: "Autres",
    montant: reste.reduce((s, n) => s + n.montant, 0), sens: cote === "gauche" ? "entrant" : "sortant", risk_flag: false
  }];
}

// Structure du réseau (nœuds, relations) puis positions calculées par dagre, de gauche à droite dans le sens du paiement.
// `signaleesSeules` : le filtre « Signalées » s'applique aussi aux réseaux déployés (on garde les nœuds déployés
// eux-mêmes, sinon la chaîne serait coupée).
function construire(entreprise, G, D, deployes, signaleesSeules) {
  const noeuds = new Map();
  const aretes = [];
  const vues = new Set();
  const ajouterArete = (src, tgt, n, base) => {
    const cle = [src, tgt].sort().join("|");
    if (vues.has(cle)) return;
    vues.add(cle);
    aretes.push({ id: `${base ? "e" : "d"}-${src}-${tgt}`, src, tgt, n, base });
  };
  [...G, ...D].forEach((n) => {
    noeuds.set(n.id, { n, parent: "__centre" });
    ajouterArete(n.sens === "entrant" ? n.id : "__centre", n.sens === "entrant" ? "__centre" : n.id, n, true);
  });
  for (const [pid, dep] of deployes) {
    if (!noeuds.has(pid)) continue;
    for (const brut of dep.noeuds) {
      if (brut.id === entreprise.mf) continue; // l'entreprise étudiée est déjà au centre
      if (signaleesSeules && !brut.risk_flag && !deployes.has(brut.id) && !noeuds.has(brut.id)) continue;
      const n = { ...brut, montant: brut.montant_dt || 0, horsSelection: false, parentId: pid, parentNom: dep.nom };
      if (!noeuds.has(n.id)) noeuds.set(n.id, { n, parent: pid });
      const existant = noeuds.get(n.id).n;
      ajouterArete(n.sens === "sortant" ? pid : n.id, n.sens === "sortant" ? n.id : pid, { ...n, risk_flag: existant.risk_flag || n.risk_flag }, false);
    }
  }
  const hCentre = Math.max(110, 40 + Math.max(G.length, D.length) * 12);
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: 150, nodesep: 14, edgesep: 10, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));
  g.setNode("__centre", { width: L_CENTRE, height: hCentre });
  for (const id of noeuds.keys()) g.setNode(id, { width: L_CARTE, height: H_CARTE });
  for (const a of aretes) g.setEdge(a.src, a.tgt, { weight: a.base ? 3 : 1 });
  dagre.layout(g);
  const pos = new Map(g.nodes().map((id) => { const p = g.node(id); return [id, { x: p.x - p.width / 2, y: p.y - p.height / 2, cy: p.y }]; }));
  return { noeuds, aretes, pos, hCentre };
}

// ---------------------------------------------------------------- panneau d'explication (compact, en onglets)
const RAISON = /^(.+?) \(\+(\d+) pts\) : (.+)$/;

function Motif({ n }) {
  const details = n.motif_detail?.details ?? [];
  const raisons = details.filter((d) => RAISON.test(d)).map((d) => d.match(RAISON));
  const action = details.find((d) => d.startsWith("Action suggérée"));
  const puces = details.filter((d) => !RAISON.test(d) && !d.startsWith("Action suggérée"));
  return (
    <Stack gap={8}>
      <Group gap={8} wrap="nowrap" align="flex-start">
        <ThemeIcon color="red" variant="light" size={26} radius="md"><AlertTriangle size={14} /></ThemeIcon>
        <Text size="sm" fw={700} c="red.8" lh={1.35}>{n.motif_detail?.titre ?? n.motif}</Text>
      </Group>
      {raisons.length > 0 && (
        <Accordion variant="separated" radius="md" chevronPosition="right"
          styles={{ control: { padding: "2px 10px" }, content: { padding: "0 10px 10px" }, label: { padding: "6px 0" }, item: { background: "var(--fond)" } }}>
          {raisons.map(([, titre, points, texte]) => (
            <Accordion.Item key={titre} value={titre}>
              <Accordion.Control>
                <Group justify="space-between" wrap="nowrap" gap={6}>
                  <Text size="xs" fw={600} truncate>{titre}</Text>
                  <Badge size="xs" variant="light" color="red" className="shrink-0">+{points} pts</Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel><Text size="xs" c="dimmed" lh={1.5}>{texte}</Text></Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
      {puces.length > 0 && (
        <Stack gap={6}>
          {puces.map((d, i) => (
            <Group key={i} gap={8} wrap="nowrap" align="flex-start">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[#dc2626]" />
              <Text size="xs" c="dimmed" lh={1.45}>{d}</Text>
            </Group>
          ))}
        </Stack>
      )}
      {action && (
        <Badge variant="light" color="ardoise" size="md" radius="sm" className="self-start" fw={500} styles={{ root: { textTransform: "none" } }}>
          {action.replace("Action suggérée par Basira pour cette entreprise : ", "Action suggérée : ").replace(/\.$/, "")}
        </Badge>
      )}
    </Stack>
  );
}

function Explication({ n, entreprise, deploye, chargement, onFermer, onFiltrer, onDeployer }) {
  const navigate = useNavigate();
  const nom = n.parentNom ?? entreprise.company_name;
  const liees = (n.liees ?? (entreprise.liens_portefeuille ? entreprise.liens_portefeuille[n.id] ?? [] : entreprisesLiees(n.id, entreprise.mf)))
    .filter((o) => o.mf !== n.id);
  const nbLiees = n.nb_liees ?? liees.length;
  const couleur = n.risk_flag ? ROUGE : n.segment ? COULEURS_SEGMENT[n.segment] : "#64748b";
  const payeur = n.sens === "sortant" ? nom : n.label, paye = n.sens === "sortant" ? n.label : nom;
  return (
    <Paper withBorder radius="lg" className="overflow-hidden !bg-white">
      <div className="border-b border-bordure p-3" style={{ background: `linear-gradient(135deg, ${couleur}14, transparent 70%)` }}>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap={10} wrap="nowrap" className="min-w-0">
            <Avatar radius="md" size={38} style={{ background: `${couleur}1f`, color: couleur }} className="font-bold">{initiales(n.label)}</Avatar>
            <div className="min-w-0">
              <Text fw={700} size="sm" lh={1.25} lineClamp={2}>{n.label}</Text>
              <Text size="xs" c="dimmed" truncate>{n.type}{n.parentId ? ` · via ${n.parentNom}` : ""}</Text>
            </div>
          </Group>
          <CloseButton size="sm" onClick={onFermer} aria-label="Fermer l'explication" />
        </Group>
        <Group gap={6} mt={10} wrap="wrap">
          {modeApi && (
            <Button size="compact-sm" color="violet" variant={deploye ? "light" : "filled"} loading={chargement}
              leftSection={deploye ? <GitBranchMinus size={14} /> : <GitBranchPlus size={14} />} onClick={() => onDeployer(n)}>
              {deploye ? "Replier" : "Déployer son réseau"}
            </Button>
          )}
          {!n.parentId && (
            <Tooltip label="Filtrer les opérations sur cette contrepartie">
              <ActionIcon variant="default" size="md" onClick={() => onFiltrer(n.label)} aria-label="Filtrer les opérations"><Filter size={14} /></ActionIcon>
            </Tooltip>
          )}
          {EST_MF.test(n.id) && (
            <Tooltip label="Ouvrir la fiche">
              <ActionIcon variant="default" size="md" onClick={() => navigate(`/entreprise/${n.id}`)} aria-label="Ouvrir la fiche"><ArrowUpRight size={14} /></ActionIcon>
            </Tooltip>
          )}
        </Group>
      </div>
      <Tabs defaultValue={n.motif ? "pourquoi" : "relation"} key={n.id}>
        <Tabs.List grow>
          <Tabs.Tab value="pourquoi" leftSection={<Sparkles size={13} />} disabled={!n.motif}>Pourquoi</Tabs.Tab>
          <Tabs.Tab value="relation" leftSection={<Scale size={13} />}>Relation</Tabs.Tab>
          <Tabs.Tab value="liens" leftSection={<Link2 size={13} />} disabled={!liees.length}>Liens{nbLiees ? ` (${nbLiees})` : ""}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="pourquoi" p="sm">{n.motif && <Motif n={n} />}</Tabs.Panel>
        <Tabs.Panel value="relation" p="sm">
          <Stack gap={10}>
            <Group gap={8} wrap="nowrap" align="center" className="rounded-lg bg-fond p-2.5">
              <Text size="xs" fw={600} className="min-w-0 flex-1 text-right" lineClamp={2}>{payeur}</Text>
              <Stack gap={0} align="center" className="shrink-0">
                <Text size="sm" fw={800} className="chiffres">{fmtCompact(n.montant)}</Text>
                <ArrowRight size={16} color={n.risk_flag ? ROUGE : GRIS} />
              </Stack>
              <Text size="xs" fw={600} className="min-w-0 flex-1" lineClamp={2}>{paye}</Text>
            </Group>
            <Text size="xs" c="dimmed" lh={1.5}>
              {n.relation} · {fmtDT(n.montant)} {n.parentId ? "sur 12 mois" : n.horsSelection ? "(cumul de la relation)" : "sur la période affichée"}.<br />
              Source : {SOURCE_RELATION[n.relation] ?? "graphe des relations"}{n.depuis ? ` · depuis le ${fmtDate(n.depuis)}` : ""}{n.nouvelle ? " · relation nouvelle" : ""}.
            </Text>
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="liens" p="sm">
          <Text size="xs" c="dimmed" mb={6}>{nbLiees} entreprise{nbLiees > 1 ? "s" : ""} du portefeuille en relation avec {n.label}{liees.length < nbLiees ? ` (${liees.length} affichées)` : ""} :</Text>
          <Stack gap={2}>
            {liees.map((o) => (
              <UnstyledButton key={o.mf} onClick={() => navigate(`/entreprise/${o.mf}`)} className="rounded-md px-2 py-1.5 hover:bg-fond-2">
                <Group gap={8} wrap="nowrap">
                  <span className="size-2 shrink-0 rounded-full" style={{ background: COULEURS_SEGMENT[o.segment] }} />
                  <Text size="xs" fw={500} truncate className="flex-1">{o.company_name}</Text>
                  <ArrowUpRight size={12} className="shrink-0 text-attenue" />
                </Group>
              </UnstyledButton>
            ))}
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Paper>
  );
}

// ---------------------------------------------------------------- graphe
function Graphe({ entreprise, montants, contrepartiesFiltrees, etat, plein, onFiltrer, onPleinEcran }) {
  const { tout, setTout, vue, setVue, choisi, setChoisi, deployes, deployer, chargement } = etat;
  const [survol, setSurvol] = useState(null);
  const { fitView } = useReactFlow();

  const { gauche, droite } = useMemo(() => preparer(entreprise, montants), [entreprise, montants]);
  const signaleesSeules = vue === "signalees";
  // le filtre garde aussi les contreparties déployées (on ne coupe pas une chaîne que l'inspecteur suit)
  const filtre = (l) => (signaleesSeules ? l.filter((n) => n.risk_flag || deployes.has(n.id)) : l);
  const G = regrouper(filtre(gauche), "gauche", tout.gauche);
  const D = regrouper(filtre(droite), "droite", tout.droite);

  // 1. structure et positions (recalculées seulement si le réseau change)
  const plan = useMemo(() => construire(entreprise, G, D, deployes, signaleesSeules),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [entreprise, montants, vue, tout, deployes, G.length, D.length]);
  const max = Math.max(1, ...plan.aretes.map((a) => a.n.montant || 0));

  // 2. focus : nœud survolé ou choisi, ses voisins, et la chaîne qui le relie à l'entreprise étudiée
  const focus = survol ?? choisi;
  const { enFocus, chaine } = useMemo(() => {
    if (!focus || !plan.noeuds.has(focus)) return { enFocus: null, chaine: new Set() };
    const enFocus = new Set([focus, "__centre"]);
    plan.aretes.forEach((a) => { if (a.src === focus || a.tgt === focus) { enFocus.add(a.src); enFocus.add(a.tgt); } });
    const chaine = new Set();
    let id = focus;
    while (id && id !== "__centre") {
      const parent = plan.noeuds.get(id)?.parent;
      if (!parent) break;
      chaine.add([id, parent].sort().join("|"));
      enFocus.add(parent);
      id = parent;
    }
    return { enFocus, chaine };
  }, [focus, plan]);

  // 3. rendu React Flow
  const { nodes, edges } = useMemo(() => {
    const { noeuds, aretes, pos, hCentre } = plan;
    const versCentre = aretes.filter((a) => a.tgt === "__centre").sort((a, b) => pos.get(a.src).cy - pos.get(b.src).cy);
    const duCentre = aretes.filter((a) => a.src === "__centre").sort((a, b) => pos.get(a.tgt).cy - pos.get(b.tgt).cy);
    const poignee = new Map([...versCentre.map((a, i) => [a.id, `g${i}`]), ...duCentre.map((a, i) => [a.id, `d${i}`])]);
    const nodes = [{ id: "__centre", type: "entreprise", position: pos.get("__centre"), draggable: false,
                     data: { e: entreprise, nG: versCentre.length, nD: duCentre.length, hauteur: hCentre } }];
    for (const [id, { n }] of noeuds) {
      nodes.push({ id, type: "contrepartie", position: pos.get(id), draggable: false,
                   data: { n, selectionnee: choisi === id || contrepartiesFiltrees.includes(n.label), deploye: deployes.has(id), estompe: !!enFocus && !enFocus.has(id) } });
    }
    const grand = deployes.size > 0 || aretes.length > 16;
    const edges = aretes.map((a) => {
      const n = a.n;
      const cle = [a.src, a.tgt].sort().join("|");
      const dansFocus = enFocus ? (a.src === focus || a.tgt === focus || chaine.has(cle)) : null;
      const couleur = n.risk_flag ? ROUGE : GRIS;
      const xs = pos.get(a.src).x, xt = pos.get(a.tgt).x;
      const sourceHandle = a.src === "__centre" ? poignee.get(a.id) : xs <= xt ? "sr" : "sl";
      const targetHandle = a.tgt === "__centre" ? poignee.get(a.id) : xs <= xt ? "tl" : "tr";
      const libelle = `${COURT[n.relation] ?? n.relation}${n.montant ? ` · ${fmtCompact(n.montant)}` : ""}`;
      return {
        id: a.id, source: a.src, target: a.tgt, sourceHandle, targetHandle,
        label: dansFocus || (!enFocus && !grand) ? libelle : undefined,
        animated: !!(dansFocus && chaine.has(cle)),
        markerEnd: { type: MarkerType.ArrowClosed, color: couleur, width: 15, height: 15 },
        style: { stroke: couleur, strokeWidth: (1.3 + 3.4 * Math.sqrt(Math.min(1, (n.montant || 0) / max))) * (dansFocus ? 1.25 : 1),
                 strokeDasharray: n.nouvelle && !chaine.has(cle) ? "6 4" : undefined,
                 opacity: enFocus ? (dansFocus ? 1 : 0.06) : n.horsSelection && !n.agregat ? 0.45 : grand ? 0.55 : 0.9,
                 transition: "opacity .2s" },
        labelStyle: { fontSize: 11, fontWeight: 600, fill: n.risk_flag ? ROUGE : "#334155" },
        labelBgStyle: { fill: "#fff", stroke: n.risk_flag ? "#fecaca" : "#e2e8f0" }, labelBgPadding: [6, 3], labelBgBorderRadius: 6
      };
    });
    return { nodes, edges };
  }, [plan, choisi, contrepartiesFiltrees, deployes, enFocus, chaine, focus, max, entreprise]);

  useEffect(() => { const t = setTimeout(() => fitView({ padding: 0.06, duration: 300 }), 40); return () => clearTimeout(t); }, [plan, fitView, plein]);

  const noeudChoisi = plan.noeuds.get(choisi)?.n ?? [...gauche, ...droite].find((n) => n.id === choisi);
  const tousNoeuds = [...gauche, ...droite];
  const tousSignales = [...plan.noeuds.values()].map((p) => p.n).filter((n) => n.risk_flag).sort((a, b) => b.montant - a.montant);
  const clic = (_, nd) => {
    if (nd.id === "__centre") { setChoisi(null); return; }
    const n = nd.data.n;
    if (n.agregat) setTout((t) => ({ ...t, [n.sens === "entrant" ? "gauche" : "droite"]: true }));
    else setChoisi((c) => (c === n.id ? null : n.id));
  };

  const somme = (l) => l.reduce((s, n) => s + n.montant, 0);
  const signalees = droite.filter((n) => n.risk_flag);
  const r = entreprise.reseau_resume;
  const lignes = Math.max(G.length, D.length, 1);
  const hauteurCanvas = plein ? "calc(100vh - 150px)" : Math.min(640, Math.max(440, lignes * 66 + 60));
  if (!tousNoeuds.length) return <Text c="dimmed" size="sm" ta="center" py="xl">Aucune contrepartie sur la période.</Text>;

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Text size="sm" lh={1.5} className="max-w-[760px]">
          {r ? `Du ${fmtMoisIso(r.debut)} au ${fmtMoisIso(r.fin)}, ` : ""}
          <b>{gauche.length} client{gauche.length > 1 ? "s" : ""}</b> ont payé <b>{fmtCompact(somme(gauche))}</b> à l'entreprise ; elle a payé{" "}
          <b>{fmtCompact(somme(droite))}</b> à <b>{droite.length} fournisseur{droite.length > 1 ? "s" : ""}</b>
          {signalees.length > 0 && <>, dont <Text span c="red.7" fw={700}>{fmtCompact(somme(signalees))} ({Math.round((100 * somme(signalees)) / Math.max(1, somme(droite)))} %) à {signalees.length} contrepartie{signalees.length > 1 ? "s" : ""} signalée{signalees.length > 1 ? "s" : ""}</Text></>}.
          {deployes.size > 0 && <Text span c="violet.7" fw={600}> · {deployes.size} réseau{deployes.size > 1 ? "x" : ""} déployé{deployes.size > 1 ? "s" : ""}</Text>}
        </Text>
        <Group gap={6} wrap="nowrap">
          <SegmentedControl size="xs" value={vue} onChange={setVue} data={[{ value: "toutes", label: "Toutes" }, { value: "signalees", label: "Signalées" }]} />
          <Tooltip label={plein ? "Quitter le plein écran" : "Plein écran"}>
            <ActionIcon variant="default" size="md" onClick={onPleinEcran} aria-label={plein ? "Quitter le plein écran" : "Afficher le réseau en plein écran"}>
              {plein ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <div className={`grid gap-3 ${plein ? "grid-cols-[minmax(0,1fr)_380px]" : "@4xl:grid-cols-[minmax(0,1fr)_330px]"}`}>
        <div style={{ height: hauteurCanvas }} className="relative overflow-hidden rounded-xl border border-bordure bg-[radial-gradient(circle_at_50%_40%,#ffffff,#f1f5f9)]">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={TYPES_NOEUDS} onNodeClick={clic} onPaneClick={() => setChoisi(null)}
            onNodeMouseEnter={(_, nd) => nd.id !== "__centre" && setSurvol(nd.id)} onNodeMouseLeave={() => setSurvol(null)}
            fitView fitViewOptions={{ padding: 0.06 }} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
            zoomOnScroll={plein} zoomOnDoubleClick={false} preventScrolling={plein} minZoom={0.15} maxZoom={1.8} proOptions={{ hideAttribution: true }}>
            <Background gap={20} size={1} color="#dbe2ea" />
            <Controls showInteractive={false} position="bottom-right" />
            <Panel position="top-left"><Badge variant="white" color="ardoise" size="sm" leftSection={<ArrowRight size={11} />} styles={{ root: { textTransform: "none" } }}>payeurs à gauche · payés à droite</Badge></Panel>
            {deployes.size > 0 && !focus && (
              <Panel position="bottom-center"><Badge variant="light" color="violet" size="sm" styles={{ root: { textTransform: "none" } }}>Survolez un nœud pour isoler ses relations</Badge></Panel>
            )}
          </ReactFlow>
        </div>

        {/* Colonne d'explication : hors du canevas, jamais rognée */}
        <ScrollArea.Autosize mah={plein ? "calc(100vh - 150px)" : Math.max(Number(hauteurCanvas) || 440, 460)} type="auto" offsetScrollbars>
          {noeudChoisi ? (
            <Explication n={noeudChoisi} entreprise={entreprise} deploye={deployes.has(noeudChoisi.id)} chargement={chargement === noeudChoisi.id}
              onFermer={() => setChoisi(null)} onFiltrer={onFiltrer} onDeployer={deployer} />
          ) : (
            <Paper withBorder p="md" radius="lg" className="!bg-white">
              <Group gap={8} mb={4}><ThemeIcon size={24} radius="md" variant="light" color="red"><AlertTriangle size={13} /></ThemeIcon>
                <Text fw={700} size="sm">{tousSignales.length ? `${tousSignales.length} contrepartie${tousSignales.length > 1 ? "s" : ""} signalée${tousSignales.length > 1 ? "s" : ""}` : "Aucune contrepartie signalée"}</Text></Group>
              <Text size="xs" c="dimmed" mb="sm">Choisissez-en une pour lire le motif et déployer son réseau.</Text>
              <Stack gap={6}>
                {tousSignales.map((n) => (
                  <UnstyledButton key={n.id} onClick={() => setChoisi(n.id)} onMouseEnter={() => setSurvol(n.id)} onMouseLeave={() => setSurvol(null)}
                    className="rounded-lg border border-[#fecaca] bg-[#fff7f7] px-3 py-2 transition-colors hover:border-[#dc2626]">
                    <Group gap={6} wrap="nowrap" justify="space-between">
                      <Text size="sm" fw={600} truncate>{n.label}</Text>
                      <Text size="xs" fw={700} className="chiffres shrink-0">{fmtCompact(n.montant)}</Text>
                    </Group>
                    <Text size="xs" c="red.8" lh={1.35} mt={2} lineClamp={1}>{n.motif_detail?.titre ?? n.motif}</Text>
                    {n.parentNom && <Text size="xs" c="violet.7" mt={2} truncate>via {n.parentNom}</Text>}
                  </UnstyledButton>
                ))}
              </Stack>
            </Paper>
          )}
        </ScrollArea.Autosize>
      </div>

      <Group gap="lg" wrap="wrap">
        <Group gap={6}><ArrowRight size={14} className="text-attenue" /><Text size="xs" c="dimmed">flèche = sens du paiement, épaisseur = montant</Text></Group>
        <Group gap={6}><ThemeIcon size={14} radius="xl" color="red" variant="light"><AlertTriangle size={9} /></ThemeIcon><Text size="xs" c="dimmed">contrepartie signalée</Text></Group>
        <Group gap={6}><span className="h-3 w-1 rounded bg-[#7c3aed]" /><Text size="xs" c="dimmed">réseau déployé</Text></Group>
        <Group gap={6}><svg width="22" height="6" aria-hidden="true"><line x1="0" y1="3" x2="22" y2="3" stroke={GRIS} strokeWidth="2" strokeDasharray="6 4" /></svg><Text size="xs" c="dimmed">relation de moins de 18 mois</Text></Group>
        {r && (
          <Tooltip label={`Sources : ${r.sources}`}>
            <Group gap={6} className="cursor-help"><History size={13} className="text-attenue" />
              <Text size="xs" c="dimmed">
                {r.relations_affichees} relation{r.relations_affichees > 1 ? "s" : ""} active{r.relations_affichees > 1 ? "s" : ""} sur 12 mois
                {r.relations_anciennes > 0 && ` · ${r.relations_anciennes} plus ancienne${r.relations_anciennes > 1 ? "s" : ""} (arrêtée${r.relations_anciennes > 1 ? "s" : ""} avant ${fmtMoisIso(r.debut)}) non affichée${r.relations_anciennes > 1 ? "s" : ""}`}
              </Text>
            </Group>
          </Tooltip>
        )}
        {(tout.gauche || tout.droite) && <Anchor size="xs" onClick={() => setTout({ gauche: false, droite: false })}>Regrouper les petites contreparties</Anchor>}
      </Group>
    </Stack>
  );
}

// État partagé entre la vue intégrée et le plein écran (sélection, réseaux déployés, filtres du graphe)
export default function GrapheReseau({ entreprise, montants, contrepartiesFiltrees, onClicContrepartie }) {
  const [tout, setTout] = useState({ gauche: false, droite: false });
  const [vue, setVue] = useState("toutes");
  const [choisi, setChoisi] = useState(null);
  const [deployes, setDeployes] = useState(new Map());
  const [chargement, setChargement] = useState(null);
  const [plein, setPlein] = useState(false);
  useEffect(() => { setTout({ gauche: false, droite: false }); setChoisi(null); setVue("toutes"); setDeployes(new Map()); setPlein(false); }, [entreprise.mf]);

  const deployer = (n) => {
    if (deployes.has(n.id)) {
      // replier ce réseau et ceux déployés à partir de ses nœuds
      setDeployes((m) => {
        const suivant = new Map(m);
        const retirer = (id) => { const d = suivant.get(id); suivant.delete(id); d?.noeuds.forEach((x) => suivant.has(x.id) && x.id !== id && retirer(x.id)); };
        retirer(n.id);
        return suivant;
      });
      return;
    }
    setChargement(n.id);
    chargerVoisins(n.id)
      .then((v) => { setDeployes((m) => new Map(m).set(n.id, { nom: v.nom, noeuds: v.noeuds, total: v.total })); setPlein(true); }) // un réseau déployé se lit en plein écran
      .finally(() => setChargement(null));
  };
  const filtrer = (libelle) => {
    onClicContrepartie(libelle);
    setPlein(false);
    setTimeout(() => document.getElementById("operations")?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
  };
  const etat = { tout, setTout, vue, setVue, choisi, setChoisi, deployes, deployer, chargement };
  const props = { entreprise, montants, contrepartiesFiltrees, etat, onFiltrer: filtrer };

  return (
    <>
      {plein ? (
        <Paper withBorder p="xl" radius="lg" className="text-center">
          <Network size={20} className="mx-auto text-attenue" />
          <Text size="sm" c="dimmed" mt={6}>Réseau affiché en plein écran.</Text>
          <Button variant="light" size="xs" mt="sm" onClick={() => setPlein(false)}>Revenir ici</Button>
        </Paper>
      ) : (
        <ReactFlowProvider><Graphe {...props} plein={false} onPleinEcran={() => setPlein(true)} /></ReactFlowProvider>
      )}
      <Modal opened={plein} onClose={() => setPlein(false)} fullScreen
        title={<Group gap={8}><ThemeIcon variant="light" size={28} radius="md"><Network size={15} /></ThemeIcon><Text fw={700}>Réseau de contreparties · {entreprise.company_name}</Text></Group>}
        transitionProps={{ transition: "fade", duration: 150 }}>
        {plein && <ReactFlowProvider><Graphe {...props} plein onPleinEcran={() => setPlein(false)} /></ReactFlowProvider>}
      </Modal>
    </>
  );
}
