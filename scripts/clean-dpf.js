#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
//  Nettoie une COPIE du Dictionnaire des Propriétés Fonctionnelles (DPF).
//
//  Usage : node scripts/clean-dpf.js "<DPF original.xlsx>" "<copie nettoyée.xlsx>"
//
//  Le fichier d'origine n'est jamais modifié. Dans la copie, seules les VALEURS
//  des cellules fautives changent (couleurs et mise en forme conservées, y compris
//  celles de « DPF-2 (fmt) ») ; chaque changement est noté sur la cellule et listé
//  dans la feuille « Nettoyage DPF ». Ce qui demande une décision humaine n'est pas
//  touché : il est listé dans la feuille « À décider ».
//
//  Règles : mêmes que l'audit des questionnaires (public/phakts-audit.js,
//  normalizeDpfCode) pour les codes de variables ; pour les listes, uniquement des
//  coquilles vérifiées une à une (LIST_FIXES) et les modalités en double.
// ─────────────────────────────────────────────────────────────────────────────
const path = require('path');
const ExcelJS = require('exceljs');
const CORE = require('../public/phakts-core.js');
const AUDIT = require('../public/phakts-audit.js');

// Valeurs de listes : correction exacte, cellule par cellule, jamais devinée par motif.
const LIST_FIXES = {
  'Infifférent': { to: 'Indifférent', status: 'Appliqué' },
  'Alimemtation': { to: 'Alimentation', status: 'Appliqué' },
  'Fosse_Sceptiqu': { to: 'Fosse_Septique', status: 'Appliqué' },
  'Fosse_Sceptique': { to: 'Fosse_Septique', status: 'Appliqué' },
  // « 0 » préfixe la négation dans la grammaire : 0Activité_Sportive = pas d'activité sportive
  '0Ativité_Sportive': { to: '0Activité_Sportive', status: 'Appliqué' },
  // espace parasite avant le pluriel ; Brûlées / Jetées_Rivière sont au pluriel féminin
  'Enterrée s': { to: 'Enterrées', status: 'À confirmer' },
};
const CODE_FIXES = { 'Admin_Dsitrict_Sanitaire_': 'Admin_District_Sanitaire_' };

const raw = c => CORE.excelCellText(c && c.value !== undefined ? c.value : c);
const text = c => raw(c).trim();

