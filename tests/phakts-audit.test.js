// Tests de l'audit de conformité PHAKTS / DPF (public/phakts-audit.js).
// Lancer : node --test tests/
//
// Les cas reprennent le « Journal des corrections PHAKTS » tenu par l'équipe sur
// le questionnaire du prétest (erreurs réelles : boulean, Practiques, 1C, Z au lieu
// de X, skip vers une question inexistante…), avec des valeurs d'exemple.
const test = require('node:test');
const assert = require('node:assert/strict');
const AUDIT = require('../public/phakts-audit.js');

const q = (pf_question, pf_modalites = '', pf_skip = '', libelle = '') => ({ libelle, pf_question, pf_modalites, pf_skip });
const audit = (items, opts) => AUDIT.auditQuestionnaire(Array.isArray(items) ? items : [items], opts || {});
const findingsOf = (res, i = 0) => res.items[i].findings;
const rule = (res, name, i = 0) => findingsOf(res, i).find(f => f.rule === name);
const ids = (res, i = 0) => findingsOf(res, i).map(f => f.rule);

// ── Forme du code ───────────────────────────────────────────────────────────
test('faute de frappe dans !boolean : corrigée d\'office, sévérité Critique', () => {
  const r = audit(q('Pratique_Traditionnelle_Protege_Enfant__B!boulean', 'Oui | Non'));
  const f = rule(r, 'contrainte.typo');
  assert.equal(f.category, 'Faute de frappe');
  assert.equal(f.severity, 'Critique');
  assert.equal(f.auto, true);
  assert.equal(r.items[0].corrected.pf_question, 'Pratique_Traditionnelle_Protege_Enfant__B!boolean');
});

test('__B sans contrainte reçoit !boolean et les modalités « Oui | Non »', () => {
  const r = audit(q('Emploi__B', ''));
  assert.equal(r.items[0].corrected.pf_question, 'Emploi__B!boolean');
  assert.equal(r.items[0].corrected.pf_modalites, 'Oui | Non');
});

test('accents, espaces, caractères interdits et casse dans le code', () => {
  const r = audit(q('enfant né cs-2__B!boolean', 'Oui | Non'));
  assert.equal(r.items[0].corrected.pf_question, 'Enfant_Ne_Cs_2__B!boolean');
  assert.ok(ids(r).includes('code.espaces'));
  assert.ok(ids(r).includes('code.accents'));
  assert.ok(ids(r).includes('code.caracteres'));
  assert.ok(findingsOf(r).every(f => f.auto));
});

test('CamelCase : Doses_FievreJaune → Doses_Fievre_Jaune, mais HepB reste intact', () => {
  const r = audit([q('Doses_FievreJaune__1', ''), q('Doses_DN_HepB__1', '')]);
  assert.equal(r.items[0].corrected.pf_question, 'Doses_Fievre_Jaune__1');
  assert.equal(r.items[1].corrected.pf_question, 'Doses_DN_HepB__1');
});

test('affixe séparé par un seul « _ » (nom XLSForm abîmé) et affixe en minuscules', () => {
  const r = audit([q('Region_Sanitaire_X'), q('Sexe__x!1*1Sexe_', 'Sexe_=[Masculin,Feminin,Autre]')]);
  assert.equal(r.items[0].corrected.pf_question.startsWith('Region_Sanitaire__X'), true);
  assert.equal(rule(r, 'affixe.separateur').auto, true);
  assert.equal(r.items[1].corrected.pf_question, 'Sexe__X!1*1Sexe_');
});

test('code sans affixe : Critique, jamais corrigé en silence', () => {
  const r = audit(q('niveau_instruction', '', '', 'Niveau d\'instruction'));
  const f = rule(r, 'affixe.absent');
  assert.equal(f.severity, 'Critique');
  assert.equal(f.applied, false);
});

test('unités : 1C inconnue (à valider), 1N ramenée à __1 d\'office (décision du 02/11/2026)', () => {
  const r = audit([q('Cout_Transport__1C!C', 'Montant', '', 'Coût du transport (CFA)'), q('Nb_Enfants__1N!N', 'Nombre', '', 'Nombre d\'enfants')]);
  const bad = rule(r, 'affixe.unite_inconnue', 0);
  assert.equal(bad.auto, false);
  assert.equal(bad.after, 'Cout_Transport__1!C');
  assert.match(bad.action, /2F/);
  const n = rule(r, 'affixe.unite_N', 1);
  assert.equal(n.auto, true);
  assert.equal(n.source, AUDIT.SRC.DECISION);
  assert.equal(r.items[1].corrected.pf_question, 'Nb_Enfants__1!N');
});

test('ancienne écriture du GPS __G__X → __G!DMS', () => {
  const r = audit(q('Etablissement__Coordonnees__G__X!DMS', ''));
  assert.equal(r.items[0].corrected.pf_question, 'Etablissement__Coordonnees__G!DMS');
});

test('« ! » oublié avant la contrainte : réinséré, pas aplati en soulignés', () => {
  const r = audit(q('Danger_Fumer__Allaitement__X1*1Dangereux_', 'Dangereux_=[Tres_dangereux,Dangereux]'));
  assert.equal(r.items[0].corrected.pf_question, 'Danger_Fumer__Allaitement__X!1*1Dangereux_');
  assert.equal(rule(r, 'code.bang_manquant').auto, true);
});

test('cellule de code sur plusieurs lignes : signalée, jamais fusionnée', () => {
  const r = audit(q('Nombre_Consultations__Prenatales\nConsultation_Prenatale__1', '', '', 'Combien de consultations ?'));
  assert.ok(rule(r, 'code.multiligne'));
  assert.equal(r.items[0].corrected.pf_question, 'Nombre_Consultations__Prenatales\nConsultation_Prenatale__1');
});

// ── Cohérence du type ───────────────────────────────────────────────────────
test('Z + liste de choix = type X (Critique, corrigé d\'office)', () => {
  const r = audit(q('Duree_Trajet__Z!1*1Duree_Trajet_', 'Duree_Trajet_=[Moins_d_1_Heure,1_a_2_Heures]'));
  const f = rule(r, 'type.texte_liste');
  assert.equal(f.severity, 'Critique');
  assert.equal(f.category, 'Type variable');
  assert.equal(r.items[0].corrected.pf_question, 'Duree_Trajet__X!1*1Duree_Trajet_');
});

test('texte libre sans contrainte → !1*Expression ; Expression mal écrit → corrigé', () => {
  const r = audit([q('Nom_Chef__Z', 'Expression'), q('Nom_Chef__Z!1*Expresion', 'Expression')]);
  assert.equal(r.items[0].corrected.pf_question, 'Nom_Chef__Z!1*Expression');
  assert.equal(r.items[1].corrected.pf_question, 'Nom_Chef__Z!1*Expression');
});

test('__Z!Expression (usage de l\'équipe) n\'est pas un écart', () => {
  const r = audit(q('Nom_Chef__Z!Expression', 'Expression'));
  assert.deepEqual(ids(r), []);
});

