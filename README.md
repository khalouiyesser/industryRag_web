# 🏭 Industrial RAG — Ahmed (Version Web)

Assistant expert en ingénierie industrielle (Lean, Six Sigma, TPM, ISO 9001).
Converti de l'application desktop Tkinter vers une application web Flask.

## Structure

```
industryRag_web/
├── server.py               ← Backend Flask (API REST)
├── requirements.txt
├── .env                    ← (à créer) ANTHROPIC_API_KEY=sk-ant-...
├── documents/              ← Vos fichiers industriels
├── documents_index.json    ← Index RAG (auto-géré)
├── static/
│   └── index.html          ← Frontend complet (HTML + CSS + JS)
└── src/
    ├── config.py           ← Configuration (modèles, paramètres)
    ├── document_processor.py ← Extraction et indexation PDF/DOCX/TXT
    ├── rag_engine.py       ← Moteur RAG + prompt Ahmed (inchangé)
    └── __init__.py
```

## Lancement local

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Configurer la clé API (optionnel — saisie possible dans l'interface)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 3. Démarrer le serveur
python server.py
# → http://localhost:5000
```

## Déploiement (exemples)

### Railway / Render / Fly.io
```bash
# Ajouter la variable d'environnement ANTHROPIC_API_KEY dans le dashboard
# Commande de démarrage :
python server.py
```

### Gunicorn (production)
```bash
pip install gunicorn
gunicorn server:app --bind 0.0.0.0:$PORT --workers 2
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:5000"]
```

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/chat` | Envoyer une question à Ahmed |
| POST | `/api/chat/clear` | Effacer l'historique de session |
| GET  | `/api/documents` | Lister les documents indexés |
| POST | `/api/documents/upload` | Ajouter des fichiers (multipart) |
| POST | `/api/documents/scan` | Scanner le dossier `documents/` |
| DELETE | `/api/documents/<nom>` | Supprimer un document de l'index |
| GET  | `/api/health` | Santé du serveur |

### Exemple curl
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Procédure de maintenance préventive ?","api_key":"sk-ant-..."}'
```

## Principes préservés

- ✅ Même prompt système Ahmed (ingénierie industrielle)
- ✅ Même logique RAG (documents en priorité, fallback bonnes pratiques)
- ✅ Même modèles Claude avec fallback automatique
- ✅ Même extraction PDF/DOCX/TXT
- ✅ Même historique de conversation (MAX_HISTORY_TURNS)
- ✅ Même gestion des erreurs et retry exponentiel
