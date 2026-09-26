// Contexte partagé entre la page affichée et le copilote : chaque page publie
// un résumé compact de ce qu'elle montre (filtres actifs, agrégats visibles).
import { createContext, useContext, useState } from "react";

const Ctx = createContext(null);

export function ContextePageProvider({ children }) {
  const [contexte, setContexte] = useState(null);
  return <Ctx.Provider value={{ contexte, setContexte }}>{children}</Ctx.Provider>;
}

export const useContextePage = () => useContext(Ctx);