test('la lettre d\'unité dans la plage est admise (la grammaire écrit __1D!0<D<31)', () => {
  const r = audit([q('Cigarette_Electro_Conso__1D!0<D<31', '', '', 'Combien de jours ?'), q('Age__1Y!0<Y<120')]);
  assert.equal(r.items[0].corrected.pf_question, 'Cigarette_Electro_Conso__1D!0<D<31');
  assert.equal(r.items[1].corrected.pf_question, 'Age__1Y!0<Y<120');
});

test('plages : lettre N/R, bornes inversées, réel sans plage', () => {
  const r = audit([q('Age__1Y!0<R<120'), q('Poids__2K!0<N<300'), q('Taille__1!5<N<1'), q('Poids_Naissance__2K')]);
  assert.equal(r.items[0].corrected.pf_question, 'Age__1Y!0<N<120');
  assert.equal(r.items[1].corrected.pf_question, 'Poids__2K!0<R<300');
  assert.ok(rule(r, 'contrainte.plage_bornes', 2));
  assert.ok(rule(r, 'contrainte.plage_reel', 3));
});

test('choix : multiplicité absente, liste absente, incohérente', () => {
  const r = audit([
    q('Sexe__X!Sexe_', 'Sexe_=[Masculin,Feminin]'),
    q('Religion__X!1*1', 'Religion_=[Chretienne,Musulmane]'),
    q('Sport__X!3*1Sport_', 'Sport_=[A|B|C]'),
  ]);
  assert.ok(rule(r, 'contrainte.multiplicite_absente', 0));
  assert.equal(r.items[1].corrected.pf_question, 'Religion__X!1*1Religion_');
  assert.ok(rule(r, 'contrainte.multiplicite_incoherente', 2));
});

test('booléen dont les modalités sont à trois états → proposition triléen', () => {
  const r = audit(q('Vaccin__B!boolean', 'Oui | Non | Ne_Sait_Pas'));
  const f = rule(r, 'type.booleen_liste');
  assert.equal(f.auto, false);
  assert.equal(f.after, 'Vaccin__C!trilean');
});

test('libellé et type : Combien / Quel / Pourquoi codés en booléen, âge en texte', () => {
  const r = audit([
    q('Cas_Rougeole__B!boolean', 'Oui | Non', '', 'Combien de cas de rougeole avez-vous notifiés ?'),
    q('Maladie__B!boolean', 'Oui | Non', '', 'Quelle maladie ?'),
    q('Refus__B!boolean', 'Oui | Non', '', 'Pourquoi refusez-vous ?'),
    q('Age_Mere__Z!1*Expression', 'Expression', '', 'Quel est l\'âge de la mère ?'),
  ]);
  assert.equal(rule(r, 'type.combien', 0).severity, 'Critique');
  assert.ok(rule(r, 'type.quel_booleen', 1));
  assert.ok(rule(r, 'type.pourquoi_booleen', 2));
  assert.ok(rule(r, 'type.age', 3));
});

test('couverture vaccinale en réel sans __2P : une seule alerte, plage conservée', () => {
  const r = audit(q('Couverture_Vaccinale_Rougeole__2!0<R<200', '0<R<200', '', 'Quelle a été la couverture vaccinale (%) pour la rougeole ?'));
  const f = rule(r, 'type.pourcentage');
  assert.equal(f.after, 'Couverture_Vaccinale_Rougeole__2P!0<R<200');
  assert.equal(ids(r).includes('type.unite_libelle'), false);
});

test('unité explicite du libellé : « en mois » avec __1N', () => {
  const r = audit(q('Age_Enfant_Mois__1N!N', 'Nombre', '', 'Age de l\'enfant (en mois)'));
  assert.equal(rule(r, 'affixe.unite_N').after, 'Age_Enfant_Mois__1M!N');
});

// ── Modalités ───────────────────────────────────────────────────────────────
test('valeurs : accents, espaces, parenthèses, numérotation, crochets parasites', () => {
  const r = audit(q('Situation__X!1*Situation_', 'Situation_ = [Célibataire | Marié(e) |Veuf/Veuve | Divorcé (e) | Concubinage) ]*'));
  assert.equal(r.items[0].corrected.pf_modalites, 'Situation_ = [Celibataire | Marie_e | Veuf/Veuve | Divorce_e | Concubinage]');
  const r2 = audit(q('Distance__X!1*Distance_', 'Distance_=[Moins de 1km | 1 à moins 3 km | 4. 5 km et plus ]*'));
  assert.equal(r2.items[0].corrected.pf_modalites, 'Distance_=[Moins_de_1km | 1_a_moins_3_km | 5_km_et_plus]');
});

test('doublons de modalités supprimés, liste à une seule modalité signalée', () => {
  const r = audit([q('Etat__X!1*1Etat_', 'Etat_=[Bon,Mauvais,bon]'), q('Etat2__X!1*1Etat2_', 'Etat2_=[Bon]')]);
  assert.equal(r.items[0].corrected.pf_modalites, 'Etat_=[Bon,Mauvais]');
  assert.ok(rule(r, 'modalites.une_seule', 1));
});

test('l\'identifiant de la contrainte fait foi (District_ → District_Sanitaire_)', () => {
  const r = audit(q('District__X!1*1Zone_', 'District_=[A,B,C]'));
  assert.equal(r.items[0].corrected.pf_modalites, 'Zone_=[A,B,C]');
  assert.equal(rule(r, 'liste.identifiant_discordant').auto, true);
});

test('choix unique avec « | » : séparateur corrigé d\'office selon la grammaire (décision du 02/11/2026)', () => {
  const r = audit(q('Religion__X!1*1Religion_', 'Religion_=[Chretienne|Musulmane|Traditionnelle]', '', 'Quelle est votre religion ?'));
  const f = rule(r, 'modalites.separateur');
  assert.equal(f.auto, true);
  assert.equal(f.applied, true);
  assert.equal(f.source, AUDIT.SRC.DECISION);
  assert.equal(r.items[0].corrected.pf_modalites, 'Religion_=[Chretienne,Musulmane,Traditionnelle]');
});

test('choix multiple avec « , » : séparateur ramené à « | » d\'office, et on peut le refuser', () => {
  const items = q('Sport__X!1*Sport_', 'Sport_=[Football,Course,Natation]', '', 'Quels sports pratiquez-vous ?');
  const r = audit(items);
  const f = rule(r, 'modalites.separateur');
  assert.equal(r.items[0].corrected.pf_modalites, 'Sport_=[Football|Course|Natation]');
  const refused = audit(items, { rejected: new Set([f.id]) });
  assert.equal(refused.items[0].corrected.pf_modalites, 'Sport_=[Football,Course,Natation]');
});

test('le libellé annonce plusieurs réponses : on propose 1*, on ne touche pas aux modalités', () => {
  const r = audit(q('Vaccins__X!1*1Vaccins_', 'Vaccins_=[VAT|Td|Rougeole]', '', 'Si oui, citez les vaccins obligatoires'));
  const f = rule(r, 'contrainte.multiplicite_libelle');
  assert.equal(f.after, 'Vaccins__X!1*Vaccins_');
  assert.equal(f.auto, true);
  assert.equal(r.items[0].corrected.pf_question, 'Vaccins__X!1*Vaccins_');
  assert.equal(ids(r).includes('modalites.separateur'), false);
});

