// Réseau de contreparties en flux d'argent (React Flow) : qui paie l'entreprise (à gauche) → l'entreprise → qui elle
// paie (à droite). Chaque flèche suit le paiement et porte la relation et le montant ; une phrase résume le réseau ;
// un clic sur une contrepartie ouvre son explication (relation, motif du signalement, entreprises liées).
import { memo, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Background, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import { Alert, Anchor, Badge, Button, CloseButton, Group, Paper, SegmentedControl, Stack, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { AlertTriangle, ArrowRight, ArrowUpRight, Filter, History } from "lucide-react";
import { entreprisesLiees } from "../lib/donnees.js";
import { SEGMENTS } from "../lib/palettes.js";
import { COULEURS_SEGMENT } from "../lib/theme.js";
import { fmtCompact, fmtDate, fmtDT, fmtMoisIso } from "../lib/format.js";

const PAR_COTE = 6;           // contreparties visibles par côté avant regroupement
const L_CARTE = 230, H_CARTE = 58, PAS = 74, X_CENTRE = 400, L_CENTRE = 190, X_DROITE = 800;
const ENTRANTS = new Set(["Client", "Client (honoraires)", "Acheteur public"]);
const EST_MF = /^\d{7}[A-Z]{3}\d{3}$/;
const ROUGE = "#dc2626", GRIS = "#94a3b8";
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
    <div className={`rounded-lg border bg-white px-3 py-2 shadow-sm transition-shadow ${data.selectionnee ? "ring-2 ring-[var(--mantine-color-basira-5)]" : ""} ${n.agregat ? "border-dashed" : ""}`}
      style={{ width: L_CARTE, height: H_CARTE, borderColor: signalee ? ROUGE : "var(--bordure)", opacity: n.horsSelection && !n.agregat ? 0.55 : 1, cursor: "pointer" }}>
      {n.sens === "entrant" ? <Handle type="source" position={Position.Right} className="!opacity-0" /> : <Handle type="target" position={Position.Left} className="!opacity-0" />}
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

// ---------------------------------------------------------------- panneau d'explication
function Explication({ n, entreprise, onFermer, onFiltrer }) {
  const navigate = useNavigate();
  const nom = entreprise.company_name;
  const phrase = n.sens === "sortant"
    ? <><b>{nom}</b> a payé <b>{fmtDT(n.montant)}</b> à <b>{n.label}</b></>
    : <><b>{n.label}</b> a payé <b>{fmtDT(n.montant)}</b> à <b>{nom}</b></>;
  const liees = (entreprise.liens_portefeuille ? entreprise.liens_portefeuille[n.id] ?? [] : entreprisesLiees(n.id, entreprise.mf)).filter((o) => o.mf !== n.id);
  return (
    <Paper withBorder shadow="md" p="md" radius="lg" w={320} className="!bg-white">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb={6}>
        <div className="min-w-0">
          <Text fw={700} size="sm" lh={1.3}>{n.label}</Text>
          <Text size="xs" c="dimmed">{n.type} · {n.relation}</Text>
        </div>
        <CloseButton size="sm" onClick={onFermer} aria-label="Fermer l'explication" />
      </Group>
      <Stack gap={8}>
        <Text size="sm" lh={1.45}>{phrase}{n.horsSelection ? " (cumul de la relation)" : " sur la période affichée"}.</Text>
        <Text size="xs" c="dimmed">Source : {SOURCE_RELATION[n.relation] ?? "graphe des relations"}{n.depuis ? ` · relation depuis le ${fmtDate(n.depuis)}` : ""}{n.nouvelle ? " (nouvelle)" : ""}</Text>
        {n.motif && (
          <Alert color="red" variant="light" p="xs" icon={<AlertTriangle size={15} />} title="Pourquoi elle est signalée">
            <Text size="xs">{n.motif}</Text>
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
          <Button size="xs" variant="light" leftSection={<Filter size={13} />} onClick={() => onFiltrer(n.label)}>Filtrer les opérations</Button>
          {EST_MF.test(n.id) && <Button size="xs" variant="default" rightSection={<ArrowUpRight size={13} />} onClick={() => navigate(`/entreprise/${n.id}`)}>Ouvrir la fiche</Button>}
        </Group>
      </Stack>
    </Paper>
  );
}

// ---------------------------------------------------------------- graphe
function Graphe({ entreprise, montants, contrepartiesFiltrees, onClicContrepartie }) {
  const [tout, setTout] = useState({ gauche: false, droite: false });
  const [vue, setVue] = useState("toutes");
  const [choisi, setChoisi] = useState(null);
  const { fitView } = useReactFlow();
  useEffect(() => { setTout({ gauche: false, droite: false }); setChoisi(null); setVue("toutes"); }, [entreprise.mf]);

  const { gauche, droite } = useMemo(() => preparer(entreprise, montants), [entreprise, montants]);
  const filtre = (l) => (vue === "signalees" ? l.filter((n) => n.risk_flag) : l);
  const G = regrouper(filtre(gauche), "gauche", tout.gauche);
  const D = regrouper(filtre(droite), "droite", tout.droite);

  const lignes = Math.max(G.length, D.length, 1);
  const hauteur = lignes * PAS;
  const hCentre = Math.max(110, Math.min(hauteur - 20, 40 + Math.max(G.length, D.length) * 14));
  const y = (i, n) => hauteur / 2 + (i - (n - 1) / 2) * PAS - H_CARTE / 2;
  const max = Math.max(1, ...[...G, ...D].map((n) => n.montant));

  const { nodes, edges } = useMemo(() => {
    const nodes = [{ id: "__centre", type: "entreprise", position: { x: X_CENTRE, y: hauteur / 2 - hCentre / 2 }, draggable: false,
                     data: { e: entreprise, nG: G.length, nD: D.length, hauteur: hCentre } }];
    const edges = [];
    const ajouter = (liste, cote) => liste.forEach((n, i) => {
      nodes.push({ id: n.id, type: "contrepartie", position: { x: cote === "gauche" ? 0 : X_DROITE, y: y(i, liste.length) }, draggable: false,
                   data: { n, selectionnee: choisi === n.id || contrepartiesFiltrees.includes(n.label) } });
      const couleur = n.risk_flag ? ROUGE : GRIS;
      const libelle = `${COURT[n.relation] ?? n.relation}${n.montant ? ` · ${fmtCompact(n.montant)}` : ""}`;
      edges.push({
        id: `e-${n.id}`, source: cote === "gauche" ? n.id : "__centre", target: cote === "gauche" ? "__centre" : n.id,
        sourceHandle: cote === "gauche" ? undefined : `d${i}`, targetHandle: cote === "gauche" ? `g${i}` : undefined,
        label: libelle, markerEnd: { type: MarkerType.ArrowClosed, color: couleur, width: 16, height: 16 },
        style: { stroke: couleur, strokeWidth: 1.4 + 3.6 * Math.sqrt(n.montant / max), strokeDasharray: n.nouvelle ? "6 4" : undefined, opacity: n.horsSelection && !n.agregat ? 0.45 : 0.9 },
        labelStyle: { fontSize: 11, fontWeight: 600, fill: n.risk_flag ? ROUGE : "#334155" },
        labelBgStyle: { fill: "#fff", stroke: n.risk_flag ? "#fecaca" : "#e2e8f0" }, labelBgPadding: [6, 3], labelBgBorderRadius: 6
      });
    });
    ajouter(G, "gauche");
    ajouter(D, "droite");
    return { nodes, edges };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entreprise, G.length, D.length, montants, choisi, contrepartiesFiltrees, vue, tout]);

  useEffect(() => { const t = setTimeout(() => fitView({ padding: 0.08, duration: 200 }), 30); return () => clearTimeout(t); }, [nodes.length, fitView]);

  const tousNoeuds = [...gauche, ...droite];
  const noeudChoisi = tousNoeuds.find((n) => n.id === choisi);
  const clic = (_, nd) => {
    if (nd.id === "__centre") return;
    const n = nd.data.n;
    if (n.agregat) setTout((t) => ({ ...t, [n.sens === "entrant" ? "gauche" : "droite"]: true }));
    else setChoisi((c) => (c === n.id ? null : n.id));
  };

  // Phrase de synthèse : ce que montre le graphe, en clair
  const somme = (l) => l.reduce((s, n) => s + n.montant, 0);
  const signalees = droite.filter((n) => n.risk_flag);
  const r = entreprise.reseau_resume;
  const hauteurCanvas = Math.min(620, Math.max(300, lignes * 66 + 40));
  if (!tousNoeuds.length) return <Text c="dimmed" size="sm" ta="center" py="xl">Aucune contrepartie sur la période.</Text>;

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Text size="sm" lh={1.5} className="max-w-[720px]">
          {r ? `Du ${fmtMoisIso(r.debut)} au ${fmtMoisIso(r.fin)}, ` : ""}
          <b>{gauche.length} client{gauche.length > 1 ? "s" : ""}</b> ont payé <b>{fmtCompact(somme(gauche))}</b> à l'entreprise ; elle a payé{" "}
          <b>{fmtCompact(somme(droite))}</b> à <b>{droite.length} fournisseur{droite.length > 1 ? "s" : ""}</b>
          {signalees.length > 0 && <>, dont <Text span c="red.7" fw={700}>{fmtCompact(somme(signalees))} ({Math.round((100 * somme(signalees)) / Math.max(1, somme(droite)))} %) à {signalees.length} contrepartie{signalees.length > 1 ? "s" : ""} signalée{signalees.length > 1 ? "s" : ""}</Text></>}.
        </Text>
        <SegmentedControl size="xs" value={vue} onChange={setVue} data={[{ value: "toutes", label: "Toutes" }, { value: "signalees", label: "Signalées" }]} />
      </Group>

      <div style={{ height: hauteurCanvas }} className="relative overflow-hidden rounded-lg border border-bordure bg-fond">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={TYPES_NOEUDS} onNodeClick={clic} fitView fitViewOptions={{ padding: 0.08 }}
          nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnScroll={false} zoomOnDoubleClick={false}
          preventScrolling={false} minZoom={0.3} maxZoom={1.6} proOptions={{ hideAttribution: true }}>
          <Background gap={18} size={1} color="#e2e8f0" />
          <Controls showInteractive={false} position="bottom-right" />
          <Panel position="top-left">
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Paient l'entreprise</Text>
          </Panel>
          <Panel position="top-right">
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.05em">Payés par l'entreprise</Text>
          </Panel>
          {noeudChoisi && (
            <Panel position="top-center">
              <Explication n={noeudChoisi} entreprise={entreprise} onFermer={() => setChoisi(null)} onFiltrer={(l) => { onClicContrepartie(l); setChoisi(null); }} />
            </Panel>
          )}
        </ReactFlow>
      </div>

      <Group gap="lg" wrap="wrap">
        <Group gap={6}><ArrowRight size={14} className="text-attenue" /><Text size="xs" c="dimmed">flèche = sens du paiement, épaisseur = montant</Text></Group>
        <Group gap={6}><ThemeIcon size={14} radius="xl" color="red" variant="light"><AlertTriangle size={9} /></ThemeIcon><Text size="xs" c="dimmed">contrepartie signalée (cliquer pour le motif)</Text></Group>
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

export default function GrapheReseau(props) {
  return (
    <ReactFlowProvider>
      <Graphe {...props} />
    </ReactFlowProvider>
  );
}
