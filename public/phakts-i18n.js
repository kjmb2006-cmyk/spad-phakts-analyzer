/**
 * PHAKTS Studio — paramétrage de langue (FR/EN/ES/PT), 2026-11-03.
 *
 * Même motif que le sélecteur d'apparence déjà présent dans PHAKTS·STUDIO.html
 * (localStorage + attribut sur <html>, voir setTheme()/VALID_THEMES) : rien de
 * server-side, un fichier chargé en <script src> comme phakts-core.js et
 * phakts-audit.js.
 *
 * Portée de ce premier passage (demande de l'utilisateur, « infrastructure +
 * écrans clés ») : l'en-tête/barre d'onglets (partagés par tous les onglets) +
 * les onglets Codification et Correction DPF intégralement. Le reste de l'app
 * (Uploads, Résultats, Fichier XLSForm, Questionnaire Codifié, Agent IA,
 * Dictionnaire) reste en français — data-i18n n'y est pas posé, donc rien ne
 * change pour ces écrans tant qu'on n'y revient pas.
 *
 * Le français n'a PAS d'entrée dans DICT ci-dessous : le HTML est déjà écrit
 * en français, c'est la langue de repli naturelle. applyTranslations() capture
 * automatiquement le texte français d'origine de chaque élément [data-i18n] la
 * première fois qu'il le voit (attribut data-i18n-fr), pour pouvoir revenir en
 * français après un aller vers une autre langue sans dupliquer ce texte ici.
 *
 * public/phakts-audit.js (moteur d'audit « Correction DPF ») : ses jetons
 * internes SEV/CAT/SRC (ex. « Critique », « Faute de frappe ») restent
 * EXACTEMENT tels quels dans le moteur — ils servent de clé de comparaison/tri/
 * couleur partout dans ce fichier (CORR_SEV_COLOR[fi.severity], filtres, etc.).
 * AUDIT_LABELS ci-dessous ne fournit qu'un texte d'AFFICHAGE parallèle, jamais
 * substitué à la valeur réelle de fi.severity/fi.category/fi.source — voir
 * labelFor(). Les ~160 textes fi.message/fi.action du moteur (constats
 * individuels, souvent construits par concaténation avec le code/mot signalé)
 * ne sont PAS traduits dans ce passage : trop imbriqués dans la logique des
 * règles pour le faire sûrement ici — restent en français dans les 4 langues,
 * décision assumée et documentée (voir le rapport remis à l'utilisateur).
 */