// ── DPF : listes ────────────────────────────────────────────────────────────
test('liste Sexe_ : synonymes Homme/Femme ramenés aux valeurs du DPF, à valider', () => {
  const r = audit(q('Sexe__X!1*1Sexe_', 'Sexe_ = [Homme | Femme]'));
  const f = rule(r, 'liste.dpf_valeurs');
  assert.equal(f.category, 'Liste DPF');
  assert.match(f.message, /Homme.*Masculin/);
  assert.equal(f.auto, false);
  assert.equal(f.after, 'Sexe_ = [Masculin,Feminin,Autre,0]');
});

test('seules les listes de source DPF font référence (Instruction_ est une liste Studio)', () => {
  const r = audit(q('Niveau__X!1*1Instruction_', 'Instruction_ = [Primaire | Secondaire | Superieur | Technique | Autre]'));
  assert.equal(ids(r).includes('liste.dpf_valeurs'), false);
});

test('un sous-ensemble du DPF est Mineure, une valeur hors DPF est Majeure', () => {
  const sub = audit(q('Sexe__X!1*1Sexe_', 'Sexe_=[Masculin,Feminin]'));
  assert.equal(rule(sub, 'liste.dpf_valeurs').severity, 'Mineure');
  const extra = audit(q('Sexe__X!1*1Sexe_', 'Sexe_=[Masculin,Feminin,Garcon]'));
  assert.equal(rule(extra, 'liste.dpf_valeurs').severity, 'Majeure');
});

test('jamais une coquille du DPF en proposition, même avec un DPF ancien qui la contient', () => {
  const oldDpf = [{ identifiant: 'Type_Latrine_', valeurs: 'Latrine_Amenagee, Fosse_Sceptiqu, Latrine_partage, Latrine_Simple, 0', source: 'DPF' }];
  // la bonne graphie n'est pas un écart
  const ok = audit(q('Latrine__Type__X!1*1Type_Latrine_', 'Type_Latrine_=[Latrine_Amenagee,Fosse_Septique,Latrine_partage,Latrine_Simple,0]'), { dpfLists: oldDpf });
  assert.equal(findingsOf(ok).some(f => f.rule === 'liste.dpf_valeurs'), false);
  // une liste incomplète se voit proposer la graphie corrigée, jamais la coquille
  const sub = audit(q('Latrine__Type__X!1*1Type_Latrine_', 'Type_Latrine_=[Latrine_Amenagee,Latrine_Simple]'), { dpfLists: oldDpf });
  const f = rule(sub, 'liste.dpf_valeurs');
  assert.ok(f);
  assert.equal(/Sceptiqu/i.test(f.after + f.message), false);
  assert.match(f.after, /Fosse_Septique/);
});

test('0Activite_Sportive : le préfixe 0 est une négation, pas un « | » oublié', () => {
  const v = AUDIT.dpfValues({ valeurs: 'Maladies, Alimemtation, 0Ativite_Sportive' });
  assert.deepEqual(v, ['Maladies', 'Alimentation', '0Activite_Sportive']);
});

test('normalizeDpfCode : codes du DPF mis aux normes, en-têtes et cellules sans code non concernés', () => {
  const n = c => AUDIT.normalizeDpfCode(c).code;
  assert.equal(n('Drainage__Eaux_Type_X'), 'Drainage__Eaux_Type__X');
  assert.equal(n('Eau_Potable__Netoyage_Contenant__Régulier__C'), 'Eau_Potable__Nettoyage_Contenant__Regulier__C');
  assert.equal(n('Connaissance_Risque__Fumer__SRC__X'), 'Connaissance_Risque__Fumer__SRC');
  assert.equal(n('Menage__Taille__1N'), 'Menage__Taille__1');
  assert.equal(n('Cigarette__Conso___QTE__1'), 'Cigarette__Conso__QTE__1');
  assert.equal(n('Zone_Habitation__X '), 'Zone_Habitation__X');
  assert.equal(n('Menage__Cuisson__Combustible__X!1*1Combustible_Cuisson_'), 'Menage__Cuisson__Combustible__X!1*1Combustible_Cuisson_');
  assert.equal(AUDIT.normalizeDpfCode('Age__1Y').changed, false);
});

test('liste « jumelle » : mêmes valeurs qu\'une liste du DPF sous un autre nom', () => {
  const r = audit(q('Religion__X!1*1Croyance_', 'Croyance_=[Chretienne,Musulmane,Traditionnelle,0]'));
  const f = rule(r, 'liste.dpf_jumeau');
  assert.ok(f, ids(r).join(','));
  assert.equal(f.also.pf_question, 'Religion__X!1*1Religion_');
});

test('Règle 16 d\'après le libellé : seulement quand le libellé désigne l\'unité', () => {
  const detectAdmin = libelle => (/etablissement/i.test(libelle) ? { pf_question: 'Etablissement_Sante__X!1*1Admin_Etablissement_Sante_', pf_modalites: '' } : null);
  const r = audit([
    q('Nom_Etablissement__Z!1*Expression', 'Expression', '', 'Etablissement de santé :'),
    q('Responsable_Etablissement__Z!1*Expression', 'Expression', '', 'Responsable de l\'Etablissement de Santé'),
    q('Nom_Etablissement2__Z!1*Expression', 'Expression', '', 'Nom de l\'établissement'),
  ], { detectAdmin });
  assert.ok(rule(r, 'liste.admin_libelle', 0));
  assert.equal(findingsOf(r, 1).some(f => f.rule === 'liste.admin_libelle'), false);
  assert.equal(findingsOf(r, 2).some(f => f.rule === 'liste.admin_libelle'), false);
});

test('Règle 16 : région/district en liste inline → référentiel Admin_', () => {
  const vals = 'A|B|C|D|E|F';
  const r = audit(q('Region_Sanitaire__X!1*1Region_Sanitaire_', 'Region_Sanitaire_=[' + vals + ']'));
  const f = rule(r, 'liste.admin');
  assert.equal(f.severity, 'Majeure');
  assert.equal(f.auto, false);
  r.items[0].findings; // proposition seulement
  const accepted = audit(q('Region_Sanitaire__X!1*1Region_Sanitaire_', 'Region_Sanitaire_=[' + vals + ']'), { accepted: new Set([f.id]) });
  assert.equal(accepted.items[0].corrected.pf_question, 'Region_Sanitaire__X!1*1Admin_Region_Sanitaire_');
  assert.equal(accepted.items[0].corrected.pf_modalites, '');
});

// ── Skip Logic ──────────────────────────────────────────────────────────────
const skipForm = (skip, libelle = 'Si oui, lesquels ?') => [
  q('Effets_Constates__B!boolean', 'Oui | Non', '', 'Avez-vous constaté des effets ?'),
  q('Effets__X!1*Effets_', 'Effets_=[A|B]', skip, libelle),
];

