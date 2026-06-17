"""
rag_engine.py — Moteur RAG basé sur l'API Anthropic (Claude).

- Construit un contexte documentaire à partir des fichiers indexés.
- Interroge Claude avec un fallback automatique entre modèles.
- Applique un retry exponentiel sur surcharge / limite de débit.
- Retourne une réponse Markdown structurée orientée ingénierie industrielle.
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
    MAX_RETRIES,
    RETRY_BACKOFF,
    RETRY_DELAY,
    TEMPERATURE,
    API_KEY_CONSOLE_URL,
)
from src.document_processor import get_all_documents_text

logger = logging.getLogger(__name__)


# ── Prompt système ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu t'appelles Ahmed, un assistant expert en ingénierie industrielle
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


def _build_prompt(question: str, documents_text: str) -> str:
    """Construit le message utilisateur avec le contexte documentaire."""
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


def _build_messages(
        question: str, documents_text: str, conversation_history: list[dict] | None
) -> list[dict[str, Any]]:
    """Assemble l'historique + la nouvelle question au format API Anthropic."""
    messages: list[dict[str, Any]] = []
    if conversation_history:
        for turn in conversation_history:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": _build_prompt(question, documents_text)})
    return messages


def _call_claude(
        client: anthropic.Anthropic, model: str, messages: list[dict[str, Any]]
) -> str:
    """Appelle l'API avec retry exponentiel. Lève l'exception si tout échoue."""
    delay = RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Appel modèle %s (tentative %d/%d)", model, attempt, MAX_RETRIES)
            response = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            )
        except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
            # Surcharge serveur / limite de débit : on retente sauf dernière fois
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


def ask_rag(
        question: str, api_key: str, conversation_history: list[dict] | None = None
) -> str:
    """Point d'entrée du RAG : retourne une réponse Markdown.

    Args:
        question: la question de l'ingénieur.
        api_key: clé API Anthropic.
        conversation_history: liste de tours {"role", "content"} (optionnel).
    """
    # ── Validation de la clé ────────────────────────────────────────────────
    if not api_key or not api_key.strip():
        return (
            "❌ **Clé API manquante.**\n\n"
            f"Créez une clé sur : {API_KEY_CONSOLE_URL}\n"
            "Puis saisissez-la dans le champ en haut de la fenêtre."
        )

    # ── Vérification de la base documentaire ───────────────────────────────
    documents_text = get_all_documents_text()

    if not documents_text.strip():
        return (
            "⚠️ **Aucun document chargé.**\n\n"
            "Ajoutez vos documents industriels (PDF, DOCX, TXT...) via l'onglet "
            "**📂 Documents**.\n\nLe système fonctionne en mode RAG : il s'appuie "
            "d'abord sur votre base documentaire."
        )

    messages = _build_messages(question, documents_text, conversation_history)

    # ── Initialisation du client ────────────────────────────────────────────
    try:
        client = anthropic.Anthropic(api_key=api_key.strip())
    except Exception as exc:  # noqa: BLE001
        return f"❌ **Impossible d'initialiser le client Anthropic :** {exc}"

    last_error: Exception | None = None

    # ── Boucle de fallback sur les modèles ──────────────────────────────────
    for model in CLAUDE_MODELS:
        try:
            # On ne renvoie que la réponse, sans bruit (ni en-tête documents,
            # ni mention de modèle / clé API).
            return _call_claude(client, model, messages)

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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            break

    # ── Messages d'erreur finaux ────────────────────────────────────────────
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