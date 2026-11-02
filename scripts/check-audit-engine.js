#!/usr/bin/env node
// Test de fumée du moteur « Correction DPF » (public/phakts-audit.js) pour scripts/audit-prod.sh :
// quelques règles clés, y compris les décisions du 02/11/2026. Code de sortie 0 = tout est bon,
// 1 = la première règle en échec est affichée.
const path = require('path');
const AUDIT = require(path.join(__dirname, '..', 'public', 'phakts-audit.js'));

const q = (pf_question, pf_modalites = '', libelle = '') => ({ libelle, pf_question, pf_modalites, pf_skip: '' });
const fixed = (item, opts) => AUDIT.auditQuestionnaire([item], opts).items[0].corrected;

const checks = [
  ['registre des variables du DPF chargé', () => AUDIT.defaultRegistry && AUDIT.defaultRegistry.variables.length >= 250],
  ['faute de frappe !boulean corrigée', () => fixed(q('Pratique__B!boulean', 'Oui | Non')).pf_question === 'Pratique__B!boolean'],
  ['accent du code corrigé', () => fixed(q('Enfant_Né__B!boolean', 'Oui | Non')).pf_question === 'Enfant_Ne__B!boolean'],
  ['Z + liste de choix → X', () => fixed(q('Duree__Z!1*1Duree_', 'Duree_=[A,B]')).pf_question === 'Duree__X!1*1Duree_'],
  ['séparateur d\'un choix unique : virgule', () => fixed(q('Religion__X!1*1Religion_', 'Religion_=[A|B|C]')).pf_modalites === 'Religion_=[A,B,C]'],
  ['unité 1N ramenée à 1', () => fixed(q('Nb_Enfants__1N!N', 'Nombre')).pf_question === 'Nb_Enfants__1!N'],
  ['coquille du DPF jamais proposée', () => !/Sceptiqu/i.test(JSON.stringify(AUDIT.dpfValues({ valeurs: 'Fosse_Sceptiqu, Latrine' })))],
  ['XLSForm : nom renommé d\'office', () => {
    const items = AUDIT.xlsformToItems({ headers: ['type', 'name', 'label'], rows: [{ _row: 2, type: 'text', name: 'Nom_Z', label: 'Nom' }] }, { headers: [], rows: [] });
    return AUDIT.auditQuestionnaire(items).items[0].corrected.pf_question === 'Nom__Z';
  }],
];

let bad = 0;
for (const [name, fn] of checks) {
  let ok = false;
  try { ok = Boolean(fn()); } catch (e) { ok = false; }
  if (!ok) { console.error('✗ ' + name); bad++; }
}
process.exit(bad ? 1 : 0);
