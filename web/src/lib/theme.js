// Thème Mantine : mêmes couleurs et polices que les jetons CSS de l'interface (src/index.css).
import { createTheme } from "@mantine/core";

const bleu = ["#eff6ff", "#dbeafe", "#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8", "#1e40af", "#1e3a8a"];
const ardoise = ["#f8fafc", "#f1f5f9", "#e2e8f0", "#cbd5e1", "#94a3b8", "#64748b", "#475569", "#334155", "#1e293b", "#0f172a"];

export const theme = createTheme({
  primaryColor: "basira",
  primaryShade: 6,
  colors: { basira: bleu, ardoise },
  fontFamily: '"Public Sans", "Segoe UI", system-ui, sans-serif',
  fontFamilyMonospace: '"IBM Plex Mono", ui-monospace, Menlo, monospace',
  headings: { fontFamily: '"Public Sans", "Segoe UI", system-ui, sans-serif', fontWeight: "700" },
  defaultRadius: "md",
  fontSizes: { xs: "11.5px", sm: "13px", md: "14px", lg: "16px", xl: "20px" },
  components: {
    Card: { defaultProps: { withBorder: true, radius: "lg", padding: "lg" } },
    Paper: { defaultProps: { radius: "lg" } },
    Tooltip: { defaultProps: { withArrow: true, openDelay: 250, multiline: true, maw: 320, fz: "xs" } },
    Badge: { defaultProps: { radius: "sm", fw: 600 }, styles: { root: { textTransform: "none" } } },
    Button: { defaultProps: { radius: "md" } },
    ActionIcon: { defaultProps: { variant: "subtle", color: "ardoise" } },
    Table: { defaultProps: { verticalSpacing: "sm", horizontalSpacing: "md", highlightOnHover: true } }
  }
});

// Couleurs de statut (mêmes valeurs que --seg-* de la palette A)
export const COULEURS_SEGMENT = { PRIORITAIRE: "#dc2626", SURVEILLANCE: "#e08a00", NORMAL: "#9aa5b8", CONFIANCE: "#047857" };
