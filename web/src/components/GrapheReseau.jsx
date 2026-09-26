// Réseau de contreparties en flux d'argent (React Flow) : qui paie l'entreprise (à gauche) → l'entreprise → qui elle
// paie (à droite). Chaque flèche suit le paiement et porte la relation et le montant ; une phrase résume le réseau ;
// un clic sur une contrepartie ouvre son explication (relation, motif détaillé, entreprises liées).
// « Déployer son réseau » ajoute les contreparties d'une contrepartie (signalées d'abord) : on remonte une chaîne
// (client → fournisseur coquille → autres clients de la coquille…) ; une relation vers un nœud déjà affiché crée une
// flèche vers lui, ce qui fait apparaître les boucles d'un réseau. Mode plein écran pour les grands réseaux.
import { memo, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Background, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import {
  ActionIcon, Alert, Anchor, Badge, Button, CloseButton, Group, List, Modal, Paper, ScrollArea, SegmentedControl, Stack, Text,
  ThemeIcon, Tooltip, UnstyledButton
} from "@mantine/core";
import { AlertTriangle, ArrowRight, ArrowUpRight, Filter, GitBranchPlus, History, Maximize2, Minimize2, Network } from "lucide-react";
import { chargerVoisins, entreprisesLiees, modeApi } from "../lib/donnees.js";
import { SEGMENTS } from "../lib/palettes.js";
import { COULEURS_SEGMENT } from "../lib/theme.js";
import { fmtCompact, fmtDate, fmtDT, fmtMoisIso } from "../lib/format.js";

const PAR_COTE = 6;           // contreparties visibles par côté avant regroupement
const L_CARTE = 230, H_CARTE = 58, PAS = 74, X_CENTRE = 400, L_CENTRE = 190, X_DROITE = 800, DX_DEPLOIEMENT = 440;
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

// ---------------------------------------------------------------- nœuds
const CarteContrepartie = memo(function CarteContrepartie({ data }) {
  const n = data.n;
  const signalee = n.risk_flag;
  const badge = n.agregat ? null : n.coquille ? ["Coquille", ROUGE] : signalee ? ["Signalée", ROUGE] : n.nouvelle ? ["Nouvelle", "#b45309"] : null;
  return (
    <div className={`rounded-lg border bg-white px-3 py-2 shadow-sm ${data.selectionnee ? "ring-2 ring-[var(--mantine-color-basira-5)]" : ""} ${n.agregat ? "border-dashed" : ""}`}
      style={{ width: L_CARTE, height: H_CARTE, borderColor: signalee ? ROUGE : "var(--bordure)", borderLeft: data.deploye ? `4px solid ${VIOLET}` : undefined,
               opacity: n.horsSelection && !n.agregat ? 0.55 : 1, cursor: "pointer" }}>
      {/* poignées des deux côtés : un nœud déployé peut être relié vers l'extérieur comme vers l'intérieur */}
      <Handle id="tl" type="target" position={Position.Left} className="!opacity-0" />
      <Handle id="sl" type="source" position={Position.Left} className="!opacity-0" />
      <Handle id="tr" type="target" position={Position.Right} className="!opacity-0" />
      <Handle id="sr" type="source" position={Position.Right} className="!opacity-0" />
      <div className="flex items-center gap-1.5">
        {signalee && <AlertTriangle size={13} color={ROUGE} className="shrink-0" />}
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-encre" title={n.label}>{n.label}</span>
        {badge && <Badge size="xs" variant="light" color={badge[1]} className="shrink-0">{badge[0]}</Badge>}
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[11.5px] text-attenue">
        <span className="chiffres font-semibold text-encre-2">{n.montant ? fmtCompact(n.montant) : "—"}</span>
        {!n.agregat && <span className="truncate">· {n.type}</span>}
        {n.agregat && <span>· cliquer pour afficher</span>}
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
    <div className="flex flex-col items-center justify-center rounded-xl border-2 bg-white px-3 text-center shadow-md" style={{ width: L_CENTRE, height: data.hauteur, borderColor: couleur }}>
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

const arete = (id, source, target, n, sourceHandle, targetHandle, max) => {
  const couleur = n.risk_flag ? ROUGE : GRIS;
  const libelle = `${COURT[n.relation] ?? n.relation}${n.montant ? ` · ${fmtCompact(n.montant)}` : ""}`;
  return {
    id, source, target, sourceHandle, targetHandle, label: libelle,
    markerEnd: { type: MarkerType.ArrowClosed, color: couleur, width: 16, height: 16 },
    style: { stroke: couleur, strokeWidth: 1.4 + 3.6 * Math.sqrt(Math.min(1, n.montant / max)), strokeDasharray: n.nouvelle ? "6 4" : undefined,
             opacity: n.horsSelection && !n.agregat ? 0.45 : 0.9 },
    labelStyle: { fontSize: 11, fontWeight: 600, fill: n.risk_flag ? ROUGE : "#334155" },
    labelBgStyle: { fill: "#fff", stroke: n.risk_flag ? "#fecaca" : "#e2e8f0" }, labelBgPadding: [6, 3], labelBgBorderRadius: 6
  };
};

// ---------------------------------------------------------------- panneau d'explication
function Explication({ n, entreprise, deploye, chargement, onFermer, onFiltrer, onDeployer }) {
  const navigate = useNavigate();
  const nom = n.parentNom ?? entreprise.company_name;
  const phrase = n.sens === "sortant"
    ? <><b>{nom}</b> a payé <b>{fmtDT(n.montant)}</b> à <b>{n.label}</b></>
    : <><b>{n.label}</b> a payé <b>{fmtDT(n.montant)}</b> à <b>{nom}</b></>;
  const liees = (n.liees ?? (entreprise.liens_portefeuille ? entreprise.liens_portefeuille[n.id] ?? [] : entreprisesLiees(n.id, entreprise.mf)))
    .filter((o) => o.mf !== n.id);
  const periode = n.parentId ? " sur 12 mois" : n.horsSelection ? " (cumul de la relation)" : " sur la période affichée";
  return (
    <Paper withBorder p="md" radius="lg" className="!bg-white">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb={6}>
        <div className="min-w-0">
          <Text fw={700} size="sm" lh={1.3}>{n.label}</Text>
          <Text size="xs" c="dimmed">{n.type} · {n.relation}{n.parentId ? ` · réseau de ${n.parentNom}` : ""}</Text>
        </div>
        <CloseButton size="sm" onClick={onFermer} aria-label="Fermer l'explication" />
      </Group>
      <Stack gap={8}>
        <Text size="sm" lh={1.45}>{phrase}{periode}.</Text>
        <Text size="xs" c="dimmed">Source : {SOURCE_RELATION[n.relation] ?? "graphe des relations"}{n.depuis ? ` · relation depuis le ${fmtDate(n.depuis)}` : ""}{n.nouvelle ? " (nouvelle)" : ""}</Text>
        {n.motif && (
          <Alert color="red" variant="light" p="sm" icon={<AlertTriangle size={16} />} title={n.motif_detail?.titre ?? n.motif}>
            {n.motif_detail?.details?.length > 0 && (
              <List size="xs" spacing={6} mt={4} className="text-encre-2">
                {n.motif_detail.details.map((d, i) => <List.Item key={i}>{d}</List.Item>)}
              </List>
            )}
          </Alert>
        )}
        {liees.length > 0 && (
          <div>
            <Text size="xs" fw={600} c="dimmed" mb={4}>Aussi en relation avec {n.nb_liees ?? liees.length} entreprise{(n.nb_liees ?? liees.length) > 1 ? "s" : ""} du portefeuille :</Text>
            <Group gap={4}>
              {liees.map((o) => (
                <Badge key={o.mf} variant="outline" color={COULEURS_SEGMENT[o.segment]} size="sm" className="cursor-pointer" maw={280}
                  onClick={() => navigate(`/entreprise/${o.mf}`)} rightSection={<ArrowUpRight size={10} />}>{o.company_name}</Badge>
              ))}
            </Group>
          </div>
        )}
        <Group gap={6} mt={4}>
          {modeApi && (
            <Button size="xs" color="violet" variant={deploye ? "outline" : "filled"} loading={chargement} leftSection={<GitBranchPlus size={13} />}
              onClick={() => onDeployer(n)}>{deploye ? "Replier son réseau" : "Déployer son réseau"}</Button>
          )}
          {!n.parentId && <Button size="xs" variant="light" leftSection={<Filter size={13} />} onClick={() => onFiltrer(n.label)}>Filtrer les opérations</Button>}
          {EST_MF.test(n.id) && <Button size="xs" variant="default" rightSection={<ArrowUpRight size={13} />} onClick={() => navigate(`/entreprise/${n.id}`)}>Ouvrir la fiche</Button>}
        </Group>
        {modeApi && !deploye && (
          <Text size="xs" c="dimmed">« Déployer » ajoute ses propres contreparties au graphe (signalées d'abord) pour remonter la chaîne.</Text>
        )}
      </Stack>
    </Paper>
  );
}

// ---------------------------------------------------------------- graphe
function Graphe({ entreprise, montants, contrepartiesFiltrees, etat, plein, onFiltrer, onPleinEcran }) {
  const { tout, setTout, vue, setVue, choisi, setChoisi, deployes, deployer, chargement } = etat;
  const { fitView } = useReactFlow();

  const { gauche, droite } = useMemo(() => preparer(entreprise, montants), [entreprise, montants]);
  const filtre = (l) => (vue === "signalees" ? l.filter((n) => n.risk_flag) : l);
  const G = regrouper(filtre(gauche), "gauche", tout.gauche);
  const D = regrouper(filtre(droite), "droite", tout.droite);

  const lignes = Math.max(G.length, D.length, 1);
  const hauteur = lignes * PAS;
  const hCentre = Math.max(110, Math.min(hauteur - 20, 40 + Math.max(G.length, D.length) * 14));
  const y = (i, n) => hauteur / 2 + (i - (n - 1) / 2) * PAS - H_CARTE / 2;
  const max = Math.max(1, ...[...G, ...D].map((n) => n.montant));

  const { nodes, edges, parId } = useMemo(() => {
    const nodes = [{ id: "__centre", type: "entreprise", position: { x: X_CENTRE, y: hauteur / 2 - hCentre / 2 }, draggable: false,
                     data: { e: entreprise, nG: G.length, nD: D.length, hauteur: hCentre } }];
    const edges = [];
    const parId = new Map();
    const occupes = [];
    const poser = (n, x, yy) => {
      nodes.push({ id: n.id, type: "contrepartie", position: { x, y: yy }, draggable: false,
                   data: { n, selectionnee: choisi === n.id || contrepartiesFiltrees.includes(n.label), deploye: deployes.has(n.id) } });
      parId.set(n.id, { n, x, y: yy });
      occupes.push([x, yy]);
    };
    G.forEach((n, i) => {
      poser(n, 0, y(i, G.length));
      edges.push(arete(`e-${n.id}`, n.id, "__centre", n, "sr", `g${i}`, max));
    });
    D.forEach((n, i) => {
      poser(n, X_DROITE, y(i, D.length));
      edges.push(arete(`e-${n.id}`, "__centre", n.id, n, `d${i}`, "tl", max));
    });
    // Réseaux déployés : une colonne de plus vers l'extérieur, sans chevaucher les cartes déjà posées
    const libre = (x, yy) => !occupes.some(([ox, oy]) => Math.abs(ox - x) < L_CARTE && Math.abs(oy - yy) < H_CARTE + 8);
    const vues = new Set(edges.map((e) => [e.source, e.target].sort().join("|")));
    for (const [pid, dep] of deployes) {
      const parent = parId.get(pid);
      if (!parent) continue;
      const vers = parent.x >= X_CENTRE ? 1 : -1;
      const xc = parent.x + vers * DX_DEPLOIEMENT;
      let k = 0;
      for (const brut of dep.noeuds) {
        if (brut.id === entreprise.mf) continue; // déjà au centre
        const n = { ...brut, montant: brut.montant_dt || 0, horsSelection: false, parentId: pid, parentNom: dep.nom };
        if (!parId.has(n.id)) {
          let yy = parent.y, pas = 0;
          while (!libre(xc, yy) && pas < 40) { pas += 1; yy = parent.y + (pas % 2 ? 1 : -1) * Math.ceil(pas / 2) * (H_CARTE + 12); }
          poser(n, xc, yy);
          k += 1;
        }
        const cible = parId.get(n.id);
        const [src, tgt] = n.sens === "sortant" ? [pid, n.id] : [n.id, pid];
        const cle = [src, tgt].sort().join("|");
        if (vues.has(cle)) continue;
        vues.add(cle);
        const xs = (src === pid ? parent : cible).x, xt = (tgt === pid ? parent : cible).x;
        edges.push(arete(`d-${pid}-${n.id}`, src, tgt, n, xs <= xt ? "sr" : "sl", xs <= xt ? "tl" : "tr", max));
      }
    }
    return { nodes, edges, parId };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entreprise, G.length, D.length, montants, choisi, contrepartiesFiltrees, vue, tout, deployes]);

  useEffect(() => { const t = setTimeout(() => fitView({ padding: 0.08, duration: 250 }), 40); return () => clearTimeout(t); }, [nodes.length, fitView, plein]);

  const noeudChoisi = parId.get(choisi)?.n ?? [...gauche, ...droite].find((n) => n.id === choisi);
  const tousNoeuds = [...gauche, ...droite];
  const tousSignales = [...parId.values()].map((p) => p.n).filter((n) => n.risk_flag).sort((a, b) => b.montant - a.montant);
  const clic = (_, nd) => {
    if (nd.id === "__centre") return;
    const n = nd.data.n;
    if (n.agregat) setTout((t) => ({ ...t, [n.sens === "entrant" ? "gauche" : "droite"]: true }));
    else setChoisi((c) => (c === n.id ? null : n.id));
  };

  const somme = (l) => l.reduce((s, n) => s + n.montant, 0);
  const signalees = droite.filter((n) => n.risk_flag);
  const r = entreprise.reseau_resume;
  const hauteurCanvas = plein ? "calc(100vh - 150px)" : Math.min(620, Math.max(420, lignes * 66 + 40));
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

      <div className={`grid gap-3 ${plein ? "grid-cols-[minmax(0,1fr)_400px]" : "@4xl:grid-cols-[minmax(0,1fr)_340px]"}`}>
        <div style={{ height: hauteurCanvas }} className="relative overflow-hidden rounded-lg border border-bordure bg-fond">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={TYPES_NOEUDS} onNodeClick={clic} fitView fitViewOptions={{ padding: 0.08 }}
            nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnScroll={plein} zoomOnDoubleClick={false}
            preventScrolling={plein} minZoom={0.2} maxZoom={1.8} proOptions={{ hideAttribution: true }}>
            <Background gap={18} size={1} color="#e2e8f0" />
            <Controls showInteractive={false} position="bottom-right" />
            <Panel position="top-left"><Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Paient l'entreprise</Text></Panel>
            <Panel position="top-right"><Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Payés par l'entreprise</Text></Panel>
          </ReactFlow>
        </div>

        {/* Colonne d'explication : hors du canevas, jamais rognée */}
        <ScrollArea.Autosize mah={plein ? "calc(100vh - 150px)" : Math.max(Number(hauteurCanvas) || 420, 460)} type="auto" offsetScrollbars>
          {noeudChoisi ? (
            <Explication n={noeudChoisi} entreprise={entreprise} deploye={deployes.has(noeudChoisi.id)} chargement={chargement === noeudChoisi.id}
              onFermer={() => setChoisi(null)} onFiltrer={onFiltrer} onDeployer={deployer} />
          ) : (
            <Paper withBorder p="md" radius="lg" className="!bg-white">
              <Text fw={700} size="sm" mb={4}>{tousSignales.length ? `${tousSignales.length} contrepartie${tousSignales.length > 1 ? "s" : ""} signalée${tousSignales.length > 1 ? "s" : ""}` : "Aucune contrepartie signalée"}</Text>
              <Text size="xs" c="dimmed" mb="sm">Cliquez une contrepartie, ici ou dans le graphe, pour voir la relation, le détail du motif et déployer son réseau.</Text>
              <Stack gap={6}>
                {tousSignales.map((n) => (
                  <UnstyledButton key={n.id} onClick={() => setChoisi(n.id)} className="rounded-md border border-[#fecaca] bg-[#fff5f5] px-3 py-2 hover:border-[#dc2626]">
                    <Group gap={6} wrap="nowrap" justify="space-between">
                      <Text size="sm" fw={600} truncate>{n.label}</Text>
                      <Text size="xs" fw={700} className="chiffres shrink-0">{fmtCompact(n.montant)}</Text>
                    </Group>
                    <Text size="xs" c="red.8" lh={1.35} mt={2}>{n.motif_detail?.titre ?? n.motif}</Text>
                    {n.parentNom && <Text size="xs" c="violet.7" mt={2}>via {n.parentNom}</Text>}
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
      <Modal opened={plein} onClose={() => setPlein(false)} fullScreen title={<Text fw={700}>Réseau de contreparties · {entreprise.company_name}</Text>}
        transitionProps={{ transition: "fade", duration: 150 }}>
        {plein && <ReactFlowProvider><Graphe {...props} plein onPleinEcran={() => setPlein(false)} /></ReactFlowProvider>}
      </Modal>
    </>
  );
}
