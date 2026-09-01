#!/usr/bin/env node
//
// Importe un fichier Admin_SPAD.xlsx (ou compatible) directement dans
// data/admin_referentiel.json — même logique de correspondance de colonnes
// que le parseur client (_adminRefColumnMap dans PHAKTS·STUDIO.html), pour
// seeder ou mettre à jour le Référentiel Administratif sans passer par le
// navigateur.
//
// Usage : node scripts/seed-admin-referentiel.js /chemin/vers/Admin_SPAD.xlsx
//
const fs = require("fs");
const path = require("path");
const ExcelJS = require("exceljs");

const filePath = process.argv[2];
if (!filePath) {
  console.error("Usage: node scripts/seed-admin-referentiel.js /chemin/vers/Admin_SPAD.xlsx");
  process.exit(1);
}
if (!fs.existsSync(filePath)) {
  console.error(`Fichier introuvable : ${filePath}`);
  process.exit(1);
}

function colIdx(headers, keywords) {
  const h = headers.map((s) => String(s || "").toLowerCase().trim());
  for (const kw of keywords) {
    const idx = h.findIndex((x) => x === kw);
    if (idx !== -1) return idx;
  }
  for (const kw of keywords) {
    const idx = h.findIndex((x) => x.includes(kw));
    if (idx !== -1) return idx;
  }
  return -1;
}

function columnMap(headers) {
  return {
    list_name: colIdx(headers, ["list_name", "liste", "categorie"]),
    name: colIdx(headers, ["name", "nom"]),
    label: colIdx(headers, ["label", "libell"]),
    code_id: colIdx(headers, ["code_id", "code"]),
    region_code: colIdx(headers, ["region_code", "region"]),
    district_code: colIdx(headers, ["district_code", "district"]),
    enqueteur_code: colIdx(headers, ["enqueteur_code", "enqueteur"]),
  };
}

async function main() {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const ws = workbook.worksheets[0];
  if (!ws) {
    console.error("Aucune feuille trouvée dans le fichier.");
    process.exit(1);
  }

  const headers = [];
  ws.getRow(1).eachCell({ includeEmpty: true }, (cell, colNum) => {
    headers[colNum - 1] = String(cell.value || "");
  });
  const cols = columnMap(headers);

  const rows = [];
  ws.eachRow({ includeEmpty: false }, (row, rowNum) => {
    if (rowNum === 1) return;
    const get = (idx) => (idx !== -1 ? String(row.getCell(idx + 1).value || "").trim() : "");
    const name = get(cols.name);
    if (!name) return;
    rows.push({
      list_name: get(cols.list_name),
      name,
      label: get(cols.label),
      code_id: get(cols.code_id),
      region_code: get(cols.region_code),
      district_code: get(cols.district_code),
      enqueteur_code: get(cols.enqueteur_code),
    });
  });

  const DATA_DIR = process.env.PHAKTS_DATA_DIR || path.join(__dirname, "../data");
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  const outFile = path.join(DATA_DIR, "admin_referentiel.json");
  fs.writeFileSync(outFile, JSON.stringify(rows, null, 2), "utf8");

  const byList = {};
  rows.forEach((r) => { byList[r.list_name] = (byList[r.list_name] || 0) + 1; });
  console.log(`✅ ${rows.length} lignes écrites dans ${outFile}`);
  Object.entries(byList).forEach(([k, v]) => console.log(`   ${k || "(sans catégorie)"} : ${v}`));
}

main().catch((e) => {
  console.error("Erreur:", e.message);
  process.exit(1);
});
