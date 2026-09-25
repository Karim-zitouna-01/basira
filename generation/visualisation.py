"""Interactive, offline explorer of the generated world (graph + company time series).

    uv run python -m generation.visualisation [--data data] [--out data/graphe/explorateur.html]

Writes one self-contained HTML file (the vis-network library is embedded, no network access needed).
Open it in a browser: search a company or click a hero, explore its network, and read its monthly
declarations, imports and graph metrics. The "answer key" switch overlays the hidden scenario from
verite_terrain.csv; it exists for testing and must stay off in a demo of the detection itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from .referentiels import GOUV_LIBELLE, NAT_BY_CODE

ASSET = Path(__file__).parent / "assets" / "vis-network.min.js"
EDGE_CODES = {"IMPORT_FOURNISSEUR": 0, "ACHAT_LOCAL_A5": 1, "HONORAIRES_A2": 2, "PAIEMENT_PUBLIC": 3}
MONTHS = cfg.SIM_MONTHS[cfg.METRIC_T0:]


def _series(df: pd.DataFrame, index: str, value: str) -> dict[str, list]:
    p = df.pivot_table(index=index, columns="mois", values=value, aggfunc="sum").reindex(columns=MONTHS)
    out = {}
    for mf, row in p.iterrows():
        vals = row.to_numpy(dtype=float)
        if np.nansum(np.abs(vals)) == 0:
            continue
        out[mf] = [None if np.isnan(v) else round(float(v)) for v in vals]
    return out


def build_payload(root: Path) -> dict:
    raw, gdir = root / "raw", root / "graphe"
    c = pd.read_csv(raw / "contribuables.csv", dtype={"code_nat": str})
    vt = pd.read_csv(raw / "verite_terrain.csv").set_index("mf")
    fe = pd.read_csv(raw / "fournisseurs_etrangers.csv")
    ap = pd.read_csv(raw / "ref_acheteurs_publics.csv")
    e = pd.read_csv(gdir / "aretes.csv")
    mt = pd.read_csv(gdir / "metriques_noeuds.csv")
    dm = pd.read_csv(raw / "declarations_mensuelles.csv", usecols=["mf", "mois", "ca_total_declare", "tva_deductible_biens_services_local"])
    dd = pd.read_csv(raw / "douane_declarations.csv", usecols=["mf_importateur", "date_enregistrement", "valeur_caf_tnd"])
    ad = pd.read_csv(raw / "adeb_paiements.csv", usecols=["mf_beneficiaire", "date_paiement", "montant_ht"])
    ctl = pd.read_csv(raw / "historique_controles.csv")

    nodes: dict[str, dict] = {}
    for r in c.itertuples():
        t = vt.loc[r.mf]
        nodes[r.mf] = {
            "l": r.raison_sociale, "k": "E", "nat": r.code_nat, "nl": NAT_BY_CODE[r.code_nat].libelle,
            "g": GOUV_LIBELLE.get(int(r.gouvernorat_code), ""), "fj": r.forme_juridique, "eff": int(r.effectif_declare),
            "d0": r.date_debut_activite, "oea": bool(r.statut_oea), "imp": isinstance(r.code_en_douane, str) and r.code_en_douane != "",
            "sc": t.scenario, "sd": t.mois_debut_scenario if isinstance(t.mois_debut_scenario, str) else "",
            "rs": t.id_reseau if isinstance(t.id_reseau, str) else "", "fr": round(float(t.montant_fraude_reel)),
        }
    for r in fe.itertuples():
        nodes[r.id_fournisseur] = {"l": r.nom, "k": "F", "pays": r.pays, "d0": r.date_premiere_apparition, "ch": r.chapitres_sh_principaux}
    for r in ap.itertuples():
        nodes[r.id_acheteur_public] = {"l": r.libelle, "k": "P", "ty": r.type, "g": GOUV_LIBELLE.get(int(r.gouvernorat_code), "")}

    edges = [[s, t, EDGE_CODES[ty], round(float(m)), p, d]
             for s, t, ty, m, p, d in e[["source", "cible", "type_relation", "montant_total", "premiere_date", "derniere_date"]].itertuples(index=False)]

    dd["mois"] = dd["date_enregistrement"].str[:7]
    ad["mois"] = ad["date_paiement"].str[:7]
    dm = dm.assign(dl=dm["tva_deductible_biens_services_local"] / 0.19)
    series = {
        "ca": _series(dm, "mf", "ca_total_declare"),
        "im": _series(dd, "mf_importateur", "valeur_caf_tnd"),
        "pu": _series(ad, "mf_beneficiaire", "montant_ht"),
        "dl": _series(dm, "mf", "dl"),
    }
    mt = mt.assign(pc=(mt["part_achats_coquilles"] * 100), sh=mt["est_profil_coquille"].astype(int))
    for key, col in (("sp", "nb_clients_partageant_fournisseur_nouveau"), ("pc", "pc"), ("ds", "distance_entite_redressee"),
                     ("nf", "nb_fournisseurs_nouveaux_12m"), ("dg", "degre_fournisseurs"), ("sh", "sh")):
        p = mt.pivot_table(index="mf", columns="mois", values=col, aggfunc="first").reindex(columns=MONTHS)
        series[key] = {mf: [None if np.isnan(v) else round(float(v), 1) for v in row.to_numpy(dtype=float)] for mf, row in p.iterrows()}

    controls: dict[str, list] = {}
    for r in ctl.itertuples():
        controls.setdefault(r.mf, []).append([r.date_avis, r.type_controle, r.origine_selection, r.categorie_resultat,
                                              r.date_notification_resultats,
                                              round(r.montant_redresse_tva + r.montant_redresse_is + r.montant_redresse_rs)])
    sanctioned = {r.mf: r.date_notification_resultats for r in ctl.itertuples() if r.categorie_resultat == "FRAUDE_SIGNIFICATIVE"}
    a5 = pd.read_csv(raw / "employeur_annexe5.csv", usecols=["mf_fournisseur", "exercice", "montant_ttc", "mf_payeur"])
    dis = pd.read_csv(raw / "declarations_is.csv", usecols=["mf", "exercice", "ca_local", "ca_export"])
    rec = a5.groupby(["mf_fournisseur", "exercice"]).agg(t=("montant_ttc", "sum"), n=("mf_payeur", "nunique"))
    cay = (dis["ca_local"] + dis["ca_export"]).groupby([dis["mf"], dis["exercice"]]).sum()
    annual: dict[str, list] = {}
    for (mf, y), r in rec.iterrows():
        annual.setdefault(mf, []).append([int(y), round(float(r["t"])), int(r["n"]), round(float(cay.get((mf, y), 0.0)))])
    heroes = [[h.mf, h.raison_sociale, h.scenario] for h in cfg.HEROES]
    return {"months": MONTHS, "nodes": nodes, "edges": edges, "series": series, "controls": controls,
            "sanctioned": sanctioned, "heroes": heroes, "annual": annual}


def render(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    lib = ASSET.read_text(encoding="utf-8")
    return TEMPLATE.replace("/*__VIS__*/", lib).replace("/*__DATA__*/null", data)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or args.data / "graphe" / "explorateur.html"
    html = render(build_payload(args.data))
    out.write_text(html, encoding="utf-8")
    print(f"written {out} ({len(html) / 1e6:.1f} MB) - open it in a browser")


TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Basira Explorer</title>
<style>
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #1c2330; --muted: #5d6778; --line: #dde1e8; --accent: #2458d6;
  --imp: #d9822b; --a5: #2f6fd6; --a2: #8a93a3; --pub: #2e9e6a; --shell: #d63b3b; --sanct: #111111;
  --node: #7f8ea6; --fraud: #e0662f; --honest: #9aa6b8; --citizen: #2f86d6; --growth: #2e9e6a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #11151c; --panel: #1a2029; --ink: #e6e9ef; --muted: #9aa4b5; --line: #2c3440; --accent: #6e9bff;
    --node: #8d9bb2; --sanct: #f2f2f2; --honest: #6d7788;
  }
}
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
header { display: flex; align-items: center; gap: 16px; padding: 10px 16px; border-bottom: 1px solid var(--line); background: var(--panel); flex-wrap: wrap; }
header h1 { font-size: 16px; margin: 0; letter-spacing: .2px; }
header .sub { color: var(--muted); font-size: 12px; }
.layout { display: grid; grid-template-columns: 260px 1fr 420px; height: calc(100vh - 53px); }
aside, section.detail { background: var(--panel); overflow: auto; padding: 14px; }
aside { border-right: 1px solid var(--line); }
section.detail { border-left: 1px solid var(--line); }
#graphwrap { position: relative; min-height: 0; min-width: 0; }
#graph { position: absolute; inset: 0; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); margin: 16px 0 8px; }
h2:first-child { margin-top: 0; }
input[type=search] { width: 100%; padding: 7px 9px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--ink); }
.results div, .hero { padding: 5px 7px; border-radius: 5px; cursor: pointer; }
.results div:hover, .hero:hover { background: var(--bg); }
.hero small, .results small { color: var(--muted); display: block; font-size: 11px; }
label.opt { display: flex; gap: 7px; align-items: center; margin: 4px 0; cursor: pointer; }
.sw { width: 18px; height: 3px; display: inline-block; border-radius: 2px; }
.legend div { display: flex; align-items: center; gap: 8px; margin: 3px 0; color: var(--muted); font-size: 12px; }
.dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
.kv { display: grid; grid-template-columns: 150px 1fr; gap: 3px 10px; font-size: 13px; }
.kv span:nth-child(odd) { color: var(--muted); }
.badge { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 11px; font-weight: 600; margin: 2px 4px 2px 0; border: 1px solid currentColor; }
.b-shell { color: var(--shell); } .b-sanct { color: var(--sanct); } .b-oea { color: var(--citizen); } .b-key { color: var(--fraud); }
.chart { width: 100%; height: 150px; }
.chart text { fill: var(--muted); font-size: 10px; }
.chart .grid { stroke: var(--line); }
.chartlegend { font-size: 11px; color: var(--muted); display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 2px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
td, th { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--line); }
.note { color: var(--muted); font-size: 12px; }
.key { border: 1px dashed var(--fraud); border-radius: 6px; padding: 8px 10px; margin-top: 10px; }
select { background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 6px; padding: 4px; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; height: auto; } #graphwrap { height: 70vh; } }
.warn { color: var(--shell); font-weight: 600; }
</style>
</head>
<body>
<header>
  <h1>Basira Explorer</h1>
  <span class="sub" id="stats"></span>
  <span class="sub">Synthetic data. Arrows follow the money: payer to payee.</span>
</header>
<div class="layout">
  <aside>
    <h2>Find a company</h2>
    <input type="search" id="q" placeholder="Name, matricule or supplier id">
    <div class="results" id="results"></div>
    <h2>Hero cases</h2>
    <div id="heroes"></div>
    <h2>View</h2>
    <label class="opt">Depth <select id="depth"><option value="1">1 hop</option><option value="2" selected>2 hops</option></select></label>
    <label class="opt"><input type="checkbox" class="et" value="0" checked><span class="sw" style="background:var(--imp)"></span>Imports (customs)</label>
    <label class="opt"><input type="checkbox" class="et" value="1" checked><span class="sw" style="background:var(--a5)"></span>Local purchases (annex V)</label>
    <label class="opt"><input type="checkbox" class="et" value="2"><span class="sw" style="background:var(--a2)"></span>Fees and rents (annex II)</label>
    <label class="opt"><input type="checkbox" class="et" value="3" checked><span class="sw" style="background:var(--pub)"></span>Public payments (ADEB)</label>
    <label class="opt"><input type="checkbox" id="newonly">Only relations started in 2025-2026</label>
    <label class="opt"><input type="checkbox" id="answer"><b>Show answer key</b></label>
    <p class="note">The answer key colours companies by their hidden scenario (verite_terrain). Use it to test, not in the demo.</p>
    <h2>Legend</h2>
    <div class="legend">
      <div><span class="dot" style="background:var(--node)"></span>Company</div>
      <div><span class="dot" style="background:var(--imp);border-radius:2px;transform:rotate(45deg)"></span>Foreign supplier</div>
      <div><span class="dot" style="background:var(--pub);border-radius:2px"></span>Public buyer</div>
      <div><span class="dot" style="background:var(--shell)"></span>Shell profile (2026-08)</div>
      <div><span class="dot" style="background:var(--bg);border:3px solid var(--sanct)"></span>Found in significant fraud</div>
      <div><span class="sw" style="background:repeating-linear-gradient(90deg,var(--ink) 0 4px,transparent 4px 7px)"></span>Relation new since 2025</div>
      <div id="keylegend" style="display:none;flex-direction:column;align-items:flex-start">
        <div><span class="dot" style="background:var(--fraud)"></span>Fraud scenario (A-F, shell)</div>
        <div><span class="dot" style="background:var(--growth)"></span>Legitimate growth</div>
        <div><span class="dot" style="background:var(--citizen)"></span>Model citizen</div>
        <div><span class="dot" style="background:var(--honest)"></span>No scenario</div>
      </div>
    </div>
  </aside>
  <div id="graphwrap"><div id="graph"></div></div>
  <section class="detail" id="detail"><p class="note">Select a company.</p></section>
</div>
<script>/*__VIS__*/</script>
<script>
const D = /*__DATA__*/null;
const M = D.months, N = D.nodes, E = D.edges, S = D.series;
const ET = ["Import", "Local purchase (annex V)", "Fees/rents (annex II)", "Public payment"];
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const ECOL = () => [css("--imp"), css("--a5"), css("--a2"), css("--pub")];
const fmt = v => v == null ? "-" : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2) + " M" : Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(1) + " k" : Number.isInteger(v) ? String(v) : v.toFixed(1);
const adj = {};
E.forEach((e, i) => { (adj[e[0]] = adj[e[0]] || []).push(i); (adj[e[1]] = adj[e[1]] || []).push(i); });
document.getElementById("stats").textContent =
  `${Object.values(N).filter(n => n.k === "E").length.toLocaleString()} companies, ${E.length.toLocaleString()} relations, metrics ${M[0]} to ${M[M.length - 1]}`;

const last = (key, id) => { const s = S[key][id]; return s ? s[s.length - 1] : null; };
const FRAUD = new Set(["A", "B", "C", "D", "E", "F", "COQUILLE"]);
function nodeColor(id) {
  const n = N[id];
  if (n.k === "F") return css("--imp");
  if (n.k === "P") return css("--pub");
  if (document.getElementById("answer").checked) {
    if (FRAUD.has(n.sc)) return css("--fraud");
    if (n.sc === "CROISSANCE_LEGITIME") return css("--growth");
    if (n.sc === "CITOYEN_MODELE") return css("--citizen");
    return css("--honest");
  }
  if (last("sh", id) === 1) return css("--shell");
  return css("--node");
}

let network, current = null;
function ego(center) {
  const depth = +document.getElementById("depth").value;
  const types = new Set([...document.querySelectorAll(".et:checked")].map(x => +x.value));
  const newOnly = document.getElementById("newonly").checked;
  const ok = e => types.has(e[2]) && (!newOnly || e[4] >= "2025-01-01");
  const keepN = new Set([center]), keepE = new Set(), hubs = {};
  const pick = (id, cap) => (adj[id] || []).filter(i => ok(E[i])).sort((a, b) => E[b][3] - E[a][3]).slice(0, cap);
  const first = pick(center, 60);
  first.forEach(i => { keepE.add(i); keepN.add(E[i][0]); keepN.add(E[i][1]); });
  if (depth === 2) {
    [...keepN].forEach(id => {
      if (id === center) return;
      const deg = (adj[id] || []).length;
      if (N[id] && N[id].k !== "E" && deg > 12 && id !== center) { hubs[id] = deg; }
      if (deg > 40) { hubs[id] = deg; return; }
      pick(id, 8).forEach(i => { if (keepN.size < 220) { keepE.add(i); keepN.add(E[i][0]); keepN.add(E[i][1]); } });
    });
  }
  return { keepN, keepE, hubs };
}

function draw(center) {
  current = center;
  const { keepN, keepE, hubs } = ego(center);
  const col = ECOL();
  const nodes = [...keepN].filter(id => N[id]).map(id => {
    const n = N[id], sanct = D.sanctioned[id];
    const shape = n.k === "F" ? "diamond" : n.k === "P" ? "square" : "dot";
    const size = id === center ? 26 : n.k === "E" ? 11 + Math.min(10, Math.log10(1 + (adj[id] || []).length) * 5) : 10;
    let label = n.l.length > 26 ? n.l.slice(0, 25) + "..." : n.l;
    if (hubs[id]) label += `\n(${hubs[id]} links)`;
    return { id, label, shape, size, color: { background: nodeColor(id), border: sanct ? css("--sanct") : nodeColor(id) },
             borderWidth: sanct ? 4 : 1, font: { color: css("--ink"), size: id === center ? 15 : 11, strokeWidth: 3, strokeColor: css("--panel") },
             title: `${n.l}\n${id}${n.k === "E" ? "\n" + n.nat + " - " + n.g : ""}` };
  });
  const edges = [...keepE].map(i => {
    const e = E[i];
    return { id: i, from: e[0], to: e[1], arrows: { to: { enabled: true, scaleFactor: .5 } }, color: { color: col[e[2]], opacity: .85 },
             width: Math.max(1, Math.log10(1 + e[3]) - 2.5), dashes: e[4] >= "2025-01-01",
             title: `${ET[e[2]]}\n${fmt(e[3])} TND\n${e[4]} to ${e[5]}` };
  });
  const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
  const opts = { physics: { barnesHut: { gravitationalConstant: -6000, springLength: 140, avoidOverlap: .3 }, stabilization: { iterations: 250 } },
                 interaction: { hover: true, tooltipDelay: 120 }, edges: { smooth: { type: "continuous" } } };
  if (network) network.destroy();
  network = new vis.Network(document.getElementById("graph"), data, opts);
  network.once("stabilizationIterationsDone", () => network.setOptions({ physics: false }));
  network.on("click", p => { if (p.nodes.length) detail(p.nodes[0]); });
  network.on("doubleClick", p => { if (p.nodes.length && N[p.nodes[0]]) draw(p.nodes[0]); });
  detail(center);
}

function chart(lines, opts = {}) {
  const W = 390, H = 150, L = 46, R = 8, T = 8, B = 20;
  const all = lines.flatMap(l => l.v.filter(x => x != null));
  let max = Math.max(opts.floor || 1, ...all), min = opts.min != null ? opts.min : 0;
  if (opts.max != null) max = opts.max;
  if (opts.int) max = Math.max(3, Math.ceil(max / 3) * 3);
  const x = i => L + i * (W - L - R) / (M.length - 1), y = v => T + (H - T - B) * (1 - (v - min) / (max - min || 1));
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">`;
  for (let k = 0; k <= 3; k++) { const v = min + (max - min) * k / 3; s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${fmt(v)}</text>`; }
  [0, 6, 12, 18, 23].forEach(i => s += `<text x="${x(i)}" y="${H - 5}" text-anchor="${i === 23 ? "end" : i === 0 ? "start" : "middle"}">${M[i]}</text>`);
  if (opts.mark) { const i = M.indexOf(opts.mark); if (i >= 0) s += `<line x1="${x(i)}" x2="${x(i)}" y1="${T}" y2="${H - B}" stroke="${css("--fraud")}" stroke-dasharray="3 3"/>`; }
  lines.forEach(l => {
    let d = "", pen = false;
    l.v.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1) + " "; pen = true; });
    s += `<path d="${d}" fill="none" stroke="${l.c}" stroke-width="2"${l.dash ? ' stroke-dasharray="4 3"' : ""}/>`;
  });
  return s + "</svg>";
}
const zeros = () => M.map(() => 0);

function detail(id) {
  const n = N[id], el = document.getElementById("detail");
  if (!n) return;
  const key = document.getElementById("answer").checked;
  if (n.k !== "E") {
    const links = (adj[id] || []).map(i => E[i]);
    const rows = links.sort((a, b) => b[3] - a[3]).slice(0, 25).map(e => { const o = e[0] === id ? e[1] : e[0];
      return `<tr><td>${N[o] ? N[o].l : o}</td><td>${fmt(e[3])}</td><td>${e[4]}</td></tr>`; }).join("");
    el.innerHTML = `<h2>${n.k === "F" ? "Foreign supplier" : "Public buyer"}</h2><h3 style="margin:0 0 8px">${n.l}</h3>
      <div class="kv"><span>Id</span><span>${id}</span>${n.pays ? `<span>Country</span><span>${n.pays}</span><span>First seen</span><span>${n.d0}</span><span>HS chapters</span><span>${n.ch}</span>` : `<span>Type</span><span>${n.ty}</span><span>Governorate</span><span>${n.g}</span>`}
      <span>Counterparts</span><span>${links.length}</span></div>
      <h2>Counterparts by amount</h2><table><tr><th>Company</th><th>TND</th><th>Since</th></tr>${rows}</table>
      <p class="note">Double-click a node to centre the graph on it.</p>`;
    return;
  }
  const g = k => S[k][id] || zeros();
  const shellNow = last("sh", id) === 1, sanct = D.sanctioned[id];
  const badges = (shellNow ? `<span class="badge b-shell">Shell profile</span>` : "") + (sanct ? `<span class="badge b-sanct">Significant fraud, notified ${sanct}</span>` : "") + (n.oea ? `<span class="badge b-oea">OEA</span>` : "");
  const ctl = (D.controls[id] || []).map(c => `<tr><td>${c[0]}</td><td>${c[1].replace("VERIF_", "").replace(/_/g, " ").toLowerCase()}</td><td>${c[3].replace(/_/g, " ").toLowerCase()}</td><td>${fmt(c[5])}</td></tr>`).join("");
  el.innerHTML = `<h2>Company</h2><h3 style="margin:0 0 4px">${n.l}</h3><div>${badges}</div>
    <div class="kv" style="margin-top:8px"><span>Matricule</span><span>${id}</span><span>Activity</span><span>${n.nat} ${n.nl}</span>
      <span>Governorate</span><span>${n.g}</span><span>Legal form, staff</span><span>${n.fj}, ${n.eff} declared</span><span>Active since</span><span>${n.d0}</span></div>
    <h2>Graph metrics, 2026-08</h2>
    <div class="kv"><span>Suppliers (12 m, latest annex V)</span><span>${last("dg", id) ?? 0}</span>
      <span>New suppliers</span><span>${last("nf", id) ?? 0}</span>
      <span>Share a new supplier with</span><span>${last("sp", id) ?? 0} companies</span>
      <span>Purchases from shells</span><span>${(last("pc", id) ?? 0).toFixed(1)} %</span>
      <span>Distance to sanctioned</span><span>${(last("ds", id) ?? 99) === 99 ? "none within 3 hops" : last("ds", id) + " hop(s)"}</span></div>
    <h2>Monthly flows (TND)</h2>
    <div class="chartlegend"><span style="color:var(--ink)">&#9644; declared turnover</span><span style="color:var(--imp)">&#9644; imports (CAF)</span><span style="color:var(--pub)">&#9644; public payments</span><span style="color:var(--a5)">&#9644; local purchases</span></div>
    ${chart([{ v: g("ca"), c: css("--ink") }, { v: g("im"), c: css("--imp") }, { v: g("pu"), c: css("--pub") }, { v: g("dl"), c: css("--a5"), dash: true }], { mark: key ? n.sd : null })}
    <h2>Graph signals over time</h2>
    <div class="chartlegend"><span style="color:var(--fraud)">&#9644; companies sharing a new supplier</span><span style="color:var(--shell)">&#9644; % purchases from shells / 10</span></div>
    ${chart([{ v: g("sp"), c: css("--fraud") }, { v: g("pc").map(v => v == null ? null : v / 10), c: css("--shell") }], { min: 0, int: true })}
    ${D.annual[id] ? `<h2>What clients report paying it (annex V)</h2><table><tr><th>Year</th><th>Clients</th><th>Reported by clients</th><th>Declared turnover (HT)</th></tr>${
      D.annual[id].map(r => `<tr><td>${r[0]}</td><td>${r[2]}</td><td${r[1] > 1.2 * r[3] ? ' class="warn"' : ""}>${fmt(r[1])}</td><td>${fmt(r[3])}</td></tr>`).join("")}</table>
      <p class="note">Highlighted when clients report more than 1.2 x the declared turnover.</p>` : ""}
    ${ctl ? `<h2>Past audits</h2><table><tr><th>Notice</th><th>Type</th><th>Outcome</th><th>Reassessed</th></tr>${ctl}</table>` : ""}
    ${key ? `<div class="key"><b>Answer key</b> (hidden from signals and training)<div class="kv" style="margin-top:6px">
      <span>Scenario</span><span>${n.sc}</span><span>Start</span><span>${n.sd || "-"}</span><span>Ring / group</span><span>${n.rs || "-"}</span>
      <span>Evaded duties</span><span>${fmt(n.fr)} TND</span></div></div>` : ""}
    <p class="note">Double-click a node to centre the graph on it. Dashed orange line on the chart: scenario start (answer key on).</p>`;
}

// search
const index = Object.entries(N).map(([id, n]) => [id, (id + " " + n.l).toLowerCase()]);
document.getElementById("q").addEventListener("input", ev => {
  const q = ev.target.value.trim().toLowerCase(), box = document.getElementById("results");
  if (q.length < 2) { box.innerHTML = ""; return; }
  box.innerHTML = index.filter(x => x[1].includes(q)).slice(0, 12).map(([id]) =>
    `<div data-id="${id}">${N[id].l}<small>${id}${N[id].k === "E" ? " - " + N[id].nat + " - " + N[id].g : ""}</small></div>`).join("");
});
document.getElementById("results").addEventListener("click", ev => { const d = ev.target.closest("[data-id]"); if (d) draw(d.dataset.id); });
document.getElementById("heroes").innerHTML = D.heroes.map(h => `<div class="hero" data-id="${h[0]}">${h[1]}<small>${h[0]}</small></div>`).join("");
document.getElementById("heroes").addEventListener("click", ev => { const d = ev.target.closest("[data-id]"); if (d) draw(d.dataset.id); });
document.querySelectorAll(".et, #depth, #newonly").forEach(x => x.addEventListener("change", () => current && draw(current)));
document.getElementById("answer").addEventListener("change", ev => {
  document.getElementById("keylegend").style.display = ev.target.checked ? "flex" : "none";
  if (current) draw(current);
});
draw(D.heroes[0][0]);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
