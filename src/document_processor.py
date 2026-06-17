"""
document_processor.py — Lecture, extraction et indexation des documents.

Formats pris en charge : PDF, DOCX/DOC, TXT, MD, CSV.
L'index est persisté dans un fichier JSON et sert de base documentaire au RAG.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.config import DOCUMENTS_DIR, INDEX_FILE

logger = logging.getLogger(__name__)

# ── Dépendances optionnelles ────────────────────────────────────────────────
try:
    import PyPDF2  # type: ignore
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

try:
    from docx import Document as DocxDocument  # type: ignore
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False

# Extensions supportées
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}


# ── Utilitaires de répertoire ───────────────────────────────────────────────
def ensure_documents_dir() -> None:
    """Crée le dossier des documents s'il n'existe pas."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Extraction de texte ─────────────────────────────────────────────────────
def extract_text_from_pdf(filepath: str | Path) -> str:
    """Extrait le texte d'un PDF, page par page."""
    if not _PDF_OK:
        return "[PyPDF2 non installé — impossible de lire ce PDF]"
    try:
        parts: list[str] = []
        with open(filepath, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for i, page in enumerate(reader.pages, start=1):
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(f"[Page {i}]\n{txt}")
        return "\n\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erreur lecture PDF %s : %s", filepath, exc)
        return f"[Erreur lecture PDF : {exc}]"


def extract_text_from_docx(filepath: str | Path) -> str:
    """Extrait le texte d'un document Word (.docx)."""
    if not _DOCX_OK:
        return "[python-docx non installé — impossible de lire ce DOCX]"
    try:
        doc = DocxDocument(str(filepath))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erreur lecture DOCX %s : %s", filepath, exc)
        return f"[Erreur lecture DOCX : {exc}]"


def extract_text_from_txt(filepath: str | Path) -> str:
    """Lit un fichier texte brut (TXT, MD, CSV)."""
    try:
        return Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erreur lecture TXT %s : %s", filepath, exc)
        return f"[Erreur lecture TXT : {exc}]"


def extract_text(filepath: str | Path) -> str:
    """Aiguille l'extraction selon l'extension du fichier."""
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    if ext in (".docx", ".doc"):
        return extract_text_from_docx(filepath)
    if ext in (".txt", ".md", ".csv"):
        return extract_text_from_txt(filepath)
    return f"[Format non supporté : {ext}]"


# ── Persistance de l'index ──────────────────────────────────────────────────
def load_index() -> dict[str, Any]:
    """Charge l'index JSON des documents (dict vide si absent/corrompu)."""
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Index illisible (%s), réinitialisation.", exc)
        return {}


def save_index(index: dict[str, Any]) -> None:
    """Sauvegarde l'index des documents au format JSON."""
    try:
        INDEX_FILE.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Impossible d'écrire l'index : %s", exc)


# ── Indexation ──────────────────────────────────────────────────────────────
def index_document(filepath: str | Path) -> dict[str, Any]:
    """Indexe un document et retourne ses métadonnées."""
    ensure_documents_dir()
    path = Path(filepath)
    text = extract_text(path)

    doc_info: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "size": path.stat().st_size if path.exists() else 0,
        "pages": text.count("[Page ") if "[Page " in text else 1,
        "chars": len(text),
        "text": text,
    }

    index = load_index()
    index[path.name] = doc_info
    save_index(index)
    logger.info("Document indexé : %s (%d caractères)", path.name, len(text))
    return doc_info


def get_all_documents_text() -> str:
    """Concatène le texte de tous les documents indexés."""
    index = load_index()
    if not index:
        return ""
    blocks = [
        f"\n{'=' * 60}\nDOCUMENT : {name}\n{'=' * 60}\n{info['text']}"
        for name, info in index.items()
    ]
    return "\n".join(blocks)


def get_documents_list() -> list[dict[str, Any]]:
    """Retourne la liste (métadonnées) des documents indexés."""
    index = load_index()
    return [
        {
            "name": name,
            "chars": info.get("chars", 0),
            "pages": info.get("pages", 1),
            "path": info.get("path", ""),
        }
        for name, info in index.items()
    ]


def remove_document(doc_name: str) -> bool:
    """Supprime un document de l'index. Retourne True si supprimé."""
    index = load_index()
    if doc_name in index:
        del index[doc_name]
        save_index(index)
        logger.info("Document retiré de l'index : %s", doc_name)
        return True
    return False


def scan_documents_folder() -> list[str]:
    """Indexe automatiquement les nouveaux fichiers du dossier documents/."""
    ensure_documents_dir()
    added: list[str] = []
    for file in DOCUMENTS_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS:
            if file.name not in load_index():
                index_document(file)
                added.append(file.name)
    return added
