#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
//  Génère public/dpf-registry.js — registre des variables normalisées du DPF
//  (feuille « DPF-2 » du Dictionnaire des Propriétés Fonctionnelles).
//
//  Usage : node scripts/build-dpf-registry.js "<chemin du DPF .xlsx>"
//
//  Même lecture que l'import « D. Listes standard » du Studio : le registre
//  par défaut et celui que l'on réimporte dans l'onglet « Correction DPF »
//  passent par PHAKTS_AUDIT.parseDpfRegistryRows(), donc ne peuvent pas
//  diverger.
// ─────────────────────────────────────────────────────────────────────────────
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');
const CORE = require('../public/phakts-core.js');
const AUDIT = require('../public/phakts-audit.js');

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('Usage : node scripts/build-dpf-registry.js "<Dictionnaire des Propriete Fonctionnelles….xlsx>"');
    process.exit(1);
  }
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(file);
  const sheet = wb.worksheets.find(ws => /^DPF-?2$/i.test(ws.name.trim()));
  if (!sheet) throw new Error('feuille « DPF-2 » introuvable dans ' + file);
  const rows = [];
  sheet.eachRow({ includeEmpty: false }, row => rows.push(row.values.map(CORE.excelCellText)));
  const registry = AUDIT.parseDpfRegistryRows(rows);
  registry.source = path.basename(file);

  const out = path.join(__dirname, '..', 'public', 'dpf-registry.js');
  const body = '{\n  "source": ' + JSON.stringify(registry.source) + ',\n  "studies": ' + JSON.stringify(registry.studies, null, 2).replace(/\n/g, '\n  ') +
    ',\n  "variables": [\n' + registry.variables.map(v => '    ' + JSON.stringify(v)).join(',\n') + '\n  ]\n  }';
  fs.writeFileSync(out,
`// ─────────────────────────────────────────────────────────────────────────────
//  Registre des variables normalisées du DPF (feuille « DPF-2 ») — GÉNÉRÉ par
//  scripts/build-dpf-registry.js, ne pas éditer à la main.
//  Source : ${registry.source}
//  Les codes sont ceux de ce fichier. Si un DPF plus ancien contient encore des fautes
//  (accents, coquilles), phakts-audit.js compare sur une clé normalisée et ne les
//  propose jamais comme correction (voir scripts/clean-dpf.js pour nettoyer un DPF).
// ─────────────────────────────────────────────────────────────────────────────
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PHAKTS_DPF_REGISTRY = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  return ${body};
});
`, 'utf8');
  console.log(`${registry.variables.length} variables, ${Object.keys(registry.studies).length} série(s) → ${path.relative(process.cwd(), out)}`);
}

main().catch(e => { console.error(e.message); process.exit(1); });