test('skip : source inexistante → question fermée précédente proposée (« Si oui »)', () => {
  const r = audit(skipForm('Effet_Vaccination__B = Oui -> @Effets__X'));
  const f = rule(r, 'skip.source_inconnue', 1);
  assert.equal(f.severity, 'Critique');
  assert.equal(f.after, 'Effets_Constates__B = Oui -> @Effets__X');
  assert.equal(f.applied, false);
});

test('skip : cible inexistante → la question elle-même, corrigé d\'office', () => {
  const r = audit(skipForm('Effets_Constates__B = Oui -> @Effet_Type__X'));
  const f = rule(r, 'skip.cible_inconnue', 1);
  assert.equal(f.auto, true);
  assert.equal(r.items[1].corrected.pf_skip, 'Effets_Constates__B = Oui -> @Effets__X');
});

test('skip : deux corrections acceptées se cumulent (pas d\'état périmé)', () => {
  const base = audit(skipForm('Effet_Vaccination__B = Oui -> @Effet_Type__X'));
  const src = rule(base, 'skip.source_inconnue', 1);
  const r = audit(skipForm('Effet_Vaccination__B = Oui -> @Effet_Type__X'), { accepted: new Set([src.id]) });
  assert.equal(r.items[1].corrected.pf_skip, 'Effets_Constates__B = Oui -> @Effets__X');
});

test('skip : valeur hors liste, booléen comparé à autre chose que Oui/Non, source posée après', () => {
  const r1 = audit([q('Fumer_Type__X!1*1Fumer_Type_', 'Fumer_Type_=[Cigarette,Pipe]', '', 'Type'), q('Conso__1', '', 'Fumer_Type__X = Cigarete -> @Conso__1', 'Combien ?')]);
  assert.equal(rule(r1, 'skip.valeur', 1).after, 'Fumer_Type__X = Cigarette -> @Conso__1');
  const r2 = audit([q('A__B!boolean', 'Oui | Non'), q('B__1', '', 'A__B = Peut-etre -> @B__1')]);
  assert.ok(rule(r2, 'skip.valeur', 1));
  const r3 = audit([q('B__1', '', 'A__B = Oui -> @B__1'), q('A__B!boolean', 'Oui | Non')]);
  assert.ok(rule(r3, 'skip.source_apres', 0));
});

test('skip : la graphie d\'une source renommée suit la correction du code', () => {
  const r = audit([q('Enfant_Né__B!boolean', 'Oui | Non'), q('Suite__1', '', 'Enfant_Né__B = Oui -> @Suite__1')]);
  assert.equal(r.items[0].corrected.pf_question, 'Enfant_Ne__B!boolean');
  assert.equal(r.items[1].corrected.pf_skip, 'Enfant_Ne__B = Oui -> @Suite__1');
});

test('skip : « Si oui » sans règle écrite est signalé avec la règle à écrire', () => {
  const r = audit(skipForm(''));
  const f = rule(r, 'skip.manquant', 1);
  assert.equal(f.after, 'Effets_Constates__B = Oui -> @Effets__X');
});

// ── Registre des variables du DPF ───────────────────────────────────────────
test('variable du DPF reconnue, avec ou sans les accents que le DPF y a mis', () => {
  const r = audit([q('Age__1Y!0<N<120', '', '', 'Quel est votre âge ?'), q('Menage__SS__Qualite__X!1*1Qualite_', 'Qualite_=[A,B]')]);
  assert.equal(r.items[0].dpf.status, 'exact');
  assert.equal(r.items[1].dpf.status, 'exact');
  assert.equal(r.summary.dpf.exact, 2);
});

test('même question que celle du DPF sous un autre code : proposition du code normalisé, sans accent', () => {
  const libelle = 'Seriez-vous intéressée par un programme d’accompagnement pour arrêter le tabac ou la nicotine pendant l\'allaitement ?';
  const r = audit(q('Allaitement__Accompagnement__B!boolean', 'Oui | Non', '', libelle));
  const f = rule(r, 'dpf.variable_equivalente');
  assert.ok(f);
  assert.equal(f.after, 'Allaitement__Fumer_Arret__Interet_Accompagnement__B!boolean');
  assert.equal(f.auto, false);
});

test('jamais de proposition issue d\'un code du DPF lui-même non conforme (double affixe SRC__X)', () => {
  const r = audit(q('Connaissance_Risque__Fumer__SRC!1*Source_Info_Sante_', 'Source_Info_Sante_=[Personnel_Sante|Media]', '', 'Si oui, comment avez-vous appris les risques du tabac sur la grossesse ?'));
  assert.equal(findingsOf(r).some(f => f.rule === 'dpf.variable_equivalente'), false);
});

test('une variable nouvelle n\'est pas un écart', () => {
  const r = audit(q('Zebre__Vitesse__2!0<R<90', '', '', 'Quelle vitesse atteint le zèbre observé ?'));
  assert.equal(r.items[0].dpf.status, 'nouvelle');
});

// ── Doublons, faute de frappe d'après le libellé ────────────────────────────
test('code en double signalé sur la deuxième occurrence', () => {
  const r = audit([q('Age__1Y!0<N<120', '', '', 'Age'), q('Age__1Y!0<N<120', '', '', 'Age du conjoint')]);
  assert.equal(findingsOf(r, 0).some(f => f.rule === 'doublon.code'), false);
  assert.ok(rule(r, 'doublon.code', 1));
});

test('faute de frappe du radical repérée par le libellé, sans faux positif sur un libellé fautif', () => {
  const r = audit([
    q('Practiques_Compatibles__X!1*1Compatibilite_', 'Compatibilite_=[Oui,Non]', '', 'Ces pratiques sont-elles compatibles ?'),
    q('Reticence_Communautaire__B!boolean', 'Oui | Non', '', 'Existe-t-il des réticense communautaires ?'),
  ]);
  const f = rule(r, 'code.typo_libelle', 0);
  assert.equal(f.after.startsWith('Pratiques_Compatibles__X'), true);
  assert.equal(f.auto, false);
  assert.equal(findingsOf(r, 1).some(x => x.rule === 'code.typo_libelle'), false);
});

test('une coquille du DPF recopiée dans un code est corrigée (Netoyage → Nettoyage)', () => {
  const r = audit(q('Eau__Netoyage_Contenant__B!boolean', 'Oui | Non'));
  assert.equal(r.items[0].corrected.pf_question, 'Eau__Nettoyage_Contenant__B!boolean');
});

// ── Décisions de la personne qui valide ─────────────────────────────────────
test('une correction automatique peut être refusée, une proposition acceptée', () => {
  const first = audit(q('Enfant_Né__B!boolean', 'Oui | Non'));
  const f = rule(first, 'code.accents');
  const refused = audit(q('Enfant_Né__B!boolean', 'Oui | Non'), { rejected: new Set([f.id]) });
  assert.equal(refused.items[0].corrected.pf_question, 'Enfant_Né__B!boolean');
  assert.equal(refused.items[0].status, 'a_valider');
  const sep = audit(q('Religion__X!1*1Religion_', 'Religion_=[Chretienne|Musulmane|Traditionnelle]'));
  const s = rule(sep, 'modalites.separateur');
  const accepted = audit(q('Religion__X!1*1Religion_', 'Religion_=[Chretienne|Musulmane|Traditionnelle]'), { accepted: new Set([s.id]) });
  assert.equal(accepted.items[0].corrected.pf_modalites, 'Religion_=[Chretienne,Musulmane,Traditionnelle]');
});

