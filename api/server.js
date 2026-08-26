// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS·STUDIO — Serveur API Express
//  v1.0.0 · Dr Jean-Marc B. KORANDJI / SPAD-WHO
// ─────────────────────────────────────────────────────────────────────────────

require("dotenv").config();
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const Anthropic = require("@anthropic-ai/sdk");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");
const pdf = require("pdf-parse");
const mammoth = require("mammoth");

let { PHAKTS_SYSTEM_PROMPT, PHAKTS_MODEL, PHAKTS_MAX_TOKENS } = require("./grammar");
const { buildXLSForm } = require("./xlsform");

// ── Hot-reload grammar.js on file change (dev-only; asar-packaged files
// can't be watched by fs.watch, so we silently skip it in production) ──
const GRAMMAR_PATH = path.join(__dirname, "grammar.js");
try {
  fs.watch(GRAMMAR_PATH, { persistent: false }, (eventType) => {
    if (eventType === "change") {
      try {
        delete require.cache[require.resolve("./grammar")];
        const reloaded = require("./grammar");
        PHAKTS_SYSTEM_PROMPT = reloaded.PHAKTS_SYSTEM_PROMPT;
        PHAKTS_MODEL = reloaded.PHAKTS_MODEL;
        PHAKTS_MAX_TOKENS = reloaded.PHAKTS_MAX_TOKENS;
        console.log("[grammar] ✅ Grammaire rechargée automatiquement");
      } catch (err) {
        console.error("[grammar] ❌ Erreur de rechargement:", err.message);
      }
    }
  });
} catch (err) {
  // Expected when running from inside an asar bundle
  console.log("[grammar] hot-reload disabled (packaged mode)");
}

// ── Storage for learned codification examples ──
// In packaged mode the bundled directory is read-only, so the launcher
// (electron-main.js) injects PHAKTS_DATA_DIR pointing to userData.
const DATA_DIR = process.env.PHAKTS_DATA_DIR || path.join(__dirname, "../data");
const LEARNED_FILE = path.join(DATA_DIR, "learned.json");
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function loadLearned() {
  try {
    if (fs.existsSync(LEARNED_FILE)) return JSON.parse(fs.readFileSync(LEARNED_FILE, "utf8"));
  } catch (_) {}
  return [];
}

function saveLearned(arr) {
  fs.writeFileSync(LEARNED_FILE, JSON.stringify(arr, null, 2), "utf8");
}

