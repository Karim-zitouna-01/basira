// Fiche entreprise (design_references/reference 2) : indicateurs + grille de graphiques
// DC.js / D3 reliés par Crossfilter. Deux crossfilters partagent la période :
//  - historique mensuel (CA déclaré, score, écart) ;
//  - opérations unitaires (SINDA, ADEB, Plateforme TJ, RAFIK).
// Choisir une période (sélecteur, glisser sur « Déclaré vs observé », clic sur un mois du score)
// filtre les deux ; cliquer un système ou une contrepartie filtre les opérations partout.
import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import crossfilter from "crossfilter2";
import * as dc from "dc";
import "../lib/dcCompat.js";
import { Card, Group, Text, ThemeIcon } from "@mantine/core";
import { AlertTriangle, Gauge, History, ListChecks, Network, Scale, Waypoints } from "lucide-react";
import { SOURCES, SEGMENTS, jeton } from "../lib/palettes.js";
import { meta, modeApi } from "../lib/donnees.js";
import { arrondirBarres, nouveauGroupe, useRedimensionnement } from "../lib/dcOutils.js";
import { fmtCompact, fmtDT, fmtDate, fmtMois, fmtMoisIso } from "../lib/format.js";
import CarteKpi from "./CarteKpi.jsx";
import GrapheReseau from "./GrapheReseau.jsx";
import TableOperations from "./TableOperations.jsx";

const auMois = (m) => new Date(`${m}-01T00:00:00`);
const versIso = d3.timeFormat("%Y-%m");
const signe = (v) => (v >= 0 ? "+" : "");

function Carte({ titre, icone: Icone, aide, actions, children, className = "", id }) {
  return (
    <Card component="section" id={id} className={`flex min-w-0 flex-col gap-2 scroll-mt-4 ${className}`}>
      <Group justify="space-between" gap="xs" wrap="wrap">
        <Group gap={8} wrap="nowrap">
          {Icone && <ThemeIcon variant="light" color="ardoise" size={28} radius="md"><Icone size={15} /></ThemeIcon>}
          <Text component="h3" fw={700} size="md">{titre}</Text>
        </Group>
        {actions}
      </Group>
      {aide && <Text size="xs" c="dimmed">{aide}</Text>}
      {children}
    </Card>
  );
}

const Legende = ({ items }) => (
  <div className="flex flex-wrap gap-3 text-[12px] text-encre-2">
    {items.map(([libelle, couleur, pointille]) => (
      <span key={libelle} className="inline-flex items-center gap-1.5">
        <svg width="16" height="8" aria-hidden="true"><line x1="0" y1="4" x2="16" y2="4" stroke={couleur} strokeWidth="2.5" strokeDasharray={pointille ? "4 3" : undefined} /></svg>
        {libelle}
      </span>
    ))}
  </div>
);

// Événements de l'historique : changements de statut, contrôles, sessions du copilote
function evenementsHistorique(e) {
  const ev = [];
  e.historique_mensuel.forEach((h, i) => {
    const prec = e.historique_mensuel[i - 1];
    if (prec && prec.segment !== h.segment) {
      ev.push({ date: `${h.mois}-01`, type: "statut", segment: h.segment, texte: `Passage en « ${SEGMENTS[h.segment].libelle} » (score ${prec.score} → ${h.score})` });
    }
  });
  e.controles_passes.forEach((c) => ev.push({ date: c.date, type: "controle", texte: `${c.type} : ${c.resultat}${c.montant_redresse_dt ? ` (${fmtDT(c.montant_redresse_dt)} redressés)` : ""}` }));
  meta.sessions_copilote.filter((s) => s.mf === e.mf).forEach((s) => ev.push({ date: s.date, type: "session", texte: `Session copilote : ${s.titre}` }));
  return ev.sort((a, b) => b.date.localeCompare(a.date));
}

