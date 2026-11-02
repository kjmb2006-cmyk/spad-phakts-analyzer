#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
//  Nettoie une COPIE du Dictionnaire des Propriétés Fonctionnelles (DPF).
//
//  Usage : node scripts/clean-dpf.js "<DPF original.xlsx>" "<copie nettoyée.xlsx>"
//
//  Le fichier d'origine n'est jamais modifié. Dans la copie, seules les VALEURS des
//  cellules fautives changent (couleurs et mise en forme conservées) ; chaque changement
//  est noté sur la cellule et listé dans « Nettoyage DPF », et chaque décision de fond
//  (point de la liste « à décider » du 02/11/2026) est justifiée dans « Décisions ».
//
//  Décisions prises (02/11/2026, à l'initiative de l'assistant sur délégation de l'utilisateur) :
//   1. Cellule portant deux codes (ancien / remplaçant) de « DPF-2 (fmt) » : la légende de la
//      feuille dit « En rouge à supprimer » → on garde le 1er code, on supprime le code rouge,
//      et la feuille « DPF-2 » (à plat, restée sur l'ancien code) est alignée sur la feuille
//      de travail, série par série.
//   2. Même variable écrite de deux façons (Qualité/Qualite) dans deux séries : c'est une
//      variable partagée par deux études (comme les 12 autres variables répétées) → conservée
//      dans chaque série, avec un seul code.
//   3. Code portant une contrainte (…__X!1*1Combustible_Cuisson_) : la colonne « PF Normalisée |
//      Variable » ne porte jamais de contrainte ailleurs ; la liste reste dans DPF_lists →
//      contrainte retirée du code.
//   4. Modalités accentuées des listes : la grammaire interdit les accents dans les noms codifiés
//      et l'équipe les translittère à la main (Supérieur → Superieur) → translittérées.
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
const RED = 'FFFF0000';

const raw = c => CORE.excelCellText(c && c.value !== undefined ? c.value : c);
const text = c => raw(c).trim();
const richRuns = c => (c && c.value && Array.isArray(c.value.richText) ? c.value.richText : null);

