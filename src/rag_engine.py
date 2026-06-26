"""
rag_engine.py — Moteur RAG basé sur l'API Anthropic (Claude).

Deux modes de fonctionnement :
  1. Chat RAG  (ask_rag)     — assistant Ahmed, s'appuie sur les documents indexés.
  2. DSL Agent (ask_dsl)     — DMAIC domain-restricted, system prompt DSL Agent complet,
                               sans contrainte de base documentaire obligatoire.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from src.config import (
    CLAUDE_MODELS,
    FALLBACK_PAUSE,
    MAX_OUTPUT_TOKENS,
    MAX_OUTPUT_TOKENS_DSL,
    MAX_RETRIES,
    RETRY_BACKOFF,
    RETRY_DELAY,
    TEMPERATURE,
    API_KEY_CONSOLE_URL,
)
from src.document_processor import get_all_documents_text
from src.dsl_system_prompt import build_system_prompt, preClassifyDomains, OUTPUT_TYPES

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# PROMPT SYSTÈME — CHAT RAG (Ahmed)
# ════════════════════════════════════════════════════════════════════════════
AHMED_SYSTEM_PROMPT = """Tu t'appelles Ahmed, un assistant expert en ingénierie industrielle
(Lean, Six Sigma, TPM, maintenance, qualité ISO, sécurité HSE, amélioration continue).

══════════════════════════════════════════════
RÈGLES (à respecter STRICTEMENT)
══════════════════════════════════════════════
1. Va DROIT AU BUT : réponds uniquement à ce qui est demandé et résous le problème.
   Pas d'analyse longue, pas de sections de remplissage.
2. Appuie-toi EN PRIORITÉ sur les documents fournis. Si l'information y figure,
   indique brièvement la source (nom du document).
3. Si l'information demandée N'EXISTE PAS dans les documents, commence ta réponse
   EXACTEMENT par cette phrase (sans rien avant) :
   "D'après votre base de données je n'ai pas de suggestions, mais je te conseille de faire ..."
   puis donne directement la meilleure solution issue des bonnes pratiques industrielles.
4. Adapte le format à la question :
   - Question de définition / simple → réponse courte en texte clair.
   - Problème technique → diagnostic bref, cause(s), puis solution concrète.
   Tu peux ajouter un petit schéma ASCII ou un tableau SEULEMENT s'il aide vraiment.
5. N'ajoute PAS de sections non demandées (pas de KPI, pas de "plan d'action",
   pas de "risques", pas de mention de clé API ou de modèle) si la question ne les
   appelle pas. Ne mets jamais de rubrique "Non applicable".
6. N'invente jamais de chiffres ou de procédures absents des documents.
7. Si la question est vraiment ambiguë, pose UNE seule question de clarification.

══════════════════════════════════════════════
Style : clair, concis, professionnel, orienté solution.
Objectif : résoudre le problème, rien de plus."""


# ════════════════════════════════════════════════════════════════════════════
# HELPERS COMMUNS
# ════════════════════════════════════════════════════════════════════════════

def _build_messages(
        question: str,
        conversation_history: list[dict] | None,
        prefix_content: str = "",
) -> list[dict[str, Any]]:
    """Assemble l'historique + la nouvelle question au format API Anthropic."""
    messages: list[dict[str, Any]] = []
    if conversation_history:
        for turn in conversation_history:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn.get("content", "")})
    user_content = (prefix_content + "\n\n" + question).strip() if prefix_content else question
    messages.append({"role": "user", "content": user_content})
    return messages


def _call_claude(
        client: anthropic.Anthropic,
        model: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:
    """Appelle l'API avec retry exponentiel. Lève l'exception si tout échoue."""
    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Appel modèle %s (tentative %d/%d)", model, attempt, MAX_RETRIES)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=messages,
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            )
        except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
            is_last = attempt == MAX_RETRIES
            retriable = isinstance(exc, anthropic.RateLimitError) or (
                    getattr(exc, "status_code", None) in (429, 503, 529)
            )
            if retriable and not is_last:
                logger.warning(
                    "Limite/surcharge sur %s (tentative %d) — attente %.0fs",
                    model, attempt, delay,
                )
                time.sleep(delay)
                delay *= RETRY_BACKOFF
            else:
                raise


