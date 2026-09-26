import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/public-sans/400.css";
import "@fontsource/public-sans/500.css";
import "@fontsource/public-sans/600.css";
import "@fontsource/public-sans/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "../node_modules/dc/dist/style/dc.css";
import "./index.css";
import "@mantine/core/styles.layer.css";
import "@xyflow/react/dist/style.css";
import { MantineProvider } from "@mantine/core";
import { theme } from "./lib/theme.js";
import { chargerPortefeuille, modeApi } from "./lib/donnees.js";

const racine = createRoot(document.getElementById("root"));
const message = (texte) => racine.render(<div className="grid h-full place-items-center p-6 text-center text-[14px] text-encre-2">{texte}</div>);

// Le portefeuille est chargé avant d'importer l'application : les pages lisent `meta` au chargement du module
message(modeApi ? "Chargement du portefeuille…" : "Chargement…");
chargerPortefeuille()
  .then(() => import("./App.jsx"))
  .then(({ default: App }) =>
    racine.render(
      <StrictMode>
        <MantineProvider theme={theme} defaultColorScheme="light">
        <BrowserRouter>
          <App />
        </BrowserRouter>
        </MantineProvider>
      </StrictMode>
    )
  )
  .catch((err) => message(`Impossible de joindre l'API Basira (${err.message}). Lancer l'API, ou vider VITE_API_URL pour le jeu fictif.`));
