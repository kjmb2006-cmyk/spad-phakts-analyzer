// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS XLSForm Builder
//  Convertit les items codifiés PHAKTS → structure XLSForm (KoboToolbox)
// ─────────────────────────────────────────────────────────────────────────────

const {
  classifyCode, selectCardinality, parseRange, rangeConstraint,
  PHONE_CONSTRAINT, trileanChoices,
} = require("../public/phakts-core.js");

function sanitizeName(str) {
  return (str || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .substring(0, 63) || "field";
}

function buildXlsName(codePart) {
  const rawName = codePart.replace(/__/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
  return /^[a-zA-Z]/.test(rawName) ? rawName.substring(0, 63) : "q_" + rawName.substring(0, 61);
}

/**
 * Parse a PHAKTS skip rule into an XLSForm relevant expression.
 * Input:  "Grossesse__B = Oui -> @Age_Grossesse__1W"
 * Output: "${Grossesse_B} = 'oui'"
 */
function parseSkipRule(rule, itemsIndex) {
  if (!rule || !rule.trim()) return "";
  const rules = rule.split(/\s*;\s*/).filter(Boolean);
  const expressions = rules.map(r => parseSingleRule(r.trim(), itemsIndex)).filter(Boolean);
  return expressions.join(" and ");
}

function parseSingleRule(rule, itemsIndex) {
  const arrowIdx = rule.indexOf("->");
  const condition = arrowIdx >= 0 ? rule.substring(0, arrowIdx).trim() : rule.trim();
  if (!condition) return "";

  // Negated boolean: !Lexia__B
  const negBool = condition.match(/^!\s*(\S+)/);
  if (negBool && !condition.includes("=")) {
    const xlsName = resolveXlsName(negBool[1], itemsIndex);
    return xlsName ? "${" + xlsName + "} = 'non'" : "";
  }

  // Inequality: Lexia__X != Value
  const neqMatch = condition.match(/^(\S+)\s*!=\s*(.+)$/);
  if (neqMatch) {
    const xlsName = resolveXlsName(neqMatch[1], itemsIndex);
    if (!xlsName) return "";
    const val = neqMatch[2].trim();
    // CORRECTION E-06: Comparaison numérique (integer) vs chaîne
    // Si valeur est un nombre, utiliser > 0 au lieu de != '0'
    if (/^\d+$/.test(val)) {
      return "${" + xlsName + "} > 0";
    }
    const v = sanitizeName(val.toLowerCase());
    return isMultipleSource(neqMatch[1], itemsIndex)
      ? "not(selected(${" + xlsName + "}, '" + v + "'))"
      : "${" + xlsName + "} != '" + v + "'";
  }

  // Equality: Lexia__X = Value
  const eqMatch = condition.match(/^(\S+)\s*=\s*(.+)$/);
  if (eqMatch) {
    const xlsName = resolveXlsName(eqMatch[1], itemsIndex);
    if (!xlsName) return "";
    const val = sanitizeName(eqMatch[2].trim().toLowerCase());
    return isMultipleSource(eqMatch[1], itemsIndex)
      ? "selected(${" + xlsName + "}, '" + val + "')"
      : "${" + xlsName + "} = '" + val + "'";
  }

  // Bare boolean: Lexia__B
  const xlsName = resolveXlsName(condition, itemsIndex);
  return xlsName ? "${" + xlsName + "} = 'oui'" : "";
}

function findSkipSource(lexia, itemsIndex) {
  const clean = lexia.replace(/^!/, "").trim();
  return (itemsIndex || []).find(entry => {
    const codePart = entry.pf_question.split("!")[0];
    return codePart === clean || entry.pf_question === clean;
  }) || null;
}

// Sur un select_multiple, « = » ne teste pas l'appartenance : seul selected() est valide.
function isMultipleSource(lexia, itemsIndex) {
  const item = findSkipSource(lexia, itemsIndex);
  return Boolean(item) && classifyCode(item.pf_question).kind === "select"
    && selectCardinality(item.pf_question, item.pf_modalites).multiple;
}

function resolveXlsName(lexia, itemsIndex) {
  const found = findSkipSource(lexia, itemsIndex);
  return buildXlsName(found ? found.pf_question.split("!")[0] : lexia.replace(/^!/, "").trim());
}

/**
 * Construit les 3 feuilles XLSForm à partir des items PHAKTS codifiés.
 * Gère le filtrage hiérarchique Région → District via choice_filter.
 * @param {Array}  items     - [{libelle, pf_question, pf_modalites, pf_skip}]
 * @param {string} formTitle - Titre du formulaire
 * @returns {{ survey, choices, settings }}
 */
function buildXLSForm(items, formTitle = "Questionnaire") {
  const surveyRows = [];
  const choicesMap = {
    yes_no: [
      { name: "oui", label: "Oui" },
      { name: "non", label: "Non" },
    ],
  };

  // listsMeta stocke les métadonnées par listKey: { hasRegionCode: bool }
  const listsMeta = {};

  // Nom XLS de la dernière question Région vue (pour choice_filter des districts)
  let lastRegionFieldName = null;

  // Compteur pour les numéros de question
  let questionNumber = 0;

  for (const item of items) {
    const { libelle, pf_question, pf_modalites, pf_skip } = item;

    const bangIdx = pf_question.indexOf("!");
    const codePart = bangIdx >= 0 ? pf_question.substring(0, bangIdx) : pf_question;
    const constraintPart = bangIdx >= 0 ? pf_question.substring(bangIdx + 1) : "";

    const xlsName = buildXlsName(codePart);

    const cls = classifyCode(pf_question);
    let type = "text";
    let constraint = "";
    let constraintMsg = "";
    let choiceFilter = "";
    const hint = pf_modalites;

    if (cls.kind === "boolean") {
      type = "select_one yes_no";

    } else if (cls.kind === "trilean") {
      // ── Triléen (__C!trilean, Règle 11 ext.)
      const options = trileanChoices(pf_modalites);
      const listKey = "trilean_" + sanitizeName(options[2].toLowerCase());
      if (!choicesMap[listKey]) {
        choicesMap[listKey] = options.map(o => ({ name: sanitizeName(o.toLowerCase()), label: o }));
        listsMeta[listKey] = { hasRegionCode: false };
      }
      type = "select_one " + listKey;

    } else if (cls.kind === "geopoint") {
      // ── Géolocalisation (__G!DMS / !DD, Règle 19 ; ancienne écriture __G__X)
      type = "geopoint";

    } else if (cls.kind === "metadata") {
      // ── Variable générée par Kobo (__G!start, !end, !today, !deviceid…)
      type = cls.metadata;

    } else if (cls.kind === "select" && codePart.includes("__SRC")) {
      // ── Source d'information (select_multiple)
      const listKey = buildSelectList(pf_modalites, choicesMap, listsMeta, false);
      type = listKey ? "select_multiple " + listKey : "text";

    } else if (cls.kind === "select") {
      // ── Choix (select_one ou select_multiple)
      const match = (pf_modalites || "").match(/(\w+_)\s*=\s*\[([^\]]+)\]/);
      if (match) {
        const rawListKey = sanitizeName(match[1].replace(/_+$/, "").toLowerCase());
        const rawList = match[2];
        const isRegionList = /region/i.test(rawListKey);
        const isDistrictList = /district/i.test(rawListKey);

        if (isDistrictList) {
          // Parsing spécial : REGION-DISTRICT
          if (!choicesMap[rawListKey]) {
            buildDistrictList(rawList, rawListKey, choicesMap, listsMeta);
          }
          if (lastRegionFieldName) {
            choiceFilter = `region_code=\${${lastRegionFieldName}}`;
          }
          type = "select_one " + rawListKey;
        } else {
          // Liste standard
          const separator = rawList.includes("|") ? "|" : ",";
          if (!choicesMap[rawListKey]) {
            const options = rawList
              .split(separator)
              .map(s => s.trim())
              .filter(s => s);
            // CORRECTION E-12: Garder "0" si présent (pour "Ne sait pas" / "Autre")
            choicesMap[rawListKey] = options.map(o => ({
              name: sanitizeName(o.toLowerCase()),
              label: o,
            }));
            listsMeta[rawListKey] = { hasRegionCode: false };
          }
          const isOne = !selectCardinality(pf_question, pf_modalites).multiple;
          type = (isOne ? "select_one " : "select_multiple ") + rawListKey;

          if (isRegionList) {
            lastRegionFieldName = xlsName;
          }
        }
      } else {
        type = "select_one yes_no";
      }

    } else if (cls.kind === "integer" || cls.kind === "decimal") {
      // CORRECTION E-08/E-10 (borne basse 0 inclusive) : voir rangeConstraint()
      type = cls.kind;
      ({ expression: constraint, message: constraintMsg } = rangeConstraint(parseRange(constraintPart)));

    } else if (cls.kind === "date" || cls.kind === "image") {
      type = cls.kind;

    } else if (cls.kind === "phone") {
      constraint = PHONE_CONSTRAINT.expression;
      constraintMsg = PHONE_CONSTRAINT.message;
    }

    // Multiplicité *N (ex. !1*3Liste_) : au moins N choix cochés
    if (type.startsWith("select_multiple ")) {
      const { min } = selectCardinality(pf_question, pf_modalites);
      if (min) {
        constraint = `count-selected(.) >= ${min}`;
        constraintMsg = `Sélectionnez au moins ${min} réponses.`;
      }
    }

    const relevant = parseSkipRule(pf_skip || "", items);

    // Incrémenter le numéro de question
    questionNumber++;

    // Une métadonnée Kobo n'est ni posée ni saisie : pas de libellé,
    // d'obligation ni de condition d'affichage.
    if (cls.kind === "metadata") {
      surveyRows.push({ type, name: xlsName, "_question_no": questionNumber });
      continue;
    }

    surveyRows.push({
      type,
      name: xlsName,
      "label::French (fr)": libelle,
      required: "yes",
      relevant,
      constraint,
      constraint_message: constraintMsg,
      choice_filter: choiceFilter,
      hint,
      // Colonne personnalisée pour numéro de question
      "_question_no": questionNumber,
    });
  }

  // ── Feuille choices (avec region_code si applicable)
  const choicesRows = [];
  for (const [listName, options] of Object.entries(choicesMap)) {
    const hasRegionCode = listsMeta[listName] && listsMeta[listName].hasRegionCode;
    for (const opt of options) {
      const row = {
        list_name: listName,
        name: opt.name,
        "label::French (fr)": opt.label,
      };
      if (hasRegionCode) {
        row.region_code = opt.region_code || "";
      }
      choicesRows.push(row);
    }
  }

  // ── Feuille settings
  const formId = formTitle
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "_")
    .replace(/_+/g, "_")
    .substring(0, 63);

  const version = new Date().toISOString().split("T")[0].replace(/-/g, "");

  const settingsRow = {
    form_title: formTitle,
    form_id: formId,
    version,
    default_language: "French (fr)",
    style: "pages",
  };

  return { survey: surveyRows, choices: choicesRows, settings: [settingsRow] };
}