def _run_with_fallback(
        api_key: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:
    """Boucle de fallback sur les modèles Claude avec gestion d'erreurs uniforme."""
    try:
        client = anthropic.Anthropic(api_key=api_key.strip())
    except Exception as exc:
        return f"❌ **Impossible d'initialiser le client Anthropic :** {exc}"

    last_error: Exception | None = None

    for model in CLAUDE_MODELS:
        try:
            return _call_claude(client, model, messages, system_prompt, max_tokens)
        except anthropic.AuthenticationError:
            return (
                "❌ **Clé API invalide ou non autorisée.**\n\n"
                f"Vérifiez votre clé sur : {API_KEY_CONSOLE_URL}"
            )
        except anthropic.PermissionDeniedError:
            return (
                "❌ **Accès refusé.** Votre clé n'a pas accès à ce modèle ou "
                "votre crédit est épuisé.\n\n"
                f"Vérifiez votre compte : {API_KEY_CONSOLE_URL}"
            )
        except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
            last_error = exc
            logger.warning("Échec sur %s, bascule modèle suivant…", model)
            time.sleep(FALLBACK_PAUSE)
            continue
        except anthropic.APIConnectionError as exc:
            last_error = exc
            break
        except Exception as exc:
            last_error = exc
            break

    if last_error is None:
        return "❌ **Erreur inconnue.**"
    if isinstance(last_error, (anthropic.RateLimitError, anthropic.APIStatusError)):
        return (
            "⚠️ **Limite de débit ou surcharge sur tous les modèles disponibles.**\n\n"
            "**Solutions :**\n"
            "1. Patientez quelques minutes puis réessayez\n"
            "2. Consultez vos limites sur la console Anthropic\n"
            "3. Augmentez votre tier d'utilisation pour des limites plus élevées"
        )
    if isinstance(last_error, anthropic.APIConnectionError):
        return "❌ **Erreur de connexion.** Vérifiez votre accès Internet."
    return f"❌ **Erreur Anthropic :** {last_error}"


# ════════════════════════════════════════════════════════════════════════════
# MODE 1 — CHAT RAG (Ahmed)
# ════════════════════════════════════════════════════════════════════════════

def _build_rag_prompt(question: str, documents_text: str) -> str:
    return (
        "Voici les documents industriels disponibles :\n\n"
        f"{documents_text}\n\n"
        "══════════════════════════════════════════════\n"
        f"QUESTION :\n{question}\n"
        "══════════════════════════════════════════════\n\n"
        "Réponds de façon directe et concise pour résoudre le problème, en suivant "
        "tes règles. Si l'information n'est pas dans les documents, commence par la "
        "phrase imposée puis donne la meilleure solution."
    )


def ask_rag(
        question: str, api_key: str, conversation_history: list[dict] | None = None
) -> str:
    """Chat RAG Ahmed — retourne une réponse Markdown.

    Args:
        question: la question de l'ingénieur.
        api_key: clé API Anthropic.
        conversation_history: liste de tours {"role", "content"} (optionnel).
    """
    if not api_key or not api_key.strip():
        return (
            "❌ **Clé API manquante.**\n\n"
            f"Créez une clé sur : {API_KEY_CONSOLE_URL}\n"
            "Puis saisissez-la dans le champ en haut de la fenêtre."
        )

    documents_text = get_all_documents_text()
    if not documents_text.strip():
        return (
            "⚠️ **Aucun document chargé.**\n\n"
            "Ajoutez vos documents industriels (PDF, DOCX, TXT...) via l'onglet "
            "**📂 Documents**.\n\nLe système fonctionne en mode RAG : il s'appuie "
            "d'abord sur votre base documentaire."
        )

    prompt = _build_rag_prompt(question, documents_text)
    messages = _build_messages(prompt, conversation_history)
    return _run_with_fallback(api_key, messages, AHMED_SYSTEM_PROMPT)


# ════════════════════════════════════════════════════════════════════════════
# MODE 2 — DSL AGENT (DMAIC domain-restricted)
# ════════════════════════════════════════════════════════════════════════════

def ask_dsl(
        question: str,
        api_key: str,
        domain: str | None = None,
        output_type: str = OUTPUT_TYPES.DIGITAL_A3.id,
        conversation_history: list[dict] | None = None,
        include_rag_context: bool = True,
) -> str:
    """DSL Agent DMAIC — retourne une réponse structurée (JSON ou Markdown).

    Args:
        question      : données opérateur soumises + instruction de génération.
        api_key       : clé API Anthropic.
        domain        : domaine explicite (A/B/C/D). Si None, auto-détecté.
        output_type   : type de sortie DSL (digital_a3, kpi_alert, etc.).
        conversation_history : historique de la session.
        include_rag_context  : si True, ajoute le contexte documentaire RAG
                               en annexe de la question opérateur.
    """
    if not api_key or not api_key.strip():
        return (
            "❌ **Clé API manquante.**\n\n"
            f"Créez une clé sur : {API_KEY_CONSOLE_URL}"
        )

    # ── Auto-détection du domaine si non fourni ──────────────────────────
    detected_domains: list[str] = []
    if domain:
        detected_domains = [domain]
    else:
        # Tenter une pré-classification à partir de la question brute
        fake_form: dict[str, str] = {}
        for token in question.split():
            fake_form[token] = token
        detected_domains = preClassifyDomains(fake_form) or ["A"]

    # ── Bascule cross-domain automatique ────────────────────────────────
    effective_output = output_type
    if len(detected_domains) > 1:
        effective_output = OUTPUT_TYPES.CROSS_DOMAIN.id

    # ── Construction du system prompt DSL ───────────────────────────────
    system_prompt = build_system_prompt(
        domains=detected_domains,
        output_type=effective_output,
    )

    # ── Contexte RAG optionnel (annexe documentaire) ─────────────────────
    rag_annex = ""
    if include_rag_context:
        docs_text = get_all_documents_text()
        if docs_text.strip():
            # Tronqué à 6 000 caractères pour ne pas dépasser la fenêtre
            excerpt = docs_text[:6000]
            if len(docs_text) > 6000:
                excerpt += "\n[… documents tronqués pour la fenêtre de contexte …]"
            rag_annex = (
                    "\n\n══════════════════════════════════════════════\n"
                    "BASE DOCUMENTAIRE RAG (contexte supplémentaire) :\n"
                    "Utilisez ces données SI elles apportent des éléments\n"
                    "concrets au problème soumis. Elles ne remplacent pas\n"
                    "les données opérateur.\n"
                    "══════════════════════════════════════════════\n"
                    + excerpt
            )

    full_question = question + rag_annex

    messages = _build_messages(full_question, conversation_history)
    return _run_with_fallback(
        api_key,
        messages,
        system_prompt,
        max_tokens=MAX_OUTPUT_TOKENS_DSL,   # Digital A3 = ~6000 tokens
    )