(function (root) {
  'use strict';

  var LANGS = ['fr', 'en', 'es', 'pt'];

  var DICT = {
    en: {
      tab_codification: 'Codification',
      tab_uploads: 'Uploads',
      tab_resultats: 'Results',
      tab_xlsform: 'XLSForm File',
      tab_qcodif: 'Coded Questionnaire',
      tab_correction: 'DPF Correction',
      tab_agent: 'PHAKTS AI Agent',
      tab_grammar: 'Functional Properties Dictionary',

      pill_entier: 'Integer',
      pill_texte: 'Text',
      pill_date: 'Date',
      pill_photo: 'Photo',
      pill_skip: 'Skip',
      input_label: 'Paste your questions',
      input_label_sub: '(one per line or numbered)',
      input_placeholder: "Does the facility have a standardized system for routine data collection?\nStaff motivation level to produce complete and accurate data\nHave staff received adequate training on the HIS?\nWhen was the register last updated?\nWhat is the patient's age?\n...",
      ref_model_label: 'Reference model',
      ref_model_short: 'Reference model (short)',
      ref_model_full: 'Full reference model (Q1-Q56)',
      ref_model_annotated: 'Annotated reference model (Kobo skips)',
      ref_model_load: 'Load model',
      ref_model_export: 'Code and export both files',
      ref_model_help: 'The annotated model adds `ref` and `si` tags to automatically demonstrate question skips in Kobo.',
      btn_codify: 'CODE WITH PHAKTS',
      btn_clear: 'Clear',
      btn_view_results: 'View results →',

      char_count_one: '%{n} question detected',
      char_count_other: '%{n} questions detected',
      err_no_question: 'Please enter at least one question.',
      api_err_low_balance_main: 'Insufficient AI service credit to generate the coding.',
      api_err_low_balance_details: "Your API key doesn't have enough credit left. Top up your account or use another valid API key.",
      api_err_invalid_key_main: 'Invalid or revoked AI service API key.',
      api_err_invalid_key_details: 'The API key in your .env file was rejected. Check or regenerate the key.',
      api_err_rate_limit_main: 'Too many requests in a short time (rate limit).',
      api_err_rate_limit_details: 'Wait 30 seconds then try again.',
      api_err_overloaded_main: 'The AI service servers are overloaded.',
      api_err_overloaded_details: 'Try again in a few seconds.',
      api_err_open_browser: 'Open in browser →',
      reason_low_balance: ' — insufficient AI credit',
      reason_invalid_key: ' — invalid API key',
      reason_rate_limit: ' — rate limit reached',
      reason_overloaded: ' — AI servers saturated',
      status_offline_fallback: '⚠ Offline coding (local reference model)',
      status_see_detail_above: '. See detail above.',

      corr_intro: 'Upload a coded questionnaire or an XLSForm: every code is checked against the PHAKTS grammar and the DPF, deviations are listed, and sound corrections are proposed',
      corr_dropzone_title: 'Drag and drop the questionnaire to check',
      corr_dropzone_help: 'KoboToolbox XLSForm (survey / choices sheets), coded questionnaire (Label · PF/Question · PF/Modalities · Skip Logic), list of labels to code (one "Label" or "Question" column, with or without "Modalities"), or data file (Kobo export: names or labels on the first row) — .xlsx',
      corr_view_findings: 'Deviations',
      corr_view_corrected: 'Corrected questionnaire',
      corr_f_pending: 'To validate',
      corr_f_applied: 'Corrected',
      corr_f_all: 'All deviations',
      corr_f_all_sev: 'All severities',
      corr_f_all_cat: 'All categories',
      sev_Critique: 'Critical',
      sev_Majeure: 'Major',
      sev_Mineure: 'Minor',
      corr_search_ph: 'Search (label, code, rule)…',
      corr_btn_codify_title: "Proposes then applies a PHAKTS code (and its modalities) to each label that doesn't have one — offline coder, free and instant; review the \"Corrected questionnaire\" tab afterwards",
      corr_btn_codify: 'Code (offline) the labels without a code',
      corr_btn_codify_ai_title: "Same thing with the PHAKTS AI (/api/codify, the same model as the Codification tab): recognizes \"Why / If yes, which…\", DPF lists and explicit skips better — uses the server, paid call",
      corr_btn_codify_ai: 'Code with PHAKTS AI',
      corr_btn_accept_title: 'Applies all displayed proposals (those not yet applied)',
      corr_btn_accept: 'Accept displayed proposals',
      corr_btn_reset_title: 'Reverts to the safe corrections applied by default',
      corr_btn_reset: 'Reset',
      corr_btn_download: 'Download the corrected file',
      corr_btn_report: 'Compliance report (XLSX)',
      corr_btn_results_title: 'Loads the corrected questionnaire into the Results tab to generate the XLSForm',
      corr_btn_results: 'Load into Results',
      corr_btn_codify_n_one: '✨ Code (offline) the %{n} label without a code',
      corr_btn_codify_n_other: '✨ Code (offline) the %{n} labels without a code',
      corr_ai_unavailable: 'API server unreachable (see "API SERVER" at the top of the page) — AI coding is unavailable offline.',
      corr_btn_codify_ai_n_one: '🤖 Code with PHAKTS AI (%{n} label)',
      corr_btn_codify_ai_n_other: '🤖 Code with PHAKTS AI (%{n} labels)',
    },
    es: {
      tab_codification: 'Codificación',
      tab_uploads: 'Cargas',
      tab_resultats: 'Resultados',
      tab_xlsform: 'Archivo XLSForm',
      tab_qcodif: 'Cuestionario Codificado',
      tab_correction: 'Corrección DPF',
      tab_agent: 'Agente IA PHAKTS',
      tab_grammar: 'Diccionario de Propiedades Funcionales',

      pill_entier: 'Entero',
      pill_texte: 'Texto',
      pill_date: 'Fecha',
      pill_photo: 'Foto',
      pill_skip: 'Salto',
      input_label: 'Pegue sus preguntas',
      input_label_sub: '(una por línea o numeradas)',
      input_placeholder: '¿El establecimiento cuenta con un sistema estandarizado de recolección de datos de rutina?\nNivel de motivación del personal para producir datos completos y exactos\n¿El personal ha recibido una formación adecuada sobre el SIS?\n¿Cuál es la fecha de la última actualización del registro?\n¿Cuál es la edad del paciente?\n...',
      ref_model_label: 'Modelo de referencia',
      ref_model_short: 'Modelo de referencia (corto)',
      ref_model_full: 'Modelo de referencia completo (Q1-Q56)',
      ref_model_annotated: 'Modelo de referencia anotado (saltos Kobo)',
      ref_model_load: 'Cargar el modelo',
      ref_model_export: 'Codificar y exportar los 2 archivos',
      ref_model_help: 'El modelo anotado agrega etiquetas `ref` y `si` para demostrar automáticamente los saltos de preguntas en Kobo.',
      btn_codify: 'CODIFICAR CON PHAKTS',
      btn_clear: 'Borrar',
      btn_view_results: 'Ver resultados →',

      char_count_one: '%{n} pregunta detectada',
      char_count_other: '%{n} preguntas detectadas',
      err_no_question: 'Por favor ingrese al menos una pregunta.',
      api_err_low_balance_main: 'Crédito insuficiente del servicio de IA para generar la codificación.',
      api_err_low_balance_details: 'Su clave API ya no tiene suficiente crédito. Recargue su cuenta o use otra clave API válida.',
      api_err_invalid_key_main: 'Clave API del servicio de IA inválida o revocada.',
      api_err_invalid_key_details: 'La clave API de su archivo .env fue rechazada. Verifique o regenere la clave.',
      api_err_rate_limit_main: 'Demasiadas solicitudes en poco tiempo (límite de frecuencia).',
      api_err_rate_limit_details: 'Espere 30 segundos y vuelva a intentarlo.',
      api_err_overloaded_main: 'Los servidores del servicio de IA están saturados.',
      api_err_overloaded_details: 'Vuelva a intentarlo en unos segundos.',
      api_err_open_browser: 'Abrir en el navegador →',
      reason_low_balance: ' — crédito de IA insuficiente',
      reason_invalid_key: ' — clave API inválida',
      reason_rate_limit: ' — límite de frecuencia alcanzado',
      reason_overloaded: ' — servidores de IA saturados',
      status_offline_fallback: '⚠ Codificación sin conexión (modelo de referencia local)',
      status_see_detail_above: '. Vea el detalle arriba.',

      corr_intro: 'Suba un cuestionario codificado o un XLSForm: cada código se verifica contra la gramática PHAKTS y el DPF, se enumeran las desviaciones y se proponen las correcciones adecuadas',
      corr_dropzone_title: 'Arrastre y suelte el cuestionario a verificar',
      corr_dropzone_help: 'XLSForm KoboToolbox (hojas survey / choices), cuestionario codificado (Etiqueta · PF/Pregunta · PF/Modalidades · Skip Logic), lista de etiquetas a codificar (una columna "Etiqueta" o "Pregunta", con o sin "Modalidades"), o archivo de datos (exportación Kobo: nombres o etiquetas en la primera fila) — .xlsx',
      corr_view_findings: 'Desviaciones',
      corr_view_corrected: 'Cuestionario corregido',
      corr_f_pending: 'Por validar',
      corr_f_applied: 'Corregidos',
      corr_f_all: 'Todas las desviaciones',
      corr_f_all_sev: 'Todas las severidades',
      corr_f_all_cat: 'Todas las categorías',
      sev_Critique: 'Crítica',
      sev_Majeure: 'Mayor',
      sev_Mineure: 'Menor',
      corr_search_ph: 'Buscar (etiqueta, código, regla)…',
      corr_btn_codify_title: 'Propone y luego aplica un código PHAKTS (y sus modalidades) a cada etiqueta que no tenga uno — codificador sin conexión, gratuito e instantáneo; revise después la pestaña "Cuestionario corregido"',
      corr_btn_codify: 'Codificar (sin conexión) las etiquetas sin código',
      corr_btn_codify_ai_title: 'Lo mismo con la IA PHAKTS (/api/codify, el mismo modelo que la pestaña Codificación): reconoce mejor "Por qué / Si es así, cuál…", las listas del DPF y los saltos explícitos — usa el servidor, llamada de pago',
      corr_btn_codify_ai: 'Codificar con la IA PHAKTS',
      corr_btn_accept_title: 'Aplica todas las propuestas mostradas (las que aún no se han aplicado)',
      corr_btn_accept: 'Aceptar las propuestas mostradas',
      corr_btn_reset_title: 'Vuelve a las correcciones seguras aplicadas por defecto',
      corr_btn_reset: 'Reiniciar',
      corr_btn_download: 'Descargar el archivo corregido',
      corr_btn_report: 'Informe de conformidad (XLSX)',
      corr_btn_results_title: 'Carga el cuestionario corregido en la pestaña Resultados para generar el XLSForm',
      corr_btn_results: 'Cargar en Resultados',
      corr_btn_codify_n_one: '✨ Codificar (sin conexión) la %{n} etiqueta sin código',
      corr_btn_codify_n_other: '✨ Codificar (sin conexión) las %{n} etiquetas sin código',
      corr_ai_unavailable: 'Servidor API inaccesible (vea "SERVIDOR API" en la parte superior de la página) — la codificación por IA no está disponible sin conexión.',
      corr_btn_codify_ai_n_one: '🤖 Codificar con la IA PHAKTS (%{n} etiqueta)',
      corr_btn_codify_ai_n_other: '🤖 Codificar con la IA PHAKTS (%{n} etiquetas)',
    },
    pt: {
      tab_codification: 'Codificação',
      tab_uploads: 'Envios',
      tab_resultats: 'Resultados',
      tab_xlsform: 'Arquivo XLSForm',
      tab_qcodif: 'Questionário Codificado',
      tab_correction: 'Correção DPF',
      tab_agent: 'Agente IA PHAKTS',
      tab_grammar: 'Dicionário de Propriedades Funcionais',

      pill_entier: 'Inteiro',
      pill_texte: 'Texto',
      pill_date: 'Data',
      pill_photo: 'Foto',
      pill_skip: 'Pular',
      input_label: 'Cole suas perguntas',
      input_label_sub: '(uma por linha ou numeradas)',
      input_placeholder: 'O estabelecimento possui um sistema padronizado de coleta de dados de rotina?\nNível de motivação da equipe para produzir dados completos e precisos\nA equipe recebeu treinamento adequado sobre o SIS?\nQual é a data da última atualização do registro?\nQual é a idade do paciente?\n...',
      ref_model_label: 'Modelo de referência',
      ref_model_short: 'Modelo de referência (curto)',
      ref_model_full: 'Modelo de referência completo (Q1-Q56)',
      ref_model_annotated: 'Modelo de referência anotado (pulos Kobo)',
      ref_model_load: 'Carregar o modelo',
      ref_model_export: 'Codificar e exportar os 2 arquivos',
      ref_model_help: 'O modelo anotado adiciona tags `ref` e `si` para demonstrar automaticamente os pulos de perguntas no Kobo.',
      btn_codify: 'CODIFICAR COM PHAKTS',
      btn_clear: 'Limpar',
      btn_view_results: 'Ver resultados →',

      char_count_one: '%{n} pergunta detectada',
      char_count_other: '%{n} perguntas detectadas',
      err_no_question: 'Digite pelo menos uma pergunta.',
      api_err_low_balance_main: 'Crédito insuficiente do serviço de IA para gerar a codificação.',
      api_err_low_balance_details: 'Sua chave API não tem mais crédito suficiente. Recarregue sua conta ou use outra chave API válida.',
      api_err_invalid_key_main: 'Chave API do serviço de IA inválida ou revogada.',
      api_err_invalid_key_details: 'A chave API do seu arquivo .env foi rejeitada. Verifique ou gere novamente a chave.',
      api_err_rate_limit_main: 'Muitas solicitações em pouco tempo (limite de taxa).',
      api_err_rate_limit_details: 'Aguarde 30 segundos e tente novamente.',
      api_err_overloaded_main: 'Os servidores do serviço de IA estão sobrecarregados.',
      api_err_overloaded_details: 'Tente novamente em alguns segundos.',
      api_err_open_browser: 'Abrir no navegador →',
      reason_low_balance: ' — crédito de IA insuficiente',
      reason_invalid_key: ' — chave API inválida',
      reason_rate_limit: ' — limite de taxa atingido',
      reason_overloaded: ' — servidores de IA saturados',
      status_offline_fallback: '⚠ Codificação offline (modelo de referência local)',
      status_see_detail_above: '. Veja o detalhe acima.',

      corr_intro: 'Envie um questionário codificado ou um XLSForm: cada código é verificado em relação à gramática PHAKTS e ao DPF, os desvios são listados e as correções corretas são propostas',
      corr_dropzone_title: 'Arraste e solte o questionário a verificar',
      corr_dropzone_help: 'XLSForm KoboToolbox (planilhas survey / choices), questionário codificado (Rótulo · PF/Pergunta · PF/Modalidades · Skip Logic), lista de rótulos a codificar (uma coluna "Rótulo" ou "Pergunta", com ou sem "Modalidades"), ou arquivo de dados (exportação Kobo: nomes ou rótulos na primeira linha) — .xlsx',
      corr_view_findings: 'Desvios',
      corr_view_corrected: 'Questionário corrigido',
      corr_f_pending: 'A validar',
      corr_f_applied: 'Corrigidos',
      corr_f_all: 'Todos os desvios',
      corr_f_all_sev: 'Todas as severidades',
      corr_f_all_cat: 'Todas as categorias',
      sev_Critique: 'Crítica',
      sev_Majeure: 'Maior',
      sev_Mineure: 'Menor',
      corr_search_ph: 'Pesquisar (rótulo, código, regra)…',
      corr_btn_codify_title: 'Propõe e depois aplica um código PHAKTS (e suas modalidades) a cada rótulo que não tenha um — codificador offline, gratuito e instantâneo; revise depois a aba "Questionário corrigido"',
      corr_btn_codify: 'Codificar (offline) os rótulos sem código',
      corr_btn_codify_ai_title: 'O mesmo com a IA PHAKTS (/api/codify, o mesmo modelo da aba Codificação): reconhece melhor "Por quê / Se sim, qual…", as listas do DPF e os pulos explícitos — usa o servidor, chamada paga',
      corr_btn_codify_ai: 'Codificar com a IA PHAKTS',
      corr_btn_accept_title: 'Aplica todas as propostas exibidas (as ainda não aplicadas)',
      corr_btn_accept: 'Aceitar as propostas exibidas',
      corr_btn_reset_title: 'Volta às correções seguras aplicadas por padrão',
      corr_btn_reset: 'Redefinir',
      corr_btn_download: 'Baixar o arquivo corrigido',
      corr_btn_report: 'Relatório de conformidade (XLSX)',
      corr_btn_results_title: 'Carrega o questionário corrigido na aba Resultados para gerar o XLSForm',
      corr_btn_results: 'Carregar em Resultados',
      corr_btn_codify_n_one: '✨ Codificar (offline) o %{n} rótulo sem código',
      corr_btn_codify_n_other: '✨ Codificar (offline) os %{n} rótulos sem código',
      corr_ai_unavailable: 'Servidor API inacessível (veja "SERVIDOR API" no topo da página) — a codificação por IA não está disponível offline.',
      corr_btn_codify_ai_n_one: '🤖 Codificar com a IA PHAKTS (%{n} rótulo)',
      corr_btn_codify_ai_n_other: '🤖 Codificar com a IA PHAKTS (%{n} rótulos)',
    },
  };

  // Jetons internes du moteur d'audit (public/phakts-audit.js, SEV/CAT/SRC) → texte
  // d'affichage uniquement. JAMAIS substitués à fi.severity/fi.category/fi.source eux-
  // mêmes (comparaisons, couleurs, tri, filtres — tout ça reste sur le jeton français).
  var AUDIT_LABELS = {
    severity: {
      en: { 'Critique': 'Critical', 'Majeure': 'Major', 'Mineure': 'Minor' },
      es: { 'Critique': 'Crítica', 'Majeure': 'Mayor', 'Mineure': 'Menor' },
      pt: { 'Critique': 'Crítica', 'Majeure': 'Maior', 'Mineure': 'Menor' },
    },
    category: {
      en: {
        'Faute de frappe': 'Typo', 'Type variable': 'Variable type', 'Modalités': 'Modalities',
        'Sémantique': 'Semantics', 'Skip Logic': 'Skip Logic', 'Nommage': 'Naming',
        'Liste DPF': 'DPF List', 'Registre DPF': 'DPF Registry', 'Doublon': 'Duplicate',
      },
      es: {
        'Faute de frappe': 'Error tipográfico', 'Type variable': 'Tipo de variable', 'Modalités': 'Modalidades',
        'Sémantique': 'Semántica', 'Skip Logic': 'Skip Logic', 'Nommage': 'Nomenclatura',
        'Liste DPF': 'Lista DPF', 'Registre DPF': 'Registro DPF', 'Doublon': 'Duplicado',
      },
      pt: {
        'Faute de frappe': 'Erro de digitação', 'Type variable': 'Tipo de variável', 'Modalités': 'Modalidades',
        'Sémantique': 'Semântica', 'Skip Logic': 'Skip Logic', 'Nommage': 'Nomenclatura',
        'Liste DPF': 'Lista DPF', 'Registre DPF': 'Registro DPF', 'Doublon': 'Duplicado',
      },
    },
    source: {
      en: {
        'Grammaire PHAKTS': 'PHAKTS Grammar',
        'DPF — listes standard': 'DPF — standard lists',
        'DPF-2 — variables normalisées': 'DPF-2 — normalized variables',
        "DPF — ToDo (décision en attente)": 'DPF — ToDo (decision pending)',
        "Décision SPAD du 02/11/2026 : la règle de la grammaire s'applique": 'SPAD decision of 2026-11-02: the grammar rule applies',
        'Grammaire PHAKTS — Règle 16 (référentiels Admin_)': 'PHAKTS Grammar — Rule 16 (Admin_ reference lists)',
        'Grammaire PHAKTS — Règle 17 (Skip Logic)': 'PHAKTS Grammar — Rule 17 (Skip Logic)',
      },
      es: {
        'Grammaire PHAKTS': 'Gramática PHAKTS',
        'DPF — listes standard': 'DPF — listas estándar',
        'DPF-2 — variables normalisées': 'DPF-2 — variables normalizadas',
        "DPF — ToDo (décision en attente)": 'DPF — Pendiente (decisión en espera)',
        "Décision SPAD du 02/11/2026 : la règle de la grammaire s'applique": 'Decisión SPAD del 02/11/2026: se aplica la regla de la gramática',
        'Grammaire PHAKTS — Règle 16 (référentiels Admin_)': 'Gramática PHAKTS — Regla 16 (listas de referencia Admin_)',
        'Grammaire PHAKTS — Règle 17 (Skip Logic)': 'Gramática PHAKTS — Regla 17 (Skip Logic)',
      },
      pt: {
        'Grammaire PHAKTS': 'Gramática PHAKTS',
        'DPF — listes standard': 'DPF — listas padrão',
        'DPF-2 — variables normalisées': 'DPF-2 — variáveis normalizadas',
        "DPF — ToDo (décision en attente)": 'DPF — Pendente (decisão em espera)',
        "Décision SPAD du 02/11/2026 : la règle de la grammaire s'applique": 'Decisão SPAD de 02/11/2026: a regra da gramática se aplica',
        'Grammaire PHAKTS — Règle 16 (référentiels Admin_)': 'Gramática PHAKTS — Regra 16 (listas de referência Admin_)',
        'Grammaire PHAKTS — Règle 17 (Skip Logic)': 'Gramática PHAKTS — Regra 17 (Skip Logic)',
      },
    },
  };

  function currentLang() {
    var l = document.documentElement.getAttribute('lang');
    return LANGS.indexOf(l) >= 0 ? l : 'fr';
  }

  function setLang(code) {
    if (LANGS.indexOf(code) < 0) code = 'fr';
    document.documentElement.setAttribute('lang', code);
    try { localStorage.setItem('phakts_lang', code); } catch (_) {}
    document.querySelectorAll('.lang-switcher button').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-lang-set') === code);
    });
    applyTranslations();
  }

  // t(key, params, fallback) : langue choisie → fallback fourni par l'appelant (déjà en
  // français à chaque site d'appel dans PHAKTS·STUDIO.html) → la clé elle-même en dernier
  // recours. Jamais de texte vide ni d'erreur, même pour une clé ou une langue absente.
  function t(key, params, fallback) {
    var lang = currentLang();
    var s = (DICT[lang] && DICT[lang][key]);
    if (s == null) s = (fallback != null ? fallback : key);
    if (params) {
      for (var k in params) {
        if (Object.prototype.hasOwnProperty.call(params, k)) {
          s = s.split('%{' + k + '}').join(params[k]);
        }
      }
    }
    return s;
  }

  // lookup(key) : UNIQUEMENT la langue choisie, aucun repli — undefined si rien. Sert à
  // distinguer « pas encore traduit pour ce code » de « traduit, même vide » (voir
  // showApiError() : repli sur le vrai texte français du serveur si lookup() ne trouve rien).
  function lookup(key) {
    var lang = currentLang();
    return DICT[lang] && DICT[lang][key];
  }

  function labelFor(kind, frValue) {
    var lang = currentLang();
    if (lang === 'fr') return frValue;
    var table = AUDIT_LABELS[kind];
    return (table && table[lang] && table[lang][frValue]) || frValue;
  }

  function applyTranslations() {
    var lang = currentLang();
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      if (!el.hasAttribute('data-i18n-fr')) el.setAttribute('data-i18n-fr', el.textContent);
      var key = el.getAttribute('data-i18n');
      var val = lang !== 'fr' && DICT[lang] && DICT[lang][key];
      el.textContent = val || el.getAttribute('data-i18n-fr');
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      if (!el.hasAttribute('data-i18n-fr-ph')) el.setAttribute('data-i18n-fr-ph', el.placeholder);
      var key = el.getAttribute('data-i18n-placeholder');
      var val = lang !== 'fr' && DICT[lang] && DICT[lang][key];
      el.placeholder = val || el.getAttribute('data-i18n-fr-ph');
    });
    document.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      if (!el.hasAttribute('data-i18n-fr-title')) el.setAttribute('data-i18n-fr-title', el.getAttribute('title') || '');
      var key = el.getAttribute('data-i18n-title');
      var val = lang !== 'fr' && DICT[lang] && DICT[lang][key];
      el.setAttribute('title', val || el.getAttribute('data-i18n-fr-title'));
    });
  }

  function initLang() {
    var saved = null;
    try { saved = localStorage.getItem('phakts_lang'); } catch (_) {}
    if (!saved || LANGS.indexOf(saved) < 0) saved = 'fr';
    document.documentElement.setAttribute('lang', saved);
    document.querySelectorAll('.lang-switcher button').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-lang-set') === saved);
    });
    applyTranslations();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLang);
  } else {
    initLang();
  }

  root.PHAKTS_I18N = { t: t, lookup: lookup, labelFor: labelFor, setLang: setLang, currentLang: currentLang, applyTranslations: applyTranslations };
})(window);
