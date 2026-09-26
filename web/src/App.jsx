import { useEffect, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { ContextePageProvider } from "./lib/contextePage.jsx";
import ListeEntreprises from "./pages/ListeEntreprises.jsx";
import FicheEntreprise from "./pages/FicheEntreprise.jsx";
import ChatDrawer from "./components/ChatDrawer.jsx";
import BarreLaterale from "./components/BarreLaterale.jsx";

function lirePalette() {
  try { return localStorage.getItem("palette") || "A"; } catch { return "A"; }
}

export default function App() {
  const { pathname } = useLocation();
  const surFiche = pathname.startsWith("/entreprise/");
  // Copilote ouvert d'office sur la fiche entreprise (référence 2), fermé sur la liste (référence 1)
  const [copiloteOuvert, setCopiloteOuvert] = useState(surFiche);
  const [palette, setPalette] = useState(lirePalette);

  useEffect(() => { setCopiloteOuvert(surFiche); }, [surFiche]);
  useEffect(() => {
    document.documentElement.dataset.palette = palette;
    try { localStorage.setItem("palette", palette); } catch { /* stockage indisponible */ }
  }, [palette]);

  const copilote = { ouvert: copiloteOuvert, basculer: () => setCopiloteOuvert((o) => !o) };

  return (
    <ContextePageProvider>
      <div className="flex h-full">
        <BarreLaterale palette={palette} onPalette={setPalette} />
        {/* Côte à côte : la page se rétrécit quand le copilote s'ouvre, rien n'est recouvert */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<ListeEntreprises copilote={copilote} palette={palette} />} />
            <Route path="/entreprise/:mf" element={<FicheEntreprise copilote={copilote} palette={palette} />} />
          </Routes>
        </main>
        {copiloteOuvert && (
          <aside className="w-[30%] min-w-[340px] max-w-[440px] shrink-0 border-l border-bordure bg-carte">
            <ChatDrawer onFermer={() => setCopiloteOuvert(false)} />
          </aside>
        )}
      </div>
    </ContextePageProvider>
  );
}
