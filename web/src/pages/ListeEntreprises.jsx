// Page d'accueil (design_references/reference 1) : indicateurs globaux du portefeuille
// + liste des entreprises. Un seul crossfilter (entreprise × mois) alimente les cartes,
// leurs mini-courbes DC.js, les effectifs des filtres et la table.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as d3 from "d3";
import crossfilter from "crossfilter2";
import * as dc from "dc";
import "../lib/dcCompat.js";
import { ArrowDown, ArrowUp, Building2, ChevronsUpDown, Gauge, Gavel, MapPin, Scale, Search, ShieldAlert, Ship, Star, Tag } from "lucide-react";
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
const LIGNES_MAX = 200; // le portefeuille réel compte 5 250 entreprises : la table n'en rend qu'une partie
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

  return (
    <div ref={racineRef} className="@container flex flex-col gap-4 px-6 py-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-2">
          <h1 className="flex items-center gap-2 text-[17px] font-bold text-encre"><Building2 size={17} aria-hidden="true" />Entreprises</h1>
          <span className="text-[13px] text-attenue">
            · {lignes.length === entreprises.length ? `${entreprises.length} entreprises` : `${lignes.length} sur ${entreprises.length} entreprises`} · situation au {fmtMoisIso(DERNIER)}
          </span>
        </div>
        <BoutonCopilote copilote={copilote} />
      </header>

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

      {/* Barre d'outils : filtres crossfilter + recherche */}
      <div className="flex flex-wrap items-center gap-2">
        <FiltreMenu icone={Tag} libelle="Statut" selection={filtres.statut} onChange={maj("statut")}
          options={options("statut", (v) => SEGMENTS[v].libelle, (v) => `var(--seg-${SEGMENTS[v].jeton})`)} />
        <FiltreMenu icone={Building2} libelle="Secteur NAT" selection={filtres.secteur} onChange={maj("secteur")} options={options("secteur", libelleSecteur)} />
        <FiltreMenu icone={MapPin} libelle="Gouvernorat" selection={filtres.gouvernorat} onChange={maj("gouvernorat")} options={options("gouvernorat", (v) => v)} />
        <FiltreMenu icone={Gavel} libelle="Action recommandée" selection={filtres.action} onChange={maj("action")} options={options("action", (v) => v)} />
        {filtresActifs && (
          <button type="button" onClick={() => setFiltres({ statut: [], secteur: [], gouvernorat: [], action: [], recherche: "" })}
            className="px-1 text-[12.5px] font-semibold text-action-texte">Réinitialiser</button>
        )}
        <div className="relative ml-auto w-full max-w-[300px]">
          <label htmlFor="recherche-liste" className="sr-only">Filtrer la liste</label>
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-attenue" aria-hidden="true" />
          <input id="recherche-liste" type="search" value={filtres.recherche} onChange={(e) => maj("recherche")(e.target.value)}
            placeholder="Filtrer : nom, matricule, code NAT…"
            className="w-full rounded-md border border-bordure bg-carte py-1.5 pl-8 pr-2 text-[13px] placeholder:text-attenue" />
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-bordure bg-carte">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-bordure text-left text-[12px] text-attenue">
              <th className="w-9 px-2.5 py-2.5"><span className="sr-only">Suivi</span></th>
              {COLONNES.map((c) => (
                <th key={c.cle} className={`whitespace-nowrap px-2.5 py-2.5 font-medium ${c.num ? "text-right" : ""} ${c.cache ?? ""}`}
                  aria-sort={tri.cle === c.cle ? (tri.sens === "asc" ? "ascending" : "descending") : "none"}>
                  <button type="button" onClick={() => trier(c.cle)} className={`inline-flex items-center gap-1 hover:text-encre ${tri.cle === c.cle ? "text-encre" : ""}`}>
                    {c.libelle}
                    {tri.cle === c.cle ? (tri.sens === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ChevronsUpDown size={12} className="opacity-50" />}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lignes.slice(0, LIGNES_MAX).map((e) => {
              const delta = Number(e.risk_delta_2m);
              const suivie = favoris.includes(e.mf);
              return (
                <tr key={e.mf} onClick={() => navigate(`/entreprise/${e.mf}`)} className="cursor-pointer border-t border-bordure hover:bg-fond">
                  <td className="px-2.5 py-2">
                    <button type="button" onClick={(ev) => { ev.stopPropagation(); basculerFavori(e.mf); }}
                      aria-label={suivie ? `Ne plus suivre ${e.company_name}` : `Suivre ${e.company_name}`} aria-pressed={suivie}
                      className="grid size-6 place-items-center rounded text-attenue hover:bg-fond-2">
                      <Star size={14} fill={suivie ? "var(--seg-surv)" : "none"} stroke={suivie ? "var(--seg-surv)" : "currentColor"} />
                    </button>
                  </td>
                  <td className="max-w-[190px] truncate px-2.5 py-2 @3xl:max-w-[300px]">
                    <Link to={`/entreprise/${e.mf}`} onClick={(ev) => ev.stopPropagation()} title={e.company_name} className="font-semibold text-encre hover:underline">{e.company_name}</Link>
                  </td>
                  <td className="chiffres whitespace-nowrap px-2.5 py-2 text-right">
                    <span className="font-semibold text-encre">{e.current_risk_score}</span>{" "}
                    <span className={delta >= 10 ? "font-semibold text-prio-texte" : "text-attenue"}>{e.risk_delta_2m}</span>
                  </td>
                  <td className="px-2.5 py-2"><Pastille segment={e.segment} /></td>
                  <td className="chiffres whitespace-nowrap px-2.5 py-2 text-right text-encre">{e.recoupment_gap_dt ? fmtCompact(e.recoupment_gap_dt) : "—"}</td>
                  <td className="hidden w-full min-w-[160px] max-w-0 truncate px-2.5 py-2 text-encre-2 @3xl:table-cell" title={e.primary_trigger}>{e.primary_trigger}</td>
                  <td className="hidden whitespace-nowrap px-2.5 py-2 text-encre-2 @5xl:table-cell">{e.recommended_action}</td>
                  <td className="hidden whitespace-nowrap px-2.5 py-2 font-mono text-[12px] text-encre-2 @6xl:table-cell">{e.company_id}</td>
                  <td className="chiffres hidden whitespace-nowrap px-2.5 py-2 text-encre-2 @6xl:table-cell" title={e.sector_nacef}>{e.sector_nacef.split(" - ")[0]}</td>
                  <td className="hidden whitespace-nowrap px-2.5 py-2 text-encre-2 @7xl:table-cell">{e.gouvernorat}</td>
                </tr>
              );
            })}
            {!lignes.length && (
              <tr><td colSpan={COLONNES.length + 1} className="px-4 py-10 text-center text-attenue">Aucune entreprise ne correspond à ces filtres.</td></tr>
            )}
            {lignes.length > LIGNES_MAX && (
              <tr><td colSpan={COLONNES.length + 1} className="px-4 py-3 text-center text-[12.5px] text-attenue">
                {LIGNES_MAX} premières lignes affichées sur {lignes.length} : affinez avec les filtres ou la recherche.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
