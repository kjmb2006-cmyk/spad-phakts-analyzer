// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS · Audit de conformité d'un questionnaire codifié (grammaire + DPF)
//
//  Entrée  : une liste de questions { libelle, pf_question, pf_modalites, pf_skip }
//            (lue d'un questionnaire codifié ou d'un XLSForm, voir xlsformToItems).
//  Sortie  : pour chaque question, les écarts à la grammaire PHAKTS et au DPF
//            (« constats »), la correction juste quand elle est déterminée, et le
//            questionnaire corrigé.
//
//  Principes :
//   • Un constat n'est CORRIGÉ d'office (auto) que si la correction est
//     déterministe (accents, séparateur, constante de type…). Tout ce qui relève
//     d'un choix (type de la variable, multiplicité, liste du DPF, saut) est
//     PROPOSÉ et attend la décision de la personne qui valide.
//   • Le DPF n'est pas un oracle : il contient lui-même des accents et des
//     coquilles (DPF_LEXIE_TYPOS). Les comparaisons se font sur une clé normalisée
//     et une graphie fautive du DPF n'est jamais proposée comme correction.
//   • Catégories et sévérités reprennent le « Journal des corrections PHAKTS »
//     tenu par l'équipe (Modalités, Type variable, Sémantique, Faute de frappe,
//     Skip Logic ; Mineure, Majeure, Critique).
//
//  Chargé par PHAKTS·STUDIO.html (après phakts-core.js et dpf-registry.js) et par
//  Node (tests, scripts). Dépend de phakts-core.js : même grammaire, une seule copie.
// ─────────────────────────────────────────────────────────────────────────────
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    let registry = null;
    try { registry = require('./dpf-registry.js'); } catch (_) { /* registre facultatif */ }
    module.exports = factory(require('./phakts-core.js'), registry);
  } else {
    root.PHAKTS_AUDIT = factory(root.PHAKTS_CORE, root.PHAKTS_DPF_REGISTRY || null);
  }
})(typeof self !== 'undefined' ? self : this, function (CORE, DEFAULT_REGISTRY) {
  'use strict';

  const AUDIT_VERSION = 'audit-2026.1 / grammaire ' + CORE.GRAMMAR_VERSION;

  const SEV = { CRITIQUE: 'Critique', MAJEURE: 'Majeure', MINEURE: 'Mineure' };
  const SEV_RANK = { Critique: 0, Majeure: 1, Mineure: 2 };
  const CAT = {
    TYPO: 'Faute de frappe', TYPE: 'Type variable', MODA: 'Modalités', SEM: 'Sémantique',
    SKIP: 'Skip Logic', NOM: 'Nommage', LISTE: 'Liste DPF', DPF: 'Registre DPF', DOUBLON: 'Doublon',
  };
  const SRC = {
    GRAMMAIRE: 'Grammaire PHAKTS',
    DPF_LISTES: 'DPF — listes standard',
    DPF_VARIABLES: 'DPF-2 — variables normalisées',
    DPF_TODO: 'DPF — ToDo (décision en attente)',
    DECISION: 'Décision SPAD du 02/11/2026 : la règle de la grammaire s\'applique',
    REGLE16: 'Grammaire PHAKTS — Règle 16 (référentiels Admin_)',
    REGLE17: 'Grammaire PHAKTS — Règle 17 (Skip Logic)',
  };

  // ── Coquilles avérées du DPF (v. 29/10/2026) ──────────────────────────────
  // Le DPF contient des fautes ; elles ne doivent ni être traitées comme la
  // norme ni être proposées en correction. Clé = graphie fautive sans accent,
  // en minuscules. La fréquence ne prouve rien (« Hygienne » y figure 4 fois
  // contre 3 pour « Hygiene »).
  const DPF_LEXIE_TYPOS = {
    coordonees: 'Coordonnees', evalution: 'Evaluation', netoyage: 'Nettoyage',
    tabgagique: 'Tabagique', yamoussouko: 'Yamoussoukro', hygienne: 'Hygiene',
    conssomation: 'Consommation', innondation: 'Inondation', prescrition: 'Prescription',
    racordement: 'Raccordement', rennoncement: 'Renoncement', dortoire: 'Dortoir',
    dsitrict: 'District', infifferent: 'Indifferent', alimemtation: 'Alimentation',
    sceptiqu: 'Septique', sceptique: 'Septique', ativite: 'Activite',
  };

  // ── Outils de texte ───────────────────────────────────────────────────────
  const strip = s => String(s == null ? '' : s)
    .replace(/œ/g, 'oe').replace(/Œ/g, 'OE').replace(/æ/g, 'ae').replace(/Æ/g, 'AE')
    .normalize('NFD').replace(/[̀-ͯ]/g, '');
  const plain = s => strip(s).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : s);
  const esc = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  // Distance d'édition (Levenshtein), bornée : au-delà de max, renvoie max + 1.
  function lev(a, b, max) {
    max = max == null ? 9 : max;
    if (a === b) return 0;
    if (Math.abs(a.length - b.length) > max) return max + 1;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      let min = i;
      for (let j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (cur[j] < min) min = cur[j];
      }
      if (min > max) return max + 1;
      prev = cur;
    }
    return prev[b.length];
  }

  // Une seule insertion, suppression ou transposition (hors substitution).
  function isSlip(a, b) {
    if (a === b) return false;
    if (Math.abs(a.length - b.length) > 1) return false;
    if (a.length === b.length) {
      const d = [];
      for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) d.push(i);
      return d.length === 2 && d[1] === d[0] + 1 && a[d[0]] === b[d[1]] && a[d[1]] === b[d[0]];
    }
    const [s, l] = a.length < b.length ? [a, b] : [b, a];
    for (let i = 0; i < l.length; i++) if (l.slice(0, i) + l.slice(i + 1) === s) return true;
    return false;
  }

  const STOPWORDS = new Set(('le la les un une des du de d l au aux et ou en a est sont vous votre vos avez etes quel quelle ' +
    'quels quelles que qui quoi dans par pour sur avec sans ce cette ces si oui non il elle ils elles nous leur leurs son sa ses ' +
    'y pas ne n se s c j m t qu on plus moins tres avoir etre fait faire cas si ete depuis lors lorsque entre ainsi comme ' +
    'selon vos notre nos apres avant chez peut peuvent doit doivent merci svp precisez preciser citez citer').split(' '));
  const contentWords = libelle => plain(libelle).split(' ').filter(w => w.length >= 3 && !STOPWORDS.has(w));

  // ── Lecture d'un code PHAKTS ──────────────────────────────────────────────
  const FIXED_AFFIXES = ['B', 'C', 'A', 'X', 'Z', 'P', 'G', 'SRC'];
  const INT_UNITS = 'YMWDHUQ';
  const REAL_UNITS = 'KTLSPVFI';

  // ok | dpf-N (« 1N », utilisé par le DPF mais absent de la grammaire) | bad
  function affixStatus(a) {
    if (FIXED_AFFIXES.includes(a)) return 'ok';
    if (a === '1' || a === '2') return 'ok';
    if (a.length === 2 && a[0] === '1' && INT_UNITS.includes(a[1])) return 'ok';
    if (a.length === 2 && a[0] === '2' && REAL_UNITS.includes(a[1])) return 'ok';
    if (a === '1N') return 'dpf-N';
    return 'bad';
  }

  function splitQ(q) {
    const s = String(q == null ? '' : q);
    const i = s.indexOf('!');
    return { code: i >= 0 ? s.slice(0, i) : s, constraint: i >= 0 ? s.slice(i + 1) : '' };
  }
  const joinQ = (code, constraint) => (constraint ? code + '!' + constraint : code);
  // Nom déjà codifié, même abîmé : affixe valide, affixe en minuscules, ou affixe séparé par un seul « _ ».
  function looksCoded(code) {
    const a = code.split('__').length >= 2 ? code.split('__').pop() : '';
    if (a && (affixStatus(a) !== 'bad' || affixStatus(a.toUpperCase()) !== 'bad')) return true;
    return !a && /^.*[A-Za-z0-9]_(B|C|A|X|Z|P|G|SRC|[12][YMWDHUQKTLSPVFIN]?)$/i.test(code);
  }
  const withConstraint = (q, k) => joinQ(splitQ(q).code, k);
  const codeOf = q => splitQ(q).code.trim();
  const affixOf = code => { const s = code.split('__'); return s.length >= 2 ? s[s.length - 1] : ''; };
  const stemOf = code => { const s = code.split('__'); return s.length >= 2 ? s.slice(0, -1).join('__') : code; };

  // Clé de comparaison de deux codes : sans accent ni casse, coquilles du DPF
  // corrigées, « _ » de fin ignorés.
  function fixKnownTypos(code) {
    return code.split('_').map(t => {
      const fixed = DPF_LEXIE_TYPOS[plain(t).replace(/ /g, '')];
      return fixed || t;
    }).join('_');
  }
  function codeKey(code) {
    return fixKnownTypos(strip(code)).toLowerCase().replace(/[^a-z0-9_]/g, '').replace(/_{3,}/g, '__').replace(/^_+|_+$/g, '').replace(/__1n$/, '__1');
  }

  // ── Listes de modalités « Liste_=[a|b|c] » ────────────────────────────────
  function parseListDef(text) {
    const s = String(text || '').trim();
    const m = s.match(/^([^=[\](){}|]+?)\s*=\s*([[({])?\s*([\s\S]*?)\s*([\])}])?\s*[*.;]*$/);
    if (!m) return null;
    const content = m[3];
    const hasPipe = content.includes('|');
    const hasComma = content.includes(',');
    const sep = hasPipe ? '|' : ',';
    const values = content.split(sep).map(v => v.trim());
    return {
      id: m[1].trim(), open: m[2] || '', close: m[4] || '', content, values, sep,
      mixed: hasPipe && hasComma,
      spacedEq: /\s=\s/.test(s),
      spacedSep: hasPipe ? /\s\|\s/.test(content) : /,\s/.test(content),
      junk: /[\])}][*.;\s]*[*.;]\s*$|[\])}]\s*[*.;]+$/.test(s) && !/[\])}]$/.test(s),
      bracketsOk: m[2] === '[' && m[4] === ']',
    };
  }

  function buildListDef(ld, id, values) {
    const eq = ld.spacedEq ? ' = ' : '=';
    const sep = ld.sep === '|' ? (ld.spacedSep ? ' | ' : '|') : (ld.spacedSep ? ', ' : ',');
    return id + eq + '[' + values.join(sep) + ']';
  }

  // Valeur d'une modalité : sans accent, sans espace ni ponctuation (Snake_Case).
  function canonValue(v) {
    let s = strip(String(v).trim()).replace(/^\d+\.\s+(?=\S)/, '');
    s = s.replace(/[’'`´]/g, '_').replace(/[()]/g, '_').replace(/\s+[-–—]\s+/g, '_').replace(/\s+/g, '_');
    s = s.replace(/[^A-Za-z0-9_/-]/g, '');
    return s.replace(/_+/g, '_').replace(/^_+|_+$/g, '');
  }
  const valueKey = v => strip(v).toLowerCase().replace(/[^a-z0-9]/g, '');

  // Identifiant de liste : Snake_Case terminé par « _ ».
  function canonListId(id) {
    let s = canonValue(id).replace(/\/|-/g, '_').replace(/_+/g, '_');
    if (!s) return s;
    return /_$/.test(s) ? s : s + '_';
  }

  // Valeurs d'une liste du DPF, coquilles corrigées (« 0Ativite_Sportive » =
  // « 0 » collé à « Activite_Sportive » faute d'un « | »).
  function dpfValues(entry) {
    const out = [];
    for (const raw of CORE.splitListValues(entry.valeurs)) {
      // « 0 » seul = option Autre/Aucun ; « 0Activite_Sportive » = négation (préfixe 0 de la grammaire)
      const neg = /^0(?=[A-Za-z])/.test(raw) ? '0' : '';
      const v = (neg ? raw.slice(1) : raw).split('_').map(t => DPF_LEXIE_TYPOS[plain(t).replace(/ /g, '')] || t).join('_');
      if (v) out.push(neg + v);
    }
    return out;
  }

  // Code de variable du DPF mis aux normes : accents, coquilles, séparateurs, casse, affixe.
  // Renvoie le code et la liste des corrections (pour le journal de nettoyage du DPF).
  function normalizeDpfCode(raw) {
    const notes = [];
    const { code: c0, constraint } = splitQ(String(raw == null ? '' : raw));
    let code = c0;
    const step = (rule, next) => { if (next !== code) { notes.push({ rule, before: code, after: next }); code = next; } };
    step('espaces', code.trim().replace(/\s+/g, '_'));
    step('accents', strip(code));
    step('coquilles', code.split('_').map(t => DPF_LEXIE_TYPOS[plain(t).replace(/ /g, '')] || t).join('_'));
    step('caracteres', code.replace(/[^A-Za-z0-9_]/g, '_'));
    step('soulignes', code.replace(/_{3,}/g, '__').replace(/^_+|_+$/g, ''));
    // affixe collé par un seul « _ » à un code qui a déjà des « __ » (Drainage__Eaux_Type_X)
    {
      const segs = code.split('__');
      const last = segs[segs.length - 1];
      const m = segs.length >= 2 && affixStatus(last) === 'bad' && last.match(/^(.+)_(B|C|A|X|Z|P|G|SRC|[12][YMWDHUQKTLSPVFIN]?)$/);
      if (m) step('affixe_separateur', segs.slice(0, -1).concat([m[1], m[2]]).join('__'));
    }
    step('double_affixe', code.replace(/__SRC__X$/, '__SRC'));
    step('unite_N', code.replace(/__1N$/, '__1'));
    step('casse', fixCaseTop(code));
    return { code: joinQ(code, constraint), changed: code !== c0, notes };
  }
  function fixCaseTop(code) {
    const segs = code.split('__');
    return segs.map((s2, i) => {
      if (segs.length > 1 && i === segs.length - 1 && affixStatus(s2) !== 'bad') return s2;
      return s2.split('_').map(t => (/^[a-z]/.test(t) ? cap(t) : t)).join('_');
    }).join('__');
  }

  // ── Registre des variables du DPF (feuille DPF-2) ─────────────────────────
  function parseDpfRegistryRows(rows) {
    const cell = c => (c == null ? '' : String(c)).trim();
    let hdr = -1, cCode = -1, cLib = -1, cFac = -1, cSer = -1;
    for (let r = 0; r < rows.length && hdr < 0; r++) {
      const row = rows[r] || [];
      const code = row.findIndex(v => /PF\s*Normalis|Variable\s*\|\s*Question/i.test(cell(v)));
      if (code >= 0) {
        hdr = r; cCode = code;
        cLib = row.findIndex(v => /^Libell/i.test(cell(v)));
        cFac = row.findIndex(v => /FACTUM/i.test(cell(v)));
        cSer = row.findIndex(v => /Index\s*\(\s*s[ée]rie/i.test(cell(v)));
      }
    }
    if (hdr < 0) throw new Error('colonne « PF Normalisée | Variable | Question » introuvable dans la feuille DPF-2');
    const variables = [];
    const studies = {};
    const seen = new Map();
    for (let r = hdr + 1; r < rows.length; r++) {
      const row = rows[r] || [];
      const code = cell(row[cCode]);
      if (!code) continue;
      const serie = cSer >= 0 ? cell(row[cSer]) : '';
      const factum = cFac >= 0 ? cell(row[cFac]) : '';
      if (serie && factum && !studies[serie]) studies[serie] = factum;
      if (seen.has(code)) continue;
      seen.set(code, true);
      variables.push({ code, libelle: cLib >= 0 ? cell(row[cLib]).replace(/\s+/g, ' ') : '', serie });
    }
    return { variables, studies };
  }

  function buildRegistry(raw) {
    const variables = (raw && raw.variables) || [];
    const byKey = new Map();
    const byStem = new Map();
    const withLib = [];
    const lexies = new Set();
    for (const v of variables) {
      const q = splitQ(v.code).code.trim();
      const key = codeKey(q);
      if (!key) continue;
      const entry = { code: v.code, key, libelle: v.libelle || '', serie: v.serie || '' };
      if (!byKey.has(key)) byKey.set(key, entry);
      const stem = codeKey(stemOf(q));
      if (!byStem.has(stem)) byStem.set(stem, []);
      byStem.get(stem).push(entry);
      if (entry.libelle) withLib.push({ entry, words: new Set(contentWords(entry.libelle)) });
      q.split('_').forEach(t => { const p = plain(t).replace(/ /g, ''); if (p) lexies.add(p); });
    }
    return { size: byKey.size, byKey, byStem, withLib, lexies, studies: (raw && raw.studies) || {} };
  }

  const jaccard = (a, b) => {
    if (!a.size || !b.size) return 0;
    let n = 0;
    a.forEach(w => { if (b.has(w)) n++; });
    return n / (a.size + b.size - n);
  };

  // ── Indices tirés du libellé ──────────────────────────────────────────────
  // Unité PHAKTS suggérée par une mention EXPLICITE dans le libellé (jamais
  // « mois » seul : « enfants de 0–23 mois » décrit une cible, pas l'unité).
  function unitHint(libelle) {
    const raw = String(libelle || '');
    const n = ' ' + plain(libelle) + ' ';
    if (/%/.test(raw) || /\b(pourcentage|taux|proportion|couverture|prevalence)\b/.test(n)) return '2P';
    if (/\b(cout|montant|prix|tarif|budget|salaire|revenus?|depenses?|cfa|fcfa|francs?)\b/.test(n)) return '2F';
    if (/\b(kg|kilogrammes?|poids)\b/.test(n)) return '2K';
    if (/\b(temperature|degres?)\b/.test(n)) return '2T';
    if (/\b(distance|km|kilometres?|metres?|longueur)\b/.test(n)) return '2L';
    if (/\ben (annees?|ans)\b/.test(n)) return '1Y';
    if (/\ben mois\b/.test(n)) return '1M';
    if (/\ben semaines?\b/.test(n)) return '1W';
    if (/\ben jours?\b/.test(n)) return '1D';
    if (/\ben heures?\b/.test(n)) return '1H';
    if (/\ben minutes?\b/.test(n)) return '1U';
    if (/\ben trimestres?\b/.test(n)) return '1Q';
    if (/^ (quel )?age\b|\bvotre age\b|\bage (de|du|des|d)\b/.test(n)) return '1Y';
    return '';
  }

  // Le libellé annonce plusieurs réponses : « (s) », « citez », « lesquels »…
  const multipleHint = libelle => {
    const raw = String(libelle || '');
    const n = ' ' + plain(libelle) + ' ';
    return /\(s\)|\(e\)s|\bquel\(le\)s/i.test(raw) || /\b(citez|lesquel(le)?s|quels sont|quelles sont|plusieurs|tous les|cochez tout)\b/.test(n);
  };

  const PHONE_RX = /\bnumero\b.*\b(telephone|portable|mobile|whatsapp|cellulaire)\b|\b(telephone|whatsapp) (du|de|des)\b|\btelephone\b/;

  // ── Audit d'une question ──────────────────────────────────────────────────
  function auditItem(item, index, ctx) {
    const w = {
      pf_question: String(item.pf_question == null ? '' : item.pf_question).replace(/[   ​﻿]/g, ' '),
      pf_modalites: String(item.pf_modalites == null ? '' : item.pf_modalites).trim(),
      pf_skip: String(item.pf_skip == null ? '' : item.pf_skip).trim(),
    };
    const original = { pf_question: String(item.pf_question == null ? '' : item.pf_question), pf_modalites: String(item.pf_modalites == null ? '' : item.pf_modalites), pf_skip: String(item.pf_skip == null ? '' : item.pf_skip) };
    const libelle = String(item.libelle || '');
    const xls = item._xls || null; // question lue d'un XLSForm : pas de contrainte ni de skip PHAKTS
    const findings = [];
    const used = new Set();

    const emit = spec => {
      const field = spec.field || 'pf_question';
      const cur = w[field];
      let next = typeof spec.fix === 'function' ? spec.fix(cur) : null;
      if (next === cur) next = null;
      // XLSForm : seul le « name » se corrige ; listes et contraintes restent à signaler
      if (xls && field !== 'pf_question') next = null;
      let rule = spec.rule;
      for (let n = 2; used.has(rule); n++) rule = spec.rule + '#' + n;
      used.add(rule);
      const f = {
        id: index + ':' + rule, index, rule, field, category: spec.category, severity: spec.severity,
        message: spec.message, action: spec.action || '', source: spec.source || SRC.GRAMMAIRE,
        before: cur, after: next, auto: Boolean(spec.auto) && next != null,
        detail: spec.detail || '', suggestion: spec.suggestion || '', also: xls ? null : (spec.also || null),
      };
      f.applied = next != null && (f.auto ? !ctx.rejected.has(f.id) : ctx.accepted.has(f.id));
      if (f.applied) {
        w[field] = next;
        if (f.also) Object.keys(f.also).forEach(k => { w[k] = f.also[k]; });
      }
      findings.push(f);
      return f;
    };

    const xlsMeta = { start: 'Entretien__Debut', end: 'Entretien__Fin', today: 'Enquete__Date', deviceid: 'Appareil', username: 'Enqueteur__Compte', phonenumber: 'Appareil__Telephone', audit: 'Entretien__Audio' };
    const xlsSuggest = () => {
      const affix = xls && (xls.affix || xls.suggest);
      if (!affix) return '';
      const { code } = splitQ(w.pf_question);
      if (xls.meta && (!code || /^(start|end|today|deviceid|username|phonenumber|audit)$/i.test(code))) return xlsMeta[xls.meta] + '__G';
      const base = strip(code).replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').split('_').filter(Boolean).map(cap).join('_');
      return base ? base + '__' + affix : '';
    };
    // Codification complète d'un libellé (code ET modalités) par le codifieur fourni.
    const deriveFull = () => {
      if (!ctx.derive || xls) return null;
      try {
        const d = ctx.derive({ ...item, pf_question: w.pf_question, pf_modalites: w.pf_modalites });
        return d && d.pf_question ? d : null;
      } catch (_) { return null; }
    };
    const derive = () => {
      if (xls && !xls.fromLabel) return xlsSuggest();
      if (!ctx.derive) return '';
      try {
        const d = ctx.derive({ ...item, pf_question: w.pf_question, pf_modalites: w.pf_modalites });
        return d && d.pf_question ? (xls ? splitQ(d.pf_question).code : d.pf_question) : '';
      } catch (_) { return ''; }
    };

    // ── 1. Forme du code (radical, déterminants, séparateurs) ────────────────
    const stepCode = (rule, category, severity, message, action, change, opts) => {
      const { code } = splitQ(w.pf_question);
      const next = change(code);
      if (next === code) return;
      const o = opts || {};
      emit({
        rule, field: 'pf_question', category, severity, message, action,
        auto: typeof o.auto === 'function' ? o.auto() : o.auto !== false, source: o.source, detail: o.detail ? o.detail(code, next) : '',
        fix: q => { const p = splitQ(q); return joinQ(change(p.code), p.constraint); },
      });
    };

    let multiLine = false;
    if (/[\r\n]/.test(w.pf_question.trim())) {
      multiLine = true;
      const lines = w.pf_question.trim().split(/\s*[\r\n]+\s*/).filter(Boolean);
      emit({
        rule: 'code.multiligne', category: CAT.NOM, severity: SEV.MAJEURE,
        message: 'La cellule du code contient ' + lines.length + ' lignes : ' + lines.slice(0, 3).map(l => '« ' + l.slice(0, 50) + ' »').join(' / '),
        action: 'Garder UN seul code PHAKTS par question (supprimer les autres lignes ou la note)', auto: false,
      });
    }
    if (multiLine) {
      // rien d'autre n'est fiable tant que le code n'est pas isolé
    } else if (!w.pf_question.trim()) {
      // libellé sans code : on le codifie (code + modalités tirés du libellé, jamais appliqués sans accord)
      const full = deriveFull();
      const alsoMod = full && full.pf_modalites && !w.pf_modalites.trim() ? { pf_modalites: String(full.pf_modalites) } : null;
      emit({
        rule: 'code.vide', category: CAT.TYPE, severity: SEV.CRITIQUE,
        message: xls && xls.data ? 'L\'en-tête de la colonne est le libellé de la question, pas son code PHAKTS' : 'Libellé non codifié : aucun code PHAKTS pour cette question',
        action: (xls && xls.data ? 'Remplacer l\'en-tête par le code PHAKTS (Radical__Déterminant__Affixe)' : 'Coder la question (Radical__Déterminant__Affixe!contrainte)')
          + (alsoMod ? ' — modalités proposées : ' + alsoMod.pf_modalites.slice(0, 90) : ''),
        suggestion: derive(), fix: () => derive() || null, also: alsoMod,
      });
    }

    // Forme du code (espaces, accents, soulignés, casse, coquilles, mots interrogatifs, affixe).
    // Exécutée aussi sur un code qui vient d'être proposé pour un libellé sans code.
    function stageCodeFormat() {
      // espaces, insécables
      {
        const q = w.pf_question;
        const fixed = (() => {
          const t = q.trim();
          const { code, constraint } = splitQ(t);
          return joinQ(code.replace(/\s+/g, '_'), constraint.trim());
        })();
        if (fixed !== q) {
          emit({
            rule: 'code.espaces', category: CAT.NOM, severity: SEV.MINEURE,
            message: 'Espace(s) dans le code ou autour du code', action: 'Remplacer les espaces internes par « _ », retirer ceux des extrémités',
            auto: true, fix: cur => { const t = cur.trim(); const p = splitQ(t); return joinQ(p.code.replace(/\s+/g, '_'), p.constraint.trim()); },
          });
        }
      }
      // contrainte collée à l'affixe : « …__X1*1Liste_ » au lieu de « …__X!1*1Liste_ »
      {
        const BANG = /^(.*?__(?:SRC|[A-Z]|[12][A-Z]?))(\d*\*\d*[A-Za-z0-9_]*)$/;
        const { code, constraint } = splitQ(w.pf_question);
        const m = !constraint && code.includes('*') ? code.match(BANG) : null;
        if (m && affixStatus(m[1].split('__').pop()) !== 'bad') {
          emit({
            rule: 'code.bang_manquant', category: CAT.TYPO, severity: SEV.MAJEURE,
            message: 'Le « ! » est oublié entre l\'affixe et la contrainte (« ' + m[1].split('__').pop() + m[2] + ' »)',
            action: 'Écrire …__' + m[1].split('__').pop() + '!' + m[2], auto: true,
            fix: q => { const p = splitQ(q); const mm = !p.constraint && p.code.match(BANG); return mm ? mm[1] + '!' + mm[2] : null; },
          });
        }
      }
      stepCode('code.accents', CAT.NOM, SEV.MINEURE, 'Caractères accentués interdits dans le code',
        'Translittérer (Né → Ne, Qualité → Qualite)', c => strip(c),
        { detail: (a, b) => lexieDiff(a, b) });
      stepCode('code.caracteres', CAT.NOM, SEV.MINEURE, 'Caractère(s) interdit(s) dans le code (seuls A-Z, 0-9 et « _ » sont admis)',
        'Remplacer par « _ »', c => c.replace(/[^A-Za-z0-9_\sÀ-ɏ]/g, '_'));
      stepCode('code.underscores', CAT.NOM, SEV.MINEURE, 'Soulignés mal placés (début, fin ou trois « _ » d\'affilée)',
        'Garder « _ » entre les mots et « __ » entre les parties', c => c.replace(/_{3,}/g, '__').replace(/^_+|_+$/g, ''));
      // XLSForm : pour un nom sans affixe, la casse fait partie de la proposition de code complète
      if (!(xls && !looksCoded(codeOf(w.pf_question)))) {
        stepCode('code.casse', CAT.NOM, SEV.MINEURE, 'Mots du code commençant par une minuscule',
          'Chaque mot commence par une majuscule (Niveau_Instruction)', fixCase, { detail: (a, b) => lexieDiff(a, b) });
      }
      stepCode('code.camelcase', CAT.NOM, SEV.MINEURE, 'Mots collés sans « _ » (CamelCase)',
        'Séparer les mots par « _ » (FievreJaune → Fievre_Jaune)', fixCamel, { detail: (a, b) => lexieDiff(a, b) });

      // coquilles connues du DPF recopiées dans le code
      {
        const { code } = splitQ(w.pf_question);
        const hits = code.split(/_+/).filter(t => DPF_LEXIE_TYPOS[plain(t).replace(/ /g, '')]);
        if (hits.length) {
          emit({
            rule: 'code.coquille_dpf', category: CAT.TYPO, severity: SEV.MAJEURE,
            message: 'Graphie fautive recopiée du DPF : ' + hits.map(t => '« ' + t + ' »').join(', '),
            action: 'Corriger l\'orthographe (le DPF contient cette faute et sera corrigé lui aussi)', source: SRC.DPF_VARIABLES, auto: true,
            fix: q => { const p = splitQ(q); return joinQ(p.code.split('_').map(t => DPF_LEXIE_TYPOS[plain(t).replace(/ /g, '')] || t).join('_'), p.constraint); },
          });
        }
      }

      // faute de frappe d'un mot du radical, d'après le libellé
      typoVsLibelle();

      // radical qui recopie la phrase de la question
      {
        const rx = /^(?:Quel(?:le)?s?|Combien(?:_(?:de|d))?|Pourquoi|Comment|Quand|Ou|Avez_Vous|Est_Ce_Que|Y_A_T_Il)_/i;
        const { code } = splitQ(w.pf_question);
        if (rx.test(code) && code.replace(rx, '').length >= 3) {
          emit({
            rule: 'code.interrogatif', category: CAT.SEM, severity: SEV.MAJEURE,
            message: 'Le radical recopie la phrase de la question (« ' + code.match(rx)[0].replace(/_$/, '') + ' »)',
            action: 'Un radical décrit le concept, sans mot interrogatif ni verbe', auto: false,
            fix: q => { const p = splitQ(q); return joinQ(p.code.replace(rx, ''), p.constraint); },
          });
        }
      }

      stageAffix();
    }
    if (!multiLine && w.pf_question.trim()) stageCodeFormat();

    function lexieDiff(a, b) {
      const A = a.split(/_+/), B = b.split(/_+/);
      const out = [];
      A.forEach((t, i) => { if (B[i] != null && t !== B[i]) out.push('« ' + t + ' » → « ' + B[i] + ' »'); });
      return out.slice(0, 6).join(' ; ');
    }
    function fixCase(code) {
      const segs = code.split('__');
      return segs.map((s, i) => {
        if (segs.length > 1 && i === segs.length - 1 && affixStatus(s) !== 'bad') return s;
        return s.split('_').map(t => (/^[a-z]/.test(t) ? cap(t) : t)).join('_');
      }).join('__');
    }
    function fixCamel(code) {
      const segs = code.split('__');
      return segs.map((s, i) => {
        if (segs.length > 1 && i === segs.length - 1) return s;
        return s.split('_').map(t => {
          if (!/^[A-Z][a-z]{2,}(?:[A-Z][a-z]{2,})+$/.test(t)) return t;
          return t.match(/[A-Z][a-z]+/g).join('_');
        }).join('_');
      }).join('__');
    }

    function typoVsLibelle() {
      const words = new Set(plain(libelle).split(' ').filter(x => x.length >= 5));
      if (!words.size) return;
      const { code } = splitQ(w.pf_question);
      const segs = code.split('__');
      const tokens = [];
      segs.forEach((s, i) => {
        if (segs.length > 1 && i === segs.length - 1) return;
        s.split('_').forEach(t => tokens.push(t));
      });
      const fixes = new Map();
      for (const t of tokens) {
        const p = plain(t).replace(/ /g, '');
        if (p.length < 5 || /^[A-Z0-9]+$/.test(t) || words.has(p) || DPF_LEXIE_TYPOS[p]) continue;
        if (ctx.registry && ctx.registry.lexies.has(p)) continue;
        for (const u of words) {
          if (u[0] !== p[0] || u.startsWith(p) || p.startsWith(u)) continue;
          if (isSlip(p, u)) { fixes.set(t, cap(u)); break; }
        }
      }
      if (!fixes.size) return;
      const list = [...fixes.entries()];
      emit({
        rule: 'code.typo_libelle', category: CAT.TYPO, severity: SEV.MAJEURE,
        message: 'Faute de frappe probable : ' + list.map(([a, b]) => '« ' + a + ' » (le libellé écrit « ' + b.toLowerCase() + ' »)').join(' ; '),
        action: 'Corriger l\'orthographe du mot dans le radical', auto: false,
        fix: q => { const p = splitQ(q); return joinQ(p.code.split('_').map(t => fixes.get(t) || t).join('_'), p.constraint); },
      });
    }

    // ── 2. Affixe de type ───────────────────────────────────────────────────
    function stageAffix() {
      const { code } = splitQ(w.pf_question);
      const segs = code.split('__');
      const last = segs[segs.length - 1];
      const hasAffixPos = segs.length >= 2;
      if (hasAffixPos && affixStatus(last) === 'ok') {
        if (last === 'X' && segs[segs.length - 2] === 'G') {
          emit({
            rule: 'affixe.gps_ancien', category: CAT.TYPE, severity: SEV.MINEURE,
            message: 'Ancienne écriture du GPS (__G__X)', action: 'Écrire …__G!DMS ou …__G!DD (Règle 19)', auto: true,
            fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__X$/, ''), p.constraint); },
          });
        }
        return;
      }
      if (hasAffixPos && affixStatus(last) === 'dpf-N') {
        const hint = unitHint(libelle);
        const target = hint && hint[0] === '1' ? hint : '1';
        emit({
          rule: 'affixe.unite_N', category: CAT.TYPE, severity: SEV.MINEURE,
          message: 'Unité « N » : absente de la grammaire v2025.10.22 (le DPF l\'utilise 8 fois)' + (target !== '1' ? ' ; le libellé mentionne explicitement l\'unité ' + target[1] : ''),
          action: target !== '1' ? 'Écrire __' + target + ' (unité du libellé)' : 'Écrire __1 (entier sans unité)',
          source: SRC.DECISION, auto: true,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__1N$/, '__' + target), p.constraint); },
        });
        return;
      }
      if (hasAffixPos && last !== last.toUpperCase() && affixStatus(last.toUpperCase()) !== 'bad') {
        emit({
          rule: 'affixe.casse', category: CAT.TYPO, severity: SEV.MINEURE,
          message: 'Affixe « ' + last + ' » en minuscules', action: 'Écrire l\'affixe en majuscules (« ' + last.toUpperCase() + ' »)', auto: true,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__[^_]+$/, '__' + last.toUpperCase()), p.constraint); },
        });
        return;
      }
      if (hasAffixPos && /^[12][A-Za-z]$/.test(last)) {
        const hint = unitHint(libelle);
        const target = hint && hint[0] === last[0] ? hint : last[0];
        emit({
          rule: 'affixe.unite_inconnue', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Unité « ' + last[1] + ' » inconnue de la grammaire (' + last + ')',
          action: hint && hint[0] === last[0] ? 'Le libellé indique l\'unité ' + hint[1] + ' → __' + hint : 'Retirer l\'unité (__' + last[0] + ') ou choisir parmi Y M W D H U Q (entiers) et K T L S P V F I (réels)' + (hint ? ' — le libellé évoque plutôt __' + hint : ''),
          auto: false,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__[12][A-Za-z]$/, '__' + target), p.constraint); },
        });
        return;
      }
      const trailing = !hasAffixPos && code.match(/^(.*[A-Za-z0-9])_(B|C|A|X|Z|P|G|SRC|[12][YMWDHUQKTLSPVFIN]?)$/);
      if (trailing && trailing[1].length >= 2) {
        emit({
          rule: 'affixe.separateur', category: CAT.NOM, severity: SEV.MAJEURE,
          message: 'Affixe « ' + trailing[2] + ' » séparé par un seul « _ »', action: 'Écrire « __ » avant l\'affixe (' + trailing[1] + '__' + trailing[2] + ')', auto: true,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/^(.*[A-Za-z0-9])_([A-Za-z0-9]+)$/, '$1__$2'), p.constraint); },
        });
        return;
      }
      const sugg = derive();
      emit({
        rule: 'affixe.absent', category: CAT.TYPE, severity: SEV.CRITIQUE,
        message: 'Code sans affixe de type (B, C, A, X, Z, 1, 2, G, P, SRC) : « ' + code + ' » n\'est pas un code PHAKTS',
        action: 'Coder selon Radical__Déterminant__Affixe!contrainte' + (sugg ? ' — proposition issue du libellé : ' + sugg : ''),
        suggestion: sugg, auto: Boolean(xls && sugg && (!xls.data || xls.affix)), fix: () => sugg || null,
        also: null,
      });
    }

    // ── 3. Contrainte du code et cohérence du type ──────────────────────────
    const info = () => CORE.classifyCode(w.pf_question);
    const q3 = () => { const p = splitQ(w.pf_question); return { code: p.code, k: p.constraint.trim() }; };

    function closedConstraint(word, kindLabel) {
      const { k } = q3();
      if (k === word) return;
      if (k === '') {
        emit({
          rule: 'contrainte.' + word + '_absente', category: CAT.TYPE, severity: SEV.MINEURE,
          message: kindLabel + ' sans « !' + word + ' »', action: 'Écrire …!' + word, auto: true,
          fix: q => withConstraint(q, word),
        });
      } else if (lev(strip(k).toLowerCase(), word, 2) <= 2) {
        emit({
          rule: 'contrainte.typo', category: CAT.TYPO, severity: SEV.CRITIQUE,
          message: 'Faute de frappe dans la contrainte « !' + k + ' »', action: 'Écrire « !' + word + ' »', auto: true,
          fix: q => withConstraint(q, word),
        });
      } else {
        emit({
          rule: 'contrainte.inattendue', category: CAT.TYPE, severity: SEV.MINEURE,
          message: 'Contrainte « !' + k + ' » inattendue pour ' + kindLabel.toLowerCase(), action: 'Écrire « !' + word + ' »', auto: false,
          fix: q => withConstraint(q, word),
        });
      }
    }

    function stageConstraint() {
      if (!w.pf_question.trim()) return;
      const ci = info();
      const kind = ci.kind;
      const { code, k } = q3();
      const lc = parseListDef(w.pf_modalites);

      if (kind === 'boolean') {
        closedConstraint('boolean', 'Booléen (__B)');
      } else if (kind === 'trilean') {
        closedConstraint('trilean', 'Triléen (__C)');
      } else if (kind === 'image') {
        if (k !== 'photo') {
          if (k === '' || lev(strip(k).toLowerCase(), 'photo', 1) <= 1) {
            emit({
              rule: 'contrainte.photo', category: CAT.TYPE, severity: SEV.MINEURE,
              message: 'Photo (__P) sans « !photo »', action: 'Écrire …__P!photo', auto: true, fix: q => withConstraint(q, 'photo'),
            });
          }
        }
      } else if (kind === 'date') {
        const rangeRx = /^\d{4}\/\d{2}\/\d{2}\s*<=?\s*A\s*<=?\s*\d{4}\/\d{2}\/\d{2}$/;
        if (k === '' || /^YYYY[-.]MM[-.]DD$/i.test(k) || /^yyyy\/mm\/dd$/i.test(k)) {
          if (k !== 'YYYY/MM/DD') {
            emit({
              rule: 'contrainte.date', category: CAT.TYPE, severity: SEV.MINEURE,
              message: k ? 'Format de date « !' + k + ' » non conforme' : 'Date (__A) sans format', action: 'Écrire …__A!YYYY/MM/DD (ISO 8601)',
              auto: true, fix: q => withConstraint(q, 'YYYY/MM/DD'),
            });
          }
        } else if (!rangeRx.test(k)) {
          emit({
            rule: 'contrainte.date_inattendue', category: CAT.TYPE, severity: SEV.MINEURE,
            message: 'Contrainte de date « !' + k + ' » illisible', action: 'Écrire !YYYY/MM/DD ou une plage 2000/01/01<A<2026/12/31', auto: false,
            fix: q => withConstraint(q, 'YYYY/MM/DD'),
          });
        }
      } else if (kind === 'select') {
        stageSelectConstraint(code, k, lc);
      } else if (kind === 'text' || kind === 'phone') {
        stageTextConstraint(code, k, lc, kind);
      } else if (kind === 'integer' || kind === 'decimal') {
        stageNumberConstraint(kind, ci.unit, k);
      } else if (kind === 'generated') {
        emit({
          rule: 'generee.sans_precision', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Variable générée __G sans précision : Kobo ne peut pas savoir laquelle produire',
          action: 'Préciser la contrainte : !DMS ou !DD (GPS), !start, !end, !today, !deviceid, !username, !phonenumber, !audit', auto: false,
        });
      }
      if (ci.affix === 'E') {
        emit({
          rule: 'affixe.E_supprime', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Affixe __E supprimé de la grammaire',
          action: 'Variable produite par Kobo → __G!<variable> ; identifiant saisi par l\'enquêteur → __Z!1*Expression', auto: false,
        });
      }
    }

    function stageSelectConstraint(code, k, lc) {
      const mm = k.match(/^(\d*)\*(\d*)\s*([A-Za-z][A-Za-z0-9_]*)?$/);
      const idOnly = !mm && /^[A-Za-z][A-Za-z0-9_]*$/.test(k) ? k : '';
      const ldId = lc ? canonListId(lc.id) : '';
      const sepMult = lc ? (lc.sep === '|' ? '1*' : '1*1') : '';
      const wantMult = () => (multipleHint(libelle) ? '1*' : (lc ? sepMult : ''));

      if (k === '') {
        emit({
          rule: 'contrainte.choix_vide', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Choix (__' + (affixOf(code) || 'X') + ') sans multiplicité ni liste',
          action: ldId ? 'Écrire …!' + wantMult() + ldId + ' (liste lue dans les modalités)' : 'Écrire …!1*1Liste_ (choix unique) ou …!1*Liste_ (choix multiple)',
          auto: false, fix: ldId ? q => withConstraint(q, wantMult() + ldId) : null,
        });
        return;
      }
      if (idOnly) {
        emit({
          rule: 'contrainte.multiplicite_absente', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Liste « ' + idOnly + ' » sans multiplicité N*M',
          action: 'Ajouter 1*1 (choix unique) ou 1* (choix multiple) devant le nom de la liste', auto: false,
          fix: wantMult() ? q => withConstraint(q, wantMult() + idOnly) : null,
        });
        return;
      }
      if (!mm) {
        emit({
          rule: 'contrainte.choix_illisible', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Contrainte de choix « !' + k + ' » illisible', action: 'Écrire !N*M<Liste_> (ex. 1*1Sexe_, 1*Maladie_)', auto: false,
          fix: ldId ? q => withConstraint(q, wantMult() + ldId) : null,
        });
        return;
      }
      const min = mm[1] === '' ? null : parseInt(mm[1], 10);
      const max = mm[2] === '' ? null : parseInt(mm[2], 10);
      if (min !== null && max !== null && min > max) {
        emit({
          rule: 'contrainte.multiplicite_incoherente', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Multiplicité incohérente (!' + min + '*' + max + ') : au moins ' + min + ' mais au plus ' + max + ' choix',
          action: 'Corriger N*M : le minimum N ne peut pas dépasser le maximum M', auto: false,
        });
      }
      const id = mm[3] || '';
      if (!id) {
        emit({
          rule: 'contrainte.liste_absente', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Multiplicité « ' + mm[1] + '*' + mm[2] + ' » sans nom de liste', action: ldId ? 'Écrire …!' + mm[1] + '*' + mm[2] + ldId + ' (liste lue dans les modalités)' : 'Ajouter le nom de la liste (Liste_) après N*M',
          auto: Boolean(ldId), fix: ldId ? q => withConstraint(q, mm[1] + '*' + mm[2] + ldId) : null,
        });
      } else if (!/_$/.test(id) && !/^Admin_/i.test(id)) {
        emit({
          rule: 'contrainte.liste_format', category: CAT.NOM, severity: SEV.MINEURE,
          message: 'Nom de liste « ' + id + ' » sans « _ » final', action: 'Un identifiant de liste se termine par « _ » (' + id + '_)', auto: true,
          fix: q => withConstraint(q, mm[1] + '*' + mm[2] + id + '_'),
        });
      }
    }

    function stageTextConstraint(code, k, lc, kind) {
      const textRx = /^\d*\*\d*(Expression|Tel)$|^(Expression|Tel)$/;
      const listLike = /^\d*\*\d*[A-Za-z][A-Za-z0-9_]*_$/.test(k) && !/(Expression|Tel)$/.test(k);
      if (listLike || (lc && lc.id && /_$/.test(canonListId(lc.id)) && lc.values.length >= 2)) {
        emit({
          rule: 'type.texte_liste', category: CAT.TYPE, severity: SEV.CRITIQUE,
          message: 'Affixe Z (texte libre) mais la question définit une liste de choix' + (listLike ? ' (« !' + k + ' »)' : ''),
          action: 'Un choix dans une liste se code __X (ou __SRC)', auto: true,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__Z$/, '__X'), p.constraint); },
        });
        return;
      }
      if (k === '') {
        emit({
          rule: 'contrainte.texte_vide', category: CAT.TYPE, severity: SEV.MINEURE,
          message: 'Texte libre (__Z) sans contrainte', action: 'Écrire …__Z!1*Expression', auto: true,
          fix: q => withConstraint(q, '1*Expression'),
        });
      } else if (!textRx.test(k)) {
        const near = k.replace(/^\d*\*\d*/, '');
        const target = lev(strip(near).toLowerCase(), 'expression', 2) <= 2 ? 'Expression' : (lev(strip(near).toLowerCase(), 'tel', 1) <= 1 ? 'Tel' : '');
        emit({
          rule: 'contrainte.texte_inattendue', category: target ? CAT.TYPO : CAT.TYPE, severity: SEV.MINEURE,
          message: 'Contrainte « !' + k + ' » inattendue pour un texte libre', action: 'Écrire …__Z!1*' + (target || 'Expression'),
          auto: Boolean(target), fix: q => withConstraint(q, '1*' + (target || 'Expression')),
        });
      }
      if (kind !== 'phone' && /\bTel$/.test(k) === false && PHONE_RX.test(plain(libelle))) {
        emit({
          rule: 'type.telephone', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Numéro de téléphone codé en texte libre', action: 'Coder __Z!1*Tel (texte validé par regex) — jamais Expression ni __1', auto: false,
          fix: q => withConstraint(q, '1*Tel'),
        });
      }
    }

    function stageNumberConstraint(kind, unit, k) {
      const letterWanted = kind === 'integer' ? 'N' : 'R';
      if (kind === 'integer' && PHONE_RX.test(plain(libelle))) {
        emit({
          rule: 'type.telephone', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Numéro de téléphone codé en entier', action: 'Coder __Z!1*Tel (un numéro commence souvent par 0 ou +, c\'est un texte)', auto: false,
          fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__[12][A-Z]?$/, '__Z'), '1*Tel'); },
        });
      }
      if (k === '') {
        if (kind === 'decimal') {
          emit({
            rule: 'contrainte.plage_reel', category: CAT.TYPE, severity: SEV.MINEURE,
            message: 'Réel (__2) sans plage de valeurs', action: 'Un réel porte toujours une plage : ex. !0<R<100', auto: false,
          });
        }
        return;
      }
      const range = k.match(/^(-?\d+(?:[.,]\d+)?)\s*(<=?)\s*([A-Za-z])\s*(<=?)\s*(-?\d+(?:[.,]\d+)?)$/);
      if (range) {
        const lo = parseFloat(range[1].replace(',', '.')), hi = parseFloat(range[5].replace(',', '.'));
        const unitLetter = unit && /^[A-Z]$/.test(unit) ? unit : '';
        if (range[3] !== letterWanted && range[3] !== unitLetter) {
          emit({
            rule: 'contrainte.plage_lettre', category: CAT.TYPE, severity: SEV.MINEURE,
            message: 'Plage écrite avec « ' + range[3] + ' » : ' + (kind === 'integer' ? 'un entier s\'écrit N' : 'un réel s\'écrit R'),
            action: 'Écrire ' + range[1] + range[2] + letterWanted + range[4] + range[5], auto: true,
            fix: q => withConstraint(q, k.replace(/([A-Za-z])(?=\s*<)/, letterWanted)),
          });
        }
        if (lo >= hi) {
          emit({
            rule: 'contrainte.plage_bornes', category: CAT.TYPE, severity: SEV.MAJEURE,
            message: 'Bornes de plage incohérentes (' + range[1] + ' ≥ ' + range[5] + ')', action: 'La borne basse doit être inférieure à la borne haute', auto: false,
          });
        }
        return;
      }
      if (kind === 'integer' && /^[A-Z]$/.test(k)) {
        const timeUnits = 'YMWDH';
        if (k !== 'N' && !timeUnits.includes(k)) {
          emit({
            rule: 'contrainte.raccourci_inconnu', category: CAT.TYPE, severity: SEV.MINEURE,
            message: '« !' + k + ' » n\'est pas un raccourci d\'unité (Y, M, W, D, H) ni une plage', action: 'Retirer la lettre ou écrire une plage (!0<N<120)', auto: false,
          });
        } else if (timeUnits.includes(k) && unit && timeUnits.includes(unit) && k !== unit) {
          emit({
            rule: 'contrainte.raccourci_incoherent', category: CAT.TYPE, severity: SEV.MINEURE,
            message: 'Raccourci « !' + k + ' » incohérent avec l\'unité de l\'affixe (' + unit + ')', action: 'Écrire !' + unit + ' ou changer l\'unité de l\'affixe',
            auto: false, fix: q => withConstraint(q, unit),
          });
        }
        return;
      }
      emit({
        rule: 'contrainte.plage_illisible', category: CAT.TYPE, severity: SEV.MAJEURE,
        message: 'Contrainte « !' + k + ' » illisible pour un ' + (kind === 'integer' ? 'entier' : 'réel'),
        action: 'Écrire une plage (!0<' + letterWanted + '<120)' + (kind === 'integer' ? ' ou le raccourci d\'unité (!Y, !M…)' : ''), auto: false,
      });
    }

    // ── 4. Modalités ────────────────────────────────────────────────────────
    function yesNoKeys(values) {
      return values.map(v => valueKey(v)).filter(v => v && v !== '0');
    }

    function stageModalites() {
      if (!w.pf_question.trim()) return;
      const ci = info();
      const kind = ci.kind;
      const m = w.pf_modalites;

      if (kind === 'boolean') {
        const vals = CORE.splitListValues(m.replace(/^[^=]*=\s*[[({]?|[\])}]\s*$/g, ''));
        const keys = yesNoKeys(m.includes('=') ? vals : CORE.splitListValues(m));
        const isYesNo = keys.length === 2 && keys.includes('oui') && keys.includes('non');
        if (m === '' || /^boolean$/i.test(m) || (isYesNo && m !== 'Oui | Non')) {
          emit({
            rule: 'modalites.booleen', category: CAT.MODA, severity: SEV.MINEURE,
            message: 'Modalités d\'un booléen : « ' + (m || 'vide') + ' »', action: 'Écrire « Oui | Non »', auto: true, field: 'pf_modalites',
            fix: () => 'Oui | Non',
          });
        } else if (!isYesNo) {
          const tri = keys.length === 3 && keys.includes('oui') && keys.includes('non');
          emit({
            rule: 'type.booleen_liste', category: CAT.TYPE, severity: SEV.CRITIQUE,
            message: tri ? 'Booléen (__B) mais les modalités ont trois états (' + CORE.splitListValues(m).join(' | ') + ')' : 'Booléen (__B) mais les modalités ne sont pas Oui/Non (« ' + m.slice(0, 80) + ' »)',
            action: tri ? 'Trois états Oui / Non / autre = triléen : __C!trilean' : 'Un choix parmi une liste se code __X', auto: false,
            fix: tri ? q => { const p = splitQ(q); return joinQ(p.code.replace(/__B$/, '__C'), 'trilean'); } : null,
          });
        }
        return;
      }
      if (kind !== 'select') return;
      stageSelectModalites(ci);
    }

    function stageSelectModalites(ci) {
      const { k } = q3();
      const mm = k.match(/^(\d*)\*(\d*)\s*([A-Za-z][A-Za-z0-9_]*)?$/);
      const cId = mm && mm[3] ? mm[3] : (/^[A-Za-z][A-Za-z0-9_]*$/.test(k) ? k : '');
      if (/^Admin_/i.test(cId)) return; // liste du référentiel externe : rien à lire dans les modalités
      let ld = parseListDef(w.pf_modalites);

      if (!ld) {
        const rebuilt = CORE.canonicalListModalites(w.pf_question, w.pf_modalites, ctx.dpfLists || []);
        if (rebuilt && rebuilt !== w.pf_modalites && parseListDef(rebuilt)) {
          emit({
            rule: 'modalites.liste_absente', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
            message: 'Modalités sans forme « Liste_=[…] » : ' + (w.pf_modalites ? '« ' + w.pf_modalites.slice(0, 70) + ' »' : 'vides'),
            action: 'Écrire ' + rebuilt, auto: true, fix: () => rebuilt,
          });
          ld = parseListDef(w.pf_modalites);
        } else {
          emit({
            rule: 'modalites.liste_illisible', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
            message: 'Aucune liste de modalités lisible pour ce choix', action: 'Écrire Liste_=[valeur1|valeur2|…] (| choix multiple, « , » choix unique)', auto: false,
          });
          return;
        }
        if (!ld) return;
      }

      // a. la contrainte fait foi pour l'identifiant de la liste
      if (cId && codeKey(cId) !== codeKey(canonListId(ld.id))) {
        emit({
          rule: 'liste.identifiant_discordant', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
          message: 'La contrainte cite la liste « ' + cId + ' » mais les modalités définissent « ' + ld.id + ' »',
          action: 'Utiliser le même identifiant : ' + canonListId(cId), auto: true,
          fix: cur => { const p = parseListDef(cur); return p ? buildListDef(p, canonListId(cId), p.values) : null; },
        });
      }

      // b. forme de la liste : crochets, caractères parasites, identifiant, valeurs vides
      {
        const cur = parseListDef(w.pf_modalites) || ld;
        const structural = [];
        if (!cur.bracketsOk) structural.push('crochets [ ] manquants ou d\'un autre type');
        if (cur.junk) structural.push('caractères parasites après la liste');
        if (canonListId(cur.id) !== cur.id) structural.push('identifiant « ' + cur.id + ' » non conforme (Snake_Case terminé par « _ »)');
        if (cur.values.some(v => v === '')) structural.push('modalité(s) vide(s)');
        if (structural.length) {
          emit({
            rule: 'modalites.forme', category: CAT.MODA, severity: SEV.MINEURE, field: 'pf_modalites',
            message: 'Forme de la liste : ' + structural.join(', '), action: 'Écrire Identifiant_=[valeur1|valeur2|…]', auto: true,
            fix: c => { const p = parseListDef(c); return p ? buildListDef(p, canonListId(p.id), p.values.filter(v => v !== '')) : null; },
          });
        }
      }

      // c. valeurs : sans accent, sans espace ni ponctuation
      {
        const cur = parseListDef(w.pf_modalites) || ld;
        const changed = cur.values.map(v => [v, canonValue(v)]).filter(([a, b]) => a !== b && a !== '');
        if (changed.length) {
          emit({
            rule: 'modalites.valeurs_format', category: CAT.MODA, severity: SEV.MINEURE, field: 'pf_modalites',
            message: 'Modalité(s) avec accent, espace ou ponctuation : ' + changed.slice(0, 4).map(([a, b]) => '« ' + a + ' » → « ' + b + ' »').join(' ; ') + (changed.length > 4 ? ' (+' + (changed.length - 4) + ')' : ''),
            action: 'Écrire chaque modalité en Snake_Case sans accent (Fièvre hémorragique → Fievre_hemorragique)', auto: true,
            detail: changed.map(([a, b]) => '« ' + a + ' » → « ' + b + ' »').join(' ; '),
            fix: c => { const p = parseListDef(c); return p ? buildListDef(p, canonListId(p.id), p.values.map(canonValue).filter(Boolean)) : null; },
          });
        }
      }

      const cur3 = parseListDef(w.pf_modalites) || ld;
      const idNow = cur3.id;
      const vNow = cur3.values.filter(v => v !== '');
      const opts = vNow.filter(v => v !== '0');
      const kNow = q3().k;

      // d. Règle 16 : une unité administrative ne se code jamais en liste inline
      const adminTarget = adminListFor(canonListId(idNow));
      if (adminTarget && opts.length >= 5) {
        emit({
          rule: 'liste.admin', category: CAT.LISTE, severity: SEV.MAJEURE, field: 'pf_modalites', source: SRC.REGLE16,
          message: 'Unité administrative codée en liste inline (' + opts.length + ' valeurs) : « ' + canonListId(idNow) + ' »',
          action: 'Utiliser le référentiel externe ' + adminTarget + ' (jamais de liste en dur pour région, district, établissement)', auto: false,
          fix: () => '',
          also: { pf_question: withConstraint(w.pf_question, (kNow.match(/^\d*\*\d*/) || ['1*1'])[0] + adminTarget) },
        });
        return;
      }

      if (cur3.mixed) {
        emit({
          rule: 'modalites.separateurs_mixtes', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
          message: 'Modalités séparées à la fois par « | » et « , »', action: 'Choisir un seul séparateur : « , » (choix unique) ou « | » (choix multiple)', auto: false,
        });
      }

      // e. doublons et liste trop courte
      {
        const seen = new Map();
        const dups = [];
        vNow.forEach(v => { const key = valueKey(v); if (seen.has(key)) dups.push(v); else seen.set(key, true); });
        if (dups.length) {
          emit({
            rule: 'modalites.doublons', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
            message: 'Modalité(s) en double : ' + [...new Set(dups)].map(v => '« ' + v + ' »').join(', '), action: 'Garder chaque modalité une seule fois', auto: true,
            fix: c => {
              const p = parseListDef(c); if (!p) return null;
              const s2 = new Set();
              return buildListDef(p, p.id, p.values.filter(v => { const key = valueKey(v); if (!v || s2.has(key)) return false; s2.add(key); return true; }));
            },
          });
        }
      }
      if (opts.length < 2) {
        emit({
          rule: 'modalites.une_seule', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
          message: 'Liste à ' + (opts.length ? 'une seule modalité' : 'aucune modalité'), action: 'Un choix propose au moins deux modalités', auto: false,
        });
      }

      // f. séparateur ↔ multiplicité (l'option « , » ou « | » reste une décision du DPF : ToDo)
      const mNow = kNow.match(/^(\d*)\*(\d*)/);
      if (mNow) {
        const single = mNow[2] === '1';
        const pipe = cur3.sep === '|' && !cur3.mixed;
        const comma = cur3.sep === ',' && !cur3.mixed && opts.length > 1;
        const rebuild = sep => c => { const p = parseListDef(c); return p ? buildListDef({ ...p, sep, spacedSep: false }, p.id, p.values) : null; };
        if (single && pipe) {
          if (multipleHint(libelle)) {
            emit({
              rule: 'contrainte.multiplicite_libelle', category: CAT.TYPE, severity: SEV.MINEURE,
              message: 'Le libellé annonce plusieurs réponses mais la contrainte dit « 1*1 » (choix unique) alors que les modalités sont cumulables (« | »)',
              action: 'Écrire !1* (au moins un choix) — modalités inchangées', source: SRC.DECISION, auto: true,
              fix: q => withConstraint(q, kNow.replace(/^\d*\*\d*/, '1*')),
            });
          } else {
            emit({
              rule: 'modalites.separateur', category: CAT.MODA, severity: SEV.MINEURE, field: 'pf_modalites',
              message: 'Choix unique (1*1) mais modalités séparées par « | » (cumulables)',
              action: 'Séparer par « , » pour un choix unique (ou écrire !1* pour un choix multiple)', source: SRC.DECISION, auto: true, fix: rebuild(','),
            });
          }
        } else if (!single && comma) {
          emit({
            rule: 'modalites.separateur', category: CAT.MODA, severity: SEV.MINEURE, field: 'pf_modalites',
            message: 'Choix multiple (!' + mNow[1] + '*' + mNow[2] + ') mais modalités séparées par « , » (exclusives)',
            action: 'Séparer par « | » pour un choix multiple (ou écrire !1*1 pour un choix unique)', source: SRC.DECISION, auto: true, fix: rebuild('|'),
          });
        }
        if (mNow[1] !== '' && parseInt(mNow[1], 10) >= 2 && opts.length && opts.length < parseInt(mNow[1], 10)) {
          emit({
            rule: 'contrainte.min_modalites', category: CAT.TYPE, severity: SEV.MAJEURE,
            message: 'Au moins ' + mNow[1] + ' choix demandés mais seulement ' + opts.length + ' modalité(s)', action: 'Réduire la multiplicité ou compléter la liste', auto: false,
          });
        }
      }

      // g. identifiant copié de la phrase
      if (/^(Quel(le)?s?|Combien|Pourquoi|Comment)_/i.test(idNow)) {
        emit({
          rule: 'liste.identifiant_interrogatif', category: CAT.LISTE, severity: SEV.MAJEURE, field: 'pf_modalites',
          message: 'Identifiant de liste copié de la phrase (« ' + idNow + ' »)', action: 'Donner un nom court et réutilisable (Distance_, Niveau_, Frequence_)', auto: false,
        });
      }

      stageDpfList(cur3, idNow, kNow);
    }

    function adminListFor(id) {
      const k = id.toLowerCase().replace(/_+$/, '');
      if (k === 'region' || k === 'region_sanitaire') return 'Admin_Region_Sanitaire_';
      if (k === 'district' || k === 'district_sanitaire') return 'Admin_District_Sanitaire_';
      if (k === 'etablissement' || k === 'etablissement_sante') return 'Admin_Etablissement_Sante_';
      return '';
    }

    function stageDpfList(ld, id, kNow) {
      // seules les listes du DPF font référence : les listes « Studio » ou
      // « local » sont des conventions de l'outil, pas le vocabulaire contrôlé
      const lists = (ctx.dpfLists || []).filter(l => l.source === 'DPF');
      const key = CORE.dpfListKey(id);
      const entry = lists.find(l => CORE.dpfListKey(l.identifiant) === key);
      const userVals = ld.values.filter(v => v !== '' && v !== '0');
      const userKeys = new Map(userVals.map(v => [valueKey(v), v]));

      if (entry) {
        const dv = dpfValues(entry);
        const dKeys = new Map(dv.filter(v => v !== '0').map(v => [valueKey(v), v]));
        const syn = SYNONYMS[key.replace(/_+$/, '')] || {};
        const extra = [], mapped = [];
        userVals.forEach(v => {
          const vk = valueKey(v);
          if (dKeys.has(vk)) return;
          const s = syn[vk];
          if (s && dKeys.has(valueKey(s))) mapped.push([v, dKeys.get(valueKey(s))]);
          else extra.push(v);
        });
        const mappedTargets = new Set(mapped.map(([, t]) => valueKey(t)));
        const missing = [...dKeys.entries()].filter(([vk]) => !userKeys.has(vk) && !mappedTargets.has(vk)).map(([, v]) => v);
        const only = !entry.ouverte && (extra.length || mapped.length || missing.length);
        if (only || (entry.ouverte && missing.length && !extra.length && !mapped.length)) {
          const subset = !extra.length && !mapped.length;
          const parts = [];
          if (mapped.length) parts.push('synonymes : ' + mapped.map(([a, b]) => '« ' + a + ' » → « ' + b + ' »').join(', '));
          if (extra.length) parts.push('hors DPF : ' + extra.map(v => '« ' + v + ' »').join(', '));
          if (missing.length) parts.push('du DPF absentes : ' + missing.map(v => '« ' + v + ' »').join(', '));
          const target = dv.slice();
          const proposed = entry.ouverte ? target.concat(extra) : target;
          emit({
            rule: 'liste.dpf_valeurs', category: CAT.LISTE, severity: subset ? SEV.MINEURE : SEV.MAJEURE, field: 'pf_modalites', source: SRC.DPF_LISTES,
            message: 'Liste « ' + canonListId(id) + ' » différente de celle du DPF — ' + parts.join(' ; '),
            action: 'Reprendre les valeurs du DPF (' + dv.join(', ') + '), ou renommer la liste si la question n\'a pas le même sens (ex. ' + canonListId(id).replace(/_$/, '') + '_Enfant_)',
            auto: false,
            fix: cur => { const p = parseListDef(cur); return p ? buildListDef(p, p.id, proposed) : null; },
          });
        }
        return;
      }
      if (userVals.length >= 2) {
        const sig = userVals.map(valueKey).sort().join('|');
        const twin = lists.find(l => l.source === 'DPF' && dpfValues(l).filter(v => v !== '0').map(valueKey).sort().join('|') === sig);
        if (twin) {
          emit({
            rule: 'liste.dpf_jumeau', category: CAT.LISTE, severity: SEV.MINEURE, field: 'pf_modalites', source: SRC.DPF_LISTES,
            message: 'Mêmes modalités que la liste du DPF « ' + twin.identifiant + ' »', action: 'Réutiliser l\'identifiant ' + twin.identifiant + ' (vocabulaire contrôlé)',
            auto: false,
            fix: cur => { const p = parseListDef(cur); return p ? buildListDef(p, twin.identifiant, p.values) : null; },
            also: { pf_question: withConstraint(w.pf_question, kNow.replace(/[A-Za-z][A-Za-z0-9_]*$/, twin.identifiant)) },
          });
        }
      }
    }

    // ── 3 bis. XLSForm : type du champ ↔ affixe du nom ───────────────────────
    function stageXlsType() {
      if (!w.pf_question.trim() || !xls || !xls.affix) return;
      const have = affixOf(codeOf(w.pf_question));
      if (!have || affixStatus(have) === 'bad') return;
      const klass = a => (a === 'SRC' ? 'X' : (/^[12]/.test(a) ? a[0] : a));
      if (klass(have) === klass(xls.affix)) return;
      const label = { B: 'Oui/Non', C: 'Oui/Non/autre', X: 'liste de choix', Z: 'texte', A: 'date', 1: 'entier', 2: 'réel', G: 'variable générée', P: 'photo' };
      emit({
        rule: 'type.xlsform_affixe', category: CAT.TYPE, severity: SEV.CRITIQUE,
        message: (xls.data ? 'Les valeurs de la colonne sont ' + xls.type : 'Le champ est de type « ' + xls.type + ' »') + ' (' + (label[klass(xls.affix)] || xls.affix) + ') mais le nom se termine par __' + have + ' (' + (label[klass(have)] || have) + ')',
        action: 'Écrire __' + xls.affix + (xls.data ? ' (les valeurs de la colonne font foi)' : ' (le type du champ fait foi)'), auto: true,
        fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__[^_]+$/, '__' + xls.affix), p.constraint); },
      });
    }

    function stageXlsModalites() {
      if (!xls || xls.kind !== 'select') return;
      const ld = parseListDef(w.pf_modalites);
      if (!ld) return;
      const opts = ld.values.filter(v => v !== '' && v !== '0');
      if (opts.length < 2) {
        emit({
          rule: 'modalites.une_seule', category: CAT.MODA, severity: SEV.MAJEURE, field: 'pf_modalites',
          message: 'Liste « ' + ld.id + ' » à ' + (opts.length ? 'une seule modalité' : 'aucune modalité'), action: 'Un choix propose au moins deux modalités', auto: false,
        });
        return;
      }
      const adminTarget = adminListFor(canonListId(ld.id));
      if (adminTarget && opts.length >= 5) {
        emit({
          rule: 'liste.admin', category: CAT.LISTE, severity: SEV.MAJEURE, field: 'pf_modalites', source: SRC.REGLE16,
          message: 'Unité administrative codée en liste inline (' + opts.length + ' valeurs) : liste « ' + xls.list + ' »',
          action: 'Utiliser le référentiel externe ' + adminTarget + ' (select_one_external / pulldata), jamais de liste en dur — Règle 16', auto: false,
        });
        return;
      }
      stageDpfList(ld, ld.id, '');
    }

    // ── 5. Cohérence libellé ↔ code ─────────────────────────────────────────
    function stageSemantics() {
      if (!w.pf_question.trim() || !libelle.trim()) return;
      // Sans affixe, le type est inconnu : les contrôles qui en dépendent n'ont pas de base
      if (findings.some(f => f.rule === 'affixe.absent' && !f.applied)) return;
      const ci = info();
      const kind = ci.kind;
      const n = ' ' + plain(libelle) + ' ';
      const sugg = () => derive();
      // Correction prévue par la grammaire (« âge → entier __1Y », « combien → entier », « pourquoi / quel /
      // où → liste ou texte libre »), proposée seulement : elle ne s'applique qu'au code d'une question
      // codifiée, jamais au nom d'un XLSForm ou d'une colonne.
      const retype = (affix, constraint, modalites) => ({
        fix: xls ? null : q => { const p = splitQ(q); return joinQ(p.code.replace(/__[^_]+$/, '__' + affix), constraint); },
        also: xls ? null : { pf_modalites: modalites },
      });
      const flag = (rule, severity, message, action, fixSpec) => {
        const s = sugg();
        const spec = fixSpec || { fix: null, also: null };
        emit({
          rule, category: CAT.TYPE, severity, message, action: action + (s && s !== w.pf_question && !spec.fix ? ' — proposition issue du libellé : ' + s : ''),
          suggestion: s && s !== w.pf_question ? s : '', auto: false, fix: spec.fix, also: spec.also,
        });
      };
      // « Si oui, quel … ? », « Selon vous, pourquoi … ? » : ces préfixes ne changent pas la nature de la question
      const nq = n.replace(/^ (si oui|si non|selon vous|d apres vous|le cas echeant|si c est le cas) /, ' ');
      const numeric = kind === 'integer' || kind === 'decimal';
      if (/ combien | nombre de | nombre d | nb de /.test(n) && !numeric) {
        if (kind === 'boolean' || kind === 'trilean') flag('type.combien', SEV.CRITIQUE, '« Combien / Nombre de » appelle un nombre, le code est un booléen', 'Coder un entier : __1 (ou __1Y, __2…)', retype('1', '', 'Nombre entier'));
        else if (kind === 'text') flag('type.combien', SEV.MAJEURE, '« Combien / Nombre de » appelle un nombre, le code est un texte libre', 'Coder un entier : __1 (avec une plage)', retype('1', '', 'Nombre entier'));
      }
      if (/ age /.test(n) && !/ age gestationnel /.test(n) && (kind === 'text' || kind === 'boolean')) {
        flag('type.age', SEV.CRITIQUE, '« Âge » codé ' + (kind === 'text' ? 'en texte libre' : 'en booléen'), 'Un âge est un entier : __1Y!0<N<120', retype('1Y', '0<N<120', 'Années'));
      }
      if (kind === 'boolean' && /^ (quel|quelle|quels|quelles) /.test(nq)) {
        flag('type.quel_booleen', SEV.CRITIQUE, '« Quel(le)(s) … » attend un choix ou un texte, pas Oui/Non', 'Coder __X (liste) ou __Z!1*Expression : texte libre proposé tant que la liste des choix n\'est pas connue', retype('Z', '1*Expression', 'Expression'));
      }
      if (kind === 'boolean' && /^ (pourquoi|pour quelle raison) /.test(nq)) {
        flag('type.pourquoi_booleen', SEV.CRITIQUE, '« Pourquoi » attend une raison, pas Oui/Non', 'Coder __X!1*Raison_ ou __Z!1*Expression : texte libre proposé tant que la liste des raisons n\'est pas connue', retype('Z', '1*Expression', 'Expression'));
      }
      if (kind === 'boolean' && /^ (ou|dans quel lieu|a quel endroit) /.test(nq)) {
        flag('type.ou_booleen', SEV.CRITIQUE, '« Où » attend un lieu, pas Oui/Non', 'Coder __X!1*1Lieu_ ou __Z!1*Expression : texte libre proposé tant que la liste des lieux n\'est pas connue', retype('Z', '1*Expression', 'Expression'));
      }
      if (numeric && ci.unit !== 'P' && (/%/.test(libelle) || / (pourcentage|taux|proportion|couverture|prevalence) /.test(n))) {
        const isReal = ci.affix === '2';
        emit({
          rule: 'type.pourcentage', category: CAT.TYPE, severity: SEV.MAJEURE,
          message: 'Pourcentage ou taux codé sans l\'affixe __2P (« ' + ci.affix + ' »)',
          action: 'Coder __2P en gardant la plage' + (isReal ? '' : ' (un pourcentage est un réel : __2P!0<R<100, ou jusqu\'à 200 pour une couverture administrative)'), auto: false,
          fix: isReal ? q => { const p = splitQ(q); return joinQ(p.code.replace(/__2$/, '__2P'), p.constraint); } : null,
        });
      }
      if (kind !== 'geopoint' && kind !== 'metadata' && kind !== 'generated' && / (coordonnees gps|geolocalisation|position gps|latitude|longitude) /.test(n)) {
        flag('type.gps', SEV.CRITIQUE, 'Coordonnées GPS non codées __G', 'Coder …__G!DMS ou …__G!DD (Règle 19)');
      }
      if ((kind === 'text' || kind === 'boolean') && / date /.test(n) && !/ mise a jour | datee? /.test(n)) {
        flag('type.date', SEV.MAJEURE, 'Question de date codée ' + (kind === 'text' ? 'en texte libre' : 'en booléen'), 'Coder __A!YYYY/MM/DD');
      }

      // Règle 16 : le libellé désigne une unité administrative (région, district, établissement…)
      // Seul un libellé qui DÉSIGNE l'unité (« Région sanitaire », « Etablissement de santé ») est retenu :
      // « Responsable de l'établissement » ou « Nom de l'établissement » sont des textes libres (grammaire).
      if (ctx.detectAdmin && (kind === 'text' || kind === 'select') && !/Admin_/i.test(w.pf_question)
          && /^(region|district|etablissement|commune|enqueteur|superviseur)\b/.test(n.trim())
          && !findings.some(f => f.rule === 'liste.admin')) {
        let a = null;
        try { a = ctx.detectAdmin(libelle, n.trim()); } catch (_) { a = null; }
        if (a && a.pf_question) {
          emit({
            rule: 'liste.admin_libelle', category: CAT.LISTE, severity: SEV.MAJEURE, source: SRC.REGLE16,
            message: 'Le libellé désigne une unité du référentiel administratif (« ' + libelle.slice(0, 60) + ' ») mais le code ne pointe pas vers une liste Admin_',
            action: 'Utiliser ' + a.pf_question + ' (liste externe, jamais de valeurs en dur) — Règle 16', auto: false,
            fix: () => a.pf_question, also: { pf_modalites: a.pf_modalites || '' },
          });
        }
      }

      // dérive d'unité d'après une mention explicite du libellé
      if (numeric) {
        const hint = unitHint(libelle);
        const cur = ci.affix;
        if (hint && hint !== cur && hint !== '2P' && cur !== '1N' && /^[12]/.test(hint) && hint[0] === cur[0] && cur !== hint) {
          const sameKind = hint[0] === cur[0];
          if (sameKind && !(cur.length === 1 && hint === '2P' && false)) {
            emit({
              rule: 'type.unite_libelle', category: CAT.TYPE, severity: SEV.MINEURE,
              message: 'Le libellé mentionne explicitement l\'unité « ' + hint[1] + ' » mais le code est __' + cur, action: 'Écrire __' + hint, auto: false,
              fix: q => { const p = splitQ(q); return joinQ(p.code.replace(/__[12][A-Z]?$/, '__' + hint), p.constraint); },
            });
          }
        }
      }

      // radical sans rapport avec le libellé
      const words = contentWords(libelle);
      const { code } = q3();
      const radicalTokens = stemOf(code).split(/_+/).map(t => plain(t).replace(/ /g, '')).filter(t => t.length >= 3 && !/^\d+$/.test(t));
      if (words.length >= 2 && radicalTokens.some(t => t.length >= 4)) {
        const overlap = radicalTokens.some(t => words.some(x => x === t || (t.length >= 4 && x.length >= 4 && (x.startsWith(t.slice(0, 4)) || t.startsWith(x.slice(0, 4))))));
        const abbrev = (ctx.abbreviations || []).some(a => radicalTokens.includes(a.code.toLowerCase()) && plain(a.sens).split(' ').some(x => words.includes(x)));
        const generic = radicalTokens.some(t => /^(nombre|nb|raison|lieu|type|motif|cause|source|niveau|statut|frequence|moyen|mode)/.test(t));
        if (!overlap && !abbrev && !generic) {
          const s = sugg();
          emit({
            rule: 'semantique.radical', category: CAT.SEM, severity: SEV.MAJEURE,
            message: 'Le radical « ' + stemOf(code) + ' » n\'a aucun mot en commun avec le libellé « ' + libelle.slice(0, 70) + ' »',
            action: 'Vérifier que le code décrit bien la question' + (s ? ' — proposition issue du libellé : ' + s : ''), suggestion: s, auto: false, fix: null,
          });
        }
      }
    }

    // ── 6. Variable du DPF (feuille DPF-2) ──────────────────────────────────
    let dpf = { status: 'sans_registre', match: null };
    function stageRegistry() {
      const reg = ctx.registry;
      if (!reg || !w.pf_question.trim()) return;
      const { code } = q3();
      if (!code || affixStatus(affixOf(code)) === 'bad' && !affixOf(code)) return;
      const key = codeKey(code);
      const hit = reg.byKey.get(key);
      if (hit) { dpf = { status: 'exact', match: hit.code, libelle: hit.libelle }; return; }
      const mine = new Set(contentWords(libelle));
      // même radical, autre affixe
      const sib = (reg.byStem.get(codeKey(stemOf(code))) || []).find(e => jaccard(mine, new Set(contentWords(e.libelle))) >= 0.5);
      if (sib && codeKey(sib.code) !== key) {
        dpf = { status: 'meme_radical', match: sib.code, libelle: sib.libelle };
        if (!soundDpfCode(sib.code)) return;
        emit({
          rule: 'dpf.type_different', category: CAT.DPF, severity: SEV.MAJEURE, source: SRC.DPF_VARIABLES,
          message: 'Le DPF définit déjà ce radical avec un autre type : « ' + cleanDpfCode(sib.code) + ' » (« ' + sib.libelle.slice(0, 70) + ' »)',
          action: 'Reprendre le code normalisé du DPF, ou garder le vôtre s\'il mesure autre chose', auto: false,
          fix: q => withConstraint(q, splitQ(q).constraint).replace(/^[^!]*/, cleanDpfCode(sib.code)),
        });
        return;
      }
      // même question, autre code
      if (mine.size >= 3) {
        let best = null, bestScore = 0;
        for (const r of reg.withLib) {
          const s = jaccard(mine, r.words);
          if (s > bestScore) { bestScore = s; best = r; }
        }
        if (best && bestScore >= 0.8 && codeKey(best.entry.code) !== key) {
          dpf = { status: 'question_equivalente', match: best.entry.code, libelle: best.entry.libelle, score: bestScore };
          if (!soundDpfCode(best.entry.code)) return;
          emit({
            rule: 'dpf.variable_equivalente', category: CAT.DPF, severity: SEV.MAJEURE, source: SRC.DPF_VARIABLES,
            message: 'Même question que la variable du DPF « ' + cleanDpfCode(best.entry.code) + ' » (« ' + best.entry.libelle.slice(0, 70) + ' »)' + affixNote(affixOf(code), best.entry.code),
            action: 'Réutiliser le code normalisé du DPF (une variable = un code dans toutes les études)', auto: false,
            fix: q => withConstraint(q, splitQ(q).constraint).replace(/^[^!]*/, cleanDpfCode(best.entry.code)),
          });
          return;
        }
      }
      dpf = { status: 'nouvelle', match: null };
    }
    const cleanDpfCode = c => fixKnownTypos(strip(splitQ(c).code)).replace(/[^A-Za-z0-9_]/g, '').replace(/_{3,}/g, '__').replace(/^_+|_+$/g, '');
    // Le DPF n'est pas toujours conforme (ex. « …__SRC__X » : deux affixes) : on ne propose
    // jamais un code que la grammaire elle-même refuserait.
    const soundDpfCode = c => {
      const segs = cleanDpfCode(c).split('__');
      if (segs.length < 2 || affixStatus(segs[segs.length - 1]) === 'bad') return false;
      return !segs.slice(0, -1).some(x => FIXED_AFFIXES.includes(x) && x.length <= 3 && x === x.toUpperCase() && x !== 'ES' && x !== 'SS');
    };
    const affixNote = (mine, dpfCode) => {
      const a = affixOf(cleanDpfCode(dpfCode));
      return a && mine && a !== mine ? ' — attention : l\'affixe du DPF est « ' + a + ' », le vôtre « ' + mine + ' » (l\'unité ne serait plus portée par le code)' : '';
    };

    // ── Exécution ────────────────────────────────────────────────────────────
    if (!multiLine) {
      if (xls) { stageXlsType(); stageXlsModalites(); } else { stageConstraint(); stageModalites(); }
      stageSemantics();
      stageRegistry();
    }

    const corrected = { pf_question: w.pf_question, pf_modalites: w.pf_modalites, pf_skip: w.pf_skip };
    return { index, libelle, original, corrected, findings, dpf, work: w };
  }

  // Listes que l'on sait rapprocher d'un synonyme sans ambiguïté.
  const SYNONYMS = {
    sexe: { homme: 'Masculin', femme: 'Feminin' },
  };

  // ── Skip Logic (Règle 17) ─────────────────────────────────────────────────
  // « Lexia = valeur -> @Cible » ; plusieurs règles séparées par « ; ».
  function parseSkipRule(rule) {
    const s = String(rule || '').trim();
    const m = s.match(/^(!?)\s*([\w\u00C0-\u024F]+(?:\s*!\s*[^\s=<>]*)?)\s*(?:(!=|>=|<=|=|>|<)\s*(.+?))?\s*(?:-+>|=>|→)\s*@?\s*([\w\u00C0-\u024F]+)\s*$/);
    if (!m) return null;
    return { neg: m[1] === '!', lexia: m[2].replace(/\s/g, '').split('!')[0], op: m[3] || '', value: (m[4] || '').trim(), target: m[5], arrow: /-+>/.test(s) && !/--+>/.test(s) };
  }

  function auditSkip(res, idx, all, byKey, ctx) {
    const item = all[idx];
    const w = res.work;
    const skip = w.pf_skip.trim();
    const emitS = spec => {
      let rule = spec.rule;
      const used = new Set(res.findings.map(f => f.rule));
      for (let n = 2; used.has(rule); n++) rule = spec.rule + '#' + n;
      const cur = w.pf_skip;
      let next = typeof spec.fix === 'function' ? spec.fix(cur) : null;
      if (next === cur) next = null;
      const f = {
        id: idx + ':' + rule, index: idx, rule, field: 'pf_skip', category: CAT.SKIP, severity: spec.severity,
        message: spec.message, action: spec.action || '', source: SRC.REGLE17, before: cur, after: next,
        auto: Boolean(spec.auto) && next != null, detail: '', suggestion: spec.suggestion || '', also: null,
      };
      f.applied = next != null && (f.auto ? !ctx.rejected.has(f.id) : ctx.accepted.has(f.id));
      if (f.applied) w.pf_skip = next;
      res.findings.push(f);
    };
    const ownCode = codeOf(w.pf_question);
    const hasOwn = Boolean(ownCode);

    if (!skip) {
      // « Si oui, … » sans règle : le saut se déduit de la question booléenne précédente
      if (/^\s*si\s+(oui|non)\b/i.test(strip(item.libelle || '')) && idx > 0 && hasOwn) {
        const prev = all[idx - 1];
        const pcode = codeOf(prev.work.pf_question);
        if (pcode && CORE.classifyCode(prev.work.pf_question).kind === 'boolean') {
          const yes = /^\s*si\s+oui/i.test(strip(item.libelle));
          emitS({
            rule: 'skip.manquant', severity: SEV.MINEURE, message: 'Le libellé commence par « Si ' + (yes ? 'oui' : 'non') + ' » mais aucune Skip Logic n\'est écrite',
            action: 'Écrire ' + pcode + ' = ' + (yes ? 'Oui' : 'Non') + ' -> @' + ownCode, auto: false,
            fix: () => pcode + ' = ' + (yes ? 'Oui' : 'Non') + ' -> @' + ownCode,
          });
        }
      }
      return;
    }

    const parts = skip.split(/\s*;\s*/).filter(Boolean);
    parts.forEach((p, pi) => {
      const parsed = parseSkipRule(p);
      const tag = parts.length > 1 ? '#' + (pi + 1) : '';
      if (!parsed) {
        emitS({
          rule: 'skip.syntaxe' + tag, severity: SEV.CRITIQUE, message: 'Skip Logic illisible : « ' + p + ' »',
          action: 'Écrire <Lexia> = <valeur> -> @<Lexia cible> (Règle 17)', auto: false,
        });
        return;
      }
      const { lexia, value, op, target } = parsed;
      let lexiaFixed = lexia;
      // source
      const sk = codeKey(lexia);
      let srcIdx = byKey.has(sk) ? byKey.get(sk) : -1;
      if (srcIdx < 0) {
        const cand = bestSkipCandidate(lexia, idx, all, item);
        if (cand) {
          lexiaFixed = codeOf(all[cand.index].work.pf_question);
          srcIdx = cand.index;
          emitS({
            rule: 'skip.source_inconnue' + tag, severity: SEV.CRITIQUE,
            message: 'La condition porte sur « ' + lexia + ' », qui n\'existe pas dans le questionnaire',
            action: 'Question la plus proche (ligne ' + (cand.index + 1) + ') : ' + lexiaFixed, auto: false,
            fix: cur => replaceSkipPart(cur, pi, parsed, { lexia: lexiaFixed }),
          });
        } else {
          emitS({
            rule: 'skip.source_inconnue' + tag, severity: SEV.CRITIQUE,
            message: 'La condition porte sur « ' + lexia + ' », qui n\'existe pas dans le questionnaire', action: 'Citer le code exact de la question source', auto: false,
          });
        }
      } else if (srcIdx > idx) {
        emitS({
          rule: 'skip.source_apres' + tag, severity: SEV.MAJEURE,
          message: 'La condition porte sur « ' + lexia + ' », posée APRÈS cette question (ligne ' + (srcIdx + 1) + ')',
          action: 'Kobo n\'évalue qu\'une question déjà posée : déplacer l\'une des deux questions', auto: false,
        });
      } else if (lexia !== codeOf(all[srcIdx].work.pf_question)) {
        lexiaFixed = codeOf(all[srcIdx].work.pf_question);
        emitS({
          rule: 'skip.source_graphie' + tag, severity: SEV.MINEURE,
          message: 'Graphie de « ' + lexia + ' » différente du code de la question (' + lexiaFixed + ')', action: 'Écrire le code exact', auto: true,
          fix: cur => replaceSkipPart(cur, pi, parsed, { lexia: lexiaFixed }),
        });
      }
      // cible = la question elle-même
      if (hasOwn && target !== ownCode) {
        const tk = codeKey(target);
        const exists = byKey.has(tk);
        if (!exists) {
          emitS({
            rule: 'skip.cible_inconnue' + tag, severity: SEV.CRITIQUE,
            message: 'La cible « @' + target + ' » n\'existe pas dans le questionnaire', action: 'Cibler cette question : @' + ownCode, auto: true,
            fix: cur => replaceSkipPart(cur, pi, parsed, { target: ownCode }),
          });
        } else if (tk === codeKey(ownCode)) {
          emitS({
            rule: 'skip.cible_graphie' + tag, severity: SEV.MINEURE, message: 'Graphie de la cible « @' + target + ' » différente du code (' + ownCode + ')', action: 'Écrire le code exact', auto: true,
            fix: cur => replaceSkipPart(cur, pi, parsed, { target: ownCode }),
          });
        }
      }
      // valeur attendue d'après le type de la question source
      if (srcIdx >= 0 && srcIdx <= idx && op) {
        const sw = all[srcIdx].work;
        const sKind = CORE.classifyCode(sw.pf_question).kind;
        const sNum = sKind === 'integer' || sKind === 'decimal';
        const isCmp = ['>', '<', '>=', '<='].includes(op);
        if (sKind === 'boolean' && !/^(oui|non)$/i.test(strip(value))) {
          emitS({
            rule: 'skip.valeur' + tag, severity: SEV.MAJEURE, message: 'La question source « ' + lexiaFixed + ' » est un booléen : la valeur « ' + value + ' » n\'est ni Oui ni Non',
            action: 'Écrire = Oui ou = Non', auto: false,
          });
        } else if (sNum && !isCmp && !/^-?\d+([.,]\d+)?$/.test(value)) {
          emitS({
            rule: 'skip.valeur' + tag, severity: SEV.MAJEURE, message: 'La question source « ' + lexiaFixed + ' » est numérique : la valeur « ' + value + ' » n\'est pas un nombre',
            action: 'Comparer à un nombre (= 2, > 0)', auto: false,
          });
        } else if (sKind === 'select') {
          const sl = parseListDef(sw.pf_modalites);
          if (sl) {
            const opts = sl.values.filter(Boolean);
            if (!opts.some(o => valueKey(o) === valueKey(value))) {
              const near = opts.find(o => lev(valueKey(o), valueKey(value), 2) <= 2);
              emitS({
                rule: 'skip.valeur' + tag, severity: SEV.MAJEURE, message: 'La valeur « ' + value + ' » ne fait pas partie de la liste « ' + sl.id + ' » de la question source',
                action: near ? 'Valeur la plus proche : ' + near : 'Choisir une modalité de la liste', auto: false,
                fix: near ? cur => replaceSkipPart(cur, pi, parsed, { value: near }) : null,
              });
            }
          }
        }
      }
    });
  }

  // Réécrit UNE règle du pf_skip à partir de son état courant (jamais d'un état
  // périmé : deux corrections acceptées l'une après l'autre doivent se cumuler).
  function replaceSkipPart(cur, partIndex, _staleParsed, patch) {
    const parts = cur.split(/\s*;\s*/).filter(Boolean);
    const parsed = parseSkipRule(parts[partIndex]);
    if (!parsed) return null;
    const lexia = patch.lexia || parsed.lexia;
    const target = patch.target || parsed.target;
    const value = patch.value != null ? patch.value : parsed.value;
    const left = (parsed.neg ? '!' : '') + lexia + (parsed.op ? ' ' + parsed.op + ' ' + value : '');
    parts[partIndex] = left + ' -> @' + target;
    return parts.join(' ; ');
  }

  // Classe de type d'un affixe : 1Y, 1N et 1 sont tous « entier ».
  const affixClass = a => (/^[12]/.test(a) ? a[0] : a);

  // Question la plus proche d'un code introuvable : mêmes mots, même affixe, et
  // posée avant la question qui porte la règle.
  function bestSkipCandidate(lexia, idx, all, item) {
    // « Si oui, … » : la source est la question fermée posée juste avant
    if (idx > 0 && /^\s*si\s+(oui|non)\b/i.test(strip((item && item.libelle) || ''))) {
      const k = CORE.classifyCode(all[idx - 1].work.pf_question).kind;
      if (k === 'boolean' || k === 'trilean') return { index: idx - 1, score: 1 };
    }
    const toks = c => codeKey(stemOf(c)).split(/_+/).filter(Boolean).map(t => t.replace(/s$/, ''));
    const myAffix = affixOf(lexia);
    const mine = new Set(toks(lexia));
    let best = null;
    for (let i = 0; i < all.length; i++) {
      if (i === idx || i > idx) continue;
      const c = codeOf(all[i].work.pf_question);
      if (!c) continue;
      if (myAffix && affixClass(affixOf(c)) !== affixClass(myAffix)) continue;
      const theirs = new Set(toks(c));
      let n = 0;
      mine.forEach(t => {
        for (const u of theirs) {
          if (t === u || (t.length >= 2 && u.length >= 2 && (u.startsWith(t) || t.startsWith(u)))) { n++; break; }
        }
      });
      const score = n / (mine.size + theirs.size - n);
      if (score > (best ? best.score : 0)) best = { index: i, score };
    }
    return best && best.score >= 0.6 ? best : null;
  }

  // ── Audit d'un questionnaire ──────────────────────────────────────────────
  // options : { dpfLists, abbreviations, registry (brut) ou registryIndex,
  //             accepted:Set, rejected:Set, derive(item) }
  function auditQuestionnaire(items, options) {
    const o = options || {};
    const ctx = {
      dpfLists: (o.dpfLists || (CORE.DEFAULT_DPF_CATALOGUE && CORE.DEFAULT_DPF_CATALOGUE.lists) || []).filter(l => l && l.identifiant),
      abbreviations: o.abbreviations || (CORE.DEFAULT_DPF_CATALOGUE && CORE.DEFAULT_DPF_CATALOGUE.abbreviations) || [],
      registry: o.registryIndex || (o.registry ? buildRegistry(o.registry) : (DEFAULT_REGISTRY ? getDefaultIndex() : null)),
      accepted: o.accepted || new Set(),
      rejected: o.rejected || new Set(),
      derive: o.derive || null,
      detectAdmin: o.detectAdmin || null,
    };
    const results = items.map((it, i) => auditItem(it, i, ctx));

    // index des codes corrigés
    const byKey = new Map();
    results.forEach((r, i) => {
      const c = codeOf(r.work.pf_question);
      const k = codeKey(c);
      if (k && !byKey.has(k)) byKey.set(k, i);
    });
    results.forEach((r, i) => { if (!items[i]._xls) auditSkip(r, i, results, byKey, ctx); });

    // doublons de code
    const groups = new Map();
    results.forEach((r, i) => {
      const k = codeKey(codeOf(r.work.pf_question));
      if (!k) return;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(i);
    });
    groups.forEach(list => {
      if (list.length < 2) return;
      const first = list[0];
      list.slice(1).forEach(i => {
        const r = results[i];
        const sameLib = plain(r.libelle) === plain(results[first].libelle);
        // Le mot qui distingue cette question de celle qui garde le code (« Rougeole », « VPO »…)
        const base = new Set(contentWords(results[first].libelle));
        const tokens = strip(r.libelle).split(/[^A-Za-z0-9]+/).filter(Boolean);
        const extra = [];
        tokens.forEach(t => {
          const k = t.toLowerCase();
          if (k.length >= 3 && !STOPWORDS.has(k) && !base.has(k) && !extra.some(e => e.toLowerCase() === k)) {
            extra.push(/^[A-Z0-9]{2,5}$/.test(t) ? t : cap(k));
          }
        });
        let after = null;
        if (!sameLib && extra.length) {
          const { code, constraint } = splitQ(r.work.pf_question);
          const segs = code.split('__');
          const affix = segs.length >= 2 ? segs.pop() : '';
          const tag = extra.slice(0, 2).join('_');
          after = joinQ(affix ? segs.join('__') + '_' + tag + '__' + affix : code + '_' + tag, constraint);
          if (codeKey(codeOf(after)) !== codeKey(codeOf(r.work.pf_question)) && groups.has(codeKey(codeOf(after)))) after = null; // déjà pris
        }
        const f = {
          id: i + ':doublon.code', index: i, rule: 'doublon.code', field: 'pf_question', category: CAT.DOUBLON, severity: SEV.MAJEURE,
          message: 'Code déjà utilisé ' + (r.xls && r.xls.data ? 'par la colonne ' : 'ligne ') + (r.xls && r.xls.row != null ? r.xls.row : first + 1) + ' (' + (sameLib ? 'même libellé : question répétée' : 'autre question') + ')',
          action: after ? 'Deux questions ne peuvent pas porter le même code : ajouter ce qui les distingue (' + extra.slice(0, 2).join(' ') + ')' : 'Deux questions ne peuvent pas porter le même code (Kobo refuse deux « name » identiques) : préciser le déterminant',
          source: SRC.GRAMMAIRE, before: r.work.pf_question, after, auto: false, applied: false, detail: '', suggestion: after ? codeOf(after) : '', also: null,
        };
        f.applied = after != null && ctx.accepted.has(f.id);
        if (f.applied) r.work.pf_question = after;
        r.findings.push(f);
      });
    });

    results.forEach(r => {
      r.corrected = { pf_question: r.work.pf_question, pf_modalites: r.work.pf_modalites, pf_skip: r.work.pf_skip };
      if (items[r.index]._xls) r.xls = items[r.index]._xls;
      r.findings.sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]);
      const open = r.findings.filter(f => !f.applied);
      r.status = !r.findings.length ? 'conforme' : (open.length ? 'a_valider' : 'corrige');
      r.changed = r.corrected.pf_question !== r.original.pf_question || r.corrected.pf_modalites !== r.original.pf_modalites || r.corrected.pf_skip !== r.original.pf_skip;
      delete r.work;
    });

    return { version: AUDIT_VERSION, items: results, findings: results.flatMap(r => r.findings), summary: summarize(results, ctx) };
  }

  function summarize(results, ctx) {
    const all = results.flatMap(r => r.findings);
    const bySeverity = { Critique: 0, Majeure: 0, Mineure: 0 };
    const byCategory = {};
    all.forEach(f => { bySeverity[f.severity]++; byCategory[f.category] = (byCategory[f.category] || 0) + 1; });
    const dpf = { exact: 0, meme_radical: 0, question_equivalente: 0, nouvelle: 0, sans_registre: 0 };
    results.forEach(r => { dpf[r.dpf.status] = (dpf[r.dpf.status] || 0) + 1; });
    const total = results.length;
    const conformes = results.filter(r => r.status === 'conforme').length;
    return {
      total, conformes,
      corriges: results.filter(r => r.status === 'corrige').length,
      aValider: results.filter(r => r.status === 'a_valider').length,
      findings: all.length, auto: all.filter(f => f.auto).length, appliquees: all.filter(f => f.applied).length,
      nonCodifiees: results.filter(r => !r.original.pf_question.trim()).length,
      bySeverity, byCategory, dpf,
      registre: ctx.registry ? ctx.registry.size : 0,
      conformiteInitiale: total ? Math.round((conformes / total) * 100) : 100,
    };
  }


  // ── Lecture des fichiers ──────────────────────────────────────────────────
  // En-têtes d'une feuille « questionnaire codifié » : Libellé / PF-Question /
  // PF-Modalités / Skip Logic (même détection que l'onglet Questionnaire Codifié,
  // mais le code est cherché AVANT le libellé : « PF/Question » contient
  // « question »).
  function detectCodifiedColumns(headers) {
    const h = headers.map(x => plain(x));
    const find = (exact, partial) => {
      for (const e of exact) { const i = h.findIndex(x => x === e); if (i >= 0) return i; }
      for (const e of partial) { const i = h.findIndex(x => x.includes(e)); if (i >= 0) return i; }
      return -1;
    };
    const code = find(['pf question', 'code phakts', 'pf_question', 'code', 'codification'], ['pf question', 'pf', 'phakts', 'codif']);
    const libelle = find(['libelle', 'label', 'intitule', 'question'], ['libelle', 'intitule']);
    const modalites = find(['pf modalites', 'modalites', 'pf_modalites', 'choix', 'options'], ['modalite', 'choix', 'option']);
    const skip = find(['skip logic', 'skip', 'pf_skip', 'saut', 'relevant'], ['skip', 'saut']);
    return { code, libelle: libelle === code ? -1 : libelle, modalites, skip };
  }

  // Ligne qui sert de TITRE (« SECTION 1 : … », « IDENTIFICATION ») et non de question à codifier.
  function isSectionTitle(libelle) {
    const t = String(libelle || '').trim();
    if (!t || /\?\s*$/.test(t)) return false;
    if (/^(section|partie|module|chapitre|bloc|rubrique|theme|volet|annexe|titre)\b/i.test(strip(t))) return true;
    const letters = strip(t).replace(/[^A-Za-z]/g, '');
    return letters.length >= 4 && t === t.toUpperCase();
  }

  // Questions d'une feuille « Libellé / PF-Question / PF-Modalités / Skip Logic » (colonnes
  // de detectCodifiedColumns ; code absent = -1 pour une simple liste de libellés).
  // table : { headers, rows:[{_row, <colonne>: texte}] }. Un libellé sans code est une question
  // à codifier, sauf s'il s'agit manifestement d'un titre de section.
  function questionnaireToItems(table, cols) {
    const get = (r, c) => (c >= 0 ? String(r[table.headers[c]] || '') : '').trim();
    const items = [], rows = [];
    let sections = 0;
    (table.rows || []).forEach(r => {
      const code = get(r, cols.code), libelle = get(r, cols.libelle), mod = get(r, cols.modalites), skip = get(r, cols.skip);
      if (!code && !libelle) return;
      if (!code && !mod && !skip && isSectionTitle(libelle)) { sections++; return; }
      items.push({ libelle, pf_question: code, pf_modalites: mod, pf_skip: skip });
      rows.push(r._row);
    });
    return { items, rows, sections };
  }

  // Une feuille est un questionnaire codifié si elle a une colonne de code PHAKTS
  // distincte du libellé ; un XLSForm si elle a « type » et « name » (survey).
  function detectSheetKind(headers) {
    const h = headers.map(x => String(x || '').trim().toLowerCase());
    if (h.includes('type') && h.includes('name')) return 'survey';
    if (h.includes('list_name') && h.includes('name')) return 'choices';
    const c = detectCodifiedColumns(headers);
    if (c.code >= 0 && c.code !== c.libelle) return 'codified';
    if (c.libelle >= 0 && c.code < 0) return 'libelles'; // simple liste de libellés à codifier
    return '';
  }

  // Question d'un XLSForm → question du modèle d'audit (le « name » tient lieu de code).
  // survey / choices : { headers:[], rows:[{ _row, <colonne>: texte }] }
  function xlsformToItems(survey, choices) {
    const labelKey = hs => (hs || []).find(h => /^label(::|$)/i.test(h)) || 'label';
    const lk = labelKey(survey.headers);
    const clk = labelKey(choices && choices.headers);
    const lists = new Map();
    ((choices && choices.rows) || []).forEach(r => {
      const l = String(r.list_name || '').trim();
      if (!l) return;
      if (!lists.has(l)) lists.set(l, []);
      lists.get(l).push({ name: String(r.name || '').trim(), label: String(r[clk] || '').trim() });
    });
    const items = [];
    (survey.rows || []).forEach(r => {
      const type = String(r.type || '').trim();
      const name = String(r.name || '').trim();
      if (!type || !name) return;
      const t = type.toLowerCase();
      if (/^(begin|end)[\s_]/.test(t) || /^(note|calculate|hidden|rank|simserial|subscriberid|caseid)\b/.test(t)) return;
      const meta = /^(start|end|today|deviceid|username|phonenumber|audit)$/.test(t) ? t : '';
      let affix = '', kind = '', list = '', modalites = '';
      let m;
      if ((m = type.match(/^select_(one|multiple)\s+(\S+)$/i))) {
        kind = 'select'; list = m[2];
        const opts = lists.get(list) || [];
        const keys = opts.map(o => valueKey(o.name || o.label));
        const yn = keys.length === 2 && keys.includes('oui') && keys.includes('non');
        const tri = keys.length === 3 && keys.includes('oui') && keys.includes('non');
        affix = m[1].toLowerCase() === 'one' && yn ? 'B' : (m[1].toLowerCase() === 'one' && tri ? 'C' : 'X');
        if (affix === 'X' && opts.length) {
          const id = list.split(/[_\s-]+/).filter(Boolean).map(cap).join('_') + '_';
          modalites = id + '=[' + opts.map(o => o.name || o.label).join('|') + ']';
        }
      } else if (/^select_one_(external|from_file)/i.test(type)) { kind = 'select'; affix = 'X'; list = ''; }
      else if (/^integer$/i.test(type)) affix = '1';
      else if (/^decimal$/i.test(type)) affix = '2';
      else if (/^text$/i.test(type)) affix = 'Z';
      else if (/^(date|datetime|time)$/i.test(type)) affix = 'A';
      else if (/^(geopoint|geotrace|geoshape)$/i.test(type)) affix = 'G';
      else if (/^(image|photo)$/i.test(type)) affix = 'P';
      else if (meta) affix = 'G';
      items.push({
        libelle: String(r[lk] || '').trim(), pf_question: name, pf_modalites: modalites, pf_skip: '',
        _xls: { row: r._row, type, list, affix, kind, meta },
      });
    });
    return items;
  }


  // ── Fichier de données (export Kobo) ──────────────────────────────────────
  // La première ligne porte les noms de variables, ou les libellés des questions selon
  // l'option d'export choisie dans Kobo. rows : lignes d'échantillon (tableaux de texte).
  const KOBO_SYSTEM = /^(_|meta\/|formhub\/)|^(__version__|instanceID|instanceName)$/i;
  const KOBO_META = /^(start|end|today|deviceid|username|phonenumber|audit)$/i;

  // Un en-tête qui contient espaces, accents ou ponctuation est un libellé, pas un code.
  const looksLikeLabel = h => /[\s'’?:,;()]|[^\x00-\x7f]/.test(h) || h.length > 60;

  // Type probable d'une colonne d'après ses valeurs : { affix } quand c'est sûr (nombre,
  // date, oui/non), { suggest } quand ce n'est qu'une probabilité (liste ou texte libre).
  function inferColumn(values) {
    const v = values.map(x => String(x == null ? '' : x).trim()).filter(Boolean);
    if (v.length < 3) return { affix: '', suggest: '', label: 'sans valeurs' };
    if (v.every(x => /^-?\d+$/.test(x))) return { affix: '1', suggest: '1', label: 'entières' };
    if (v.every(x => /^-?\d+([.,]\d+)?$/.test(x))) return { affix: '2', suggest: '2', label: 'décimales' };
    if (v.every(x => /^\d{4}-\d{2}-\d{2}([ T][\d:.+-]+)?$/.test(x))) return { affix: 'A', suggest: 'A', label: 'de dates' };
    const set = new Set(v.map(x => valueKey(x)));
    if ([...set].every(x => ['oui', 'non', 'yes', 'no', 'true', 'false', 'vrai', 'faux'].includes(x))) return { affix: 'B', suggest: 'B', label: 'oui/non' };
    const distinct = new Set(v);
    const choice = v.length >= 5 && distinct.size <= Math.max(8, Math.ceil(v.length * 0.2)) && v.every(x => x.length < 40);
    return { affix: '', suggest: choice ? 'X' : 'Z', label: choice ? 'un choix dans une liste' : 'du texte', distinct: choice ? [...distinct].slice(0, 12) : [] };
  }

  function datasetToItems(headers, rows) {
    const hs = headers.map(h => String(h == null ? '' : h).trim());
    const col = new Map();
    hs.forEach((h, i) => { if (h && !col.has(h)) col.set(h, i); });
    const prefixOf = h => (h.includes('/') ? h.slice(0, h.lastIndexOf('/')) : '');
    // colonnes « Question/choix » d'une question à choix multiples : la question parente
    // est elle-même une colonne, ou au moins deux colonnes partagent un préfixe codifié
    const siblings = new Map();
    hs.forEach(h => { const p = prefixOf(h); if (p && !col.has(p)) siblings.set(p, (siblings.get(p) || 0) + 1); });
    const isChild = h => {
      const p = prefixOf(h);
      if (!p) return false;
      if (col.has(p)) return true;
      const last = p.split('/').pop();
      return (siblings.get(p) || 0) >= 2 && (looksCoded(last) || looksLikeLabel(last) && !looksLikeLabel(h.split('/').pop()));
    };
    const items = [];
    const sample = i => rows.map(r => (r || [])[i]);
    const add = (h, i, children) => {
      const parts = h.split('/');
      const name = parts[parts.length - 1];
      const inf = inferColumn(sample(i));
      const meta = KOBO_META.test(name) ? name.toLowerCase() : '';
      const label = !meta && looksLikeLabel(name);
      items.push({
        libelle: label ? name : '', pf_question: label ? '' : name,
        pf_modalites: label && inf.distinct && inf.distinct.length ? inf.distinct.join(' | ') : '', pf_skip: '',
        _xls: { row: i + 1, type: 'valeurs ' + inf.label, list: '', affix: meta ? 'G' : inf.affix, suggest: meta ? 'G' : inf.suggest, kind: '', meta, data: true, fromLabel: label, header: h, children },
      });
    };
    hs.forEach((h, i) => {
      if (!h || KOBO_SYSTEM.test(h) || col.get(h) !== i) return;
      if (isChild(h)) return;
      add(h, i, hs.filter(c => c.startsWith(h + '/')));
    });
    // question à choix multiples sans colonne parente : une entrée pour le préfixe commun
    siblings.forEach((n, p) => {
      if (n < 2) return;
      const kids = hs.filter(c => prefixOf(c) === p);
      if (!kids.length || !kids.every(k => !col.has(k) || isChild(k))) return;
      const first = hs.indexOf(kids[0]);
      add(p, first, kids);
    });
    items.sort((a, b) => a._xls.row - b._xls.row);
    return items;
  }

  // { en-tête d'origine → nouvel en-tête } pour toutes les colonnes touchées, enfants d'un
  // choix multiple compris. Le chemin de groupe (grp/…) n'est jamais modifié.
  function datasetHeaderRenames(res) {
    const map = new Map();
    res.items.forEach(r => {
      if (!r.xls || !r.xls.data) return;
      const after = r.corrected.pf_question.trim();
      const before = (r.xls.fromLabel ? r.libelle : r.original.pf_question).trim();
      if (!after || after === before) return;
      const path = r.xls.header.includes('/') ? r.xls.header.slice(0, r.xls.header.lastIndexOf('/') + 1) : '';
      const newHeader = path + after;
      if (newHeader === r.xls.header) return;
      map.set(r.xls.header, newHeader);
      (r.xls.children || []).forEach(c => { map.set(c, newHeader + c.slice(r.xls.header.length)); });
    });
    return map;
  }

  // ${ancien_nom} → ${nouveau_nom} dans une expression XLSForm (relevant,
  // constraint, calculation, choice_filter, libellés…).
  const renameRefs = (text, map) => String(text == null ? '' : text).replace(/\$\{([^}]+)\}/g, (m, n) => (map.has(n) ? '${' + map.get(n) + '}' : m));

  // Noms à changer dans le XLSForm : { ancien: nouveau } (corrections appliquées).
  function xlsformRenames(res) {
    const map = new Map();
    res.items.forEach(r => {
      if (!r.xls) return;
      const before = r.original.pf_question.trim();
      const after = r.corrected.pf_question.trim();
      if (before && after && before !== after) map.set(before, after);
    });
    return map;
  }

  // Questions corrigées, dans la forme du Studio (onglet Résultats).
  const correctedItems = (res, items) => res.items.map((r, i) => ({
    libelle: (items && items[i] && items[i].libelle) || r.libelle,
    pf_question: r.corrected.pf_question, pf_modalites: r.corrected.pf_modalites, pf_skip: r.corrected.pf_skip,
  }));

  // Lignes du « Journal des corrections PHAKTS » (même colonnes que celui de l'équipe :
  // Feuille, Ligne, Champ, Catégorie, Sévérité, Avant, Après) + règle et source.
  const FIELD_LABEL = { pf_question: 'PF/Question', pf_modalites: 'PF/Modalités', pf_skip: 'Skip Logic' };
  function journalRows(sheetName, res, rowOf) {
    const rowFor = i => (rowOf ? rowOf(i) : i + 2);
    const rows = { appliquees: [], aValider: [] };
    res.items.forEach(r => {
      r.findings.forEach(f => {
        const line = {
          feuille: sheetName, ligne: rowFor(r.index), champ: r.xls ? (r.xls.data ? 'En-tête' : 'name') : FIELD_LABEL[f.field], categorie: f.category, severite: f.severity,
          avant: f.before, apres: f.after == null ? '' : f.after, regle: f.rule, source: f.source,
          anomalie: f.message, action: f.action, libelle: r.libelle,
        };
        (f.applied ? rows.appliquees : rows.aValider).push(line);
      });
    });
    return rows;
  }

  let _defaultIndex = null;
  function getDefaultIndex() {
    if (!_defaultIndex) _defaultIndex = buildRegistry(DEFAULT_REGISTRY);
    return _defaultIndex;
  }

  return {
    AUDIT_VERSION, SEV, CAT, SRC, DPF_LEXIE_TYPOS,
    auditQuestionnaire, auditItem, parseSkipRule, parseListDef, canonValue, canonListId, codeKey,
    parseDpfRegistryRows, buildRegistry, unitHint, dpfValues, affixStatus, strip, plain,
    isSectionTitle, questionnaireToItems, datasetToItems, datasetHeaderRenames, inferColumn, normalizeDpfCode, detectCodifiedColumns, detectSheetKind, xlsformToItems, renameRefs, xlsformRenames, correctedItems, journalRows,
    get defaultRegistry() { return DEFAULT_REGISTRY; },
  };
});
