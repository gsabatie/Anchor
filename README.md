# ⚓ Anchor

**Compagnon ERP vocal pour les TOC** — Séances d'exposition guidées par IA générative

> Hackathon Google — Live Agents + Creative Storyteller

---

## Le concept

Anchor est un agent vocal qui accompagne les personnes vivant avec des TOC (Troubles Obsessionnels Compulsifs) à travers des séances d'ERP (Exposition avec Prévention de la Réponse).

L'agent :
- **Ecoute** l'utilisateur décrire son TOC en temps réel (Gemini Live)
- **Construit** une hiérarchie d'exposition personnalisée (niveaux 1 à 10)
- **Génère** des images des situations anxiogènes (Imagen 3)
- **Narre** vocalement la scène pendant que l'image apparaît
- **Coach** l'utilisateur pendant la montée d'anxiété — sans jamais rassurer
- **Sauvegarde** les progrès dans Firestore

**Différenciateur :** Anchor refuse activement de rassurer l'utilisateur. La réassurance est elle-même une compulsion qui renforce le cycle des TOC. L'Anti-Reassurance Guard intercepte toute formule rassurante et redirige vers les protocoles ERP.

---

## Architecture

```
Utilisateur (Audio + Caméra)
        │
        │ WebSocket
        ▼
   Cloud Run — FastAPI
        │
        ├── Gemini Live API (audio bidirectionnel)
        │
        └── Google ADK Agent
              ├── reassurance_guard
              ├── hierarchy_builder
              ├── image_generator (Imagen 3)
              ├── erp_timer
              └── session_tracker (Firestore)
        │
        ▼
   Firebase Hosting — React + Vite
```

## Stack

| Besoin              | Outil                           |
| ------------------- | ------------------------------- |
| LLM + Audio Live    | Gemini 2.0 Flash                |
| Agent orchestration | Google ADK                      |
| Image generation    | Vertex AI Imagen 3              |
| Database            | Firestore                       |
| Secrets             | Secret Manager                  |
| Backend             | Cloud Run (FastAPI)             |
| Frontend            | Firebase Hosting (React + Vite) |
| IaC                 | Terraform                       |
| CI/CD               | Cloud Build                     |

---

## Prérequis

- **Python** 3.12+
- **Node.js** 22+
- **Docker** + Docker Compose
- **gcloud CLI** (`brew install google-cloud-sdk`)

---

## Quick start

### 1. Cloner et configurer

```bash
git clone <repo-url> && cd anchor
cp .env.example .env
# Editer .env avec vos valeurs (projet GCP, tokens...)
```

### 2. Lancer avec Docker Compose

```bash
docker compose up
```

- Backend : http://localhost:8000
- Frontend : http://localhost:5173

### 3. Ou lancer manuellement

```bash
# Terminal 1 — Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

---

## Variables d'environnement

| Variable               | Description            | Valeur par défaut           |
| ---------------------- | ---------------------- | --------------------------- |
| `GOOGLE_CLOUD_PROJECT` | ID du projet GCP       | —                           |
| `GOOGLE_CLOUD_REGION`  | Région GCP             | `europe-west1`              |
| `GEMINI_MODEL`         | Modèle Gemini Live     | `gemini-2.0-flash-live-001` |
| `VERTEX_LOCATION`      | Région Vertex AI       | `europe-west1`              |
| `IMAGEN_MODEL`         | Modèle Imagen          | `imagegeneration@006`       |
| `FIRESTORE_COLLECTION` | Collection Firestore   | `sessions`                  |
| `ENV`                  | Environnement          | `development`               |
| `BACKEND_URL`          | URL du backend         | `http://localhost:8000`     |
| `FRONTEND_URL`         | URL du frontend        | `http://localhost:5173`     |
| `WS_AUTH_TOKEN`        | Token auth WebSocket   | —                           |
| `VITE_WS_AUTH_TOKEN`   | Token WS côté frontend | —                           |

---

## Déploiement GCP

### Authentification

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>
```

### Activer les APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  firebasehosting.googleapis.com
```

### Backend — Cloud Run

```bash
gcloud builds submit --tag europe-west1-docker.pkg.dev/$PROJECT_ID/anchor/backend ./backend

gcloud run deploy anchor-backend \
  --image europe-west1-docker.pkg.dev/$PROJECT_ID/anchor/backend \
  --region europe-west1
```

### Frontend — Firebase Hosting

```bash
cd frontend
npm run build
npx firebase-tools deploy --only hosting
```

### Terraform (optionnel)

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

---

## Note clinique

Anchor **n'est pas** un substitut à un suivi thérapeutique, ni un outil de diagnostic. C'est un compagnon d'entraînement ERP entre les séances, un support pour pratiquer les techniques de façon autonome.

Si l'utilisateur exprime des idées suicidaires, l'agent redirige immédiatement vers le **3114** (numéro national de prévention du suicide en France).

---

## Licence

Voir [LICENSE](LICENSE).
