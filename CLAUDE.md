# ⚓ Anchor — Agent Documentation
> ERP Thérapeute Simulé — Séances d'exposition guidées par IA générative  
> Hackathon Google Live Agents + Creative Storyteller

---

## Table des matières

1. [Concept](#1-concept)
2. [Pourquoi ce projet](#2-pourquoi-ce-projet)
3. [Catégories hackathon](#3-catégories-hackathon)
4. [Architecture technique](#4-architecture-technique)
5. [Stack — Google First](#5-stack--google-first)
6. [Structure du monorepo](#6-structure-du-monorepo)
7. [Flow d'une séance ERP](#7-flow-dune-séance-erp)
8. [System Prompt](#8-system-prompt)
9. [ADK Tools](#9-adk-tools)
10. [Interleaved Output](#10-interleaved-output)
11. [Variables d'environnement](#11-variables-denvironnement)
12. [Ordre de développement](#12-ordre-de-développement)
13. [Déploiement GCP](#13-déploiement-gcp)
14. [Note clinique](#14-note-clinique)

---

## 1. Concept

**Anchor** est un agent vocal qui simule une séance de thérapie ERP (Exposition avec Prévention de la Réponse) pour les personnes vivant avec des TOC (Troubles Obsessionnels Compulsifs).

L'agent :
- **Écoute** l'utilisateur décrire son TOC en temps réel (Gemini Live)
- **Construit** une hiérarchie d'exposition personnalisée (niveaux 1→10)
- **Génère** des images des situations anxiogènes en temps réel (Imagen 3)
- **Narre** vocalement la scène d'exposition pendant que l'image apparaît (interleaved)
- **Coach** l'utilisateur pendant la montée d'anxiété sans jamais rassurer
- **Sauvegarde** les progrès dans Firestore

**Différenciateur clé :** C'est le seul agent qui refuse activement de faire ce que l'utilisateur demande — et qui a raison de le faire. L'Anti-Reassurance Guard intercepte toute formule rassurante et redirige vers les protocoles ERP.

---

## 2. Pourquoi ce projet

### Le problème des TOC
Les TOC touchent 2-3% de la population. Le cycle est le suivant :

```
Pensée intrusive → Anxiété → Compulsion (rituel) → Soulagement temporaire → Anxiété revient plus forte
```

### Pourquoi la réassurance aggrave les TOC
La recherche de réassurance **est elle-même une compulsion**. Chaque fois qu'on rassure quelqu'un avec un TOC, on renforce le cycle. Un agent vocal classique qui dit "ça va aller" ferait plus de mal que de bien.

### Ce que fait l'ERP
L'Exposition avec Prévention de la Réponse brise le cycle :

```
Pensée intrusive → Anxiété monte → ... on résiste ... → Anxiété redescend SEULE → Cerveau apprend : pas dangereux
```

### Pourquoi la voix + vision change tout
- Les crises arrivent **en temps réel** — pas le temps d'ouvrir une app
- Un thérapeute ERP doit parfois **aller sur le terrain** avec le patient (coûteux, logistiquement difficile)
- Anchor génère l'environnement d'exposition **à la demande**, **calibré**, **depuis chez soi**
- La voix en temps réel accompagne les 20-40 minutes les plus difficiles

---

## 3. Catégories hackathon

Anchor couvre **deux catégories simultanément** :

### 🗣️ Live Agents (Principal)
- ✅ Gemini Live API — audio bidirectionnel natif
- ✅ Interruptions gérées naturellement
- ✅ Vision comportementale (caméra détecte les compulsions)
- ✅ ADK pour l'orchestration
- ✅ Hébergé sur Google Cloud

### ✍️ Creative Storyteller (Bonus)
- ✅ Interleaved output : audio + image générée dans le même flow
- ✅ Narration immersive synchronisée avec Imagen 3
- ✅ Génération de scénarios d'exposition en temps réel

### Bonus points
- ✅ Terraform (IaC)
- ✅ Cloud Build (CI/CD automatisé)
- ✅ Blog post / contenu à publier

---

## 4. Architecture technique

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                      UTILISATEUR                            │
│           🎤 Audio Live    📷 Caméra (optionnel)            │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket (WSS)
                       │ Audio stream + Video frames
┌──────────────────────▼──────────────────────────────────────┐
│                  CLOUD RUN — FastAPI                         │
│                    websocket.py                              │
└──────┬───────────────┬──────────────────────────────────────┘
       │               │
┌──────▼──────┐ ┌──────▼──────────────────────────────────┐
│ Gemini Live │ │          Google ADK                      │
│ API         │ │                                          │
│             │ │  ┌─────────────────────────────────┐    │
│ Audio natif │ │  │       anchor_agent.py           │    │
│ Vision      │ │  │  State Machine ERP               │    │
│ Interrupts  │ │  │  Intake → Hiérarchie →           │    │
│             │ │  │  Exposition → Timer → Débriefing │    │
└─────────────┘ │  └──────────────┬──────────────────┘    │
                │                 │                         │
                │  ┌──────────────▼──────────────────┐    │
                │  │           ADK Tools              │    │
                │  │  🛡️ reassurance_guard            │    │
                │  │  📋 hierarchy_builder            │    │
                │  │  🖼️ image_generator (Imagen 3)  │    │
                │  │  ⏱️ erp_timer                   │    │
                │  │  📊 session_tracker (Firestore)  │    │
                │  └──────────────────────────────────┘    │
                └─────────────────────────────────────────┘
                       │               │
          ┌────────────▼──┐    ┌───────▼──────────┐
          │  Vertex AI    │    │    Firestore      │
          │  Imagen 3     │    │  Sessions + Progs │
          │  Images expo  │    │                  │
          └───────────────┘    └──────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              FIREBASE HOSTING — React + Vite                 │
│   🎙️ AudioCapture  🖼️ ExposureImage  ⏱️ ERPTimer          │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Stack — Google First

| Besoin | Outil Google | Justification hackathon |
|---|---|---|
| LLM + Audio Live | **Gemini 2.0 Flash** via Google GenAI SDK | Mandatory |
| Agent orchestration | **Google ADK** (Python) | Mandatory |
| Image generation | **Vertex AI Imagen 3** | Google native |
| Database | **Firestore** | Serverless, temps réel |
| Secrets | **Secret Manager** | GCP native |
| Hosting backend | **Cloud Run** | Serverless, Docker |
| Hosting frontend | **Firebase Hosting** | CDN global, gratuit |
| Logs | **Cloud Logging** | Preuve déploiement jurés |
| IaC | **Terraform** | Bonus points |
| CI/CD | **Cloud Build** | Bonus points |
| Container registry | **Artifact Registry** | GCP native |

**Aucun outil externe.** Zéro dépendance non-Google.

---

## 6. Structure du monorepo

```
anchor/
│
├── README.md                        ← Instructions spin-up jurés
├── .env.example                     ← Variables (jamais de secrets)
├── .gitignore
├── docker-compose.yml               ← Dev local
├── cloudbuild.yaml                  ← CI/CD Cloud Build
│
├── terraform/                       ← IaC (bonus points)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                      ← Entrypoint FastAPI
│   │
│   ├── agent/
│   │   ├── anchor_agent.py          ← ADK Agent principal
│   │   ├── tools/
│   │   │   ├── erp_timer.py
│   │   │   ├── image_generator.py   ← Imagen 3
│   │   │   ├── hierarchy_builder.py
│   │   │   ├── session_tracker.py   ← Firestore
│   │   │   └── reassurance_guard.py ← Règle absolue n°1
│   │   └── prompts/
│   │       └── system_prompt.py
│   │
│   ├── api/
│   │   ├── websocket.py             ← Audio ↔ Gemini Live
│   │   └── routes.py
│   │
│   └── services/
│       ├── firestore.py
│       ├── secret_manager.py
│       └── vertex.py                ← Client Imagen 3
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── firebase.json
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── AudioCapture.jsx
│       │   ├── CameraFeed.jsx
│       │   ├── ExposureImage.jsx    ← Affichage image générée
│       │   ├── AnxietyMeter.jsx     ← Slider 0-10
│       │   ├── ERPTimer.jsx
│       │   └── SessionHistory.jsx
│       └── hooks/
│           ├── useWebSocket.js
│           └── useAudioStream.js
```

---

## 7. Flow d'une séance ERP

```
ÉTAPE 1 — INTAKE (vocal)
  Anchor : "Quel est ton TOC principal aujourd'hui ?"
  Utilisateur décrit sa peur à voix haute
  Gemini extrait : type de TOC, déclencheurs, compulsions habituelles

ÉTAPE 2 — HIÉRARCHIE (vocal + texte)
  Anchor génère 10 niveaux d'exposition adaptés au TOC décrit
  Validation vocale avec l'utilisateur : "Ce niveau 5 te semble juste ?"
  Sauvegarde dans Firestore

ÉTAPE 3 — EXPOSITION (interleaved output — moment clé)
  Anchor annonce le niveau : "On commence par le niveau 2."
  → Imagen 3 génère l'image de la situation anxiogène (~2s)
  → Gemini narre vocalement la scène pendant que l'image apparaît
  → Les deux arrivent simultanément sur le frontend

ÉTAPE 4 — TIMER ERP (vocal live)
  ERP Timer lancé : 10-40 minutes selon le niveau
  Coaching vocal progressif :
    "Tu es à combien sur 10 ?"
    "C'est normal que ça monte. La vague a un pic."
    "Tu tiens. Continue."
  Anti-Reassurance Guard actif : toute demande de réassurance → redirection

ÉTAPE 5 — DESCENTE
  L'anxiété redescend naturellement
  Anchor célèbre : "Tu l'as traversée. C'est ça l'ERP."
  Log dans Firestore : { level, anxiety_peak, resistance: true/false, duration }

ÉTAPE 6 — PALLIER SUIVANT
  Si résistance réussie → niveau +1 → nouvelle image générée
  Si échec → même niveau → encouragement + retry
```

---

## 8. System Prompt

### Identité
Anchor est un compagnon de soutien entraîné aux principes TCC/ERP. Pas un médecin. Pas un thérapeute. Un compagnon cliniquement rigoureux.

### Règle absolue n°1 — Ne jamais rassurer

Anchor ne dit **jamais** :
- "Ça va aller"
- "T'inquiète pas, tu n'as pas fait de mal"
- "C'est propre / c'est sûr / c'est bien fermé"

Quand l'utilisateur demande une réassurance :
> *"Je t'entends, et je sais que tu souffres là. Mais tu sais aussi que si je te rassure, ça ne va pas t'aider vraiment. On va traverser ça ensemble autrement."*

### Règle absolue n°2 — Interrompre les spirales

Si l'utilisateur rumine en boucle depuis 2-3 échanges :
> *"Stop. Je t'arrête là. Tu es en train de spiraler et continuer à en parler ne va pas t'aider. On change d'approche. Respire avec moi."*

### Protocoles

**🌊 VAGUE** (crise aiguë)
1. Nommer l'anxiété
2. Ancrage sensoriel (3 choses visibles)
3. Lancer ERP Timer
4. Coaching pendant la montée
5. Célébrer si résistance réussie

**🌬️ RESPIRATION** (début de crise)
Inspire 4 — Retiens 4 — Expire 6 — Répéter 3 cycles

**🔍 OBSERVATION** (vision activée)
Caméra détecte comportement répétitif → ouverture douce, jamais accusatrice

**💬 DIALOGUE SOCRATIQUE** (obsessions cognitives)
- "Qu'est-ce qui se passerait vraiment si tu n'avais pas fait ça ?"
- "Cette pensée, c'est toi ou c'est le TOC qui parle ?"
- "Combien de fois tu as eu cette pensée et il s'est passé quoi ?"

### Tonalité vocale
- Débit lent en crise, normal en conversation
- Pauses de 2-3 secondes après questions difficiles
- Jamais : "Bien sûr !", "Absolument !", "Super !"
- Toujours : "Je t'entends.", "C'est courageux.", "On y est ensemble."

### Phrases clés
- Ouverture : *"Bonjour, je suis Anchor. Je suis là avec toi. Comment tu te sens là, maintenant ?"*
- Clôture : *"Tu as travaillé dur aujourd'hui. Je sauvegarde cette session."*
- Urgence : *"Ce que tu traverses dépasse ce que je peux t'offrir seul. Appelle le 3114."*

---

## 9. ADK Tools

### `reassurance_guard`
```
Input  : output_text (str) — texte que Gemini s'apprête à dire
Output : { allowed: bool, replacement: str | None }
Logique: Si output contient des patterns de réassurance → blocked=True
         Retourne une reformulation ERP à la place
```

### `hierarchy_builder`
```
Input  : toc_description (str), toc_type (str)
Output : { levels: List[{ level: int, situation: str, anxiety_estimate: int }] }
Logique: Gemini génère 10 situations graduées
         Sauvegarde dans Firestore (réutilisable)
```

### `image_generator`
```
Input  : situation (str), level (int), toc_type (str)
Output : { image_url: str, prompt_used: str }
Logique: Construit un prompt Imagen 3 calibré sur le niveau
         Vertex AI Imagen 3 génère l'image
         Retourne l'URL signée GCS
```

### `erp_timer`
```
Input  : level (int), duration_minutes (int)
Output : { timer_id: str, started_at: timestamp }
Logique: Lance un timer côté backend
         Envoie des WebSocket events de coaching toutes les N minutes
         Signal "descente" quand le timer se termine
```

### `session_tracker`
```
Input  : action (str), session_data (dict)
Output : { success: bool }
Actions: "start_session" | "log_level" | "end_session" | "get_history"
Logique: Firestore CRUD sur la collection "sessions"
```

---

## 10. Interleaved Output

Le moment différenciateur de la démo. Quand l'agent passe à une exposition :

```
Timeline (secondes)

t=0    Gemini commence à parler : "On passe au niveau 6..."
t=0.5  image_generator tool lancé en parallèle (Imagen 3)
t=1    Gemini continue la narration pendant la génération
t=2.5  Image reçue → envoyée au frontend via WebSocket
t=2.5  Image apparaît à l'écran pendant que la voix continue
t=4    "Regarde cette scène. Où tu en es sur 10 ?"
t=4    ERP Timer lancé
```

### Exemple concret — TOC contamination niveau 6/10

| Output | Contenu |
|---|---|
| 🔊 Audio | *"On passe au niveau 6. Je vais te montrer une scène. Respire, tu es en sécurité."* |
| 🖼️ Image | Poignée de porte de toilettes publiques, plan rapproché, éclairage réaliste |
| 🔊 Audio | *"Tu vois cette poignée. Elle est là. Tu n'as pas à la toucher, juste à la regarder."* |
| ⚡ Action | ERP Timer 15 min lancé. Anti-Reassurance Guard activé. |
| 💾 Log | `{ level: 6, toc: "contamination", anxiety_peak: 7, resistance: true }` |

---

## 11. Variables d'environnement

```bash
# .env.example

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=europe-west1

# Gemini Live
GEMINI_MODEL=gemini-2.0-flash-live-001

# Vertex AI (Imagen 3)
VERTEX_LOCATION=europe-west1
IMAGEN_MODEL=imagegeneration@006

# Firestore
FIRESTORE_COLLECTION=sessions

# App
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
WEBSOCKET_PATH=/ws/session
```

---

## 12. Ordre de développement

```
Phase 1 — Squelette (2h)
  [ ] Init monorepo + .env.example + .gitignore
  [ ] Backend FastAPI minimal qui tourne (main.py + routes.py)
  [ ] Frontend React + Vite qui s'affiche
  [ ] docker-compose.yml dev local

Phase 2 — Core Agent (4h)
  [ ] anchor_agent.py (ADK) avec system prompt
  [ ] websocket.py — connexion Gemini Live API
  [ ] Audio bidirectionnel qui fonctionne end-to-end
  [ ] Test : parler → Anchor répond

Phase 3 — ADK Tools (3h)
  [ ] reassurance_guard.py
  [ ] hierarchy_builder.py
  [ ] image_generator.py (Vertex AI Imagen 3)
  [ ] erp_timer.py
  [ ] session_tracker.py (Firestore)

Phase 4 — Frontend (2h)
  [ ] AudioCapture.jsx + useAudioStream.js
  [ ] useWebSocket.js
  [ ] ExposureImage.jsx (affichage interleaved)
  [ ] ERPTimer.jsx (visible pendant la séance)
  [ ] AnxietyMeter.jsx (slider 0-10)

Phase 5 — GCP Deploy (2h)
  [ ] Dockerfile backend
  [ ] Cloud Run deployment
  [ ] Firebase Hosting frontend
  [ ] Secret Manager (clés API)
  [ ] Cloud Logging
  [ ] Terraform (main.tf)

Phase 6 — Polish (1h)
  [ ] README.md avec spin-up instructions complètes
  [ ] cloudbuild.yaml
  [ ] Architecture diagram
  [ ] Proof of deployment (screen recording)
```

---

## 13. Déploiement GCP

### Backend — Cloud Run
```bash
# Build et push
gcloud builds submit --tag europe-west1-docker.pkg.dev/$PROJECT_ID/anchor/backend

# Deploy
gcloud run deploy anchor-backend \
  --image europe-west1-docker.pkg.dev/$PROJECT_ID/anchor/backend \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"
```

### Frontend — Firebase Hosting
```bash
npm run build
firebase deploy --only hosting
```

### Terraform (bonus)
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Cloud Build CI/CD
Chaque `git push main` → build automatique → deploy Cloud Run + Firebase

---

## 14. Note clinique

### Ce qu'Anchor n'est pas
- ❌ Un substitut à un suivi thérapeutique
- ❌ Un outil de diagnostic
- ❌ Un agent qui rassure

### Ce qu'Anchor est
- ✅ Un compagnon d'entraînement ERP entre les séances
- ✅ Un outil de psychoéducation sur les TOC
- ✅ Un support pour pratiquer les techniques ERP de façon autonome

### Sécurité
- Si l'utilisateur exprime des idées suicidaires → redirection immédiate vers le **3114** (numéro national prévention suicide France)
- L'agent ne pose jamais de questions d'évaluation du risque lui-même
- Toutes les sessions sont loggées (Firestore) pour un futur suivi professionnel éventuel

---