test('l\'audit est déterministe', () => {
  const items = [q('Enfant_Né__B!boulean', 'Oui | Non'), q('Sexe__X!1*1Sexe_', 'Sexe_ = [Homme | Femme]')];
  assert.deepEqual(audit(items), audit(items));
});

test('stabilité : un questionnaire corrigé ne produit plus aucune correction automatique', () => {
  const items = [
    q('Pratique__B!boulean', 'oui|non', '', 'Utilisez-vous ?'),
    q('Enfant né-CS__B', '', '', 'L\'enfant est-il né dans un centre ?'),
    q('Situation__X!1*1Situation_', 'Situation_ = [Célibataire | Marié(e) |Veuf/Veuve | Divorcé (e) | Concubinage) ]*', '', 'Situation'),
    q('Duree__Z!1*1Duree_', 'Duree_=[Moins d\'1 Heure | 1 Heure - 2 Heure]', '', 'Durée'),
    q('Region_Sanitaire_X', '', '', 'Région'),
    q('Doses_FievreJaune__1N!N', 'Nombre', '', 'Doses'),
  ];
  const first = audit(items);
  const corrected = AUDIT.correctedItems(first, items);
  const second = audit(corrected);
  const stillAuto = second.findings.filter(f => f.auto);
  assert.deepEqual(stillAuto.map(f => f.rule), []);
  second.items.forEach((r, i) => {
    assert.equal(r.corrected.pf_question, corrected[i].pf_question);
    assert.equal(r.corrected.pf_modalites, corrected[i].pf_modalites);
  });
});

// ── Registre et lecture de fichiers ─────────────────────────────────────────
test('le registre par défaut est chargé (variables du DPF du 29/10/2026)', () => {
  assert.ok(AUDIT.defaultRegistry.variables.length >= 290);
  assert.ok(AUDIT.defaultRegistry.variables.some(v => v.code === 'Age__1Y'));
});

test('parseDpfRegistryRows lit la feuille DPF-2 (en-têtes repérés, doublons fusionnés)', () => {
  const rows = [
    [],
    ['', 'Index(Study)', 'PF Normalisée | Variable | Question', 'Libellé', 'FACTUM | Study Reference', 'Index(serie)'],
    ['', '1', 'Age__1Y', 'Quel est votre âge ?', 'FACTUM_A', '1'],
    ['', '2', 'Age__1Y', 'Quel est votre âge ?', 'FACTUM_B', '2'],
    ['', '3', 'Sexe__X', 'Sexe ?', 'FACTUM_A', '1'],
  ];
  const reg = AUDIT.parseDpfRegistryRows(rows);
  assert.equal(reg.variables.length, 2);
  assert.deepEqual(reg.studies, { 1: 'FACTUM_A', 2: 'FACTUM_B' });
  assert.throws(() => AUDIT.parseDpfRegistryRows([['a', 'b']]), /introuvable/);
});

test('détection des colonnes : PF/Question n\'est pas pris pour le libellé', () => {
  const c = AUDIT.detectCodifiedColumns(['Libelle', 'PF/Question', 'PF/Modalités', 'Skip Logic']);
  assert.deepEqual(c, { code: 1, libelle: 0, modalites: 2, skip: 3 });
  assert.equal(AUDIT.detectSheetKind(['type', 'name', 'label::French (fr)']), 'survey');
  assert.equal(AUDIT.detectSheetKind(['list_name', 'name', 'label']), 'choices');
  assert.equal(AUDIT.detectSheetKind(['Libelle', 'PF/Question']), 'codified');
  assert.equal(AUDIT.detectSheetKind(['Nom', 'Prénom']), '');
});

// ── XLSForm ─────────────────────────────────────────────────────────────────
const xlsSurvey = {
  headers: ['type', 'name', 'label::French (fr)', 'relevant'],
  rows: [
    { _row: 2, type: 'begin_group', name: 'grp', 'label::French (fr)': 'Groupe' },
    { _row: 3, type: 'select_one region', name: 'Region_Sanitaire_X', 'label::French (fr)': 'Région sanitaire' },
    { _row: 4, type: 'select_one yes_no', name: 'Responsable_B', 'label::French (fr)': 'Existe-t-il un responsable ?' },
    { _row: 5, type: 'text', name: 'Nom_Responsable_Z', 'label::French (fr)': 'Nom du responsable', relevant: "${Responsable_B} = 'oui'" },
    { _row: 6, type: 'integer', name: 'Cas_Rougeole_1', 'label::French (fr)': 'Combien de cas de rougeole ?' },
    { _row: 7, type: 'text', name: 'Autre_Maladie', 'label::French (fr)': 'Autre maladie' },
    { _row: 8, type: 'integer', name: 'Age_Mere__Z', 'label::French (fr)': 'Age de la mère' },
    { _row: 9, type: 'end_group', name: '' },
    { _row: 10, type: 'note', name: 'intro', 'label::French (fr)': 'Bonjour' },
  ],
};
const xlsChoices = {
  headers: ['list_name', 'name', 'label::French (fr)'],
  rows: [
    { list_name: 'yes_no', name: 'oui', 'label::French (fr)': 'Oui' },
    { list_name: 'yes_no', name: 'non', 'label::French (fr)': 'Non' },
    ...['abidjan_1', 'belier', 'bere', 'folon', 'gbeke', 'moronou'].map(n => ({ list_name: 'region', name: n, 'label::French (fr)': n })),
  ],
};

test('XLSForm : groupes et notes ignorés, le type du champ fixe l\'affixe attendu', () => {
  const items = AUDIT.xlsformToItems(xlsSurvey, xlsChoices);
  assert.deepEqual(items.map(i => i.pf_question), ['Region_Sanitaire_X', 'Responsable_B', 'Nom_Responsable_Z', 'Cas_Rougeole_1', 'Autre_Maladie', 'Age_Mere__Z']);
  assert.deepEqual(items.map(i => i._xls.affix), ['X', 'B', 'Z', '1', 'Z', '1']);
});

test('XLSForm : noms corrigés d\'office, type incohérent aligné sur le type du champ', () => {
  const items = AUDIT.xlsformToItems(xlsSurvey, xlsChoices);
  const r = audit(items);
  const names = r.items.map(i => i.corrected.pf_question);
  assert.deepEqual(names.slice(0, 4), ['Region_Sanitaire__X', 'Responsable__B', 'Nom_Responsable__Z', 'Cas_Rougeole__1']);
  assert.equal(names[4], 'Autre_Maladie__Z');
  assert.equal(rule(r, 'affixe.absent', 4).auto, true);
  const bad = rule(r, 'type.xlsform_affixe', 5);
  assert.equal(bad.severity, 'Critique');
  assert.equal(bad.after, 'Age_Mere__1');
  assert.equal(bad.applied, true);
  // le renommage reste réversible champ par champ
  const refused = audit(AUDIT.xlsformToItems(xlsSurvey, xlsChoices), { rejected: new Set([bad.id]) });
  assert.equal(refused.items[5].corrected.pf_question, 'Age_Mere__Z');
  assert.ok(rule(r, 'liste.admin', 0));
});

