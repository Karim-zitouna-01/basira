// « Pourquoi ce score ? » (contrat §6, fiche entreprise) : contributions de chaque signal en points, phrase
// vérifiable, lignes brutes à l'appui (preuves), position face aux pairs, et décision de l'inspecteur.
import { useState } from "react";
import { Alert, Badge, Button, Card, Collapse, Group, Loader, Progress, Select, Stack, Table, Text, Textarea, ThemeIcon, Timeline, Tooltip } from "@mantine/core";
import { ChevronDown, ChevronRight, FileSearch, Gavel, Lightbulb, Users } from "lucide-react";
import { chargerPreuves, enregistrerDecision, oublierFiche } from "../lib/donnees.js";
import { fmtCompact, fmtDT, fmtDate } from "../lib/format.js";
import { LIBELLES_SOURCES, nettoyerFait } from "../lib/signaux.js";

const LENTILLES = {
  COHERENCE: ["Cohérence entre sources", "red"], CHANGEMENT: ["Changement de comportement", "orange"],
  PAIRS: ["Comparaison aux pairs", "basira"], RESEAU: ["Réseau", "teal"], COMBINAISON: ["Combinaison", "ardoise"]
};
const DECISIONS = {
  AUCUNE: "Aucune action", RELANCE: "Relance de conformité", DEMANDE_INFO: "Demande d'information",
  VERIFICATION: "Vérification approfondie", SIGNALEMENT_DOUANE: "Signalement à la douane"
};
const VISIBLES = 4;
const nombre = (v, d = 1) => v.toLocaleString("fr-FR", { maximumFractionDigits: d });
const pts = (v) => `${v >= 0 ? "+" : ""}${nombre(v)}`;
const estMontant = (nom) => /CA par salarié/.test(nom);
const fmtIndicateur = (nom, v) => (v === null || v === undefined ? "—" : estMontant(nom) ? fmtCompact(v) : `${Math.round(v * 100)} %`);

function EnTete({ titre, icone: Icone, droite }) {
  return (
    <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
      <Group gap={8} wrap="nowrap">
        <ThemeIcon variant="light" color="ardoise" size={28} radius="md"><Icone size={15} /></ThemeIcon>
        <Text fw={700} size="md">{titre}</Text>
      </Group>
      {droite}
    </Group>
  );
}

function Preuves({ mf, code, nb }) {
  const [etat, setEtat] = useState({ ouvert: false, donnees: null, erreur: null });
  const basculer = () => {
    if (!etat.ouvert && !etat.donnees) {
      chargerPreuves(mf, code).then((d) => setEtat({ ouvert: true, donnees: d, erreur: null }), (e) => setEtat({ ouvert: true, donnees: null, erreur: e.message }));
    }
    setEtat((s) => ({ ...s, ouvert: !s.ouvert }));
  };
  const lignes = etat.donnees?.lignes ?? [];
  return (
    <>
      <Button variant="subtle" size="compact-xs" onClick={basculer} aria-expanded={etat.ouvert}
        leftSection={etat.ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}>
        {nb} preuve{nb > 1 ? "s" : ""}
      </Button>
      <Collapse expanded={etat.ouvert} className="w-full basis-full">
        <div className="mt-2 max-h-[260px] overflow-auto rounded-md border border-bordure">
          {etat.erreur && <Alert color="red" variant="light" m="xs">Preuves indisponibles : {etat.erreur}</Alert>}
          {!etat.erreur && !etat.donnees && <Group p="sm"><Loader size="xs" /><Text size="xs" c="dimmed">Chargement des pièces…</Text></Group>}
          {etat.donnees && (
            <Table fz="xs" verticalSpacing={6} horizontalSpacing="sm" highlightOnHover={false} stickyHeader>
              <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Pièce</Table.Th><Table.Th ta="right">Montant</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {lignes.map((l) => {
                  const sousEvalue = l.champs?.prix_reference_tnd && l.champs.prix_unitaire_tnd < 0.9 * l.champs.prix_reference_tnd;
                  return (
                    <Table.Tr key={`${l.source}:${l.ref}`}>
                      <Table.Td className="chiffres whitespace-nowrap align-top text-attenue">{fmtDate(l.date)}</Table.Td>
                      <Table.Td className="align-top">
                        <Text size="xs">{l.libelle}</Text>
                        <Text size="xs" c="dimmed" title={l.ref}>
                          {LIBELLES_SOURCES[l.source] ?? l.source}
                          {l.champs?.prix_reference_tnd && (
                            <Text span size="xs" c={sousEvalue ? "red.7" : "dimmed"} fw={sousEvalue ? 700 : 400}>
                              {" "}· prix {fmtDT(l.champs.prix_unitaire_tnd)} pour une référence de {fmtDT(l.champs.prix_reference_tnd)}
                            </Text>
                          )}
                        </Text>
                      </Table.Td>
                      <Table.Td className="chiffres whitespace-nowrap text-right align-top">{l.montant === null ? "—" : fmtDT(l.montant)}</Table.Td>
                    </Table.Tr>
                  );
                })}
                {!lignes.length && <Table.Tr><Table.Td colSpan={3}><Text size="xs" c="dimmed">Aucune ligne brute rattachée à ce signal.</Text></Table.Td></Table.Tr>}
              </Table.Tbody>
            </Table>
          )}
        </div>
      </Collapse>
    </>
  );
}

