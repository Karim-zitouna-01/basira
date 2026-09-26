// Utilitaires DC.js partagés : redimensionnement, style « référence » (barres arrondies).
import { useEffect } from "react";
import * as dc from "dc";

// Redessine un groupe de graphiques quand la largeur du conteneur change
// (ouverture / fermeture du copilote, redimensionnement de la fenêtre).
export function useRedimensionnement(ref, groupeRef) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let largeur = el.clientWidth;
    let minuterie;
    const obs = new ResizeObserver(() => {
      const l = el.clientWidth;
      if (!l || Math.abs(l - largeur) < 4 || !groupeRef.current) return;
      largeur = l;
      clearTimeout(minuterie);
      minuterie = setTimeout(() => {
        dc.chartRegistry.list(groupeRef.current).forEach((c) => c.width && c.width(null));
        dc.renderAll(groupeRef.current);
      }, 180);
    });
    obs.observe(el);
    return () => { obs.disconnect(); clearTimeout(minuterie); };
  }, [ref, groupeRef]);
}

// Arrondit les barres (verticales ou horizontales) après chaque rendu
export const arrondirBarres = (rayon = 5) => (chart) => {
  chart.selectAll("rect.bar, g.row rect").attr("rx", rayon).attr("ry", rayon);
};

let compteur = 0;
export const nouveauGroupe = (prefixe) => `${prefixe}-${++compteur}`;