test('XLSForm : un nom sans affixe reçoit le code tiré du type du champ (casse comprise)', () => {
  const r = audit(AUDIT.xlsformToItems({ headers: ['type', 'name', 'label'], rows: [
    { _row: 2, type: 'date', name: 'date_collecte', label: 'Date de la collecte' },
    { _row: 3, type: 'text', name: 'nom_chef__z', label: 'Nom du chef' },
  ] }, { headers: [], rows: [] }));
  assert.equal(r.items[0].corrected.pf_question, 'Date_Collecte__A');
  assert.equal(rule(r, 'affixe.absent', 0).after, 'Date_Collecte__A');
  assert.equal(findingsOf(r, 0).some(f => f.rule === 'code.casse'), false, 'pas de doublon avec la proposition complète');
  assert.equal(r.items[1].corrected.pf_question, 'Nom_Chef__Z');
});

test('XLSForm : les renommages se propagent dans les ${références}', () => {
  const r = audit(AUDIT.xlsformToItems(xlsSurvey, xlsChoices));
  const map = AUDIT.xlsformRenames(r);
  assert.equal(map.get('Responsable_B'), 'Responsable__B');
  assert.equal(AUDIT.renameRefs("${Responsable_B} = 'oui' and ${autre} > 1", map), "${Responsable__B} = 'oui' and ${autre} > 1");
});

test('journal : colonnes de l\'équipe, corrections appliquées séparées des écarts à valider', () => {
  const r = audit([q('Pratique__B!boulean', 'Oui | Non'), q('Cas__B!boolean', 'Oui | Non', '', 'Combien de cas ?')]);
  const j = AUDIT.journalRows('Popul', r, i => i + 2);
  assert.equal(j.appliquees.length, 1);
  assert.deepEqual(
    { champ: j.appliquees[0].champ, ligne: j.appliquees[0].ligne, categorie: j.appliquees[0].categorie, severite: j.appliquees[0].severite },
    { champ: 'PF/Question', ligne: 2, categorie: 'Faute de frappe', severite: 'Critique' },
  );
  assert.equal(j.appliquees[0].avant, 'Pratique__B!boulean');
  assert.equal(j.appliquees[0].apres, 'Pratique__B!boolean');
  assert.equal(j.aValider.length >= 1, true);
});

// ── Fichier de données (export Kobo) ────────────────────────────────────────
const dataHeaders = ['_id', '_uuid', 'grp/Nb_Cas', 'Poids__Z', 'Sexe', 'Sport__X', 'Sport__X/Football', 'Sport__X/Course', 'Région sanitaire', 'start'];
const dataRows = Array.from({ length: 12 }, (_, i) => [String(i), 'u' + i, String(i + 2), (50 + i / 2).toFixed(1), i % 2 ? 'Masculin' : 'Feminin', 'Football', '1', '0', i % 3 ? 'ABIDJAN_1' : 'BELIER', '2026-05-01 08:00:00']);

test('données : colonnes système et enfants d\'un choix multiple écartés, chemin de groupe gardé', () => {
  const items = AUDIT.datasetToItems(dataHeaders, dataRows);
  assert.deepEqual(items.map(i => i._xls.header), ['grp/Nb_Cas', 'Poids__Z', 'Sexe', 'Sport__X', 'Région sanitaire', 'start']);
  assert.deepEqual(items.map(i => i._xls.row), [3, 4, 5, 6, 9, 10]);
  assert.equal(items[3]._xls.children.length, 2);
});

test('données : le type se lit sur les valeurs (entier, réel) ; un choix deviné reste une proposition', () => {
  const items = AUDIT.datasetToItems(dataHeaders, dataRows);
  const r = audit(items);
  const byHeader = h => r.items[items.findIndex(i => i._xls.header === h)];
  assert.equal(byHeader('grp/Nb_Cas').corrected.pf_question, 'Nb_Cas__1');
  assert.equal(byHeader('Poids__Z').corrected.pf_question, 'Poids__2');
  const sexe = byHeader('Sexe');
  assert.equal(sexe.corrected.pf_question, 'Sexe');
  assert.equal(sexe.findings.find(f => f.rule === 'affixe.absent').auto, false);
  assert.equal(sexe.findings.find(f => f.rule === 'affixe.absent').after, 'Sexe__X');
});

test('données : un en-tête qui est un libellé reçoit un code proposé, jamais appliqué sans accord', () => {
  const items = AUDIT.datasetToItems(dataHeaders, dataRows);
  const derive = it => ({ pf_question: 'Region_Sanitaire__X!1*1Admin_Region_Sanitaire_', pf_modalites: '' + it.libelle.length });
  const r = audit(items, { derive });
  const i = items.findIndex(x => x._xls.header === 'Région sanitaire');
  const f = rule(r, 'code.vide', i);
  assert.equal(f.auto, false);
  assert.equal(f.after, 'Region_Sanitaire__X');
  assert.match(f.message, /libellé de la question/);
  const ok = audit(items, { derive, accepted: new Set([f.id]) });
  assert.equal(ok.items[i].corrected.pf_question, 'Region_Sanitaire__X');
});

test('données : renommage des en-têtes avec chemin de groupe et colonnes enfants', () => {
  const items = AUDIT.datasetToItems(dataHeaders, dataRows);
  const r = audit(items);
  const map = AUDIT.datasetHeaderRenames(r);
  assert.equal(map.get('grp/Nb_Cas'), 'grp/Nb_Cas__1');
  assert.equal(map.get('Poids__Z'), 'Poids__2');
  assert.equal(map.has('Sexe'), false);
  assert.equal(map.has('_id'), false);
  const sport = audit(AUDIT.datasetToItems(['Sport_X', 'Sport_X/Football', 'Sport_X/Course'], [['Football', '1', '0'], ['Course', '0', '1'], ['Football', '1', '0']]));
  const m2 = AUDIT.datasetHeaderRenames(sport);
  assert.equal(m2.get('Sport_X'), 'Sport__X');
  assert.equal(m2.get('Sport_X/Football'), 'Sport__X/Football');
  assert.equal(m2.get('Sport_X/Course'), 'Sport__X/Course');
});

test('données : les colonnes Kobo start/end sont des variables générées', () => {
  const items = AUDIT.datasetToItems(['start', 'end'], [['2026-05-01 08:00:00', '2026-05-01 09:00:00'], ['2026-05-01 08:10:00', '2026-05-01 09:10:00'], ['2026-05-01 08:20:00', '2026-05-01 09:20:00']]);
  const r = audit(items);
  assert.equal(r.items[0].corrected.pf_question, 'Entretien__Debut__G');
  assert.equal(r.items[1].corrected.pf_question, 'Entretien__Fin__G');
});