function Contribution({ mf, c, max }) {
  const [lentille, couleur] = LENTILLES[c.lentille] ?? [c.lentille, "ardoise"];
  const fait = nettoyerFait(c.fait_fr);
  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <Group justify="space-between" wrap="nowrap" gap="md">
        <Group gap={8} wrap="nowrap" className="min-w-0">
          <Tooltip label={`${lentille} · ${c.code_signal}`}>
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: `var(--mantine-color-${couleur}-6)` }} />
          </Tooltip>
          <Text size="sm" fw={600} truncate>{c.libelle}</Text>
        </Group>
        <Group gap={10} wrap="nowrap">
          <Progress value={(100 * Math.max(0, c.points)) / max} color={couleur} size="sm" w={90} radius="xl" className="hidden @xl:block" />
          <Text size="sm" fw={700} className="chiffres w-[64px] text-right">{pts(c.points)} pts</Text>
        </Group>
      </Group>
      <Group gap="xs" mt={4} pl={18} wrap="wrap" align="baseline">
        {fait && <Text size="sm" c="dimmed" lh={1.45} className="min-w-0 flex-1">{fait}</Text>}
        {c.nb_preuves > 0 && <Preuves mf={mf} code={c.code_signal} nb={c.nb_preuves} />}
      </Group>
    </div>
  );
}

function Decision({ mf, suggeree, initiales }) {
  const [decision, setDecision] = useState(suggeree);
  const [justification, setJustification] = useState("");
  const [historique, setHistorique] = useState(initiales);
  const [etat, setEtat] = useState({ envoi: false, erreur: null });
  const envoyer = (ev) => {
    ev.preventDefault();
    if (!justification.trim()) return;
    setEtat({ envoi: true, erreur: null });
    enregistrerDecision(mf, { decision, justification: justification.trim(), inspecteur: "demo" }).then(
      (r) => {
        setHistorique((h) => [...h, { id_decision: r.id_decision, date_heure: r.date_heure, decision, justification: justification.trim() }]);
        setJustification("");
        setEtat({ envoi: false, erreur: null });
        oublierFiche(mf);
      },
      (e) => setEtat({ envoi: false, erreur: e.message })
    );
  };
  return (
    <Card>
      <EnTete titre="Décision" icone={Gavel} />
      <form onSubmit={envoyer}>
        <Stack gap="xs">
          <Select label="Décision" description={`Suggérée par Basira : ${DECISIONS[suggeree]}`} size="sm" value={decision} onChange={(v) => v && setDecision(v)} allowDeselect={false}
            data={Object.entries(DECISIONS).map(([k, v]) => ({ value: k, label: v }))} />
          <Textarea label="Justification" size="sm" autosize minRows={2} maxRows={5} value={justification}
            onChange={(e) => setJustification(e.currentTarget.value)} placeholder="Motif de la décision (obligatoire)" />
          <Button type="submit" loading={etat.envoi} disabled={!justification.trim()}>Enregistrer la décision</Button>
          {etat.erreur && <Alert color="red" variant="light" p="xs">Échec : {etat.erreur}</Alert>}
          <Text size="xs" c="dimmed">Basira propose, l'inspecteur décide.</Text>
        </Stack>
      </form>
      {historique.length > 0 && (
        <Timeline mt="md" bulletSize={14} lineWidth={2} active={historique.length}>
          {[...historique].reverse().map((d) => (
            <Timeline.Item key={d.id_decision} title={<Text size="sm" fw={600}>{DECISIONS[d.decision] ?? d.decision}</Text>}>
              <Text size="xs" c="dimmed">{fmtDate(d.date_heure)} · {d.justification}</Text>
            </Timeline.Item>
          ))}
        </Timeline>
      )}
    </Card>
  );
}

