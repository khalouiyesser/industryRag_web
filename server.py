"""
server.py — Backend Flask pour Industrial RAG (Ahmed) + DSL Agent.

Routes exposées :
  GET  /                          → index.html
  POST /api/chat                  → Chat RAG (Ahmed)
  POST /api/chat/clear            → Vider session
  POST /api/dsl/analyze           → DSL Agent DMAIC (nouveau)
  GET  /api/dsl/domains           → Métadonnées domaines (nouveau)
  GET  /api/dsl/output-types      → Types d'output disponibles (nouveau)
  GET  /api/documents             → Liste des documents indexés
  POST /api/documents/upload      → Upload + indexation
  POST /api/documents/scan        → Scan du dossier documents/
  DELETE /api/documents/<name>    → Suppression
  GET  /api/health                → Santé du service
"""

from __future__ import annotations

import json
import os
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from src.config import load_env_file, DOCUMENTS_DIR, MAX_HISTORY_TURNS
from src.document_processor import (
    ensure_documents_dir,
    get_documents_list,
    index_document,
    remove_document,
    scan_documents_folder,
)
from src.rag_engine import ask_rag, ask_dsl
from src.dsl_system_prompt import (
    DOMAIN_META,
    DEPLOYED_DOMAINS,
    ROADMAP_DOMAINS,
    OUTPUT_TYPES,
    preClassifyDomains,
)

load_env_file()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("server")

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}

# ── Sessions de conversation (en mémoire) ────────────────────────────────────
_sessions: dict[str, list[dict]] = {}


def _session(sid: str) -> list[dict]:
    if sid not in _sessions:
        _sessions[sid] = []
    return _sessions[sid]


