// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS XLSForm Builder
//  Convertit les items codifiés PHAKTS → structure XLSForm (KoboToolbox)
// ─────────────────────────────────────────────────────────────────────────────

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
    return "${" + xlsName + "} != '" + sanitizeName(val.toLowerCase()) + "'";
  }

  // Equality: Lexia__X = Value
  const eqMatch = condition.match(/^(\S+)\s*=\s*(.+)$/);
  if (eqMatch) {
    const xlsName = resolveXlsName(eqMatch[1], itemsIndex);
    if (!xlsName) return "";
    const val = sanitizeName(eqMatch[2].trim().toLowerCase());
    return "${" + xlsName + "} = '" + val + "'";
  }

  // Bare boolean: Lexia__B
  const xlsName = resolveXlsName(condition, itemsIndex);
  return xlsName ? "${" + xlsName + "} = 'oui'" : "";
}

function resolveXlsName(lexia, itemsIndex) {
  const clean = lexia.replace(/^!/, "").trim();
  if (itemsIndex) {
    const found = itemsIndex.find(entry => {
      const codePart = entry.pf_question.split("!")[0];
      return codePart === clean || entry.pf_question === clean;
    });
    if (found) return buildXlsName(found.pf_question.split("!")[0]);
  }
  return buildXlsName(clean);
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

    let type = "text";
    let constraint = "";
    let constraintMsg = "";
    let choiceFilter = "";
    const hint = pf_modalites;

    // Extraction de la plage numérique (ex: "0<N<120", "35<R<42")
    // CORRECTION E-01/E-02: Utiliser integer quand il y a contrainte numérique
    // CORRECTION E-08/E-10: Utiliser >= 0 pour inclure zéro (enfants non vaccinés)
    const rangeMatch = constraintPart.match(
      /(\d+(?:\.\d+)?)\s*<\s*[A-Za-z]\s*<\s*(\d+(?:\.\d+)?)/
    );
    if (rangeMatch) {
      const lower = parseFloat(rangeMatch[1]);
      const upper = parseFloat(rangeMatch[2]);
      // CORRECTION: Utiliser >= pour inclure zéro, sauf si lower > 0 explicitement
      const op = lower === 0 ? ". >= " : ". > ";
      constraint = op + lower + " and . < " + upper;
      constraintMsg = `Valeur entre ${lower} et ${upper}`;
      // Type numérique avec contrainte → integer
      type = "integer";
    }

    if (codePart.includes("__B") || constraintPart === "boolean") {
      // ── Booléen
      type = "select_one yes_no";
      constraint = "";
      constraintMsg = "";

    } else if (codePart.includes("__SRC")) {
      // ── Source d'information (select_multiple)
      const listKey = buildSelectList(pf_modalites, choicesMap, listsMeta, false);
      type = listKey ? "select_multiple " + listKey : "text";
      constraint = "";
      constraintMsg = "";

    } else if (codePart.includes("__X")) {
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
          const usesComma = !rawList.includes("|");
          const isOne = usesComma || constraintPart.includes("1*1");
          type = (isOne ? "select_one " : "select_multiple ") + rawListKey;

          if (isRegionList) {
            lastRegionFieldName = xlsName;
          }
        }
      } else {
        type = "select_one yes_no";
      }
      constraint = "";
      constraintMsg = "";

    } else if (/__2[A-Z]?$/.test(codePart)) {
      // ── Réel (decimal)
      type = "decimal";

    } else if (/__1[YMWDHU]/.test(codePart)) {
      // ── Entier temporel
      type = "integer";

    } else if (codePart.includes("__Z")) {
      type = "text";
      constraint = "";
      constraintMsg = "";

    } else if (codePart.includes("__A")) {
      type = "date";
      constraint = "";
      constraintMsg = "";

    } else if (/__1(?:[^A-Za-z]|$)/.test(codePart)) {
      // ── Entier pur
      type = "integer";
    }

    const relevant = parseSkipRule(pf_skip || "", items);

    // Incrémenter le numéro de question
    questionNumber++;

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