async function main() {
  const [src, dst] = process.argv.slice(2);
  if (!src || !dst) {
    console.error('Usage : node scripts/clean-dpf.js "<DPF original.xlsx>" "<copie nettoyée.xlsx>"');
    process.exit(1);
  }
  if (path.resolve(src) === path.resolve(dst)) throw new Error('la copie doit avoir un autre nom que le fichier d\'origine');

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(src);
  const log = [];
  const toDecide = [];
  const perSheetCodes = {};

  const change = (ws, cell, before, after, rule, status) => {
    cell.value = after;
    cell.note = 'Nettoyage DPF (' + rule + ') — avant : ' + before.slice(0, 300);
    log.push({ feuille: ws.name, cellule: cell.address, avant: before, apres: after, regle: rule, statut: status || 'Appliqué' });
  };

  // ── Feuilles « DPF-2 » : codes des variables ──────────────────────────────
  wb.worksheets.filter(ws => /^DPF-?2(\s*\(fmt\))?$/i.test(ws.name.trim())).forEach(ws => {
    let col = 0, first = 0;
    ws.eachRow({ includeEmpty: false }, (row, n) => {
      if (col) return;
      row.eachCell({ includeEmpty: false }, (cell, c) => { if (!col && /PF\s*Normalis/i.test(text(cell))) { col = c; first = n + 1; } });
    });
    if (!col) return;
    const seen = new Map();
    for (let r = first; r <= ws.rowCount; r++) {
      const cell = ws.getRow(r).getCell(col);
      const before = raw(cell); // brut : l'espace final fait partie de la faute
      if (!before.trim()) continue;
      // En-têtes répétés dans la feuille de travail, ou cellule portant plusieurs codes
      // (ancien → remplaçant) : ce ne sont pas des codes à normaliser, on n'y touche pas.
      if (/[\r\n]/.test(before.trim())) {
        toDecide.push({ feuille: ws.name, objet: cell.address, detail: 'La cellule contient plusieurs codes : ' + before.trim().split(/\s*[\r\n]+\s*/).filter(Boolean).join('  /  '), decision: 'Garder un seul code (cellule non modifiée)' });
        continue;
      }
      if (/\s\|\s|PF\s+Normalis/i.test(before)) continue;
      const { code, notes } = AUDIT.normalizeDpfCode(before);
      if (code !== before) change(ws, cell, before, code, notes.map(n => n.rule).join('+'));
      const key = code.split('!')[0];
      if (!seen.has(key)) seen.set(key, []);
      seen.get(key).push({ row: r, original: before.trim() });
    }
    perSheetCodes[ws.name] = seen;
  });

  // Variables devenues identiques après nettoyage alors que le DPF les écrivait différemment
  Object.entries(perSheetCodes).forEach(([name, seen]) => {
    seen.forEach((rows, code) => {
      const originals = new Set(rows.map(x => x.original));
      if (originals.size > 1) {
        toDecide.push({ feuille: name, objet: code, detail: 'Écrit de ' + originals.size + ' façons dans le DPF (lignes ' + rows.map(x => x.row).join(', ') + ') : ' + [...originals].join(' | '), decision: 'Garder une seule ligne ? (le DPF les distinguait par l\'accent ou la coquille)' });
      }
    });
  });

  // ── Feuilles de listes : codes de listes et valeurs ───────────────────────
  let accentedValues = 0;
  wb.worksheets.filter(ws => /^DPF_lists/i.test(ws.name)).forEach(ws => {
    let cCode = 0, cVal = 0, first = 0;
    ws.eachRow({ includeEmpty: false }, (row, n) => {
      if (cCode) return;
      let a = 0, b = 0;
      row.eachCell({ includeEmpty: false }, (cell, c) => { if (/^code$/i.test(text(cell))) a = c; if (/^valeurs?\b/i.test(text(cell))) b = c; });
      if (a && b) { cCode = a; cVal = b; first = n + 1; }
    });
    if (!cCode) return;
    for (let r = first; r <= ws.rowCount; r++) {
      const row = ws.getRow(r);
      const codeCell = row.getCell(cCode), valCell = row.getCell(cVal);
      const code = text(codeCell), val = text(valCell);
      if (code && CODE_FIXES[code]) change(ws, codeCell, code, CODE_FIXES[code], 'coquille');
      if (!val) continue;
      const tokens = val.split('|').map(t => t.trim());
      const seen = new Set();
      let status = 'Appliqué';
      const fixed = [];
      let touched = false;
      tokens.forEach(t => {
        const fx = LIST_FIXES[t];
        const v = fx ? fx.to : t;
        if (fx) { touched = true; if (fx.status !== 'Appliqué') status = fx.status; }
        const k = AUDIT.plain(v).replace(/ /g, '');
        if (k && seen.has(k) && !/^(0|etc\.?)$/i.test(v)) { touched = true; return; } // modalité en double
        seen.add(k);
        fixed.push(v);
        if (/[^\x00-\x7f]/.test(v) && !/\(fmt\)/i.test(ws.name)) accentedValues++;
      });
      if (touched) change(ws, valCell, val, fixed.join(' | '), 'coquille/doublon', status);
    }
  });
  if (accentedValues) {
    toDecide.push({ feuille: 'DPF_lists_Abreviations', objet: 'Modalités accentuées', detail: accentedValues + ' modalités de listes contiennent des accents (Féminin, Considérablement…), alors que la grammaire interdit les accents dans les noms codifiés. L\'outil les translittère à l\'import.', decision: 'Translittérer aussi les listes du DPF (Feminin, Considerablement…) ?' });
  }

  // ── Journal ───────────────────────────────────────────────────────────────
  const addSheet = (name, columns, rows) => {
    const old = wb.getWorksheet(name);
    if (old) wb.removeWorksheet(old.id);
    const ws = wb.addWorksheet(name);
    ws.columns = columns;
    rows.forEach(r => ws.addRow(r));
    const h = ws.getRow(1);
    h.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    h.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F3A5F' } };
    ws.views = [{ state: 'frozen', ySplit: 1 }];
    ws.eachRow((row, n) => { if (n > 1) row.alignment = { vertical: 'top', wrapText: true }; });
  };
  addSheet('Nettoyage DPF', [
    { header: 'Feuille', key: 'feuille', width: 28 }, { header: 'Cellule', key: 'cellule', width: 9 },
    { header: 'Avant', key: 'avant', width: 60 }, { header: 'Après', key: 'apres', width: 60 },
    { header: 'Règle', key: 'regle', width: 26 }, { header: 'Statut', key: 'statut', width: 14 },
  ], log);
  addSheet('À décider', [
    { header: 'Feuille', key: 'feuille', width: 28 }, { header: 'Objet', key: 'objet', width: 48 },
    { header: 'Constat', key: 'detail', width: 90 }, { header: 'Décision à prendre', key: 'decision', width: 60 },
  ], toDecide);

  await wb.xlsx.writeFile(dst);

  const byRule = {};
  log.forEach(l => l.regle.split('+').forEach(r => { byRule[r] = (byRule[r] || 0) + 1; }));
  console.log('Cellules corrigées :', log.length, JSON.stringify(byRule));
  console.log('À décider :', toDecide.length);
  console.log('→', dst);
}

main().catch(e => { console.error(e.message); process.exit(1); });