test('inferColumn : types sûrs et types probables', () => {
  assert.equal(AUDIT.inferColumn(['1', '2', '3']).affix, '1');
  assert.equal(AUDIT.inferColumn(['1,5', '2', '3.2']).affix, '2');
  assert.equal(AUDIT.inferColumn(['2026-01-02', '2026-01-03', '2026-01-04']).affix, 'A');
  assert.equal(AUDIT.inferColumn(['Oui', 'Non', 'oui']).affix, 'B');
  const choice = AUDIT.inferColumn(['A', 'B', 'A', 'B', 'A', 'B']);
  assert.deepEqual([choice.affix, choice.suggest], ['', 'X']);
  assert.equal(AUDIT.inferColumn(['x', 'y']).suggest, '');
});

test('doublon de code : un code distinct est proposé d\'après le mot qui différencie les libellés', () => {
  const items = [
    q('Nombre_Doses__1', '', '', 'Nombre de doses reçues pour la Rougeole'),
    q('Nombre_Doses__1', '', '', 'Nombre de doses reçues pour la VPO'),
    q('Nombre_Doses__1', '', '', 'Nombre de doses reçues pour la Fièvre jaune'),
  ];
  const r = audit(items);
  assert.equal(findingsOf(r, 0).some(f => f.rule === 'doublon.code'), false);
  const f1 = rule(r, 'doublon.code', 1), f2 = rule(r, 'doublon.code', 2);
  assert.equal(f1.after, 'Nombre_Doses_VPO__1');
  assert.equal(f2.after, 'Nombre_Doses_Fievre_Jaune__1');
  assert.equal(f1.applied, false);
  const ok = audit(items, { accepted: new Set([f1.id, f2.id]) });
  assert.deepEqual(ok.items.map(i => i.corrected.pf_question), ['Nombre_Doses__1', 'Nombre_Doses_VPO__1', 'Nombre_Doses_Fievre_Jaune__1']);
});

test('doublon de code : une question répétée (même libellé) n\'est pas renommée', () => {
  const r = audit([q('Age__1Y', '', '', 'Age'), q('Age__1Y', '', '', 'Age')]);
  assert.equal(rule(r, 'doublon.code', 1).after, null);
});

// ── Libellés non codifiés : les codifier ────────────────────────────────────
const stubDerive = it => ({
  'Quel est votre sexe ?': { pf_question: 'Sexe__X!1*1Sexe_', pf_modalites: 'Sexe_=[Masculin,Feminin,Autre]' },
  'Avez-vous un emploi ?': { pf_question: 'Emploi__B!boolean', pf_modalites: 'Oui | Non' },
  'Si oui, quel est votre métier ?': { pf_question: 'Emploi_Metier__Z!1*Expression', pf_modalites: 'Expression' },
  "Seriez-vous intéressée par un programme d’accompagnement pour arrêter le tabac ou la nicotine pendant l'allaitement ?": { pf_question: 'Accompagnement_Allaitement__B!boolean', pf_modalites: 'Oui | Non' },
}[it.libelle] || null);

test('libellé sans code : code ET modalités proposés d\'après le libellé, rien d\'appliqué sans accord', () => {
  const items = [q('', '', '', 'Quel est votre sexe ?')];
  const r = audit(items, { derive: stubDerive });
  const f = rule(r, 'code.vide');
  assert.equal(f.severity, 'Critique');
  assert.match(f.message, /non codifié/);
  assert.equal(f.after, 'Sexe__X!1*1Sexe_');
  assert.equal(f.applied, false);
  assert.deepEqual(f.also, { pf_modalites: 'Sexe_=[Masculin,Feminin,Autre]' });
  assert.equal(r.items[0].corrected.pf_question, '');
  assert.equal(r.summary.nonCodifiees, 1);
  const ok = audit(items, { derive: stubDerive, accepted: new Set([f.id]) });
  assert.equal(ok.items[0].corrected.pf_question, 'Sexe__X!1*1Sexe_');
  assert.equal(ok.items[0].corrected.pf_modalites, 'Sexe_=[Masculin,Feminin,Autre]');
});

test('libellé sans code : les modalités déjà saisies ne sont pas écrasées', () => {
  const items = [q('', 'Oui | Non', '', 'Avez-vous un emploi ?')];
  const f = rule(audit(items, { derive: stubDerive }), 'code.vide');
  assert.equal(f.also, null);
});

test('libellé sans code et codifieur indisponible : constat sans proposition, jamais d\'invention', () => {
  const r = audit([q('', '', '', 'Quel est votre sexe ?')]);
  const f = rule(r, 'code.vide');
  assert.equal(f.after, null);
  assert.equal(r.items[0].corrected.pf_question, '');
});

test('une fois codifiés, les libellés sont audités : saut « Si oui » proposé, variable du DPF reconnue', () => {
  const items = [q('', '', '', 'Avez-vous un emploi ?'), q('', '', '', 'Si oui, quel est votre métier ?')];
  const first = audit(items, { derive: stubDerive });
  const accepted = new Set(first.findings.filter(f => f.rule === 'code.vide').map(f => f.id));
  const r = audit(items, { derive: stubDerive, accepted });
  assert.deepEqual(r.items.map(i => i.corrected.pf_question), ['Emploi__B!boolean', 'Emploi_Metier__Z!1*Expression']);
  assert.equal(rule(r, 'skip.manquant', 1).after, 'Emploi__B = Oui -> @Emploi_Metier__Z');

  const lib = "Seriez-vous intéressée par un programme d’accompagnement pour arrêter le tabac ou la nicotine pendant l'allaitement ?";
  const d = audit([q('', '', '', lib)], { derive: stubDerive });
  const id = rule(d, 'code.vide').id;
  const dd = audit([q('', '', '', lib)], { derive: stubDerive, accepted: new Set([id]) });
  assert.equal(rule(dd, 'dpf.variable_equivalente').after, 'Allaitement__Fumer_Arret__Interet_Accompagnement__B!boolean');
});

test('feuille de libellés seuls reconnue ; titres de section écartés, libellés sans code gardés', () => {
  assert.equal(AUDIT.detectSheetKind(['Libellé']), 'libelles');
  assert.equal(AUDIT.detectSheetKind(['Question', 'Modalités']), 'libelles');
  assert.equal(AUDIT.detectSheetKind(['Libelle', 'PF/Question']), 'codified');
  assert.equal(AUDIT.detectSheetKind(['Nom', 'Prénom']), '');
  assert.equal(AUDIT.isSectionTitle('SECTION 1 : IDENTIFIANTS DE L\'ÉTABLISSEMENT'), true);
  assert.equal(AUDIT.isSectionTitle('Partie B — Connaissances'), true);
  assert.equal(AUDIT.isSectionTitle('IDENTIFICATION'), true);
  assert.equal(AUDIT.isSectionTitle('Quel est votre âge ?'), false);
  assert.equal(AUDIT.isSectionTitle('Etablissement de santé :'), false);
  assert.equal(AUDIT.isSectionTitle('Sexe'), false);

  const table = { headers: ['Libellé', 'Modalités'], rows: [
    { _row: 2, Libellé: 'SECTION 1 : IDENTITÉ', Modalités: '' },
    { _row: 3, Libellé: 'Quel est votre sexe ?', Modalités: 'Masculin | Féminin' },
    { _row: 4, Libellé: 'Région sanitaire', Modalités: '' },
    { _row: 5, Libellé: '', Modalités: '' },
  ] };
  const cols = AUDIT.detectCodifiedColumns(table.headers);
  assert.equal(cols.code, -1);
  const out = AUDIT.questionnaireToItems(table, cols);
  assert.deepEqual(out.rows, [3, 4]);
  assert.equal(out.sections, 1);
  assert.deepEqual(out.items.map(i => [i.libelle, i.pf_question, i.pf_modalites]), [['Quel est votre sexe ?', '', 'Masculin | Féminin'], ['Région sanitaire', '', '']]);
});