// Police de la première portion non vide : sert à garder la couleur de série quand une
// cellule à texte riche est réécrite avec une seule valeur.
function leadFont(cell) {
  const runs = richRuns(cell);
  const r = runs && runs.find(x => String(x.text).trim());
  return r && r.font ? r.font : null;
}

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
  const decisions = [];
  const toDecide = [];

  const write = (cell, value) => {
    const f = leadFont(cell);
    cell.value = f && typeof value === 'string' ? { richText: [{ text: value, font: f }] } : value;
  };
  const change = (ws, cell, before, after, rule, status) => {
    write(cell, after);
    cell.note = 'Nettoyage DPF (' + rule + ') — avant : ' + before.replace(/\r?\n/g, ' / ').slice(0, 300);
    log.push({ feuille: ws.name, cellule: cell.address, avant: before.replace(/\r?\n/g, ' / '), apres: after, regle: rule, statut: status || 'Appliqué' });
  };

  // ── Feuilles « DPF-2 » : codes des variables ──────────────────────────────
  const sheets2 = wb.worksheets.filter(ws => /^DPF-?2(\s*\(fmt\))?$/i.test(ws.name.trim()))
    .sort((a, b) => /\(fmt\)/i.test(b.name) - /\(fmt\)/i.test(a.name)); // la feuille de travail d'abord
  const drops = []; // { serie, from, to } : codes supprimés dans la feuille de travail
  const perSheet = {};

  const locate = ws => {
    let col = 0, serie = 0, first = 0;
    ws.eachRow({ includeEmpty: false }, (row, n) => {
      if (col) return;
      row.eachCell({ includeEmpty: false }, (cell, c) => {
        const t = text(cell);
        if (!col && /PF\s*Normalis/i.test(t)) { col = c; first = n + 1; }
      });
      if (col) row.eachCell({ includeEmpty: false }, (cell, c) => { if (/Index\s*\(\s*s[ée]rie/i.test(text(cell))) serie = c; });
    });
    return { col, serie: serie || 6, first };
  };

  sheets2.forEach(ws => {
    const { col, serie, first } = locate(ws);
    if (!col) return;
    const isWork = /\(fmt\)/i.test(ws.name);
    const seen = new Map();
    for (let r = first; r <= ws.rowCount; r++) {
      const row = ws.getRow(r);
      const cell = row.getCell(col);
      const before = raw(cell);
      if (!before.trim()) continue;
      const rowSerie = text(row.getCell(serie));
      // en-têtes répétés dans la feuille de travail : pas des codes
      if (/PF\s+Normalis/i.test(before) || /\s\|\s/.test(before)) continue;

      let candidate = before;
      let rule = null;
      let decisionRow = null;

      // 1. deux codes dans la même cellule (ancien / remplaçant) → on garde le premier
      const lines = before.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
      if (lines.length > 1) {
        const kept = AUDIT.normalizeDpfCode(lines[0]).code;
        const dropped = lines.slice(1).map(l => AUDIT.normalizeDpfCode(l).code);
        candidate = lines[0];
        rule = 'décision : deux codes → 1er conservé';
        dropped.forEach(d => drops.push({ serie: rowSerie, from: d.split('!')[0], to: kept.split('!')[0] }));
        decisionRow = {
          point: 'Cellule à deux codes', feuille: ws.name, objet: cell.address + ' (série ' + rowSerie + ')',
          constat: lines.join('  /  '), decision: 'Conservé : ' + kept.split('!')[0] + ' — supprimé : ' + dropped.join(', '),
          justification: 'Légende de la feuille « En rouge à supprimer » : le 2e code (en rouge) est le doublon. Le code conservé est celui des autres séries pour la même question (une variable = un code). La feuille « DPF-2 » à plat portait encore le code rouge : alignée.',
        };
      }

      let { code } = AUDIT.normalizeDpfCode(candidate);
      let notes = AUDIT.normalizeDpfCode(candidate).notes.map(n => n.rule);

      // 3. contrainte dans un code de variable
      if (code.includes('!')) {
        const [c0, ...k] = code.split('!');
        decisions.push({
          point: 'Code avec contrainte', feuille: ws.name, objet: cell.address + ' (série ' + rowSerie + ')', constat: code,
          decision: 'Contrainte retirée : ' + c0, justification: 'La colonne « PF Normalisée | Variable » ne porte aucune contrainte ailleurs ; la liste ' + k.join('!').replace(/^[\d*]*/, '') + ' reste décrite dans la feuille DPF_lists.',
        });
        code = c0;
        notes = notes.concat('contrainte_retiree');
      }

      // 2'. feuille à plat : aligner sur la feuille de travail (même série, même ancien code)
      if (!isWork) {
        const d = drops.find(x => x.serie === rowSerie && x.from === code);
        if (d) {
          decisions.push({
            point: 'Cellule à deux codes', feuille: ws.name, objet: cell.address + ' (série ' + rowSerie + ')', constat: code,
            decision: 'Renommé : ' + d.from + ' → ' + d.to, justification: 'Même variable que dans « DPF-2 (fmt) » où ' + d.from + ' est marqué à supprimer.',
          });
          code = d.to;
          notes = notes.concat('aligne_sur_fmt');
        }
      }

      if (code !== before) change(ws, cell, before, code, (rule ? [rule] : []).concat(notes).join('+'), rule ? 'Décision' : 'Appliqué');
      if (decisionRow) decisions.push(decisionRow);
      const key = code;
      if (!seen.has(key)) seen.set(key, []);
      seen.get(key).push({ row: r, original: before.trim(), serie: rowSerie });
    }
    perSheet[ws.name] = seen;
  });

  // 2. variables écrites de façons différentes dans le DPF mais identiques une fois nettoyées
  Object.entries(perSheet).forEach(([name, seen]) => {
    seen.forEach((rows, code) => {
      const originals = new Set(rows.map(x => x.original.split(/\r?\n/)[0].trim()));
      if (originals.size < 2) return;
      const series = rows.map(x => x.serie);
      if (new Set(series).size === rows.length) {
        decisions.push({
          point: 'Variable écrite de deux façons', feuille: name, objet: code + ' (lignes ' + rows.map(x => x.row).join(', ') + ')',
          constat: [...originals].join(' | '),
          decision: 'Conservées toutes les lignes, avec un seul code : ' + code,
          justification: 'Même variable utilisée par les séries ' + series.join(' et ') + ' : le DPF répète déjà ainsi 12 autres variables (une ligne par étude). Seule la graphie (accent) différait.',
        });
      } else {
        toDecide.push({ feuille: name, objet: code, detail: 'Même série, deux lignes : ' + [...originals].join(' | '), decision: 'Fusionner ?' });
      }
    });
  });

  // ── Feuilles de listes : codes, coquilles, doublons et accents des modalités ──
  let accented = 0;
  wb.worksheets.filter(ws => /^DPF_lists/i.test(ws.name)).forEach(ws => {
    let cCode = 0, cVal = 0, first = 0;
    ws.eachRow({ includeEmpty: false }, (row, n) => {
      if (cCode) return;
      let a = 0, b = 0;
      row.eachCell({ includeEmpty: false }, (cell, c) => { if (/^code$/i.test(text(cell))) a = c; if (/^valeurs?\b/i.test(text(cell))) b = c; });
      if (a && b) { cCode = a; cVal = b; first = n + 1; }
    });
    if (!cCode) return;
    const work = /\(fmt\)/i.test(ws.name);
    let inAbbrev = false;
    for (let r = first; r <= ws.rowCount; r++) {
      const row = ws.getRow(r);
      const codeCell = row.getCell(cCode), valCell = row.getCell(cVal);
      const code = text(codeCell), val = text(valCell);
      if (code && !val && /abr[ée]viation/i.test(code)) inAbbrev = true;
      if (inAbbrev) continue; // les abréviations (code + sens) ne sont pas des listes
      if (code) {
        // identifiant de liste : coquille connue, puis translittération (Periode_Année_ → Periode_Annee_)
        const fixed = CODE_FIXES[code] || code;
        const ascii = AUDIT.strip(fixed);
        if (ascii !== code) change(ws, codeCell, code, ascii, fixed !== code ? 'coquille' : 'décision : accents', fixed !== code ? 'Appliqué' : 'Décision');
      }
      if (!val) continue;
      const tokens = val.split('|').map(t => t.trim());
      const seen = new Set();
      let status = 'Appliqué';
      const fixed = [];
      const rules = new Set();
      tokens.forEach(t => {
        const fx = LIST_FIXES[t];
        let v = fx ? fx.to : t;
        if (fx) { rules.add('coquille'); if (fx.status !== 'Appliqué') status = fx.status; }
        const ascii = AUDIT.strip(v);
        if (ascii !== v) { rules.add('décision : accents'); if (!work) accented++; v = ascii; }
        const k = AUDIT.plain(v).replace(/ /g, '');
        if (k && seen.has(k) && !/^(0|etc\.?)$/i.test(v)) { rules.add('doublon'); return; }
        seen.add(k);
        fixed.push(v);
      });
      if (rules.size) change(ws, valCell, val, fixed.join(' | '), [...rules].join('+'), status === 'Appliqué' && rules.has('décision : accents') && rules.size === 1 ? 'Décision' : status);
    }
  });
  decisions.push({
    point: 'Modalités accentuées', feuille: 'DPF_lists_Abreviations', objet: accented + ' modalités',
    constat: 'Féminin, Considérablement, Dépôt_Riverain…',
    decision: 'Translittérées (Feminin, Considerablement, Depot_Riverain…)',
    justification: 'La grammaire interdit les accents dans les noms codifiés ; l\'équipe translittère à la main les modalités (Supérieur → Superieur) et l\'outil les translittère déjà à l\'import : le DPF et l\'usage sont maintenant identiques. Les abréviations (sens) ne sont pas touchées.',
  });

  // ── Journal et décisions ──────────────────────────────────────────────────
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
  ['À décider', 'Décisions', 'Nettoyage DPF'].forEach(n => { const o = wb.getWorksheet(n); if (o) wb.removeWorksheet(o.id); });
  addSheet('Nettoyage DPF', [
    { header: 'Feuille', key: 'feuille', width: 28 }, { header: 'Cellule', key: 'cellule', width: 9 },
    { header: 'Avant', key: 'avant', width: 60 }, { header: 'Après', key: 'apres', width: 60 },
    { header: 'Règle', key: 'regle', width: 34 }, { header: 'Statut', key: 'statut', width: 14 },
  ], log);
  addSheet('Décisions', [
    { header: 'Point', key: 'point', width: 28 }, { header: 'Feuille', key: 'feuille', width: 24 }, { header: 'Objet', key: 'objet', width: 40 },
    { header: 'Constat', key: 'constat', width: 60 }, { header: 'Décision prise', key: 'decision', width: 56 }, { header: 'Justification', key: 'justification', width: 90 },
  ], decisions);
  if (toDecide.length) {
    addSheet('À décider', [
      { header: 'Feuille', key: 'feuille', width: 28 }, { header: 'Objet', key: 'objet', width: 48 },
      { header: 'Constat', key: 'detail', width: 90 }, { header: 'Décision à prendre', key: 'decision', width: 60 },
    ], toDecide);
  }

  await wb.xlsx.writeFile(dst);

  const byRule = {};
  log.forEach(l => l.regle.split('+').forEach(r => { byRule[r] = (byRule[r] || 0) + 1; }));
  console.log('Cellules corrigées :', log.length, JSON.stringify(byRule));
  console.log('Décisions consignées :', decisions.length, '| encore à décider :', toDecide.length);
  console.log('→', dst);
}

main().catch(e => { console.error(e.message); process.exit(1); });
