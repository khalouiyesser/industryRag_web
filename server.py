"""
server.py — Backend Flask pour Industrial RAG (Ahmed).
Expose une API REST que le frontend consomme.
Les principes, le prompt système et la logique RAG restent intacts.
"""
from __future__ import annotations

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
from src.rag_engine import ask_rag

load_env_file()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("server")

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}

# ── Conversation sessions (en mémoire — suffisant pour un déploiement solo) ──
_sessions: dict[str, list[dict]] = {}


def _session(sid: str) -> list[dict]:
    if sid not in _sessions:
        _sessions[sid] = []
    return _sessions[sid]


# ── Routes statiques ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── API Chat ─────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    api_key  = (data.get("api_key")  or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
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


# ── API Documents ─────────────────────────────────────────────────────────────
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


# ── Santé ─────────────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    docs = get_documents_list()
    return jsonify({"status": "ok", "documents": len(docs), "version": "2.0.0"})


if __name__ == "__main__":
    ensure_documents_dir()
    port = int(os.environ.get("PORT", 5000))
    logger.info("🏭 Industrial RAG — serveur sur http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
