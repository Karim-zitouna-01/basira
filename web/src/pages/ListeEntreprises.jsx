// Page d'accueil (design_references/reference 1) : indicateurs globaux du portefeuille
// + liste des entreprises. Un seul crossfilter (entreprise × mois) alimente les cartes,
// leurs mini-courbes DC.js, les effectifs des filtres et la table.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as d3 from "d3";
import crossfilter from "crossfilter2";
import * as dc from "dc";
import "../lib/dcCompat.js";
import { ActionIcon, Button, Group, Pagination, Paper, Select, Table, Text, TextInput, Title, UnstyledButton } from "@mantine/core";
import { ArrowDown, ArrowUp, Building2, ChevronsUpDown, Gauge, Gavel, MapPin, Scale, Search, ShieldAlert, Ship, Star, Tag } from "lucide-react";
import { COULEURS_SEGMENT } from "../lib/theme.js";
import { listerEntreprises, meta, modeApi } from "../lib/donnees.js";
import { useContextePage } from "../lib/contextePage.jsx";
import { basculerFavori, useSuivis } from "../lib/suivis.js";
import { ORDRE_SEGMENTS, SEGMENTS, jeton } from "../lib/palettes.js";
import { nouveauGroupe, useRedimensionnement } from "../lib/dcOutils.js";
import { fmtCompact, fmtMois, fmtMoisIso } from "../lib/format.js";
import CarteKpi from "../components/CarteKpi.jsx";
import FiltreMenu from "../components/FiltreMenu.jsx";
import Pastille from "../components/Pastille.jsx";
import BoutonCopilote from "../components/BoutonCopilote.jsx";

const DERNIER = meta.mois_reference;
const auMois = (m) => new Date(`${m}-01T00:00:00`);
const division = (nat) => nat.split(" - ")[0].slice(0, 2);

// Colonnes par ordre d'importance ; `cache` : masquée quand la page est étroite (copilote ouvert, petit écran)
const COLONNES = [
  { cle: "nom", libelle: "Entreprise", val: (e) => e.company_name },
  { cle: "score", libelle: "Score", val: (e) => e.current_risk_score, num: true },
  { cle: "statut", libelle: "Statut", val: (e) => ORDRE_SEGMENTS.indexOf(e.segment) },
  { cle: "ecart", libelle: modeApi ? "Enjeu" : "Écart", val: (e) => e.recoupment_gap_dt, num: true },
  { cle: "declencheur", libelle: "Déclencheur principal", val: (e) => e.primary_trigger, cache: "hidden @3xl:table-cell" },
  { cle: "action", libelle: "Action recommandée", val: (e) => e.recommended_action, cache: "hidden @5xl:table-cell" },
  { cle: "mf", libelle: "Matricule fiscal", val: (e) => e.company_id, cache: "hidden @6xl:table-cell" },
  { cle: "secteur", libelle: "NAT", val: (e) => e.sector_nacef, cache: "hidden @6xl:table-cell" },
  { cle: "gouv", libelle: "Gouvernorat", val: (e) => e.gouvernorat, cache: "hidden @7xl:table-cell" }
];