/** Build an augmented SYSTEM prompt that includes learned examples */
function buildAugmentedPrompt() {
  const learned = loadLearned();
  if (!learned.length) return PHAKTS_SYSTEM_PROMPT;
  const lines = learned.map(r => {
    let line = '- "' + (r.libelle || '').replace(/"/g, "'") + '" → ' + (r.pf_question || '');
    if (r.pf_modalites && r.pf_modalites.trim()) line += '            ' + r.pf_modalites.trim();
    return line;
  }).join('\n');
  const marker = '\nINSTRUCTIONS:';
  const pos = PHAKTS_SYSTEM_PROMPT.indexOf(marker);
  if (pos === -1) return PHAKTS_SYSTEM_PROMPT;
  return PHAKTS_SYSTEM_PROMPT.slice(0, pos) + '\n\nEXEMPLES MÉMORISÉS (codifications validées par l\'utilisateur):\n' + lines + marker + PHAKTS_SYSTEM_PROMPT.slice(pos + marker.length);
}

// ── Helper : map une erreur Anthropic vers une réponse HTTP avec un CODE
// stable et un message clair en FR (utilisé par tous les endpoints qui
// appellent Claude).
function respondWithApiError(res, err, route = '') {
  const status = err.status;
  const msg = String(err.message || '');
  const lc = msg.toLowerCase();
  console.error(`[${route}] Anthropic err ${status}: ${msg.slice(0, 200)}`);

  // Crédit insuffisant (400 invalid_request_error avec "credit balance")
  if (lc.includes('credit balance') || lc.includes('billing') ||
      lc.includes('insufficient') || lc.includes('payment')) {
    return res.status(402).json({
      error: "Crédit Anthropic insuffisant pour générer la codification.",
      code: "low_balance",
      help_url: "https://console.anthropic.com/settings/billing",
      details: "Votre clé API n'a plus assez de crédits. Rechargez votre compte Anthropic ou utilisez une autre clé API valide.",
    });
  }

  // Clé invalide
  if (status === 401 || lc.includes('authentication') || lc.includes('invalid api key') ||
      lc.includes('invalid x-api-key') || lc.includes('not found') && lc.includes('api key')) {
    return res.status(401).json({
      error: "Clé API Anthropic invalide ou révoquée.",
      code: "invalid_key",
      help_url: "https://console.anthropic.com/settings/keys",
      details: "La clé ANTHROPIC_API_KEY de votre fichier .env est rejetée par Anthropic. Vérifiez ou régénérez la clé.",
    });
  }

  // Quota / rate limit
  if (status === 429 || lc.includes('rate limit') || lc.includes('too many requests')) {
    return res.status(429).json({
      error: "Trop de requêtes en peu de temps (rate limit Anthropic).",
      code: "rate_limit",
      details: "Attendez 30 secondes puis réessayez.",
    });
  }

  // Surcharge serveur Anthropic
  if (status === 529 || status === 503 || lc.includes('overloaded')) {
    return res.status(503).json({
      error: "Les serveurs Anthropic sont saturés.",
      code: "overloaded",
      details: "Réessayez dans quelques secondes.",
    });
  }

  // Modèle inconnu / erreur de paramètres
  if (status === 400) {
    return res.status(400).json({
      error: "Paramètres invalides envoyés à Claude : " + msg.slice(0, 200),
      code: "bad_request",
    });
  }

  return res.status(500).json({ error: "Erreur Anthropic : " + msg });
}

// ── Smart radical builder : extrait un radical PHAKTS propre depuis le libellé ──
// Stop-words FR exhaustifs + extraction des noms-clés.
const FR_STOPWORDS = new Set([
  // déterminants
  'le','la','les','l','un','une','des','du','de','d','au','aux',
  // possessifs / démonstratifs / personnels
  'votre','vos','mon','ma','mes','son','sa','ses','notre','nos','leur','leurs',
  'ce','cet','cette','ces','je','tu','il','elle','nous','vous','ils','elles','on','y',
  'me','te','se','lui','leur','moi','toi','soi','eux',
  // mots interrogatifs
  'quel','quelle','quels','quelles','comment','combien','pourquoi','quand','ou','qui','que','qu','quoi',
  // verbes courants
  'est','sont','etre','ete','etais','etait','etiez','etions','etaient','soit','soient',
  'a','as','ai','avez','avons','avoir','aurez','aurai','auront','avais','avait','avaient',
  'fait','faites','font','faire','faut','peut','peuvent','pouvez','peux','pouvoir',
  'doit','doivent','devez','devons','devoir','sait','savez','savons','savoir',
  'va','vas','vont','allez','allons','aller','viens','venez','vient','viennent','venir',
  'trouve','trouvez','trouvent','trouvons','trouver','situe','situee','situees','situes','situer',
  // prépositions
  'a','en','sur','sous','par','pour','avec','sans','rapport','vers','envers','dans','chez',
  'entre','depuis','pendant','apres','avant','contre','selon','dont','des',
  // conjonctions et marqueurs
  'et','ou','mais','donc','or','ni','car','si','que','parce','tant','aussi','meme','tres','plus','moins',
  // négations
  'ne','pas','non','plus','jamais','rien','aucun','aucune','nul','nulle',
  // misc fréquents et non discriminants
  'oui','si','peut','etre','autre','autres','divers','meme','memes',
  // mots de remplissage que PHAKTS ignore historiquement
  'lieu','cas','fois','temps','partie','type','moyen','manière','facon',
]);

function extractRadicalFromLibelle(libelle, maxWords = 4) {
  if (!libelle) return '';
  // Normalise : minuscules, accents, parenthèses, ponctuation
  let s = String(libelle).toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\[[^\]]*\]/g, ' ')
    .replace(/[?!.,;:'"\-—–«»]/g, ' ')
    .replace(/\s+/g, ' ').trim();

  // Tokenise et filtre les stop-words / mots courts
  const tokens = s.split(/\s+/).filter(t => t && t.length >= 2 && !FR_STOPWORDS.has(t));
  if (!tokens.length) return '';

  // Garde les N premiers tokens significatifs, capitalise
  const cap = w => w.charAt(0).toUpperCase() + w.slice(1);
  return tokens.slice(0, maxWords).map(cap).join('_');
}

// Détecte si un radical est jugé "douteux" (issu d'une codification LLM moisie)
// → on tentera une reconstruction depuis le libellé.
function isRadicalSuspect(radical) {
  if (!radical) return true;
  const r = radical;
  // Préfixes de déterminants français (= LLM a oublié la règle)
  if (/^(Quel(?:le)?s?|Combien|Comment|Pourquoi|Quand|Ou|Avez_Vous|Est_Ce_Que)_/i.test(r)) return true;
  // Verbes intercalés (Trouve, Se_Trouve)
  if (/(_Trouvez?_|_Se_Trouve)/i.test(r)) return true;
  return false;
}

// ── Post-processing : nettoyage des codifications PHAKTS ──
// Filet de sécurité côté serveur qui corrige les erreurs courantes du LLM.
// Si le radical produit par le LLM est suspect, on le reconstruit depuis
// le libellé original à l'aide de extractRadicalFromLibelle.
function sanitizePhaktsItem(item) {
  if (!item || !item.pf_question || typeof item.pf_question !== 'string') return item;
  let pf = item.pf_question;
  let modal = String(item.pf_modalites || '');

  const TYPE_RX = /^(.+?)(__(?:B|X|1|2|Z|A|SRC).*)$/;
  const m = pf.match(TYPE_RX);
  if (!m) return item;

  let radical = m[1];
  let rest = m[2]; // tout ce qui commence par __TYPE...
  const oldRadical = radical;

  // 1. Si le radical est suspect, RECONSTRUIRE depuis le libellé original
  if (isRadicalSuspect(radical) && item.libelle) {
    const fromLibelle = extractRadicalFromLibelle(item.libelle, 4);
    if (fromLibelle && fromLibelle.length >= 4) {
      radical = fromLibelle;
    }
  }

  // 2. Strip déterminants/verbes interrogatifs (par sécurité, même si la 1 a tourné)
  radical = radical
    .replace(/^Quel(?:le)?s?_/i, '')        // Quel, Quelle, Quels, Quelles
    .replace(/^Combien_(de_|d_)?/i, '')
    .replace(/^Pourquoi_/i, '')
    .replace(/^Comment_/i, '')
    .replace(/^Quand_/i, '')
    .replace(/^Ou_/i, '')
    .replace(/^Avez_Vous_/i, '')
    .replace(/^Est_Ce_Que_/i, '')
    .replace(/_Trouvez?_/gi, '_')
    .replace(/_Se_Trouve(_|$)/gi, '$1')
    // Retire les segments d'une seule lettre (résidus d', l', n', s', t', j', m', c')
    .split('_').filter(s => s.length >= 2 || /^\d/.test(s)).join('_')
    .replace(/^_+|_+$/g, '');

  if (!radical) radical = oldRadical;  // safety: never empty

  // 3. Détecte list_key = radical complet (ou variante) après __X!N*M
  // ex: "Quelle_Distance_Trouve__X!1*1Quelle_Distance_Trouve_"
  const listMatch = rest.match(/^(__X!\d+\*(?:\d+)?)([A-Za-z][A-Za-z0-9_]*?_)$/);
  // Ne jamais recalibrer une list_key du référentiel administratif partagé
  // (Admin_Region_Sanitaire_, Admin_District_Sanitaire_, etc. — Règle 16) :
  // ce ne sont pas des radicaux générés par le LLM mais des noms de liste
  // fixes du Dictionnaire Genesis, souvent >18 caractères par construction.
  if (listMatch && !listMatch[2].startsWith('Admin_')) {
    const oldListKey = listMatch[2].replace(/_$/, '');
    // Si la list_key est trop longue, ou égale (ou très proche) du radical →
    // la remplacer par un nom court basé sur le PREMIER segment du radical.
    if (oldListKey === oldRadical.replace(/_+$/, '') ||
        oldListKey === radical.replace(/_+$/, '') ||
        oldListKey.length > 18 ||
        /^Quelles?_|^Quels_|^Combien_/i.test(oldListKey)) {
      const segments = radical.split('_').filter(Boolean);
      const shortKey = segments[0] + '_';   // ex: Distance_Habitation → Distance_
      rest = listMatch[1] + shortKey;
      // Met à jour les modalités si elles utilisent l'ancien list_key
      const modalRx = new RegExp(
        '\\b' + oldListKey.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '_?\\s*=', 'g');
      modal = modal.replace(modalRx, shortKey + '=');
    }
  }

  const newPf = radical + rest;
  if (newPf !== pf || modal !== item.pf_modalites) {
    console.log(`[sanitize] "${pf}" → "${newPf}"`);
  }
  return { ...item, pf_question: newPf, pf_modalites: modal };
}

// ── Storage for uploaded files ──
const UPLOAD_DIR = process.env.PHAKTS_UPLOAD_DIR || path.join(__dirname, "../uploads");
if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

// Nettoyage périodique des fichiers orphelins (> 1h)
const UPLOAD_MAX_AGE_MS = 60 * 60 * 1000; // 1 heure
setInterval(() => {
  try {
    const now = Date.now();
    for (const f of fs.readdirSync(UPLOAD_DIR)) {
      const fp = path.join(UPLOAD_DIR, f);
      const stat = fs.statSync(fp);
      if (now - stat.mtimeMs > UPLOAD_MAX_AGE_MS) {
        fs.unlinkSync(fp);
        console.log('[cleanup] Fichier orphelin supprimé:', f);
      }
    }
  } catch (_) {}
}, 30 * 60 * 1000); // Toutes les 30 minutes

// ── Config ────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || "127.0.0.1";
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "http://localhost:" + PORT).split(",").map((s) => s.trim());
const API_KEY = process.env.ANTHROPIC_API_KEY;
const API_TOKEN = process.env.API_TOKEN || ""; // Bearer token pour protéger l'API
// URL publique de SPAD Analyzer, quand PHAKTS Studio et SPAD tournent sur
// des hôtes distincts (ex. déploiement web : studio.spad-analyzer... vs
// spad-analyzer... — deux sous-domaines, pas juste deux ports du même
// hôte). Sans ça, le frontend ne peut deviner l'URL de SPAD que via
// Electron IPC ou l'heuristique locale ":5050" (voir resolveSpadUrl()
// dans PHAKTS·STUDIO.html), qui ne s'applique qu'en usage bureau/local.
const SPAD_URL = process.env.SPAD_URL || "";

