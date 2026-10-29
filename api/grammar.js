// ─────────────────────────────────────────────────────────────────────────────
//  PHAKTS Grammar — System Prompt & Constants
//  La grammaire elle-même vit dans public/phakts-core.js, partagé avec le
//  moteur hors-ligne de PHAKTS·STUDIO.html : ne pas la recopier ici.
// ─────────────────────────────────────────────────────────────────────────────

const { SYSTEM_PROMPT, GRAMMAR_VERSION } = require("../public/phakts-core.js");

const PHAKTS_SYSTEM_PROMPT = SYSTEM_PROMPT;
const PHAKTS_MODEL = process.env.PHAKTS_MODEL || "claude-sonnet-5";
const PHAKTS_MAX_TOKENS = 16384;

module.exports = { PHAKTS_SYSTEM_PROMPT, PHAKTS_MODEL, PHAKTS_MAX_TOKENS, GRAMMAR_VERSION };