const variationPct = (actuel, precedent) => (precedent ? Math.round((100 * (actuel - precedent)) / precedent) : null);
const signe = (v) => (v >= 0 ? "+" : "");
const dec1 = (v) => v.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export default function ListeEntreprises({ copilote, palette }) {
  const navigate = useNavigate();
  const { setContexte } = useContextePage();
  const { favoris } = useSuivis();
  const entreprises = listerEntreprises();
  const parMf = useMemo(() => new Map(entreprises.map((e) => [e.mf, e])), [entreprises]);

  // --- Crossfilter entreprise × mois (créé une fois) ---
  const cf = useMemo(() => {
    const lignes = entreprises.flatMap((e) => e.historique_mensuel.map((h) => ({
      mf: e.mf, mois: h.mois, moisDate: auMois(h.mois), score: h.score, segmentMois: h.segment,
      ecart: h.ecart_recoupement_dt, imports: h.imports_sinda_dt,
      segment: e.segment, secteur: division(e.sector_nacef), gouvernorat: e.gouvernorat, action: e.recommended_action,
      texte: `${e.company_name} ${e.company_id} ${e.sector_nacef} ${e.gouvernorat}`.toLowerCase()
    })));
    const x = crossfilter(lignes);
    const d = {
      statut: x.dimension((r) => r.segment), secteur: x.dimension((r) => r.secteur),
      gouvernorat: x.dimension((r) => r.gouvernorat), action: x.dimension((r) => r.action),
      texte: x.dimension((r) => r.texte), mois: x.dimension((r) => r.moisDate)
    };
    const duMois = (r) => (r.mois === DERNIER ? 1 : 0);
    const groupes = {
      prio: d.mois.group().reduceSum((r) => (r.segmentMois === "PRIORITAIRE" ? 1 : 0)),
      score: d.mois.group().reduce((p, r) => ({ n: p.n + 1, s: p.s + r.score }), (p, r) => ({ n: p.n - 1, s: p.s - r.score }), () => ({ n: 0, s: 0 })),
      ecart: d.mois.group().reduceSum((r) => r.ecart),
      imports: d.mois.group().reduceSum((r) => r.imports),
      // Effectifs des filtres : une entreprise = sa ligne du mois de référence
      comptes: Object.fromEntries(["statut", "secteur", "gouvernorat", "action"].map((k) => [k, d[k].group().reduceSum(duMois)]))
    };
    return { x, d, groupes };
  }, [entreprises]);

  const [filtres, setFiltres] = useState({ statut: [], secteur: [], gouvernorat: [], action: [], recherche: "" });
  const [tri, setTri] = useState({ cle: "score", sens: "desc" });
  const [version, setVersion] = useState(0);
  const groupeRef = useRef(null);
  const racineRef = useRef(null);
  const sparks = { prio: useRef(null), score: useRef(null), ecart: useRef(null), imports: useRef(null) };

  // Filtres React → dimensions crossfilter
  useEffect(() => {
    const { d } = cf;
    for (const k of ["statut", "secteur", "gouvernorat", "action"]) {
      const v = filtres[k];
      if (v.length) d[k].filterFunction((x) => v.includes(x)); else d[k].filterAll();
    }
    const q = filtres.recherche.trim().toLowerCase();
    if (q) d.texte.filterFunction((t) => t.includes(q)); else d.texte.filterAll();
    setVersion((n) => n + 1);
    if (groupeRef.current) dc.redrawAll(groupeRef.current);
  }, [filtres, cf]);

  // Mini-courbes DC.js des cartes (recréées si la palette change)
  useEffect(() => {
    const groupe = nouveauGroupe("liste");
    groupeRef.current = groupe;
    const domaine = [auMois(meta.mois_couverts[0]), auMois(DERNIER)];
    const config = [
      ["prio", cf.groupes.prio, (d) => d.value, jeton("--seg-prio"), (v) => `${v} entreprise(s) à haut risque`],
      ["score", cf.groupes.score, (d) => (d.value.n ? d.value.s / d.value.n : 0), jeton("--seg-surv"), (v) => `score moyen ${dec1(v)}`],
      ["ecart", cf.groupes.ecart, (d) => d.value, jeton("--encre-2"), (v) => `écart ${fmtCompact(v)}`],
      ["imports", cf.groupes.imports, (d) => d.value, jeton("--src-sinda"), (v) => `imports ${fmtCompact(v)}`]
    ];
    for (const [cle, groupeCf, acces, couleur, texte] of config) {
      const c = new dc.LineChart(sparks[cle].current, groupe)
        .height(46).minWidth(60).margins({ top: 4, right: 3, bottom: 3, left: 3 })
        .dimension(cf.d.mois).group(groupeCf).valueAccessor(acces)
        .x(d3.scaleTime().domain(domaine)).elasticY(true).yAxisPadding("12%")
        .curve(d3.curveMonotoneX).renderArea(true).brushOn(false).colors(couleur)
        .title((d) => `${fmtMois(d.key)} : ${texte(acces(d))}`);
    }
    dc.renderAll(groupe);
    return () => {
      dc.chartRegistry.clear(groupe);
      Object.values(sparks).forEach((r) => { if (r.current) r.current.innerHTML = ""; });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cf, palette]);
  useRedimensionnement(racineRef, groupeRef);

  // --- Données dérivées (recalculées à chaque changement de filtre) ---
  const derive = useMemo(() => {
    const { groupes } = cf;
    const serie = (g, acces) => g.all().map(acces);
    return {
      prio: serie(groupes.prio, (d) => d.value),
      score: serie(groupes.score, (d) => (d.value.n ? d.value.s / d.value.n : 0)),
      ecart: serie(groupes.ecart, (d) => d.value),
      imports: serie(groupes.imports, (d) => d.value),
      mfs: new Set(cf.x.allFiltered().filter((r) => r.mois === DERNIER).map((r) => r.mf)),
      comptes: Object.fromEntries(Object.entries(groupes.comptes).map(([k, g]) => [k, new Map(g.all().map((d) => [d.key, d.value]))]))
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cf, version]);

  const lignes = useMemo(() => {
    const col = COLONNES.find((c) => c.cle === tri.cle);
    const s = tri.sens === "asc" ? 1 : -1;
    // À égalité, l'ordre de priorité de Basira (score × enjeu) départage
    return [...derive.mfs].map((mf) => parMf.get(mf)).sort((a, b) => {
      const va = col.val(a), vb = col.val(b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * s || (a.rang_priorite ?? 0) - (b.rang_priorite ?? 0);
    });
  }, [derive.mfs, parMf, tri]);

  const kpi = {
    prio: derive.prio.at(-1) ?? 0, prioPrec: derive.prio.at(-2) ?? 0,
    score: derive.score.at(-1) ?? 0, scorePrec: derive.score.at(-2) ?? 0,
    ecart12: d3.sum(derive.ecart), ecart: derive.ecart.at(-1) ?? 0, ecartPrec: derive.ecart.at(-2) ?? 0,
    imports: derive.imports.at(-1) ?? 0, importsPrec: derive.imports.at(-2) ?? 0
  };

  // Ce que le copilote voit : filtres, indicateurs et lignes affichées
  useEffect(() => {
    setContexte({
      page: "liste",
      titre: "Liste des entreprises",
      filtres: {
        recherche: filtres.recherche || null,
        segment: filtres.statut.map((s) => SEGMENTS[s].libelle).join(", ") || null,
        secteur: filtres.secteur.join(", ") || null,
        gouvernorat: filtres.gouvernorat.join(", ") || null,
        action: filtres.action.join(", ") || null
      },
      indicateurs: {
        entreprises_haut_risque: kpi.prio, score_moyen: Math.round(kpi.score * 10) / 10,
        ecart_recoupement_12_mois_dt: kpi.ecart12, imports_sinda_mois_dt: kpi.imports
      },
      nb_affichees: lignes.length,
      ecart_total_dt: d3.sum(lignes, (e) => e.recoupment_gap_dt),
      entreprises_affichees: lignes.slice(0, 20).map((e) => ({
        nom: e.company_name, mf: e.company_id, score: e.current_risk_score, delta: e.risk_delta_2m,
        statut: SEGMENTS[e.segment].libelle, ecart_dt: e.recoupment_gap_dt, action: e.recommended_action
      }))
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lignes, version, setContexte]);

  const maj = (cle) => (v) => setFiltres((f) => ({ ...f, [cle]: v }));
  const valeurDe = { statut: (e) => e.segment, secteur: (e) => division(e.sector_nacef), gouvernorat: (e) => e.gouvernorat, action: (e) => e.recommended_action };
  const options = (cle, libelle, pastille) =>
    [...new Set(entreprises.map(valeurDe[cle]))]
      .sort((a, b) => (cle === "statut" ? ORDRE_SEGMENTS.indexOf(a) - ORDRE_SEGMENTS.indexOf(b) : String(a).localeCompare(String(b))))
      .map((v) => ({ valeur: v, libelle: libelle(v), effectif: derive.comptes[cle].get(v) ?? 0, pastille: pastille?.(v) }));
  const libelleSecteur = (div) => `${div} · ${entreprises.find((x) => division(x.sector_nacef) === div).sector_nacef.split(" - ")[1]}`;
  const filtresActifs = ["statut", "secteur", "gouvernorat", "action"].some((k) => filtres[k].length) || filtres.recherche;
  const hautRisqueSeul = filtres.statut.length === 1 && filtres.statut[0] === "PRIORITAIRE";
  const trier = (cle) => setTri((t) => ({ cle, sens: t.cle === cle && t.sens === "desc" ? "asc" : "desc" }));

  const vEcart = variationPct(kpi.ecart, kpi.ecartPrec);
  const vImports = variationPct(kpi.imports, kpi.importsPrec);


  // Pagination de la table (le filtrage et le tri portent sur tout le portefeuille)
  const [page, setPage] = useState(1);
  const [taille, setTaille] = useState("25");
  useEffect(() => { setPage(1); }, [filtres, tri, taille]);
  const nbPages = Math.max(1, Math.ceil(lignes.length / Number(taille)));
  const debut = (Math.min(page, nbPages) - 1) * Number(taille);
  const pageLignes = lignes.slice(debut, debut + Number(taille));

  return (
    <div ref={racineRef} className="@container flex flex-col gap-5 px-6 py-5">
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
        <div>
          <Title order={2} fz={22}>Entreprises</Title>
          <Text size="sm" c="dimmed">
            {lignes.length === entreprises.length ? `${entreprises.length.toLocaleString("fr-FR")} entreprises` : `${lignes.length.toLocaleString("fr-FR")} sur ${entreprises.length.toLocaleString("fr-FR")} entreprises`} · situation au {fmtMoisIso(DERNIER)}
          </Text>
        </div>
        <BoutonCopilote copilote={copilote} />
      </Group>

      {/* Indicateurs globaux : se recalculent selon les filtres ci-dessous */}
      <section className="grid grid-cols-1 gap-3 @xl:grid-cols-2 @5xl:grid-cols-4" aria-label="Indicateurs du portefeuille">
        <CarteKpi ref={sparks.prio} icone={ShieldAlert} titre="Entreprises à haut risque" valeur={kpi.prio}
          variation={{ texte: `${signe(kpi.prio - kpi.prioPrec)}${kpi.prio - kpi.prioPrec} vs ${fmtMoisIso(meta.mois_couverts.at(-2))}`, sens: kpi.prio > kpi.prioPrec ? "hausse" : kpi.prio < kpi.prioPrec ? "baisse" : "stable", ton: kpi.prio > kpi.prioPrec ? "mauvais" : "neutre" }}
          onClick={() => maj("statut")(hautRisqueSeul ? [] : ["PRIORITAIRE"])} actif={hautRisqueSeul} aide="Cliquer pour n'afficher que les entreprises à haut risque" />
        <CarteKpi ref={sparks.score} icone={Gauge} titre="Score de risque moyen" valeur={dec1(kpi.score)} unite="/100"
          variation={{ texte: `${signe(kpi.score - kpi.scorePrec)}${dec1(kpi.score - kpi.scorePrec)} pt sur 1 mois`, sens: kpi.score > kpi.scorePrec ? "hausse" : "baisse", ton: kpi.score > kpi.scorePrec ? "mauvais" : "bon" }} />
        {/* API : l'enjeu estimé est déjà un cumul sur 12 mois glissants → valeur du dernier mois, pas une somme */}
        <CarteKpi ref={sparks.ecart} icone={Scale} titre={modeApi ? `Enjeu estimé · ${fmtMoisIso(DERNIER)}` : "Écart de recoupement · 12 mois"}
          valeur={fmtCompact(modeApi ? kpi.ecart : kpi.ecart12)}
          aide={modeApi ? "Droits éludés estimés sur 12 mois glissants, somme des entreprises affichées" : undefined}
          variation={vEcart === null ? { texte: "Aucun écart le mois précédent" } : { texte: `${signe(vEcart)}${vEcart} % sur 1 mois`, sens: vEcart > 0 ? "hausse" : "baisse", ton: vEcart > 0 ? "mauvais" : "bon" }} />
        <CarteKpi ref={sparks.imports} icone={Ship} titre={`Imports SINDA · ${fmtMoisIso(DERNIER)}`} valeur={fmtCompact(kpi.imports)}
          variation={vImports === null ? { texte: "Aucun import le mois précédent" } : { texte: `${signe(vImports)}${vImports} % sur 1 mois`, sens: vImports > 0 ? "hausse" : "baisse", ton: "neutre" }} />
      </section>

      <Paper withBorder radius="lg" className="overflow-hidden">
        {/* Barre d'outils : filtres crossfilter + recherche */}
        <Group gap="xs" p="sm" className="border-b border-bordure" wrap="wrap">
          <FiltreMenu icone={Tag} libelle="Statut" selection={filtres.statut} onChange={maj("statut")}
            options={options("statut", (v) => SEGMENTS[v].libelle, (v) => COULEURS_SEGMENT[v])} />
          <FiltreMenu icone={Building2} libelle="Secteur NAT" selection={filtres.secteur} onChange={maj("secteur")} options={options("secteur", libelleSecteur)} />
          <FiltreMenu icone={MapPin} libelle="Gouvernorat" selection={filtres.gouvernorat} onChange={maj("gouvernorat")} options={options("gouvernorat", (v) => v)} />
          <FiltreMenu icone={Gavel} libelle="Action" selection={filtres.action} onChange={maj("action")} options={options("action", (v) => v)} />
          {filtresActifs && (
            <Button variant="subtle" size="compact-sm" onClick={() => setFiltres({ statut: [], secteur: [], gouvernorat: [], action: [], recherche: "" })}>Réinitialiser</Button>
          )}
          <TextInput className="ml-auto w-full @3xl:w-[280px]" size="sm" value={filtres.recherche} onChange={(e) => maj("recherche")(e.currentTarget.value)}
            placeholder="Nom, matricule, code NAT…" leftSection={<Search size={14} />} aria-label="Filtrer la liste" />
        </Group>

        <Table.ScrollContainer minWidth={560} type="native">
          <Table highlightOnHover verticalSpacing={10} fz="sm">
            <Table.Thead className="bg-fond">
              <Table.Tr>
                <Table.Th w={44}><span className="sr-only">Suivi</span></Table.Th>
                {COLONNES.map((c) => (
                  <Table.Th key={c.cle} className={`${c.num ? "text-right" : ""} ${c.cache ?? ""}`}
                    aria-sort={tri.cle === c.cle ? (tri.sens === "asc" ? "ascending" : "descending") : "none"}>
                    <UnstyledButton onClick={() => trier(c.cle)} className={`inline-flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold ${tri.cle === c.cle ? "text-encre" : "text-attenue hover:text-encre"}`}>
                      {c.libelle}
                      {tri.cle === c.cle ? (tri.sens === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ChevronsUpDown size={12} className="opacity-50" />}
                    </UnstyledButton>
                  </Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {pageLignes.map((e) => {
                const delta = Number(e.risk_delta_2m);
                const suivie = favoris.includes(e.mf);
                return (
                  <Table.Tr key={e.mf} onClick={() => navigate(`/entreprise/${e.mf}`)} className="cursor-pointer">
                    <Table.Td>
                      <ActionIcon size="sm" onClick={(ev) => { ev.stopPropagation(); basculerFavori(e.mf); }}
                        aria-label={suivie ? `Ne plus suivre ${e.company_name}` : `Suivre ${e.company_name}`} aria-pressed={suivie}>
                        <Star size={14} fill={suivie ? "var(--seg-surv)" : "none"} stroke={suivie ? "var(--seg-surv)" : "currentColor"} />
                      </ActionIcon>
                    </Table.Td>
                    <Table.Td className="max-w-[190px] @3xl:max-w-[300px]">
                      <Text component={Link} to={`/entreprise/${e.mf}`} onClick={(ev) => ev.stopPropagation()} title={e.company_name}
                        size="sm" fw={600} truncate="end" className="block hover:underline">{e.company_name}</Text>
                    </Table.Td>
                    <Table.Td className="chiffres whitespace-nowrap text-right">
                      <Text span fw={700} size="sm">{e.current_risk_score}</Text>{" "}
                      <Text span size="xs" fw={delta >= 10 ? 700 : 400} c={delta >= 10 ? "red.7" : "dimmed"}>{e.risk_delta_2m}</Text>
                    </Table.Td>
                    <Table.Td className="w-px whitespace-nowrap"><Pastille segment={e.segment} /></Table.Td>
                    <Table.Td className="chiffres whitespace-nowrap text-right">{e.recoupment_gap_dt ? fmtCompact(e.recoupment_gap_dt) : "—"}</Table.Td>
                    <Table.Td className="hidden w-full max-w-0 @3xl:table-cell">
                      <Text size="sm" c="dimmed" truncate="end" title={e.primary_trigger}>{e.primary_trigger}</Text>
                    </Table.Td>
                    <Table.Td className="hidden whitespace-nowrap text-encre-2 @5xl:table-cell">{e.recommended_action}</Table.Td>
                    <Table.Td className="hidden whitespace-nowrap font-mono text-[12px] text-encre-2 @6xl:table-cell">{e.company_id}</Table.Td>
                    <Table.Td className="chiffres hidden whitespace-nowrap text-encre-2 @6xl:table-cell" title={e.sector_nacef}>{e.sector_nacef.split(" - ")[0]}</Table.Td>
                    <Table.Td className="hidden whitespace-nowrap text-encre-2 @7xl:table-cell">{e.gouvernorat}</Table.Td>
                  </Table.Tr>
                );
              })}
              {!lignes.length && (
                <Table.Tr><Table.Td colSpan={COLONNES.length + 1}><Text ta="center" c="dimmed" py="xl">Aucune entreprise ne correspond à ces filtres.</Text></Table.Td></Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>

        <Group justify="space-between" p="sm" className="border-t border-bordure" wrap="wrap" gap="sm">
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              {lignes.length ? `${(debut + 1).toLocaleString("fr-FR")}–${Math.min(debut + Number(taille), lignes.length).toLocaleString("fr-FR")} sur ${lignes.length.toLocaleString("fr-FR")}` : "0 résultat"}
            </Text>
            <Select size="xs" w={118} value={taille} onChange={(v) => v && setTaille(v)} allowDeselect={false} aria-label="Lignes par page"
              data={[{ value: "25", label: "25 par page" }, { value: "50", label: "50 par page" }, { value: "100", label: "100 par page" }]} />
          </Group>
          <Pagination size="sm" total={nbPages} value={Math.min(page, nbPages)} onChange={setPage} siblings={1} boundaries={1}
            getControlProps={(c) => ({ "aria-label": c === "previous" ? "Page précédente" : c === "next" ? "Page suivante" : c })} />
        </Group>
      </Paper>
    </div>
  );
}