if (!API_KEY) {
  console.error("\n❌ ANTHROPIC_API_KEY manquante dans le fichier .env\n");
  process.exit(1);
}

const client = new Anthropic({ apiKey: API_KEY });
const app = express();

// ── Headers de sécurité ───────────────────────────────────────────────────────
app.use(helmet({
  contentSecurityPolicy: false, // désactivé car le frontend inline du JS
  crossOriginEmbedderPolicy: false,
  // Par défaut Helmet met "no-referrer", ce qui supprime aussi le Referer
  // envoyé par le frontend vers SA PROPRE API (fetch same-origin) — utilisé
  // par /api/config pour vérifier que la requête vient bien d'une page
  // chargée par ce serveur. "same-origin" envoie le Referer complet pour le
  // même origine et rien du tout vers un site tiers : aussi protecteur que
  // "no-referrer" pour la navigation externe, mais compatible avec ce contrôle.
  referrerPolicy: { policy: "same-origin" },
}));

function getAccessibleUrls(port) {
  const urls = [`http://localhost:${port}`];
  const networkInterfaces = os.networkInterfaces();

  for (const interfaces of Object.values(networkInterfaces)) {
    for (const networkInterface of interfaces || []) {
      if (networkInterface.family === "IPv4" && !networkInterface.internal) {
        urls.push(`http://${networkInterface.address}:${port}`);
      }
    }
  }

  return [...new Set(urls)];
}

const ACCESSIBLE_URLS = getAccessibleUrls(PORT);

// ── Configure Multer pour les uploads ──────────────────────────────────────────
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 50 * 1024 * 1024 }, // 50MB max
  fileFilter: (req, file, cb) => {
    // Accepte PDF, Word, Excel, images, texte
    const allowed = [
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.ms-excel",
      "image/jpeg",
      "image/png",
      "text/plain",
      "text/csv",
      "application/octet-stream" // fallback navigateurs anciens (.xlsx)
    ];
    const name = (file.originalname || '').toLowerCase();
    const extOk = /\.(xlsx|xls|xlsm)$/.test(name);
    if (allowed.includes(file.mimetype) || extOk) {
      cb(null, true);
    } else {
      cb(new Error(`Type de fichier non autorisé: ${file.mimetype}`));
    }
  },
});

// ── Middlewares ───────────────────────────────────────────────────────────────
app.use(express.json({ limit: "512kb" }));