export default function DashboardVisualizations({ entreprise, palette, periode, onPeriode, onSelection, insertion }) {
  const refs = {
    tendance: useRef(null), score: useRef(null), systemes: useRef(null),
    contreparties: useRef(null), comptage: useRef(null), table: useRef(null)
  };
  const racineRef = useRef(null);
  const groupeRef = useRef(null);
  const api = useRef({});
  const [montants, setMontants] = useState(new Map());
  const [filtres, setFiltres] = useState({ systemes: [], contreparties: [] });
  const [kpis, setKpis] = useState(null);
  const [ops, setOps] = useState({ lignes: [], total: 0 });

  useEffect(() => {
    const groupe = nouveauGroupe("fiche");
    groupeRef.current = groupe;
    const moisListe = entreprise.historique_mensuel.map((h) => h.mois);
    const debut = auMois(moisListe[0]);
    const fin = d3.timeMonth.offset(auMois(moisListe.at(-1)), 1);
    const segmentDuMois = new Map(entreprise.historique_mensuel.map((h) => [+auMois(h.mois), h.segment]));
    const signalees = new Map(entreprise.operations.map((o) => [o.contrepartie, o.contrepartie_signalee]));
    const c = {
      encre: jeton("--encre"), encre2: jeton("--encre-2"), attenue: jeton("--attenue"),
      fond2: jeton("--fond-2"), action: jeton("--action"), prio: jeton("--seg-prio"), surv: jeton("--seg-surv")
    };
    const couleurSource = d3.scaleOrdinal(SOURCES.map((s) => s.id), SOURCES.map((s) => jeton(s.jeton)));
    const couleurSegment = (s) => jeton(`--seg-${SEGMENTS[s].jeton}`);
    const axeCompact = (v) => fmtCompact(v).replace(" DT", "");

    // --- Crossfilter de l'historique mensuel ---
    const cfH = crossfilter(entreprise.historique_mensuel.map((h) => ({ ...h, moisDate: auMois(h.mois) })));
    const dimMoisH = cfH.dimension((h) => h.moisDate);
    const caParMois = dimMoisH.group().reduceSum((h) => h.ca_declare_dt);
    const scoreParMois = dimMoisH.group().reduceSum((h) => h.score);

    // --- Crossfilter des opérations ---
    const cfO = crossfilter(entreprise.operations.map((o) => ({ ...o, jour: new Date(`${o.date}T00:00:00`), moisDate: auMois(o.mois) })));
    const dimMoisO = cfO.dimension((o) => o.moisDate);
    const dimSource = cfO.dimension((o) => o.source);
    const dimContrepartie = cfO.dimension((o) => o.contrepartie);
    const groupeFlux = dimMoisO.group().reduceSum((o) => o.montant_dt);
    // Tous les mois présents (0 si aucune opération) : sinon une entreprise aux flux concentrés sur un seul mois
    // (annexe V annuelle) n'a qu'un point et DC.js ne trace aucune courbe
    const observeParMois = {
      all: () => {
        const m = new Map(groupeFlux.all().map((d) => [+d.key, d.value]));
        return moisListe.map((mm) => ({ key: auMois(mm), value: m.get(+auMois(mm)) ?? 0 }));
      }
    };

    // 1. Déclaré vs observé (glisser pour choisir la période)
    const tendance = new dc.CompositeChart(refs.tendance.current, groupe);
    tendance
      .height(230).margins({ top: 10, right: 12, bottom: 24, left: 44 })
      .dimension(dimMoisH)
      .x(d3.scaleTime().domain([debut, fin])).round(d3.timeMonth.round).xUnits(d3.timeMonths)
      .elasticY(true).yAxisPadding("10%").renderHorizontalGridLines(true).brushOn(true)
      .compose([
        new dc.LineChart(tendance).group(observeParMois, "Flux observés").colors(c.action)
          .curve(d3.curveMonotoneX).renderArea(true).title((d) => `${fmtMois(d.key)} · flux observés : ${fmtDT(d.value)}`),
        new dc.LineChart(tendance).group(caParMois, "CA déclaré").colors(c.attenue).dashStyle([5, 4])
          .curve(d3.curveMonotoneX).title((d) => `${fmtMois(d.key)} · CA déclaré : ${fmtDT(d.value)}`)
      ]);
    tendance.xAxis().ticks(d3.timeMonth.every(2)).tickFormat(fmtMois);
    tendance.yAxis().ticks(4).tickFormat(axeCompact);

    // Période : le filtre de « tendance » (historique) est recopié sur les opérations
    tendance.on("filtered.periode", (ch) => {
      const plage = ch.filters()[0];
      if (plage) dimMoisO.filterRange([plage[0], plage[1]]); else dimMoisO.filterAll();
      onPeriode?.(plage ? { debut: versIso(plage[0]), fin: versIso(d3.timeMonth.offset(plage[1], -1)) } : null);
      publier();
      dc.redrawAll(groupe);
    });
    const appliquerPeriode = (p) => {
      const actuel = tendance.filters()[0];
      const cle = (r) => (r ? `${+r[0]}-${+r[1]}` : "");
      const cible = p ? [auMois(p.debut), d3.timeMonth.offset(auMois(p.fin), 1)] : null;
      if (cle(actuel) === cle(cible)) return;
      tendance.replaceFilter(cible ? dc.filters.RangedFilter(cible[0], cible[1]) : null);
      dc.redrawAll(groupe);
    };

    // 2. Score de risque mensuel : barres colorées par statut, clic = isoler ce mois
    const score = new dc.BarChart(refs.score.current, groupe)
      .height(230).margins({ top: 10, right: 8, bottom: 24, left: 30 })
      .dimension(dimMoisH).group(scoreParMois)
      .x(d3.scaleTime().domain([debut, fin])).round(d3.timeMonth.round).xUnits(d3.timeMonths)
      .y(d3.scaleLinear().domain([0, 100])).gap(5).brushOn(false).renderHorizontalGridLines(true)
      .colorAccessor((d) => segmentDuMois.get(+d.key)) // dc transmet la ligne du groupe (clé = mois)
      .colors((s) => couleurSegment(s ?? "NORMAL"))
      .title((d) => `${fmtMois(d.key)} : score ${d.value} (${SEGMENTS[segmentDuMois.get(+d.key)].libelle})`);
    score.xAxis().ticks(d3.timeMonth.every(3)).tickFormat(fmtMois);
    score.yAxis().tickValues([0, 40, 70, 100]);
    // dc ne branche le clic des barres que sur les axes ordinaux : on le branche ici (axe temporel)
    const isolerMois = (d) => {
      const m = versIso(d.x);
      const p = tendance.filters()[0];
      const memeMois = p && versIso(p[0]) === m && versIso(d3.timeMonth.offset(p[1], -1)) === m;
      appliquerPeriode(memeMois ? null : { debut: m, fin: m });
    };
    // « pretransition » : appliqué avant les transitions de dc, donc toujours à jour
    score.on("pretransition.style", (ch) => {
      arrondirBarres(3)(ch);
      const p = tendance.filters()[0];
      ch.selectAll("rect.bar").attr("opacity", (d) => (!p || (d.x >= p[0] && d.x < p[1]) ? 1 : 0.25)).style("cursor", "pointer")
        .on("click", (_, d) => isolerMois(d));
      ch.select("g.chart-body").selectAll("line.seuil").data([[70, c.prio], [40, c.surv]]).join("line").attr("class", "seuil")
        .attr("x1", 0).attr("x2", ch.xAxisLength()).attr("y1", ([v]) => ch.y()(v)).attr("y2", ([v]) => ch.y()(v))
        .attr("stroke", ([, col]) => col).attr("stroke-dasharray", "4 3").attr("pointer-events", "none");
    });

    // 3. Flux par système source (barres verticales, clic = filtrer)
    const ordreSources = SOURCES.map((s) => s.id);
    const systemes = new dc.BarChart(refs.systemes.current, groupe)
      .height(230).margins({ top: 22, right: 8, bottom: 24, left: 40 })
      .dimension(dimSource).group(dimSource.group().reduceSum((o) => o.montant_dt))
      .x(d3.scaleBand()).xUnits(dc.units.ordinal).ordering((d) => ordreSources.indexOf(d.key))
      .elasticY(true).yAxisPadding("15%").barPadding(0.35).outerPadding(0.2)
      .colors(couleurSource).colorAccessor((d) => d.key)
      .renderLabel(true).label((d) => fmtCompact(d.y).replace(" DT", ""))
      .renderHorizontalGridLines(true)
      .title((d) => `${d.key} : ${fmtDT(d.value)}`);
    systemes.yAxis().ticks(4).tickFormat(axeCompact);
    systemes.on("renderlet.style", arrondirBarres(7));

    // 4. Principales contreparties (barres de progression, clic = filtrer)
    const hauteurLigne = 14;
    const contreparties = new dc.RowChart(refs.contreparties.current, groupe)
      .height(7 * (hauteurLigne + 16) + 14).margins({ top: 4, right: 96, bottom: 4, left: 200 })
      .dimension(dimContrepartie).group(dimContrepartie.group().reduceSum((o) => o.montant_dt))
      .cap(7).othersLabel("Autres contreparties").ordering((d) => -d.value)
      .fixedBarHeight(hauteurLigne).gap(16).elasticX(true).labelOffsetX(-10)
      .colors(d3.scaleOrdinal([true, false], [c.prio, c.action])).colorAccessor((d) => signalees.get(d.key) === true)
      .label((d) => `${signalees.get(d.key) ? "⚠ " : ""}${d.key.length > 28 ? `${d.key.slice(0, 27)}…` : d.key}`)
      .title((d) => `${d.key}${signalees.get(d.key) ? " (contrepartie signalée)" : ""} : ${fmtDT(d.value)}`);
    contreparties.on("renderlet.style", (ch) => {
      const largeur = ch.effectiveWidth();
      const total = d3.sum(ch.data(), (d) => d.value) || 1;
      ch.selectAll("g.axis").style("display", "none");
      // Pistes grises dans un calque à part, derrière les lignes : dc met à jour le premier <rect>
      // de chaque ligne, il ne faut donc rien insérer avant la barre.
      const racine = ch.select("svg > g");
      const calque = racine.select("g.pistes").empty() ? racine.insert("g", ":first-child").attr("class", "pistes") : racine.select("g.pistes");
      const lignes = ch.selectAll("g.row").nodes();
      calque.selectAll("rect").data(lignes).join("rect")
        .attr("transform", (n) => n.getAttribute("transform")).attr("width", largeur).attr("height", hauteurLigne)
        .attr("rx", 7).attr("fill", c.fond2).attr("pointer-events", "none");
      ch.selectAll("g.row").each(function (d) {
        const ligne = d3.select(this);
        ligne.select("text.row").attr("text-anchor", "end").attr("fill", c.encre);
        ligne.selectAll("text.valeur").data([d]).join("text").attr("class", "valeur")
          .attr("x", largeur + 8).attr("y", hauteurLigne / 2).attr("dy", "0.35em").attr("fill", c.encre2)
          .attr("font-size", 11).attr("font-weight", 600)
          .text(`${Math.round((100 * d.value) / total)} % · ${fmtCompact(d.value).replace(" DT", "")}`);
      });
      arrondirBarres(7)(ch);
    });

    // 5. Table des opérations : rendue par React (recherche, tri, pagination) à partir de la sélection crossfilter

    // --- Résumé de la sélection : indicateurs, réseau, pastilles, copilote ---
    function publier() {
      const plage = tendance.filters()[0];
      const moisSel = plage ? moisListe.filter((m) => auMois(m) >= plage[0] && auMois(m) < plage[1]) : moisListe;
      if (!moisSel.length) return;
      const n = moisSel.length;
      const iDebut = moisListe.indexOf(moisSel[0]);
      const moisPrec = iDebut >= n ? moisListe.slice(iDebut - n, iDebut) : [];
      const histo = (liste) => entreprise.historique_mensuel.filter((h) => liste.includes(h.mois));
      const lignes = cfO.allFiltered();
      const lignesPrec = cfO.allFiltered([dimMoisO]).filter((o) => moisPrec.includes(o.mois));
      const somme = (rows) => d3.sum(rows, (o) => o.montant_dt);
      const partSignalee = (rows) => (somme(rows) ? Math.round((100 * somme(rows.filter((o) => o.contrepartie_signalee))) / somme(rows)) : 0);
      const hSel = histo(moisSel);
      const scoreFin = hSel.at(-1).score;
      const scoreRef = iDebut > 0 ? entreprise.historique_mensuel[iDebut - 1] : hSel[0];
      // API : l'enjeu estimé couvre déjà 12 mois glissants → valeur en fin de période (pas de somme)
      const ecart = modeApi ? hSel.at(-1).ecart_recoupement_dt : d3.sum(hSel, (h) => h.ecart_recoupement_dt);
      const ecartPrec = modeApi
        ? (iDebut > 0 ? entreprise.historique_mensuel[iDebut - 1].ecart_recoupement_dt : null)
        : moisPrec.length ? d3.sum(histo(moisPrec), (h) => h.ecart_recoupement_dt) : null;
      const flux = somme(lignes);
      const fluxPrec = moisPrec.length ? somme(lignesPrec) : null;
      const part = partSignalee(lignes);
      const partPrec = moisPrec.length ? partSignalee(lignesPrec) : null;
      const plagePrec = moisPrec.length
        ? (moisPrec.length === 1 ? fmtMoisIso(moisPrec[0]) : `${fmtMoisIso(moisPrec[0])} – ${fmtMoisIso(moisPrec.at(-1))}`)
        : null;
      const libellePrec = plagePrec && `vs ${plagePrec}`;

      const f = { systemes: [...systemes.filters()], contreparties: [...contreparties.filters()] };
      setFiltres(f);
      setMontants(d3.rollup(lignes, (v) => d3.sum(v, (o) => o.montant_dt), (o) => o.contrepartie_id));
      setOps({ lignes, total: cfO.size() });
      const k = {
        periode: { debut: moisSel[0], fin: moisSel.at(-1), nb_mois: n },
        score: { valeur: scoreFin, reference: scoreRef.score, mois_reference: scoreRef.mois },
        ecart: { valeur: ecart, precedent: ecartPrec },
        flux: { valeur: flux, precedent: fluxPrec },
        part_signalee: { valeur: part, precedent: partPrec },
        libellePrec, plagePrec
      };
      setKpis(k);
      const top = d3.rollups(lignes, (v) => ({ montant: somme(v), signalee: v[0].contrepartie_signalee }), (o) => o.contrepartie)
        .sort((a, b) => b[1].montant - a[1].montant).slice(0, 5)
        .map(([contrepartie, v]) => ({ contrepartie, montant_dt: v.montant, signalee: v.signalee }));
      onSelection?.({
        periode: k.periode,
        filtres_actifs: {
          periode: plage ? { debut: moisSel[0], fin: moisSel.at(-1) } : null,
          systemes: f.systemes, contreparties: f.contreparties, pays: []
        },
        indicateurs: {
          score_fin_periode: scoreFin, score_reference: scoreRef.score,
          ecart_recoupement_periode_dt: ecart, ecart_periode_precedente_dt: ecartPrec,
          flux_observes_dt: flux, flux_periode_precedente_dt: fluxPrec,
          part_contreparties_signalees_pct: part
        },
        selection: {
          nb_operations: lignes.length,
          total_dt: flux,
          par_systeme: Object.fromEntries(SOURCES.map((s) => [s.id, somme(lignes.filter((o) => o.source === s.id))])),
          principales_contreparties: top,
          part_signalee_pct: part,
          observations: [...new Set(lignes.map((o) => o.observation).filter(Boolean))]
        }
      });
    }

    const retirer = cfO.onChange(publier);
    api.current = { groupe, systemes, contreparties, tendance, appliquerPeriode };
    dc.renderAll(groupe);
    publier();

    return () => {
      retirer();
      dc.chartRegistry.clear(groupe);
      Object.values(refs).forEach((r) => { if (r.current) r.current.innerHTML = ""; });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entreprise.mf, palette]);

  useRedimensionnement(racineRef, groupeRef);

  // Période choisie dans l'en-tête (sélecteur) → filtre du graphique « Déclaré vs observé »
  useEffect(() => { api.current.appliquerPeriode?.(periode); }, [periode, palette]);

  const a = api.current;
  const retirerFiltre = (cle) => { if (a.groupe) { a[cle].filterAll(); dc.redrawAll(a.groupe); } };
  const basculerContrepartie = (libelle) => { if (a.contreparties) { a.contreparties.filter(libelle); dc.redrawAll(a.groupe); } };
  const pastilles = [
    filtres.systemes.length && ["systemes", `Système : ${filtres.systemes.join(", ")}`],
    filtres.contreparties.length && ["contreparties", `Contrepartie : ${filtres.contreparties.join(", ")}`]
  ].filter(Boolean);

  const variationPct = (v, p) => {
    if (p === null || p === undefined) return { texte: `sur ${kpis.periode.nb_mois} mois` };
    if (!p) return { texte: v ? `contre 0 sur ${kpis.plagePrec}` : `0 également sur ${kpis.plagePrec}` };
    const pct = Math.round((100 * (v - p)) / p);
    return { texte: `${signe(pct)}${pct} % ${kpis.libellePrec}`, sens: pct > 0 ? "hausse" : pct < 0 ? "baisse" : "stable", ton: pct > 0 ? "mauvais" : "bon" };
  };
  const evenements = evenementsHistorique(entreprise);

  return (
    <div ref={racineRef} className="@container flex flex-col gap-4">
      {kpis && (
        <section className="grid grid-cols-2 gap-3 @2xl:grid-cols-4" aria-label="Indicateurs de la période">
          <CarteKpi icone={Gauge} titre="Score de risque" valeur={kpis.score.valeur} unite="/100"
            variation={(() => {
              const dlt = kpis.score.valeur - kpis.score.reference;
              return { texte: `${signe(dlt)}${dlt} pts depuis ${fmtMoisIso(kpis.score.mois_reference)}`, sens: dlt > 0 ? "hausse" : dlt < 0 ? "baisse" : "stable", ton: dlt > 0 ? "mauvais" : "bon" };
            })()} />
          <CarteKpi icone={Scale} titre={modeApi ? "Enjeu estimé" : "Écart de recoupement"} aide={modeApi ? "Droits éludés estimés sur 12 mois glissants, en fin de période" : undefined} valeur={fmtCompact(kpis.ecart.valeur)} variation={variationPct(kpis.ecart.valeur, kpis.ecart.precedent)} />
          <CarteKpi icone={Waypoints} titre="Flux observés" valeur={fmtCompact(kpis.flux.valeur)}
            variation={{ ...variationPct(kpis.flux.valeur, kpis.flux.precedent), ton: "neutre" }} aide={`Somme des opérations ${SOURCES.map((s) => s.id).join(", ")} de la sélection`} />
          <CarteKpi icone={AlertTriangle} titre="Contreparties signalées" valeur={kpis.part_signalee.valeur} unite="% des flux"
            variation={kpis.part_signalee.precedent === null ? { texte: `sur ${kpis.periode.nb_mois} mois` } : (() => {
              const dlt = kpis.part_signalee.valeur - kpis.part_signalee.precedent;
              return { texte: `${signe(dlt)}${dlt} pts ${kpis.libellePrec}`, sens: dlt > 0 ? "hausse" : dlt < 0 ? "baisse" : "stable", ton: dlt > 0 ? "mauvais" : "bon" };
            })()} />
        </section>
      )}

      {pastilles.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {pastilles.map(([cle, texte]) => (
            <button key={cle} type="button" onClick={() => retirerFiltre(cle)} className="rounded-full border border-bordure bg-carte px-2.5 py-1 text-[12px] text-encre-2 hover:border-attenue" title="Retirer ce filtre">
              {texte} <span aria-hidden="true">×</span>
            </button>
          ))}
          <button type="button" onClick={() => { a.systemes.filterAll(); a.contreparties.filterAll(); dc.redrawAll(a.groupe); }} className="text-[12.5px] font-semibold text-action-texte">Tout effacer</button>
        </div>
      )}

      <div className="grid gap-4 @2xl:grid-cols-3">
        <Carte titre="Déclaré vs observé" icone={Scale} className="@2xl:col-span-2"
          aide="Glissez sur le graphique pour choisir une période."
          actions={<Legende items={[["Flux observés", "var(--action)"], ["CA déclaré", "var(--attenue)", true]]} />}>
          <div ref={refs.tendance} />
        </Carte>
        <Carte titre="Score de risque mensuel" icone={Gauge} aide="Cliquez un mois pour l'isoler.">
          <div ref={refs.score} />
        </Carte>
      </div>

      {/* « Pourquoi ce score ? » et décision : juste après la vue d'ensemble chiffrée */}
      {insertion}

      <div className="grid gap-4 @2xl:grid-cols-3">
        <Carte titre="Flux par système" icone={ListChecks} aide="Cliquez un système pour filtrer.">
          <div ref={refs.systemes} />
        </Carte>
        <Carte titre="Principales contreparties" icone={Network} className="@2xl:col-span-2" aide="Part des flux de la sélection. ⚠ contrepartie signalée. Cliquez pour filtrer.">
          <div ref={refs.contreparties} />
        </Carte>
      </div>

      <Carte titre="Réseau de contreparties" icone={Waypoints}
        aide="Qui paie qui sur la période. Cliquez une contrepartie pour comprendre la relation et le motif d'un signalement.">
        <GrapheReseau entreprise={entreprise} montants={montants} contrepartiesFiltrees={filtres.contreparties} onClicContrepartie={basculerContrepartie} palette={palette} />
      </Carte>

      <div className="grid gap-4 @2xl:grid-cols-3">
        <Carte id="operations" titre="Opérations de la sélection" icone={ListChecks} className="@2xl:col-span-2"
          aide="Chaque ligne est une pièce source : déclaration en douane (SINDA), paiement public (ADEB) ou ligne d'annexe V déclarée par un client ou par l'entreprise. Les filtres du haut (période, système, contrepartie) s'appliquent ici.">
          <TableOperations lignes={ops.lignes} total={ops.total} filtres={[...(kpis?.periode && periode ? [["periode", `Période : ${fmtMoisIso(kpis.periode.debut)} → ${fmtMoisIso(kpis.periode.fin)}`]] : []), ...pastilles]}
            onRetirer={(cle) => (cle === "periode" ? onPeriode?.(null) : retirerFiltre(cle))}
            onToutEffacer={() => { a.systemes?.filterAll(); a.contreparties?.filterAll(); if (a.groupe) dc.redrawAll(a.groupe); if (periode) onPeriode?.(null); }} />
        </Carte>
        <Carte titre="Historique" icone={History}>
          <ol className="flex flex-col gap-3">
            {evenements.map((ev, i) => (
              <li key={i} className="flex gap-3 pl-1">
                <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: ev.type === "statut" ? `var(--seg-${SEGMENTS[ev.segment].jeton})` : ev.type === "controle" ? "var(--encre-2)" : "var(--action)" }} />
                <span className="min-w-0">
                  <span className="chiffres block text-[11.5px] text-attenue">{ev.type === "statut" ? fmtMoisIso(ev.date.slice(0, 7)) : fmtDate(ev.date)}</span>
                  <span className="block text-[12.5px] text-encre">{ev.texte}</span>
                </span>
              </li>
            ))}
            {!evenements.length && <li className="text-[12.5px] text-attenue">Aucun événement enregistré.</li>}
          </ol>
        </Carte>
      </div>
    </div>
  );
}
