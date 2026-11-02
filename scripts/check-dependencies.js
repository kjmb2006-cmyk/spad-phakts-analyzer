#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
//  Garde-fou des dépendances d'exceljs (utilisé par le serveur pour lire un Excel et par
//  les scripts de nettoyage du DPF). Appelé par tests/dependencies.test.js et par
//  scripts/audit-prod.sh. Code de sortie 0 = tout est bon.
//
//  Pourquoi : « minimatch < 11.0.1 » est signalé par npm audit (déni de service sur des
//  motifs forgés). Aucune version de glob/archiver/exceljs n'embarque encore la 11, donc
//  package.json l'impose dans le sous-arbre d'exceljs (« overrides »). Conséquence connue :
//  glob@7 (indirect, jamais appelé par exceljs) ne comprend pas minimatch 11. Ce script
//  vérifie (1) que la version imposée est bien celle qui est chargée, (2) que tout ce
//  qu'exceljs fait réellement fonctionne : lire, écrire, zipper avec motifs.
//  Si une mise à jour d'exceljs/archiver se met un jour à appeler glob@7, ce contrôle échoue.
// ─────────────────────────────────────────────────────────────────────────────
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const dirOf = (name, from) => path.dirname(require.resolve(name + '/package.json', { paths: [from] }));
const versionOf = dir => JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8')).version;
const atLeast = (v, min) => {
  const a = v.split('.').map(Number), b = min.split('.').map(Number);
  for (let i = 0; i < 3; i++) { if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) > (b[i] || 0); }
  return true;
};

const results = [];
const check = async (name, fn) => {
  try { results.push({ ok: true, name, detail: (await fn()) || '' }); }
  catch (e) { results.push({ ok: false, name, detail: String(e && e.message || e).slice(0, 160) }); }
};

(async () => {
  const exceljsDir = dirOf('exceljs', ROOT);
  const archiverDir = dirOf('archiver', exceljsDir);

  await check('minimatch ≥ 11.0.1 chargé par readdir-glob (zip avec motifs)', () => {
    const v = versionOf(dirOf('minimatch', dirOf('readdir-glob', archiverDir)));
    if (!atLeast(v, '11.0.1')) throw new Error('minimatch ' + v);
    return v;
  });
  await check('minimatch ≥ 11.0.1 chargé par archiver-utils → glob', () => {
    const utils = dirOf('archiver-utils', archiverDir);
    const v = versionOf(dirOf('minimatch', dirOf('glob', utils)));
    if (!atLeast(v, '11.0.1')) throw new Error('minimatch ' + v);
    return v;
  });

  const ExcelJS = require(exceljsDir);
  await check('exceljs : écriture mémoire puis relecture', async () => {
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('survey');
    ws.addRow(['type', 'name']); ws.addRow(['text', 'Nom__Z']);
    const buf = await wb.xlsx.writeBuffer();
    const back = new ExcelJS.Workbook();
    await back.xlsx.load(buf);
    if (back.getWorksheet('survey').getRow(2).getCell(2).value !== 'Nom__Z') throw new Error('valeur relue différente');
  });
  await check('exceljs : writeFile puis readFile (chemin du serveur)', async () => {
    const f = path.join(os.tmpdir(), 'check-deps-' + process.pid + '.xlsx');
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('Q');
    ws.addRow(['Libellé', 'PF/Question']); ws.addRow(['Âge ?', 'Age__1Y!0<N<120']);
    await wb.xlsx.writeFile(f);
    const back = new ExcelJS.Workbook();
    await back.xlsx.readFile(f);
    fs.unlinkSync(f);
    if (back.getWorksheet('Q').getRow(2).getCell(2).value !== 'Age__1Y!0<N<120') throw new Error('valeur relue différente');
  });
  await check('archiver : zip avec motifs glob et directory()', async () => {
    const archiver = require(archiverDir);
    const out = path.join(os.tmpdir(), 'check-deps-' + process.pid + '.zip');
    await new Promise((resolve, reject) => {
      const o = fs.createWriteStream(out);
      const a = archiver('zip');
      o.on('close', resolve); a.on('error', reject); a.pipe(o);
      a.glob('public/*.js', { cwd: ROOT });
      a.directory(path.join(ROOT, 'scripts'), 'scripts');
      a.append('contenu', { name: 'texte.txt' });
      a.finalize();
    });
    const list = execSync('unzip -Z1 "' + out + '"').toString().trim().split('\n');
    fs.unlinkSync(out);
    if (!list.includes('public/phakts-core.js') || !list.includes('texte.txt') || !list.some(x => x.startsWith('scripts/'))) throw new Error('entrées du zip : ' + list.length);
    return list.length + ' entrées';
  });

  const bad = results.filter(r => !r.ok);
  results.forEach(r => { if (!r.ok || process.argv.includes('-v')) console.log((r.ok ? '✓ ' : '✗ ') + r.name + (r.detail ? ' — ' + r.detail : '')); });
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.error('✗ ' + e.message); process.exit(1); });
