// Liaison copilote → graphe : pendant que l'assistant travaille, chaque outil de réseau qu'il appelle envoie une action
// (calculée par l'API à partir des données, jamais par le modèle) que le graphe de la fiche applique aussitôt.
import { useEffect, useRef } from "react";

const EVENEMENT = "basira:copilote-graphe";

export function publierActionGraphe(action) {
  if (action) window.dispatchEvent(new CustomEvent(EVENEMENT, { detail: action }));
}

// `surAction(action)` est appelé pour les actions qui concernent l'entreprise `mf`
export function useActionsGraphe(mf, surAction) {
  const rappel = useRef(surAction);
  useEffect(() => { rappel.current = surAction; });
  useEffect(() => {
    const ecouter = (e) => { if (e.detail?.mf === mf) rappel.current(e.detail); };
    window.addEventListener(EVENEMENT, ecouter);
    return () => window.removeEventListener(EVENEMENT, ecouter);
  }, [mf]);
}