test('questionnaire codifié : une ligne sans code reste une question à codifier', () => {
  const table = { headers: ['Libellé', 'PF/Question', 'PF/Modalités', 'Skip Logic'], rows: [
    { _row: 2, 'Libellé': 'Quel est votre âge ?', 'PF/Question': 'Age__1Y!0<N<120', 'PF/Modalités': '', 'Skip Logic': '' },
    { _row: 3, 'Libellé': 'Avez-vous un emploi ?', 'PF/Question': '', 'PF/Modalités': '', 'Skip Logic': '' },
  ] };
  const out = AUDIT.questionnaireToItems(table, AUDIT.detectCodifiedColumns(table.headers));
  assert.deepEqual(out.rows, [2, 3]);
  assert.equal(out.items[1].pf_question, '');
});

// ── Corrections grammaticales proposées pour les types incohérents avec le libellé ──
test('« Combien » codé en booléen : entier proposé, avec ses modalités ; appliqué seulement sur accord', () => {
  const items = [q('Nombre_Enfants__B!boolean', 'Oui | Non', '', "Combien d'enfants avez-vous ?")];
  const f = rule(audit(items), 'type.combien');
  assert.equal(f.after, 'Nombre_Enfants__1');
  assert.deepEqual(f.also, { pf_modalites: 'Nombre entier' });
  assert.equal(f.applied, false);
  const ok = audit(items, { accepted: new Set([f.id]) });
  assert.equal(ok.items[0].corrected.pf_question, 'Nombre_Enfants__1');
  assert.equal(ok.items[0].corrected.pf_modalites, 'Nombre entier');
});

test('« Âge » codé en booléen ou en texte : __1Y!0<N<120 (règle de la grammaire)', () => {
  const items = [q('Age__B!boolean', 'Oui | Non', '', 'Quel est votre âge ?'), q('Age_Mere__Z!1*Expression', 'Expression', '', "Quel est l'âge de la mère ?")];
  const r = audit(items);
  assert.equal(rule(r, 'type.age', 0).after, 'Age__1Y!0<N<120');
  assert.equal(rule(r, 'type.age', 1).after, 'Age_Mere__1Y!0<N<120');
});

test('« Pourquoi / Quel / Où » codés en booléen, même derrière « Si oui, » : texte libre proposé', () => {
  const items = [
    q('Metier__B!boolean', 'Oui | Non', '', 'Si oui, quel est votre métier ?'),
    q('Refus__B!boolean', 'Oui | Non', '', 'Selon vous, pourquoi refuse-t-on le vaccin ?'),
    q('Lieu__B!boolean', 'Oui | Non', '', 'Où avez-vous reçu le vaccin ?'),
  ];
  const r = audit(items);
  assert.equal(rule(r, 'type.quel_booleen', 0).after, 'Metier__Z!1*Expression');
  assert.equal(rule(r, 'type.pourquoi_booleen', 1).after, 'Refus__Z!1*Expression');
  assert.equal(rule(r, 'type.ou_booleen', 2).after, 'Lieu__Z!1*Expression');
  assert.equal(rule(r, 'type.quel_booleen', 0).also.pf_modalites, 'Expression');
});

test('une vraie question fermée n\'est pas touchée par ces règles', () => {
  const r = audit(q('Emploi__B!boolean', 'Oui | Non', '', 'Avez-vous un emploi ?'));
  assert.deepEqual(findingsOf(r).map(f => f.rule).filter(x => x.startsWith('type.')), []);
});

test('XLSForm : ces corrections ne touchent jamais au nom (le type du champ fait foi)', () => {
  const items = AUDIT.xlsformToItems({ headers: ['type', 'name', 'label'], rows: [{ _row: 2, type: 'select_one yes_no', name: 'Age__B', label: 'Quel est votre âge ?' }] }, { headers: ['list_name', 'name', 'label'], rows: [{ list_name: 'yes_no', name: 'oui', label: 'Oui' }, { list_name: 'yes_no', name: 'non', label: 'Non' }] });
  const r = audit(items);
  assert.equal(rule(r, 'type.age', 0).after, null);
});

test('le code proposé pour un libellé sans code est lui-même contrôlé (mot interrogatif, accents)', () => {
  const derive = it => (it.libelle.startsWith('Pourquoi')
    ? { pf_question: 'Pourquoi_Avez_Refuse__B!boolean', pf_modalites: 'Oui | Non' }
    : { pf_question: 'Enfant_Né__B!boolean', pf_modalites: 'Oui | Non' });
  const items = [q('', '', '', 'Pourquoi avez-vous refusé le vaccin ?'), q('', '', '', "L'enfant est-il né dans un centre de santé ?")];
  const first = audit(items, { derive });
  const accepted = new Set(first.findings.filter(f => f.rule === 'code.vide').map(f => f.id));
  const r = audit(items, { derive, accepted });
  assert.ok(rule(r, 'code.interrogatif', 0));
  assert.equal(r.items[1].corrected.pf_question, 'Enfant_Ne__B!boolean');
});

test('stabilité : un questionnaire codifié par l\'outil, une fois toutes les propositions acceptées, est stable', () => {
  const derive = it => ({
    'Quel est votre âge ?': { pf_question: 'Age__1Y!0<N<120', pf_modalites: 'Années' },
    'Avez-vous un emploi ?': { pf_question: 'Emploi__B!boolean', pf_modalites: 'Oui | Non' },
    'Si oui, quel est votre métier ?': { pf_question: 'Metier__B!boolean', pf_modalites: 'Oui | Non' },
  }[it.libelle] || null);
  const items = [q('', '', '', 'Quel est votre âge ?'), q('', '', '', 'Avez-vous un emploi ?'), q('', '', '', 'Si oui, quel est votre métier ?')];
  const first = audit(items, { derive });
  let accepted = new Set(first.findings.filter(f => f.rule === 'code.vide').map(f => f.id));
  const second = audit(items, { derive, accepted });
  second.findings.filter(f => f.after != null && !f.applied).forEach(f => accepted.add(f.id));
  const third = audit(items, { derive, accepted });
  const corrected = AUDIT.correctedItems(third, items);
  assert.equal(corrected[2].pf_question, 'Metier__Z!1*Expression');
  assert.equal(corrected[2].pf_skip, 'Emploi__B = Oui -> @Metier__Z');
  const again = audit(corrected);
  assert.deepEqual(again.findings.filter(f => f.auto).map(f => f.rule), []);
});
