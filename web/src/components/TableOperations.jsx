// Opérations de la sélection : recherche, filtre « signalées », tri et pagination sur les pièces sources.
import { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, CloseButton, Group, Pagination, SegmentedControl, Switch, Table, Text, TextInput, Tooltip } from "@mantine/core";
import { AlertTriangle, Filter as FilterIcon, Search } from "lucide-react";
import { fmtCompact, fmtDT, fmtDate } from "../lib/format.js";

const PAR_PAGE = 12;
const COULEURS_SOURCE = { SINDA: "#3569b5", ADEB: "#b8862b", "ANNEXE V": "#2ba5a0", TJ: "#2ba5a0", RAFIK: "#4d5563" };

export default function TableOperations({ lignes, total, filtres = [], onRetirer, onToutEffacer }) {
  const [q, setQ] = useState("");
  const [signalees, setSignalees] = useState(false);
  const [tri, setTri] = useState("date");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [q, signalees, tri, lignes]);

  const filtrees = useMemo(() => {
    const t = q.trim().toLowerCase();
    const l = lignes.filter((o) => (!signalees || o.contrepartie_signalee)
      && (!t || `${o.contrepartie} ${o.reference} ${o.type_operation} ${o.source} ${o.pays ?? ""}`.toLowerCase().includes(t)));
    return l.sort(tri === "montant" ? (a, b) => b.montant_dt - a.montant_dt : (a, b) => b.date.localeCompare(a.date));
  }, [lignes, q, signalees, tri]);

  const nbPages = Math.max(1, Math.ceil(filtrees.length / PAR_PAGE));
  const page_ = Math.min(page, nbPages);
  const visibles = filtrees.slice((page_ - 1) * PAR_PAGE, page_ * PAR_PAGE);
  const somme = filtrees.reduce((s, o) => s + o.montant_dt, 0);
  const nbSignalees = lignes.filter((o) => o.contrepartie_signalee).length;

  return (
    <div className="flex flex-col gap-3">
      {/* Filtres venus du reste de la fiche (période, système, contrepartie cliquée dans le graphe) : visibles ici */}
      {filtres.length > 0 && (
        <Alert variant="light" color="basira" p="xs" icon={<FilterIcon size={15} />}
          title={<Text size="sm" fw={600}>Liste filtrée : {filtres.length} filtre{filtres.length > 1 ? "s" : ""} actif{filtres.length > 1 ? "s" : ""}</Text>}>
          <Group gap={6} mt={2}>
            {filtres.map(([cle, texte]) => (
              <Badge key={cle} variant="white" size="lg" fw={500} radius="xl" className="normal-case"
                rightSection={<CloseButton size="xs" onClick={() => onRetirer?.(cle)} aria-label={`Retirer le filtre ${texte}`} />}>{texte}</Badge>
            ))}
            {filtres.length > 1 && <Button variant="subtle" size="compact-xs" onClick={onToutEffacer}>Tout retirer</Button>}
          </Group>
        </Alert>
      )}
      <Group gap="xs" wrap="wrap">
        <TextInput size="xs" className="min-w-[200px] flex-1" value={q} onChange={(e) => setQ(e.currentTarget.value)}
          placeholder="Contrepartie, référence, pays…" leftSection={<Search size={13} />} aria-label="Rechercher une opération" />
        <Switch size="xs" checked={signalees} onChange={(e) => setSignalees(e.currentTarget.checked)} disabled={!nbSignalees}
          label={`Signalées seulement (${nbSignalees})`} color="red" />
        <SegmentedControl size="xs" value={tri} onChange={setTri} data={[{ value: "date", label: "Récentes" }, { value: "montant", label: "Montant" }]} />
      </Group>
      <Text size="xs" c="dimmed">
        <b className="text-encre">{filtrees.length.toLocaleString("fr-FR")}</b> opération{filtrees.length > 1 ? "s" : ""}
        {filtrees.length !== total && ` sur ${total.toLocaleString("fr-FR")}`} · {fmtCompact(somme)}
      </Text>
      <Table.ScrollContainer minWidth={480} type="native">
        <Table verticalSpacing={8} fz="sm" highlightOnHover>
          <Table.Thead className="bg-fond">
            <Table.Tr>
              <Table.Th w={96}>Date</Table.Th>
              <Table.Th>Contrepartie et pièce</Table.Th>
              <Table.Th ta="right" w={120}>Montant</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {visibles.map((o) => (
              <Table.Tr key={o.id}>
                <Table.Td className="chiffres whitespace-nowrap align-top text-encre-2">{fmtDate(o.date)}</Table.Td>
                <Table.Td className="align-top">
                  <Group gap={6} wrap="nowrap">
                    <Badge size="xs" variant="light" color={COULEURS_SOURCE[o.source] ?? "gray"} className="shrink-0">{o.source}</Badge>
                    {o.contrepartie_signalee && <Tooltip label="Contrepartie signalée (voir le réseau)"><AlertTriangle size={13} color="#dc2626" className="shrink-0" /></Tooltip>}
                    <Text size="sm" fw={600} c={o.contrepartie_signalee ? "red.7" : undefined} truncate>{o.contrepartie}</Text>
                  </Group>
                  <Text size="xs" c="dimmed" mt={2} className="break-words">
                    {[o.type_operation, o.pays, o.circuit && `circuit ${o.circuit}`].filter(Boolean).join(" · ")}
                    <Text span size="xs" ff="monospace" c="dimmed"> · {o.reference}</Text>
                  </Text>
                  {o.observation && <Text size="xs" fw={600} c="orange.8" mt={2}>{o.observation}</Text>}
                </Table.Td>
                <Table.Td className="chiffres whitespace-nowrap text-right align-top font-semibold">{fmtDT(o.montant_dt)}</Table.Td>
              </Table.Tr>
            ))}
            {!visibles.length && (
              <Table.Tr><Table.Td colSpan={3}><Text size="sm" c="dimmed" ta="center" py="md">Aucune opération ne correspond.</Text></Table.Td></Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {nbPages > 1 && (
        <Group justify="space-between">
          <Text size="xs" c="dimmed">Page {page_} sur {nbPages}</Text>
          <Pagination size="sm" total={nbPages} value={page_} onChange={setPage} siblings={1} boundaries={1} />
        </Group>
      )}
    </div>
  );
}
