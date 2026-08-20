"""
SPAD Analyzer — Assistant d'Analyse IA (SPAD AI Copilot)

Fournit une assistance d'analyse statistique et épidémiologique de pointe
en utilisant les modèles de langage Claude (Anthropic), avec support de
fournisseurs alternatifs (OpenAI, Gemini).
"""
import os
import json
import traceback
import pandas as pd
import numpy as np

DEFAULT_MODEL = os.environ.get("PHAKTS_MODEL", "claude-3-7-sonnet-20250219")


def get_api_key(session_key=None):
    """Récupère la clé API depuis la session utilisateur ou les variables d'environnement."""
    if session_key and str(session_key).strip():
        return str(session_key).strip()
    return (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY") or "").strip()


def is_available(session_key=None):
    """Vérifie si une clé API est configurée."""
    key = get_api_key(session_key)
    return bool(key)


def build_data_context(df: pd.DataFrame = None, completude_data: dict = None, max_vars: int = 50) -> str:
    """Construit un résumé contextuel statistique riche du jeu de données pour l'IA."""
    context_parts = []
    
    if df is not None and not df.empty:
        n_obs, n_vars = df.shape
        context_parts.append(f"=== JEU DE DONNÉES ACTIF ({n_obs} observations, {n_vars} variables) ===")
        
        missing_counts = df.isnull().sum()
        var_summaries = []
        
        for col in df.columns[:max_vars]:
            col_data = df[col]
            n_miss = missing_counts[col]
            pct_miss = round((n_miss / n_obs) * 100, 1) if n_obs > 0 else 0
            
            if pd.api.types.is_numeric_dtype(col_data):
                valid_num = col_data.dropna()
                if len(valid_num) > 0:
                    mean_val = round(valid_num.mean(), 2)
                    med_val = round(valid_num.median(), 2)
                    std_val = round(valid_num.std(), 2) if len(valid_num) > 1 else 0
                    min_val = round(valid_num.min(), 2)
                    max_val = round(valid_num.max(), 2)
                    var_summaries.append(
                        f"- [Numérique] {col} (manquants: {pct_miss}%): moyenne={mean_val}, médiane={med_val}, écart-type={std_val}, min={min_val}, max={max_val}"
                    )
                else:
                    var_summaries.append(f"- [Numérique] {col}: 100% valeurs manquantes")
            else:
                val_counts = col_data.value_counts(dropna=True).head(5)
                top_cats = ", ".join([f"{k} ({v})" for k, v in val_counts.items()])
                n_unique = col_data.nunique(dropna=True)
                var_summaries.append(
                    f"- [Catégorielle] {col} (manquants: {pct_miss}%, {n_unique} modalités): top 5 = [{top_cats}]"
                )
        
        context_parts.append("Variables & Statistiques résumées :\n" + "\n".join(var_summaries))
        if n_vars > max_vars:
            context_parts.append(f"(Et {n_vars - max_vars} autres variables non détaillées...)")
    
    if completude_data:
        context_parts.append("=== ÉTAT DE LA COMPLÉTUDE NATIONALE SPAD ===")
        if "national" in completude_data:
            nat = completude_data["national"]
            nat_lines = []
            for code, info in nat.items():
                if isinstance(info, dict):
                    nat_lines.append(
                        f"- Formulaire {code} ({info.get('label', '')}): reçu={info.get('recu', 0)}/{info.get('cible', 0)} ({info.get('taux', 0)}%), statut={info.get('statut', '')}"
                    )
            if nat_lines:
                context_parts.append("Complétude nationale par formulaire :\n" + "\n".join(nat_lines))
        
        if "district" in completude_data:
            districts = completude_data["district"]
            dist_summary = []
            for d_name, d_info in list(districts.items())[:12]:
                forms_str = ", ".join([f"{k}: {v.get('taux', 0)}%" for k, v in d_info.get("forms", {}).items()])
                dist_summary.append(f"- District {d_name} ({d_info.get('region', '')}): {forms_str}")
            if dist_summary:
                context_parts.append("Complétude par district (échantillon) :\n" + "\n".join(dist_summary))
                
    if not context_parts:
        return "Aucun jeu de données ou calcul de complétude n'est actuellement chargé dans la session."
        
    return "\n\n".join(context_parts)


def ask_ai(
    user_prompt: str,
    conversation_history: list = None,
    df: pd.DataFrame = None,
    completude_data: dict = None,
    api_key: str = None,
    model: str = DEFAULT_MODEL,
    system_instruction: str = None
) -> dict:
    """Envoie une requête d'analyse à l'IA avec injection de contexte."""
    key = get_api_key(api_key)
    if not key:
        return {
            "success": False,
            "error": "Clé API non configurée. Veuillez renseigner votre clé API Anthropic (Claude) dans les paramètres de l'assistant ou dans les variables d'environnement (ANTHROPIC_API_KEY).",
            "needs_key": True
        }
    
    data_context = build_data_context(df=df, completude_data=completude_data)
    
    system_prompt = system_instruction or (
        "Tu es SPAD AI Copilot, un expert senior en biostatistique, épidémiologie, santé publique et analyse de données d'enquêtes terrain pour l'Organisation Mondiale de la Santé (OMS) et le programme SPAD.\n\n"
        "Ton rôle :\n"
        "1. Analyser avec rigueur et clarté les données d'enquête et les indicateurs de complétude fournis ci-dessous.\n"
        "2. Répondre précisément aux questions des chercheurs, évaluateurs et équipes de santé publique.\n"
        "3. Fournir des analyses interprétatives (pas seulement des chiffres bruts) : identifier les corrélations, expliquer les disparités territoriales ou sociodémographiques, signaler les anomalies ou données aberrantes, et proposer des recommandations stratégiques concrètes.\n"
        "4. Rédiger dans un français impeccable, fluide, professionnel et bien structuré (titres markdown, listes à puces, tableaux si pertinent, mise en gras des points clés).\n\n"
        f"Voici le contexte des données actuellement actives dans l'application :\n{data_context}\n"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        
        messages = []
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": user_prompt})
        
        response = client.messages.create(
            model=model if model else "claude-3-7-sonnet-20250219",
            max_tokens=4000,
            system=system_prompt,
            messages=messages
        )
        
        reply_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply_text += block.text
            elif isinstance(block, dict) and "text" in block:
                reply_text += block["text"]
                
        return {
            "success": True,
            "response": reply_text,
            "model": model,
            "usage": {
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None)
            }
        }
    except Exception as e:
        err_msg = str(e)
        if "authentication_error" in err_msg.lower() or "api key" in err_msg.lower() or "401" in err_msg:
            return {
                "success": False,
                "error": "Clé API invalide ou expirée. Veuillez vérifier votre clé API Anthropic.",
                "needs_key": True
            }
        return {
            "success": False,
            "error": f"Erreur lors de l'appel à l'IA : {err_msg}",
            "details": traceback.format_exc()
        }


def generate_quick_analysis(
    analysis_type: str,
    df: pd.DataFrame = None,
    completude_data: dict = None,
    api_key: str = None
) -> dict:
    """Génère une analyse prédéfinie structurée."""
    prompts = {
        "summary": "Fais une synthèse globale et exécutive complète des données d'enquête actuellement chargées. Résume les caractéristiques de l'échantillon, les principaux enseignements et le profil général.",
        "correlations": "Identifie et explique les corrélations, croisements de variables et associations les plus remarquables ou statistiquement pertinentes dans ce jeu de données. Quels facteurs semblent liés ?",
        "quality": "Évalue la qualité des données collectées : taux de complétude des variables, valeurs manquantes, présence d'éventuelles anomalies ou biais d'échantillonnage, et niveau de fiabilité.",
        "recommendations": "Rédige des recommandations stratégiques et opérationnelles concrètes à l'attention des décideurs en santé publique et de la coordination du projet SPAD / OMS, basées sur ces données.",
        "completude_eval": "Analyse en détail l'avancement de la complétude nationale de collecte : quels formulaires ou districts sont en avance ou en retard ? Quelles priorités pour les équipes de terrain ?"
    }
    
    prompt = prompts.get(analysis_type, prompts["summary"])
    return ask_ai(user_prompt=prompt, df=df, completude_data=completude_data, api_key=api_key)
