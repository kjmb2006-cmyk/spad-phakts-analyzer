// Garde-fou des dépendances d'exceljs : la correction « minimatch ≥ 11.0.1 » (package.json,
// « overrides ») ne doit jamais casser la lecture/écriture Excel ni la création de zip.
// Lancer : node --test tests/dependencies.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('child_process');
const path = require('path');

test('exceljs : minimatch ≥ 11.0.1 chargé, et lecture / écriture / zip fonctionnels', () => {
  const r = spawnSync(process.execPath, [path.join(__dirname, '..', 'scripts', 'check-dependencies.js')], { encoding: 'utf8' });
  assert.equal(r.status, 0, (r.stdout + r.stderr).trim());
});