app.use(
  cors({
    origin: ALLOWED_ORIGINS.includes("*") ? "*" : ALLOWED_ORIGINS,
    methods: ["GET", "POST", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
  })
);

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: parseInt(process.env.RATE_LIMIT_MAX || "50", 10),
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Trop de requêtes. Réessayez dans 15 minutes." },
});
app.use("/api/", limiter);

// ── Authentification par Bearer token (si configuré) ──────────────────────────
if (API_TOKEN) {
  app.use("/api/", (req, res, next) => {
    // Exempter /api/health et /api/config de l'authentification
    if (req.path === "/health" || req.path === "/config") return next();
    const auth = req.headers.authorization;
    if (!auth || auth !== `Bearer ${API_TOKEN}`) {
      return res.status(401).json({ error: "Token d'authentification manquant ou invalide." });
    }
    next();
  });
}

// ── Config endpoint (fournit le token au frontend servi localement) ──────────
// Cette route est volontairement exemptée du Bearer token ci-dessus car le
// frontend en a besoin pour s'authentifier lui-même — mais rester ouverte à
// QUICONQUE atteint le port (un simple `curl`, un autre processus local)
// viderait le jeton de toute utilité : n'importe qui pourrait se le
// procurer ici puis s'en servir partout ailleurs. On exige donc un en-tête
// Origin/Referer correspondant à l'origine RÉELLE de ce serveur (protocole
// + host + port vus par la requête elle-même) — un navigateur qui charge
// réellement PHAKTS·STUDIO l'envoie automatiquement ; un script ou process
// tiers ne l'a pas par défaut. Comparé à l'origine effective de la requête
// plutôt qu'à ALLOWED_ORIGINS (qui sert à un usage différent : autoriser
// d'AUTRES origines à appeler l'API en CORS, et peut légitimement pointer
// vers un port différent de celui réellement utilisé). Pas une preuve
// d'identité absolue, mais ça ferme l'accès « gratuit » qui rendait le
// jeton sans objet.
app.get("/api/config", (req, res) => {
  if (API_TOKEN) {
    const selfOrigin = `${req.protocol}://${req.get("host")}`;
    let requestOrigin = req.headers.origin || null;
    if (!requestOrigin && req.headers.referer) {
      try { requestOrigin = new URL(req.headers.referer).origin; } catch (_) {}
    }
    if (!requestOrigin || requestOrigin !== selfOrigin) {
      return res.status(403).json({ error: "Origine non autorisée." });
    }
  }
  res.json({ token: API_TOKEN || "", spadUrl: SPAD_URL || undefined });
});

// ── Servir le frontend HTML ───────────────────────────────────────────────────
// Disable caching for HTML files so edits are reflected immediately
app.use((req, res, next) => {
  if (req.path.endsWith('.html')) {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
  }
  next();
});
app.use(express.static(path.join(__dirname, "../public")));

app.get("/", (req, res) => {
  res.redirect("/PHAKTS\u00B7STUDIO.html");
});

// ─────────────────────────────────────────────────────────────────────────────
//  FONCTIONS D'EXTRACTION DE TEXTE
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Extrait le texte depuis un PDF
 */
async function extractTextFromPDF(filePath) {
  const dataBuffer = fs.readFileSync(filePath);
  const data = await pdf.default(dataBuffer);
  return data.text;
}

/**
 * Extrait le texte depuis un document Word (.doc ou .docx)
 */
async function extractTextFromWord(filePath) {
  const dataBuffer = fs.readFileSync(filePath);
  const result = await mammoth.extractRawText({ buffer: dataBuffer });
  return result.value;
}

/**
 * Extrait le texte depuis un fichier texte brut
 */
function extractTextFromPlainText(filePath) {
  return fs.readFileSync(filePath, 'utf8');
}

/**
 * Extrait les questions depuis un classeur Excel (.xlsx / .xls / .xlsm).
 * Stratégie : cherche en-tête « question / libellé / item / intitulé »
 * (et éventuellement « modalités / choix / réponses ») dans les 5 premières
 * lignes ; sinon utilise la 1ʳᵉ colonne.
 */
async function extractTextFromExcel(filePath) {
  const ExcelJS = require("exceljs");
  const QUESTION_HEADERS = /(question|libell|intitul|item|énonc|enonc|texte)/i;
  const MODALITY_HEADERS = /(modal|choix|r[eé]ponse|valeur|option)/i;

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const lines = [];

  workbook.eachSheet((sheet) => {
    if (!sheet || !sheet.rowCount) return;
    let questionCol = null;
    let modalityCol = null;
    let headerRow = null;

    for (let r = 1; r <= Math.min(5, sheet.rowCount); r++) {
      const row = sheet.getRow(r);
      row.eachCell((cell, col) => {
        const v = String(cell.value == null ? "" : (cell.value.text || cell.value)).trim();
        if (QUESTION_HEADERS.test(v) && questionCol == null) { questionCol = col; headerRow = r; }
        if (MODALITY_HEADERS.test(v) && modalityCol == null) { modalityCol = col; headerRow = r; }
      });
      if (questionCol) break;
    }

    const startRow = headerRow ? headerRow + 1 : 1;
    const useCol = questionCol || 1;

    for (let r = startRow; r <= sheet.rowCount; r++) {
      const row = sheet.getRow(r);
      const qCell = row.getCell(useCol);
      let q = qCell && qCell.value != null
        ? String(qCell.value.text || qCell.value).trim()
        : "";
      if (!q) continue;
      if (modalityCol) {
        const mCell = row.getCell(modalityCol);
        const mod = mCell && mCell.value != null
          ? String(mCell.value.text || mCell.value).trim()
          : "";
        if (mod) q += "   [" + mod + "]";
      }
      lines.push(q);
    }
  });

  if (!lines.length) {
    throw new Error("Aucune question lisible détectée dans le fichier Excel.");
  }
  return lines.join("\n");
}

/**
 * Extrait le texte en fonction du type MIME
 */
