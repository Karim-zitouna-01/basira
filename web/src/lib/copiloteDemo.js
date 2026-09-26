// Réponses simulées du copilote, construites uniquement à partir du contexte de la page.
// À remplacer par POST /api/assistant (contrat §6.2) : même entrée { question, contexte }.
import { fmtCompact, fmtDT, fmtMoisIso } from "./format.js";

const liste = (items) => items.map((t) => `• ${t}`).join("\n");

function descriptionFiltres(f) {
  const parts = [];
  if (f.periode) parts.push(`période ${fmtMoisIso(f.periode.debut)} → ${fmtMoisIso(f.periode.fin)}`);
  if (f.systemes.length) parts.push(`systèmes ${f.systemes.join(", ")}`);
  if (f.contreparties.length) parts.push(`contreparties ${f.contreparties.join(", ")}`);
  if (f.pays.length) parts.push(`pays ${f.pays.join(", ")}`);
  return parts.length ? `Sélection affichée (${parts.join(" ; ")})` : "Sélection affichée (aucun filtre, 12 mois)";
}

function reponseFiche(question, c, intention) {
  const e = c.entreprise;
  const s = c.selection;
  const signalees = s.principales_contreparties.filter((p) => p.signalee);
  const entete = `${descriptionFiltres(c.filtres_actifs)} : ${s.nb_operations} opérations, ${fmtCompact(s.total_dt)}.`;

  if (intention === "rapport") {
    return [
      `PRÉ-RAPPORT D'AUDIT — ${e.company_name} (MF ${e.company_id})`,
      `Secteur : ${e.sector_nacef}. Gouvernorat : ${e.gouvernorat}.`,
      `1. Constat : score de risque ${e.current_risk_score}/100 (${e.risk_delta_2m} en 2 mois), statut ${e.risk_status}.`,
      `2. Déclencheur principal : ${e.primary_trigger}.`,
      `3. Écart de recoupement estimé : ${fmtDT(e.recoupment_gap_dt)}.`,
      `4. Éléments examinés : ${entete}`,
      signalees.length ? `5. Contreparties signalées : ${signalees.map((p) => `${p.contrepartie} (${fmtCompact(p.montant_dt)})`).join(", ")}.` : "5. Aucune contrepartie signalée dans la sélection.",
      `6. Suite proposée : ${e.recommended_action}. La décision appartient à l'inspecteur.`
    ].join("\n");
  }

  if (intention === "conformite") {
    return [
      `Points de conformité à vérifier pour ${e.company_name}, d'après les données affichées :`,
      liste([
        s.par_systeme.SINDA ? `Importations SINDA : ${fmtCompact(s.par_systeme.SINDA)}. Contrôle de la valeur déclarée et du circuit au titre du Code des Douanes.` : null,
        s.par_systeme.ADEB ? `Paiements publics ADEB : ${fmtCompact(s.par_systeme.ADEB)}. Vérifier l'application de la retenue à la source et le rattachement au CA déclaré.` : null,
        s.par_systeme.TJ ? `Flux Plateforme TJ : ${fmtCompact(s.par_systeme.TJ)}. Rapprocher les factures électroniques des déclarations.` : null,
        s.par_systeme.RAFIK ? `Arriérés RAFIK : ${fmtCompact(s.par_systeme.RAFIK)}.` : null
      ].filter(Boolean)),
      "Les références d'articles précises (LOB 2019-15, Code des Douanes) seront citées par le copilote connecté à la base documentaire."
    ].join("\n");
  }

  const i = c.indicateurs;
  const p = c.periode;
  const libellePeriode = p ? (p.debut === p.fin ? fmtMoisIso(p.debut) : `${fmtMoisIso(p.debut)} → ${fmtMoisIso(p.fin)}`) : "";
  const pointsCles = i
    ? [
        `Sur la période affichée (${libellePeriode}) : score ${i.score_fin_periode}/100 (${i.score_fin_periode - i.score_reference >= 0 ? "+" : ""}${i.score_fin_periode - i.score_reference} pts), écart de recoupement ${fmtCompact(i.ecart_recoupement_periode_dt)}${i.ecart_periode_precedente_dt !== null ? ` contre ${fmtCompact(i.ecart_periode_precedente_dt)} sur la période précédente` : ""}.`,
        `Flux observés : ${fmtCompact(i.flux_observes_dt)}${i.flux_periode_precedente_dt !== null ? ` contre ${fmtCompact(i.flux_periode_precedente_dt)} sur la période précédente` : ""}.`,
        `Situation au dernier mois : score ${e.current_risk_score}/100 (${e.risk_delta_2m} sur 2 mois). Déclencheur principal : ${e.primary_trigger}.`
      ]
    : [
        `Score ${e.current_risk_score}/100, évolution ${e.risk_delta_2m} sur 2 mois.`,
        `Déclencheur principal : ${e.primary_trigger}.`,
        `Écart de recoupement : ${fmtDT(e.recoupment_gap_dt)}.`
      ];
  const repartition = Object.entries(s.par_systeme).filter(([, v]) => v > 0).map(([k, v]) => `${k} ${fmtCompact(v)}`);
  return [
    intention === "anomalie" ? `Explication de l'anomalie de recoupement pour ${e.company_name} :` : `À propos de « ${question} » :`,
    liste(pointsCles),
    entete,
    repartition.length ? `Répartition par système : ${repartition.join(", ")}.` : "",
    signalees.length
      ? `Contreparties signalées dans cette sélection : ${signalees.map((p) => `${p.contrepartie} (${fmtCompact(p.montant_dt)})`).join(", ")}, soit ${s.part_signalee_pct} % du montant affiché.`
      : "Aucune contrepartie signalée dans cette sélection.",
    `Action recommandée : ${e.recommended_action}.`
  ].filter(Boolean).join("\n");
}

function reponseListe(question, c) {
  const top = c.entreprises_affichees.slice(0, 5);
  return [
    `Sur les ${c.nb_affichees} entreprises affichées${c.filtres.segment ? ` (filtre : ${c.filtres.segment})` : ""}${c.filtres.recherche ? `, recherche « ${c.filtres.recherche} »` : ""} :`,
    liste(top.map((e) => `${e.nom} : score ${e.score} (${e.delta}), écart ${fmtCompact(e.ecart_dt)}, ${e.action}.`)),
    `Écart de recoupement cumulé affiché : ${fmtCompact(c.ecart_total_dt)}.`,
    "Ouvrez une fiche pour analyser les opérations d'une entreprise."
  ].join("\n");
}

export function repondreDemo(question, contexte, intention = "libre") {
  if (!contexte) return "Aucune donnée n'est affichée pour le moment.";
  return contexte.page === "fiche_entreprise" ? reponseFiche(question, contexte, intention) : reponseListe(question, contexte);
}
