// Adaptateur dc.js 4 → D3 v7. Reprend dc/src/compat/d3v6.js, qui ne peut pas être
// importé tel quel : il lit `version` depuis 'd3', absent du build ES de D3 v7.
import { config, d3compat } from "dc";
import { schemeTableau10 } from "d3-scale-chromatic";
import { pointer } from "d3-selection";
import { groups } from "d3-array";

Object.assign(d3compat, {
  eventHandler: (handler) => function eventHandler(event, d) { handler.call(this, d, event); },
  callHandler: function callHandler(handler, that, event, d) { handler.call(that, event, d); },
  nester: ({ key, sortKeys, sortValues, entries }) => {
    if (sortValues) entries = [...entries].sort(sortValues);
    let out = groups(entries, key);
    if (sortKeys) out = out.sort(sortKeys);
    return out.map((e) => ({ key: `${e[0]}`, values: e[1] }));
  },
  pointer
});

// Évite l'avertissement sur d3.schemeCategory20c (supprimé de D3) ; chaque graphique fixe ses couleurs.
config.defaultColors(schemeTableau10);