async function extractTextFromFile(filePath, mimeType) {
  try {
    const name = (filePath || "").toLowerCase();
    const isExcelByExt = /\.(xlsx|xls|xlsm)$/.test(name);
    const isExcelByMime = mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      || mimeType === 'application/vnd.ms-excel';

    if (mimeType === 'application/pdf') {
      return await extractTextFromPDF(filePath);
    } else if (mimeType === 'application/msword' ||
               mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
      return await extractTextFromWord(filePath);
    } else if (isExcelByMime || isExcelByExt) {
      return await extractTextFromExcel(filePath);
    } else if (mimeType === 'text/plain' || mimeType === 'text/csv') {
      return extractTextFromPlainText(filePath);
    } else if (mimeType.startsWith('image/')) {
      // Pour images: retourner un message indiquant que OCR est nécessaire
      return `[Image: ${path.basename(filePath)}] - OCR non encore implémenté`;
    } else {
      throw new Error(`Type de fichier non supporté pour extraction: ${mimeType}`);
    }
  } catch (err) {
    throw new Error(`Erreur extraction texte: ${err.message}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  ROUTES API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/health
 * Vérifie que le serveur tourne et que la clé API est configurée
 */
app.get("/api/health", (req, res) => {
  const learned = loadLearned();
  res.json({
    status: "ok",
    version: "1.0.0",
    service: "PHAKTS·STUDIO API",
    model: PHAKTS_MODEL,
    host: HOST,
    port: Number(PORT),
    accessible_urls: ACCESSIBLE_URLS,
    learned_count: learned.length,
    timestamp: new Date().toISOString(),
  });
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/learned
 * Retourne la liste des codifications mémorisées sur le serveur
 */
app.get("/api/learned", (req, res) => {
  const learned = loadLearned();
  res.json({ count: learned.length, items: learned });
});

/**
 * POST /api/learn
 * Corps: { items: [{libelle, pf_question, pf_modalites, pf_skip?}] }
 * Enregistre de nouvelles codifications validées pour enrichir la grammaire
 */
app.post("/api/learn", (req, res) => {
  const { items } = req.body;
  if (!items || !Array.isArray(items) || !items.length) {
    return res.status(400).json({ error: "Le champ 'items' doit être un tableau non vide." });
  }
  // Validate & sanitize
  const cleaned = items.map(r => ({
    libelle: String(r.libelle || '').slice(0, 500),
    pf_question: String(r.pf_question || '').slice(0, 200),
    pf_modalites: String(r.pf_modalites || '').slice(0, 1000),
    pf_skip: String(r.pf_skip || '').slice(0, 300),
    learned_at: new Date().toISOString(),
  }));

  const existing = loadLearned();
  // Deduplicate by pf_question
  const existingKeys = new Set(existing.map(e => e.pf_question));
  const newItems = cleaned.filter(c => !existingKeys.has(c.pf_question));
  if (!newItems.length) {
    return res.json({ message: "Toutes les codifications existent déjà.", count: existing.length, added: 0 });
  }
  const updated = existing.concat(newItems);
  saveLearned(updated);
  console.log(`[/api/learn] +${newItems.length} codification(s) mémorisée(s) (total: ${updated.length})`);
  return res.json({ count: updated.length, added: newItems.length, items: updated });
});

/**
 * DELETE /api/learned
 * Supprime toutes les codifications mémorisées
 */
app.delete("/api/learned", (req, res) => {
  saveLearned([]);
  console.log("[/api/learned] Toutes les codifications mémorisées supprimées");
  return res.json({ message: "Codifications mémorisées supprimées.", count: 0 });
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/upload
 * Upload un fichier (PDF, Word, images, texte) pour l'analyse
 * Corps: FormData avec clé 'file'
 * Réponse: { fileId, fileName, mimeType, size, uploadedAt }
 */
app.post("/api/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "Aucun fichier fourni." });
    }

    // ── Générer un ID unique pour le fichier
    const fileId = crypto.randomBytes(12).toString("hex");
    const ext = path.extname(req.file.originalname);
    const fileName = `${fileId}${ext}`;
    const filePath = path.join(UPLOAD_DIR, fileName);

    // ── Sauvegarder le fichier sur le disque
    fs.writeFileSync(filePath, req.file.buffer);

    return res.json({
      fileId,
      fileName: req.file.originalname,
      mimeType: req.file.mimetype,
      size: req.file.size,
      uploadedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[/api/upload] Erreur:", err.message);
    if (err.status === 401) return res.status(401).json({ error: "Clé API Anthropic invalide." });
    return res.status(500).json({ error: "Erreur upload : " + err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/extract
 * Extrait le texte d'un fichier uploadé (PDF, Word, texte, images)
 * Corps: { fileId, fileName, mimeType }
 * Réponse: { extracted_text, fileId, fileName, textLength, success }
 */
app.post("/api/extract", async (req, res) => {
  const { fileId, fileName, mimeType } = req.body;

  if (!fileId || !mimeType) {
    return res.status(400).json({ error: "Les champs 'fileId' et 'mimeType' sont requis." });
  }

  try {
    // Construire le chemin du fichier
    const ext = path.extname(fileName);
    const upFile = `${fileId}${ext}`;
    const filePath = path.join(UPLOAD_DIR, upFile);

    // Vérifier que le fichier existe
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: `Fichier non trouvé: ${fileId}` });
    }

    // Extraire le texte
    const extractedText = await extractTextFromFile(filePath, mimeType);

    // Supprimer le fichier après extraction
    try { fs.unlinkSync(filePath); } catch (_) {}

    return res.json({
      success: true,
      fileId,
      fileName,
      mimeType,
      extracted_text: extractedText,
      textLength: extractedText.length,
      extractedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error("[/api/extract] Erreur:", err.message);
    return res.status(500).json({ error: "Erreur extraction : " + err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/extract-and-codify
 * Extrait le texte d'un fichier ET le codifie en une seule requête
 * Corps: { fileId, fileName, mimeType, formTitle?: string }
 * Réponse: { items, extracted_text, fileId, fileName, usage }
 */
app.post("/api/extract-and-codify", async (req, res) => {
  const { fileId, fileName, mimeType, formTitle } = req.body;

  if (!fileId || !mimeType) {
    return res.status(400).json({ error: "Les champs 'fileId' et 'mimeType' sont requis." });
  }

  try {
    // Construire le chemin du fichier
    const ext = path.extname(fileName || "file");
    const upFile = `${fileId}${ext}`;
    const filePath = path.join(UPLOAD_DIR, upFile);

    // Vérifier que le fichier existe
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: `Fichier non trouvé: ${fileId}` });
    }

    // Extraire le texte
    const extractedText = await extractTextFromFile(filePath, mimeType);

    // Codifier avec Claude (avec retry pour 529)
    let message;
    const maxRetries = 3;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        message = await client.messages.create({
          model: PHAKTS_MODEL,
          max_tokens: PHAKTS_MAX_TOKENS,
          system: buildAugmentedPrompt(),
          messages: [
            {
              role: "user",
              content: `Extrait du fichier: ${fileName}\n\nCodifie ces questions selon la grammaire PHAKTS:\n\n${extractedText.trim()}`,
            },
          ],
        });
        break;
      } catch (retryErr) {
        if (retryErr.status === 529 && attempt < maxRetries) {
          const delay = attempt * 10000;
          console.log(`[/api/extract-and-codify] Anthropic 529 – retry ${attempt}/${maxRetries} dans ${delay / 1000}s...`);
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw retryErr;
        }
      }
    }

    // Parse JSON from Claude response
    let raw = (message.content?.find(b => b.type === 'text')?.text || "").trim();
    
    // Remove markdown code blocks if present
    raw = raw.replace(/```json\n?|\n?```/g, "").trim();

    // If truncated, try to repair by closing the JSON
    if (message.stop_reason === 'max_tokens') {
      console.warn('[/api/extract-and-codify] Réponse tronquée (max_tokens atteint). Tentative de réparation JSON...');
      const lastBrace = raw.lastIndexOf('}');
      if (lastBrace > 0) {
        let repaired = raw.substring(0, lastBrace + 1);
        if (!repaired.endsWith(']}')) {
          if (!repaired.endsWith(']')) repaired += ']';
          repaired += '}';
        }
        raw = repaired;
      }
    }
    
    // Try to extract JSON object if surrounded by text
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Try to extract JSON from within the text
      const jsonMatch = raw.match(/\{[\s\S]*"items"[\s\S]*\}/);
      if (jsonMatch) {
        try {
          parsed = JSON.parse(jsonMatch[0]);
        } catch {
          console.error("[/api/extract-and-codify] JSON extraction failed:", jsonMatch[0].substring(0, 200));
          return res.status(502).json({
            error: "Réponse Claude non parsable. Réessayez.",
            raw: raw.substring(0, 300),
          });
        }
      } else {
        console.error("[/api/extract-and-codify] No JSON found in response:", raw.substring(0, 200));
        return res.status(502).json({
          error: "Réponse Claude non parsable. Réessayez.",
          raw: raw.substring(0, 300),
        });
      }
    }

    const items = (parsed.items || []).map(sanitizePhaktsItem);
    const title = formTitle || fileName || "Questionnaire";

    // Supprimer le fichier après extraction + codification
    try { fs.unlinkSync(filePath); } catch (_) {}

    return res.json({
      success: true,
      fileId,
      fileName,
      mimeType,
      extracted_text: extractedText,
      textLength: extractedText.length,
      formTitle: title,
      count: items.length,
      items,
      usage: {
        input_tokens: message.usage?.input_tokens,
        output_tokens: message.usage?.output_tokens,
      },
      extractedAt: new Date().toISOString(),
    });
  } catch (err) {
    return respondWithApiError(res, err, '/api/extract-and-codify');
  }
});

// ─────────────────────────────────────────────────────────────────────────────
/**
 * POST /api/codify
 * Corps: { questions: string, formTitle?: string }
 * Réponse: { formTitle, count, items: [{libelle, pf_question, pf_modalites, pf_skip}] }
 */
app.post("/api/codify", async (req, res) => {
  const { questions, formTitle } = req.body;

  // ── Validation
  if (!questions || typeof questions !== "string" || !questions.trim()) {
    return res.status(400).json({ error: "Le champ 'questions' est requis et ne peut pas être vide." });
  }
  if (questions.length > 20000) {
    return res.status(400).json({ error: "Texte trop long (max 20 000 caractères)." });
  }

  try {
    // Retry logic for 529 (Anthropic overloaded)
    let message;
    const maxRetries = 3;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        message = await client.messages.create({
          model: PHAKTS_MODEL,
          max_tokens: PHAKTS_MAX_TOKENS,
          system: buildAugmentedPrompt(),
          messages: [
            {
              role: "user",
              content: `Codifie ces questions selon la grammaire PHAKTS:\n\n${questions.trim()}`,
            },
          ],
        });
        break; // success
      } catch (retryErr) {
        if (retryErr.status === 529 && attempt < maxRetries) {
          const delay = attempt * 10000; // 10s, 20s, 30s
          console.log(`[/api/codify] Anthropic 529 – retry ${attempt}/${maxRetries} dans ${delay / 1000}s...`);
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw retryErr;
        }
      }
    }

    // ── Check for truncated response
    if (message.stop_reason === 'max_tokens') {
      console.warn('[/api/codify] Réponse tronquée (max_tokens atteint). Tentative de réparation JSON...');
    }

    // ── Parse JSON from Claude response
    let raw = (message.content?.find(b => b.type === 'text')?.text || "").trim();
    
    // Remove markdown code blocks if present
    raw = raw.replace(/```json\n?|\n?```/g, "").trim();

    // If truncated, try to repair by closing the JSON
    if (message.stop_reason === 'max_tokens') {
      // Find last complete item (ends with })
      const lastBrace = raw.lastIndexOf('}');
      if (lastBrace > 0) {
        let repaired = raw.substring(0, lastBrace + 1);
        // Close the items array and root object if needed
        if (!repaired.endsWith(']}')) {
          if (!repaired.endsWith(']')) repaired += ']';
          repaired += '}';
        }
        raw = repaired;
      }
    }
    
    // Try to extract JSON object if surrounded by text
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Try to extract JSON from within the text
      const jsonMatch = raw.match(/\{[\s\S]*"items"[\s\S]*\}/);
      if (jsonMatch) {
        try {
          parsed = JSON.parse(jsonMatch[0]);
        } catch {
          console.error("[/api/codify] JSON extraction failed:", jsonMatch[0].substring(0, 200));
          return res.status(502).json({
            error: "Réponse Claude non parsable. Réessayez.",
            raw: raw.substring(0, 300),
          });
        }
      } else {
        console.error("[/api/codify] No JSON found in response:", raw.substring(0, 200));
        return res.status(502).json({
          error: "Réponse Claude non parsable. Réessayez.",
          raw: raw.substring(0, 300),
        });
      }
    }

    const items = (parsed.items || []).map(sanitizePhaktsItem);
    const title = formTitle || "Questionnaire";

    return res.json({
      formTitle: title,
      count: items.length,
      items,
      usage: {
        input_tokens: message.usage?.input_tokens,
        output_tokens: message.usage?.output_tokens,
      },
    });
  } catch (err) {
    return respondWithApiError(res, err, '/api/codify');
  }
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/agent
 * Agent IA conversationnel expert en codification PHAKTS.
 * Corps: { messages: [{role:"user"|"assistant", content:string}], autoSave?: boolean }
 * Réponse: { reply: string, items?: [...], saved?: number }
 *
 * - Si la réponse contient un bloc JSON `{"items":[...]}`, ils sont extraits.
 * - Si autoSave === true, les items extraits sont écrits dans le DPF (learned).
 */
app.post("/api/agent", async (req, res) => {
  const { messages, autoSave } = req.body;
  if (!Array.isArray(messages) || !messages.length) {
    return res.status(400).json({ error: "Le champ 'messages' doit être un tableau non vide." });
  }

  // Garde uniquement les rôles valides + limite à 20 derniers messages
  const cleaned = messages
    .filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .slice(-20)
    .map(m => ({ role: m.role, content: String(m.content).slice(0, 8000) }));

  if (!cleaned.length || cleaned[cleaned.length - 1].role !== 'user') {
    return res.status(400).json({ error: "Le dernier message doit provenir de l'utilisateur." });
  }

  // Système : grammaire PHAKTS + ton conversationnel
  const agentSystem = buildAugmentedPrompt() + `

INTERACTION CONVERSATIONNELLE (Agent IA PHAKTS) :
Tu es l'« Agent IA Expert PHAKTS » du PHAKTS · STUDIO. Tu réponds en français,
de façon concise et pédagogique.
- Quand l'utilisateur soumet UNE OU PLUSIEURS questions à codifier,
  réponds par une brève explication EN PROSE (1-3 phrases) PUIS un bloc JSON
  strict de la forme :
  \`\`\`json
  {"items":[{"libelle":"…","pf_question":"…","pf_modalites":"…","pf_skip":""}]}
  \`\`\`
- Quand l'utilisateur pose une question conceptuelle (règles de grammaire,
  bonne pratique, choix entre deux codes), réponds en prose sans bloc JSON.
- Quand l'utilisateur te corrige (« non c'est plutôt X »), reconnais et
  reformule la nouvelle codification dans un bloc JSON pour qu'elle soit
  enregistrée dans le DPF.
- Si tu n'es pas sûr, propose 2 options et demande validation.

DPF = **Dictionnaire des Propriétés Fonctionnelles** — c'est la base de
connaissance vivante où sont stockées toutes les codifications PHAKTS validées.
Tout bloc JSON \`items\` que tu produis enrichit AUTOMATIQUEMENT le DPF (visible
dans l'onglet ⊘ DPF, section « I. Codifications apprises par l'Agent IA ») si
l'utilisateur a coché « Sauvegarder automatiquement dans le DPF ». Tu peux donc
activement proposer de NOUVEAUX patrons PHAKTS (nouveaux radicaux, nouvelles
listes contrôlées) pour enrichir le DPF — explique en prose POURQUOI le nouveau
patron est utile, puis émets-le dans un bloc JSON.

RÈGLE ABSOLUE : tout bloc JSON que tu émets doit respecter strictement la
grammaire PHAKTS (\`Radical__TYPE!contrainte\`, Snake_Case, listes terminées
par \`_\`, modalités séparées par \`,\` pour select_one ou \`|\` pour
select_multiple). N'invente jamais de syntaxe hors grammaire.`;

  try {
    let message;
    const maxRetries = 3;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        message = await client.messages.create({
          model: PHAKTS_MODEL,
          max_tokens: PHAKTS_MAX_TOKENS,
          system: agentSystem,
          messages: cleaned,
        });
        break;
      } catch (retryErr) {
        if (retryErr.status === 529 && attempt < maxRetries) {
          await new Promise(r => setTimeout(r, attempt * 8000));
        } else {
          throw retryErr;
        }
      }
    }

    const reply = (message.content?.find(b => b.type === 'text')?.text || "").trim();

    // Tente d'extraire un bloc JSON `{"items":[...]}`
    let items = [];
    const fenced = reply.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
    const candidate = fenced ? fenced[1] : null;
    let parsed = null;
    if (candidate) {
      try { parsed = JSON.parse(candidate); } catch (_) {}
    }
    if (!parsed) {
      const loose = reply.match(/\{[\s\S]*?"items"[\s\S]*?\}/);
      if (loose) {
        try { parsed = JSON.parse(loose[0]); } catch (_) {}
      }
    }
    if (parsed && Array.isArray(parsed.items)) {
      items = parsed.items.map(sanitizePhaktsItem);
    }

    // Sauvegarde dans le DPF si demandé
    let saved = 0;
    if (autoSave && items.length) {
      const existing = loadLearned();
      const existingKeys = new Set(existing.map(e => e.pf_question));
      const toAdd = items
        .filter(it => it.pf_question && !existingKeys.has(it.pf_question))
        .map(it => ({
          libelle: String(it.libelle || '').slice(0, 500),
          pf_question: String(it.pf_question || '').slice(0, 200),
          pf_modalites: String(it.pf_modalites || '').slice(0, 1000),
          pf_skip: String(it.pf_skip || '').slice(0, 300),
          learned_at: new Date().toISOString(),
        }));
      if (toAdd.length) {
        saveLearned(existing.concat(toAdd));
        saved = toAdd.length;
        console.log(`[/api/agent] +${saved} codification(s) DPF (total: ${existing.length + saved})`);
      }
    }

    return res.json({
      reply,
      items,
      saved,
      usage: {
        input_tokens: message.usage?.input_tokens,
        output_tokens: message.usage?.output_tokens,
      },
    });
  } catch (err) {
    return respondWithApiError(res, err, '/api/agent');
  }
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/xlsform
 * Corps: { items: [{libelle, pf_question, pf_modalites}], formTitle?: string }
 * Réponse: { survey: [], choices: [], settings: [] }
 *
 * Convertit des items PHAKTS codifiés en structure XLSForm pour KoboToolbox.
 */
app.post("/api/xlsform", (req, res) => {
  const { items, formTitle } = req.body;

  if (!items || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: "Le champ 'items' doit être un tableau non vide." });
  }

  // Validate item structure
  for (const [i, item] of items.entries()) {
    if (!item.libelle || !item.pf_question || !item.pf_modalites) {
      return res.status(400).json({
        error: `Item #${i + 1} invalide. Champs requis: libelle, pf_question, pf_modalites.`,
      });
    }
  }

  try {
    const xlsform = buildXLSForm(items, formTitle || "Questionnaire");
    return res.json({
      formTitle: formTitle || "Questionnaire",
      sheets: { survey: xlsform.survey.length, choices: xlsform.choices.length },
      ...xlsform,
    });
  } catch (err) {
    console.error("[/api/xlsform] Erreur:", err.message);
    return res.status(500).json({ error: "Erreur construction XLSForm : " + err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/codify-and-convert
 * Corps: { questions: string, formTitle?: string }
 * Réponse: { items, survey, choices, settings }
 *
 * Combiné: codification PHAKTS + conversion XLSForm en un seul appel.
 */
app.post("/api/codify-and-convert", async (req, res) => {
  const { questions, formTitle } = req.body;

  if (!questions || typeof questions !== "string" || !questions.trim()) {
    return res.status(400).json({ error: "Le champ 'questions' est requis." });
  }
  if (questions.length > 20000) {
    return res.status(400).json({ error: "Texte trop long (max 20 000 caractères)." });
  }

  try {
    // Step 1: Codify
    const message = await client.messages.create({
      model: PHAKTS_MODEL,
      max_tokens: PHAKTS_MAX_TOKENS,
      system: buildAugmentedPrompt(),
      messages: [
        {
          role: "user",
          content: `Codifie ces questions selon la grammaire PHAKTS:\n\n${questions.trim()}`,
        },
      ],
    });

    const raw = (message.content?.find(b => b.type === 'text')?.text || "").replace(/```json|```/g, "").trim();
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return res.status(502).json({ error: "Réponse Claude non parsable.", raw: raw.substring(0, 500) });
    }

    const items = (parsed.items || []).map(sanitizePhaktsItem);
    const title = formTitle || "Questionnaire";

    // Step 2: Build XLSForm
    const xlsform = buildXLSForm(items, title);

    return res.json({
      formTitle: title,
      count: items.length,
      items,
      ...xlsform,
      usage: {
        input_tokens: message.usage?.input_tokens,
        output_tokens: message.usage?.output_tokens,
      },
    });
  } catch (err) {
    return respondWithApiError(res, err, '/api/codify-and-convert');
  }
});

// ─────────────────────────────────────────────────────────────────────────────

// ── 404 catch-all
app.use((req, res) => {
  res.status(404).json({ error: "Route introuvable." });
});

// ── Global error handler
app.use((err, req, res, _next) => {
  console.error("[Error]", err.message);
  const isProduction = process.env.NODE_ENV === "production";
  res.status(500).json({ error: isProduction ? "Erreur interne du serveur." : err.message });
});

// ── Start
app.listen(PORT, HOST, () => {
  const frontendUrls = ACCESSIBLE_URLS.map((url) => `║  🌐 Accès      →  ${url}`).join("\n");
  console.log(`
╔══════════════════════════════════════════════════╗
║          PHAKTS·STUDIO  API  v1.0.0              ║
║  Public Health Assessment & Knowledge Taxonomy   ║
╠══════════════════════════════════════════════════╣
║  🟢 Écoute     →  ${HOST}:${PORT}                         ║
${frontendUrls}
║  📡 Endpoints  →  /api/health                    ║
║                   /api/codify                    ║
║                   /api/xlsform                   ║
║                   /api/codify-and-convert        ║
║                   /api/learn                     ║
║                   /api/learned                   ║
╚══════════════════════════════════════════════════╝
`);

  // Auto-open browser (seulement si lancé en dehors d'Electron)
  if (!process.versions.electron) {
    const { exec } = require("child_process");
    exec(`open http://127.0.0.1:${PORT}`);
  }
});

module.exports = app;
