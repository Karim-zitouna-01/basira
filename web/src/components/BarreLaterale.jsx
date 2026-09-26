// Barre latérale : identité, recherche rapide, navigation, dossiers suivis et consultations récentes.
// Deux formes : pleine (256 px) ou rail d'icônes (68 px) quand la place manque (copilote ouvert).
import { useMemo, useState } from "react";
import { Link, NavLink as LienRouteur, useLocation, useNavigate } from "react-router-dom";
import { ActionIcon, Avatar, Badge, Combobox, Group, Menu, NavLink, ScrollArea, Stack, Text, TextInput, Tooltip, UnstyledButton, useCombobox } from "@mantine/core";
import { Building2, ChevronsLeft, ChevronsRight, Clock, Landmark, Palette, Search, Star } from "lucide-react";
import { listerEntreprises, trouverEntreprise } from "../lib/donnees.js";
import { useSuivis } from "../lib/suivis.js";
import { PALETTES } from "../lib/palettes.js";
import { COULEURS_SEGMENT } from "../lib/theme.js";

const initiales = (nom) => nom.replace(/^(Société|Ste)\s+/i, "").split(/\s+/).slice(0, 2).map((m) => m[0]).join("").toUpperCase();

function Recherche({ rail, onOuvrirRail }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });
  const toutes = listerEntreprises();
  const resultats = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? toutes.filter((e) => `${e.company_name} ${e.company_id} ${e.mf}`.toLowerCase().includes(t)).slice(0, 8) : [];
  }, [q, toutes]);
  if (rail) {
    return (
      <Tooltip label="Rechercher une entreprise" position="right">
        <ActionIcon size="lg" onClick={onOuvrirRail} aria-label="Rechercher une entreprise"><Search size={17} /></ActionIcon>
      </Tooltip>
    );
  }
  return (
    <Combobox store={combobox} onOptionSubmit={(mf) => { setQ(""); combobox.closeDropdown(); navigate(`/entreprise/${mf}`); }}>
      <Combobox.Target>
        <TextInput size="sm" value={q} placeholder="Raison sociale, matricule…" leftSection={<Search size={14} />}
          onChange={(e) => { setQ(e.currentTarget.value); combobox.openDropdown(); combobox.updateSelectedOptionIndex(); }}
          onFocus={() => combobox.openDropdown()} onBlur={() => combobox.closeDropdown()} aria-label="Rechercher une entreprise" />
      </Combobox.Target>
      <Combobox.Dropdown hidden={!resultats.length}>
        <Combobox.Options>
          {resultats.map((e) => (
            <Combobox.Option key={e.mf} value={e.mf}>
              <Group gap={8} wrap="nowrap">
                <span className="size-2 shrink-0 rounded-full" style={{ background: COULEURS_SEGMENT[e.segment] }} />
                <div className="min-w-0">
                  <Text size="sm" fw={600} truncate>{e.company_name}</Text>
                  <Text size="xs" c="dimmed" ff="monospace">{e.company_id}</Text>
                </div>
              </Group>
            </Combobox.Option>
          ))}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}

function LienEntreprise({ mf, rail }) {
  const { pathname } = useLocation();
  const e = trouverEntreprise(mf);
  if (!e) return null;
  const actif = pathname === `/entreprise/${mf}`;
  if (rail) {
    return (
      <Tooltip label={e.company_name} position="right">
        <UnstyledButton component={Link} to={`/entreprise/${mf}`} aria-label={e.company_name}>
          <Avatar size={34} radius="md" variant={actif ? "filled" : "light"} color={COULEURS_SEGMENT[e.segment]} className="text-[11px]">
            {initiales(e.company_name)}
          </Avatar>
        </UnstyledButton>
      </Tooltip>
    );
  }
  return (
    <NavLink component={LienRouteur} to={`/entreprise/${mf}`} active={actif} label={e.company_name} variant="light"
      leftSection={<span className="size-2 rounded-full" style={{ background: COULEURS_SEGMENT[e.segment] }} />}
      styles={{ label: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }} py={6} />
  );
}