// Position de l'entreprise dans la plage P10–P90 de ses pairs (bande), médiane (trait), entreprise (point)
function Jauge({ i }) {
  const v = i.entreprise;
  const bornes = [i.p10, i.p90, i.mediane_pairs, v].filter((x) => x !== null && x !== undefined);
  let [lo, hi] = [Math.min(...bornes), Math.max(...bornes)];
  const marge = (hi - lo) * 0.08 || 1;
  [lo, hi] = [lo - marge, hi + marge];
  const x = (val) => `${(100 * (val - lo)) / (hi - lo)}%`;
  const hors = v !== null && v !== undefined && (v < i.p10 || v > i.p90);
  return (
    <div>
      <Group justify="space-between" gap="xs" wrap="nowrap" mb={6}>
        <Text size="sm" c="dimmed" truncate>{i.nom}</Text>
        <Text size="sm" fw={700} c={hors ? "red.7" : undefined} className="chiffres">{fmtIndicateur(i.nom, v)}</Text>
      </Group>
      <Tooltip label={`Pairs : médiane ${fmtIndicateur(i.nom, i.mediane_pairs)}, 80 % entre ${fmtIndicateur(i.nom, i.p10)} et ${fmtIndicateur(i.nom, i.p90)}`}>
        <div className="relative h-2 rounded-full bg-fond-2">
          {i.p10 !== null && i.p90 !== null && <span className="absolute inset-y-0 rounded-full bg-[var(--mantine-color-ardoise-2)]" style={{ left: x(i.p10), width: `calc(${x(i.p90)} - ${x(i.p10)})` }} />}
          {i.mediane_pairs !== null && <span className="absolute -inset-y-0.5 w-0.5 bg-[var(--mantine-color-ardoise-5)]" style={{ left: x(i.mediane_pairs) }} />}
          {v !== null && v !== undefined && (
            <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
              style={{ left: x(v), background: hors ? "#dc2626" : "#0f172a" }} />
          )}
        </div>
      </Tooltip>
    </div>
  );
}

export default function PourquoiScore({ mf, detail }) {
  const [tout, setTout] = useState(false);
  const contributions = detail.contributions ?? [];
  const visibles = tout ? contributions : contributions.slice(0, VISIBLES);
  const max = Math.max(1, ...contributions.map((c) => c.points));
  const somme = contributions.reduce((s, c) => s + c.points, 0);
  const base = detail.score - somme;
  const e = detail.enjeu ?? {};
  const pairs = detail.pairs ?? { indicateurs: [] };
  return (
    <div className="grid gap-4 @4xl:grid-cols-[minmax(0,1fr)_320px]">
      <Card>
        <EnTete titre="Pourquoi ce score ?" icone={Lightbulb}
          droite={<Text fz={26} fw={800} lh={1} className="chiffres">{nombre(detail.score)}<Text span size="sm" c="dimmed" fw={500}> /100</Text></Text>} />
        <Group gap="xs" mb="md" wrap="wrap">
          <Badge variant="light" color="ardoise" size="lg">base {nombre(base)}</Badge>
          <Text size="sm" c="dimmed">+</Text>
          <Badge variant="light" color="red" size="lg">{nombre(somme)} pts · {contributions.length} signal{contributions.length > 1 ? "aux" : ""}</Badge>
          {e.estime > 0 && (
            <Tooltip label={`Fourchette ${fmtCompact(e.bas)} – ${fmtCompact(e.haut)} : droits éludés estimés sur 12 mois glissants`}>
              <Badge variant="outline" color="ardoise" size="lg" className="cursor-help">enjeu estimé {fmtCompact(e.estime)}</Badge>
            </Tooltip>
          )}
        </Group>
        <div className="divide-y divide-[var(--bordure)]">
          {visibles.map((c) => <Contribution key={c.code_signal} mf={mf} c={c} max={max} />)}
          {!contributions.length && <Text size="sm" c="dimmed">Aucun signal ne contribue au score ce mois-ci.</Text>}
        </div>
        {contributions.length > VISIBLES && (
          <Button variant="subtle" size="compact-sm" mt="sm" onClick={() => setTout((t) => !t)} className="self-start"
            leftSection={tout ? <ChevronDown size={14} /> : <ChevronRight size={14} />}>
            {tout ? "Masquer les signaux secondaires" : `${contributions.length - VISIBLES} signal${contributions.length - VISIBLES > 1 ? "aux" : ""} secondaire${contributions.length - VISIBLES > 1 ? "s" : ""}`}
          </Button>
        )}
        <Group gap={6} mt="md"><FileSearch size={13} className="text-attenue" /><Text size="xs" c="dimmed">Chaque point du score renvoie à des lignes de données brutes.</Text></Group>
      </Card>
      <div className="grid content-start gap-4 @2xl:grid-cols-2 @4xl:grid-cols-1">
        <Decision mf={mf} suggeree={detail.action_suggeree} initiales={detail.decisions ?? []} />
        {pairs.indicateurs.length > 0 && (
          <Card>
            <EnTete titre="Face à ses pairs" icone={Users} droite={<Text size="xs" c="dimmed">{pairs.nb_pairs} entreprises</Text>} />
            <Stack gap="md">{pairs.indicateurs.map((i) => <Jauge key={i.nom} i={i} />)}</Stack>
            <Group gap="md" mt="md">
              <Group gap={4}><span className="h-1.5 w-4 rounded-full bg-[var(--mantine-color-ardoise-2)]" /><Text size="xs" c="dimmed">80 % des pairs</Text></Group>
              <Group gap={4}><span className="h-2.5 w-0.5 bg-[var(--mantine-color-ardoise-5)]" /><Text size="xs" c="dimmed">médiane</Text></Group>
              <Group gap={4}><span className="size-2 rounded-full bg-[#0f172a]" /><Text size="xs" c="dimmed">entreprise</Text></Group>
            </Group>
          </Card>
        )}
      </div>
    </div>
  );
}