/**
 * Construit une liste de choix standard et la stocke dans choicesMap.
 * @returns {string|null} listKey ou null
 */
function buildSelectList(pf_modalites, choicesMap, listsMeta, multiSelect) {
  const match = (pf_modalites || "").match(/(\w+_)\s*=\s*\[([^\]]+)\]/);
  if (!match) return null;
  const listKey = sanitizeName(match[1].replace(/_+$/, "").toLowerCase());
  if (!choicesMap[listKey]) {
    const rawList = match[2];
    const separator = rawList.includes("|") ? "|" : ",";
    // CORRECTION E-12: Garder "0" si présent (pour "Ne sait pas" / "Autre")
    const options = rawList.split(separator).map(s => s.trim()).filter(s => s);
    choicesMap[listKey] = options.map(o => ({ name: sanitizeName(o.toLowerCase()), label: o }));
    listsMeta[listKey] = { hasRegionCode: false };
  }
  return listKey;
}

/**
 * Construit la liste des districts depuis le format REGION-DISTRICT.
 * Ajoute region_code sur chaque option pour le choice_filter.
 */
function buildDistrictList(rawList, listKey, choicesMap, listsMeta) {
  const separator = rawList.includes("|") ? "|" : ",";
  // CORRECTION E-12: Garder "0" si présent (pour "Ne sait pas" / "Autre")
  const options = rawList.split(separator).map(s => s.trim()).filter(s => s);
  choicesMap[listKey] = options.map(o => {
    const dashIdx = o.indexOf("-");
    if (dashIdx > 0) {
      const regionPart = o.substring(0, dashIdx);
      const districtPart = o.substring(dashIdx + 1);
      return {
        name: sanitizeName(districtPart.toLowerCase()),
        label: districtPart.replace(/_/g, " "),
        region_code: sanitizeName(regionPart.toLowerCase()),
      };
    }
    return { name: sanitizeName(o.toLowerCase()), label: o.replace(/_/g, " "), region_code: "" };
  });
  listsMeta[listKey] = { hasRegionCode: true };
}

module.exports = { buildXLSForm };