function Section({ titre, icone: Icone, rail, children }) {
  return (
    <Stack gap={2} align={rail ? "center" : "stretch"}>
      {rail ? <div className="my-1 h-px w-8 bg-bordure" /> : (
        <Group gap={6} px={12} pb={4}>
          <Icone size={12} className="text-attenue" />
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.06em">{titre}</Text>
        </Group>
      )}
      {children}
    </Stack>
  );
}

export default function BarreLaterale({ rail, onRail, palette, onPalette }) {
  const { pathname } = useLocation();
  const { favoris, recents } = useSuivis();
  const nb = listerEntreprises().length;
  const recentsSeuls = recents.filter((mf) => !favoris.includes(mf));

  return (
    <nav className="flex h-full flex-col" aria-label="Navigation principale">
      <div className={`flex items-center gap-2.5 border-b border-bordure ${rail ? "justify-center px-2 py-3.5" : "px-4 py-3.5"}`}>
        <Link to="/" className="grid size-9 shrink-0 place-items-center rounded-lg bg-encre text-carte" aria-label="Accueil">
          <Landmark size={18} aria-hidden="true" />
        </Link>
        {!rail && (
          <div className="min-w-0">
            <Text size="sm" fw={700} lh={1.2}>Poste de l'inspecteur</Text>
            <Text size="xs" c="dimmed" lh={1.3} truncate>DGI · Douanes · synthétique</Text>
          </div>
        )}
      </div>

      <ScrollArea className="flex-1" scrollbarSize={6}>
        <Stack gap="lg" p={rail ? 10 : 12} align={rail ? "center" : "stretch"}>
          <Recherche rail={rail} onOuvrirRail={onRail} />
          {rail ? (
            <Tooltip label={`Entreprises (${nb})`} position="right">
              <ActionIcon component={LienRouteur} to="/" size="lg" variant={pathname === "/" ? "light" : "subtle"} color={pathname === "/" ? "basira" : "ardoise"} aria-label="Entreprises">
                <Building2 size={17} />
              </ActionIcon>
            </Tooltip>
          ) : (
            <NavLink component={LienRouteur} to="/" active={pathname === "/"} label="Entreprises" variant="light" py={7}
              leftSection={<Building2 size={16} />} rightSection={<Badge variant="light" color="ardoise" size="sm">{nb}</Badge>} />
          )}

          <Section titre="Dossiers suivis" icone={Star} rail={rail}>
            {favoris.length ? favoris.map((mf) => <LienEntreprise key={mf} mf={mf} rail={rail} />) : !rail && (
              <Text size="xs" c="dimmed" px={12}>Cliquez l'étoile d'une entreprise pour la suivre.</Text>
            )}
          </Section>

          {recentsSeuls.length > 0 && (
            <Section titre="Consultés récemment" icone={Clock} rail={rail}>
              {recentsSeuls.map((mf) => <LienEntreprise key={mf} mf={mf} rail={rail} />)}
            </Section>
          )}
        </Stack>
      </ScrollArea>

      <div className={`flex items-center gap-2 border-t border-bordure p-2.5 ${rail ? "flex-col" : ""}`}>
        {!rail && (
          <Group gap={10} wrap="nowrap" className="min-w-0 flex-1 px-1">
            <Avatar size={32} radius="xl" color="ardoise">ID</Avatar>
            <div className="min-w-0">
              <Text size="sm" fw={600} truncate>Inspecteur (démo)</Text>
              <Text size="xs" c="dimmed" truncate>Contrôle a posteriori · Sfax</Text>
            </div>
          </Group>
        )}
        <Menu position="right-end" withinPortal>
          <Menu.Target>
            <Tooltip label="Palette de couleurs" position="right"><ActionIcon aria-label="Palette de couleurs"><Palette size={16} /></ActionIcon></Tooltip>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>Palette (temporaire)</Menu.Label>
            {PALETTES.map((p) => (
              <Menu.Item key={p.id} onClick={() => onPalette(p.id)} fw={palette === p.id ? 700 : 400}>{p.nom}</Menu.Item>
            ))}
          </Menu.Dropdown>
        </Menu>
        <Tooltip label={rail ? "Déplier la barre latérale" : "Réduire la barre latérale"} position="right">
          <ActionIcon onClick={onRail} aria-label={rail ? "Déplier la barre latérale" : "Réduire la barre latérale"}>
            {rail ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </ActionIcon>
        </Tooltip>
      </div>
    </nav>
  );
}
