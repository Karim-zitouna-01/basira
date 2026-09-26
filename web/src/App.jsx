import { useEffect, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
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
  // Copilote ouvert d'office sur la fiche entreprise, fermé sur la liste
  const [copiloteOuvert, setCopiloteOuvert] = useState(surFiche);
  const [palette, setPalette] = useState(lirePalette);
  // Barre latérale : pleine ou réduite à un rail d'icônes. Choix de l'utilisateur, sinon réduite d'office
  // quand le copilote est ouvert sur un écran de moins de 1700 px (la page garde sa largeur utile)
  const [choixRail, setChoixRail] = useState(null);
  const ecranLarge = useMediaQuery("(min-width: 1700px)");
  const rail = choixRail ?? (copiloteOuvert && !ecranLarge);

  useEffect(() => { setCopiloteOuvert(surFiche); }, [surFiche]);
  useEffect(() => { setChoixRail(null); }, [copiloteOuvert]);
  useEffect(() => {
    document.documentElement.dataset.palette = palette;
    try { localStorage.setItem("palette", palette); } catch { /* stockage indisponible */ }
  }, [palette]);

  const copilote = { ouvert: copiloteOuvert, basculer: () => setCopiloteOuvert((o) => !o) };

  return (
    <ContextePageProvider>
      <AppShell
        padding={0}
        navbar={{ width: rail ? 68 : 256, breakpoint: 0 }}
        aside={{ width: { base: 360, xl: 420 }, breakpoint: 0, collapsed: { desktop: !copiloteOuvert, mobile: !copiloteOuvert } }}
        transitionDuration={180}
        styles={{ main: { background: "var(--fond)" }, navbar: { background: "var(--carte)" }, aside: { background: "var(--carte)" } }}
      >
        <AppShell.Navbar>
          <BarreLaterale rail={rail} onRail={() => setChoixRail(!rail)} palette={palette} onPalette={setPalette} />
        </AppShell.Navbar>
        <AppShell.Main>
          <Routes>
            <Route path="/" element={<ListeEntreprises copilote={copilote} palette={palette} />} />
            <Route path="/entreprise/:mf" element={<FicheEntreprise copilote={copilote} palette={palette} />} />
          </Routes>
        </AppShell.Main>
        <AppShell.Aside>
          {copiloteOuvert && <ChatDrawer onFermer={() => setCopiloteOuvert(false)} />}
        </AppShell.Aside>
      </AppShell>
    </ContextePageProvider>
  );
}