def _get_api_key(data: dict) -> str:
    """Résolution de la clé API : body → env."""
    return (data.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")).strip()


# ════════════════════════════════════════════════════════════════════════════
# ROUTES STATIQUES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ════════════════════════════════════════════════════════════════════════════
# API CHAT RAG (Ahmed)
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    data     = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    api_key  = _get_api_key(data)
    sid      = (data.get("session_id") or "default").strip()

    if not question:
        return jsonify({"error": "Question vide"}), 400
    if not api_key:
        return jsonify({"error": "Clé API manquante"}), 400

    history = _session(sid)
    answer  = ask_rag(question, api_key, history.copy())

    history.append({"role": "user",      "content": question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > MAX_HISTORY_TURNS:
        _sessions[sid] = history[-MAX_HISTORY_TURNS:]

    return jsonify({"answer": answer})


@app.route("/api/chat/clear", methods=["POST"])
def clear_chat():
    data = request.get_json(force=True)
    sid  = (data.get("session_id") or "default").strip()
    _sessions.pop(sid, None)
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════════════════
# API DSL AGENT — nouvelles routes
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/dsl/domains", methods=["GET"])
def dsl_domains():
    """Retourne les métadonnées de tous les domaines (déployés + roadmap)."""
    result = []
    for d_id, meta in DOMAIN_META.items():
        entry = {
            "id":       d_id,
            "name":     meta.name,
            "metric":   meta.metric,
            "deployed": meta.deployed,
            "tools":    meta.tools,
        }
        if meta.dmaic_tools:
            entry["dmaic_tools"] = meta.dmaic_tools
        if meta.composite_index:
            ci = meta.composite_index
            entry["composite_index"] = {
                "name":                 ci.name,
                "formula":              ci.formula,
                "factors":              ci.factors,
                "world_class_benchmark": ci.world_class_benchmark,
            }
        result.append(entry)
    return jsonify({
        "deployed": DEPLOYED_DOMAINS,
        "roadmap":  ROADMAP_DOMAINS,
        "domains":  result,
    })


@app.route("/api/dsl/output-types", methods=["GET"])
def dsl_output_types():
    """Retourne les 6 types d'output disponibles."""
    return jsonify({
        "output_types": [
            {"id": ot.id, "label": ot.label, "description": ot.description}
            for ot in OUTPUT_TYPES.all()
        ]
    })


@app.route("/api/dsl/analyze", methods=["POST"])
def dsl_analyze():
    """Point d'entrée principal du DSL Agent.

    Corps attendu (JSON) :
    {
      "form_data":   object,          // champs renseignés par l'opérateur
      "domain":      string | null,   // ex. "A" — si null, auto-détecté
      "output_type": string,          // ex. "digital_a3"
      "session_id":  string,          // pour historique multi-tours
      "api_key":     string | null    // fallback sur env ANTHROPIC_API_KEY
    }
    """
    data        = request.get_json(force=True)
    form_data   = data.get("form_data") or {}
    domain      = (data.get("domain") or "").strip().upper() or None
    output_type = (data.get("output_type") or OUTPUT_TYPES.DIGITAL_A3.id).strip()
    sid         = (data.get("session_id") or "dsl_default").strip()
    api_key     = _get_api_key(data)

    if not api_key:
        return jsonify({"error": "Clé API manquante"}), 400

    if not form_data:
        return jsonify({"error": "Aucune donnée opérateur fournie (form_data vide)"}), 400

    # ── Auto-détection du domaine si non précisé ────────────────────────
    if not domain:
        detected = preClassifyDomains(form_data)
        if not detected:
            domain = "A"          # fallback si aucun champ reconnu
        elif len(detected) > 1:
            # Cross-domain : on le laisse None, ask_dsl décidera
            domain = None
            output_type = OUTPUT_TYPES.CROSS_DOMAIN.id
        else:
            domain = detected[0]

    # ── Construction du message opérateur ───────────────────────────────
    domain_label = DOMAIN_META[domain].name if domain else "Cross-Domain"
    form_text    = json.dumps(form_data, ensure_ascii=False, indent=2)
    user_message = (
        f"Operator submission for Domain {domain or 'Cross'} ({domain_label}):\n\n"
        f"{form_text}\n\n"
        "Generate the requested output now, following the JSON schema exactly."
    )

    history = _session(sid)
    answer  = ask_dsl(
        question=user_message,
        api_key=api_key,
        domain=domain,
        output_type=output_type,
        conversation_history=history.copy(),
        include_rag_context=True,
    )

    # Tentative de parse JSON pour retourner directement l'objet structuré
    parsed_result = None
    try:
        cleaned = answer.replace("```json", "").replace("```", "").strip()
        parsed_result = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass   # on retourne le texte brut dans raw_answer

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": answer})
    if len(history) > MAX_HISTORY_TURNS:
        _sessions[sid] = history[-MAX_HISTORY_TURNS:]

    return jsonify({
        "domain":      domain,
        "output_type": output_type,
        "result":      parsed_result,    # JSON structuré si le parse réussit
        "raw_answer":  answer,           # toujours présent (fallback)
    })


@app.route("/api/dsl/chat", methods=["POST"])
def dsl_chat():
    """Chat post-A3 : questions de suivi sur un rapport DSL généré.

    Le frontend envoie le contexte A3 + la question dans le corps.
    Cette route utilise ask_rag (Ahmed) avec RAG complet — le contexte A3
    est injecté dans la question, pas dans le system prompt DSL.

    Corps attendu :
    {
      "question":   string,
      "a3_context": string | null,  // extrait du rapport A3 (optionnel)
      "session_id": string,
      "api_key":    string | null
    }
    """
    data       = request.get_json(force=True)
    question   = (data.get("question") or "").strip()
    a3_context = (data.get("a3_context") or "").strip()
    sid        = (data.get("session_id") or "dsl_chat_default").strip()
    api_key    = _get_api_key(data)

    if not question:
        return jsonify({"error": "Question vide"}), 400
    if not api_key:
        return jsonify({"error": "Clé API manquante"}), 400

    # Enrichir la question avec le contexte A3 si premier tour
    history = _session(sid)
    if a3_context and not history:
        question = (
            f"[Contexte : rapport A3 DMAIC]\n\n{a3_context[:800]}…\n\n"
            f"Question : {question}"
        )

    answer = ask_rag(question, api_key, history.copy())

    history.append({"role": "user",      "content": question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > MAX_HISTORY_TURNS:
        _sessions[sid] = history[-MAX_HISTORY_TURNS:]

    return jsonify({"answer": answer})


# ════════════════════════════════════════════════════════════════════════════
# API DOCUMENTS
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/documents", methods=["GET"])
def list_documents():
    ensure_documents_dir()
    return jsonify({"documents": get_documents_list()})


@app.route("/api/documents/upload", methods=["POST"])
def upload_document():
    ensure_documents_dir()
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    added, errors = [], []
    for f in files:
        name = secure_filename(f.filename or "unknown")
        ext  = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"{name} : format non supporté")
            continue
        dest = DOCUMENTS_DIR / name
        try:
            f.save(str(dest))
            index_document(dest)
            added.append(name)
        except Exception as exc:
            errors.append(f"{name} : {exc}")
            logger.error("Upload error %s : %s", name, exc)

    return jsonify({"added": added, "errors": errors})


@app.route("/api/documents/scan", methods=["POST"])
def scan_documents():
    ensure_documents_dir()
    added = scan_documents_folder()
    return jsonify({"added": added})


@app.route("/api/documents/<doc_name>", methods=["DELETE"])
def delete_document(doc_name: str):
    ok = remove_document(doc_name)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "Document introuvable"}), 404


# ════════════════════════════════════════════════════════════════════════════
# SANTÉ
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health():
    docs = get_documents_list()
    return jsonify({
        "status":          "ok",
        "documents":       len(docs),
        "version":         "2.1.0",
        "dsl_agent":       "active",
        "deployed_domains": DEPLOYED_DOMAINS,
    })


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ensure_documents_dir()
    port = int(os.environ.get("PORT", 5000))
    logger.info("🏭 Industrial RAG + DSL Agent — serveur sur http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)