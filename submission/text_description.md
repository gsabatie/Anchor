# Anchor — AI-Powered ERP Therapy Companion for OCD

> Real-time voice agent for Exposure with Response Prevention sessions guided by generative AI
>
> Google Hackathon 2025 — Live Agents & Creative Storyteller

---

## Inspiration

I have OCD. That's where Anchor started — not from a product idea, but from lived experience.

The cycle is exhausting: an intrusive thought triggers anxiety, which triggers a compulsion, which brings temporary relief — until the anxiety comes back stronger. The gold-standard treatment is ERP (Exposure with Response Prevention), where you gradually face your fears without performing rituals, teaching your brain that the feared outcome doesn't happen. It works. But access is the problem — ERP therapists are scarce, expensive, and sessions are limited to once a week. The hardest moments happen in between, when you're alone.

I tried using AI assistants during crises. Every single one made it worse. They all reassure you — "it's fine", "don't worry", "nothing bad will happen" — and reassurance is itself a compulsion for OCD. Every reassuring answer feeds the cycle. I needed the opposite: an agent that is warm and present but clinically rigorous enough to *refuse* to reassure me.

That's what Anchor is. A tool I built because it didn't exist, for a problem I face every day. Gemini Live's real-time voice makes it feel like having a coach next to you during a crisis. Imagen 4 brings the exposure environment to you — calibrated, safe, and available anytime.

---

## What it does

Anchor is a real-time voice agent that conducts full ERP therapy sessions through six phases:

1. **Intake** — Listens to the user describe their OCD triggers through natural conversation via Gemini Live's bidirectional audio.
2. **Hierarchy building** — Generates a personalized 10-level exposure ladder using Gemini Pro, calibrated to the user's specific fears.
3. **Interleaved exposure** — Simultaneously narrates the exposure scene vocally while Imagen 4 generates a calibrated image of the anxiety-triggering situation, both arriving on the frontend together.
4. **Live coaching** — Accompanies the user through the anxiety wave with progressive coaching, timed check-ins, and anxiety tracking (0–10 scale).
5. **Descent** — Celebrates resistance when anxiety drops naturally, reinforcing the ERP learning loop.
6. **Session tracking** — Logs progress, anxiety peaks, and compulsion resistance in Firestore for longitudinal follow-up.

**The key differentiator:** Anchor is the only AI agent designed to **refuse** what the user asks for — and be clinically correct in doing so. The Anti-Reassurance Guard intercepts 170+ reassurance patterns in French and English through three layers: system prompt, ADK tool, and `after_model_callback`. A separate Crisis Guard detects suicidal ideation in real-time and immediately redirects to France's 3114 suicide prevention hotline.

---

## How we built it

**Architecture:** A React 19 frontend (Firebase Hosting) connects via WebSocket to a FastAPI backend (Cloud Run), which manages a Gemini Live session with bidirectional audio and tool calling through Google ADK.

**The agent** is built with Google ADK's `LlmAgent`, using 5 custom tools:
- `reassurance_guard` — 170+ pattern matching (substring + regex) in French & English, with rotating ERP-appropriate redirects
- `hierarchy_builder` — Calls Gemini Pro to generate 10-level exposure ladders, cached in Firestore
- `image_generator` — Vertex AI Imagen 4 with intensity bands calibrated per level (wide-angle muted at level 1, extreme close-up hyper-realistic at level 10)
- `erp_timer` — Progressive coaching schedule with phased prompts (opening, rising, peak, falling, closing)
- `session_tracker` — Firestore CRUD for session lifecycle and progress history

**The interleaved output** (Creative Storyteller): when an exposure starts, the agent calls `image_generator` while continuing to narrate vocally. The image generates in ~2–3s and arrives on the frontend via WebSocket while the voice keeps coaching. Background pre-generation of the next 1–2 levels eliminates latency on progression.

**Voice tuning:** We configured Gemini Live with `END_SENSITIVITY_LOW` on the VAD so the model waits through anxious pauses of 3–5 seconds without cutting the user off — critical for therapy where silence is part of the process.

**Infrastructure:** Terraform provisions Cloud Run, Firestore, Secret Manager, IAM, and API enablement. Cloud Build runs a 7-step CI/CD pipeline on every push to main.

| Layer | Google Service |
|---|---|
| Real-time voice | Gemini 2.5 Flash Live API (bidirectional audio, native VAD) |
| Agent framework | Google ADK (LlmAgent, tool declarations, after_model_callback) |
| Hierarchy generation | Gemini 2.5 Pro (structured ERP output) |
| Exposure images | Vertex AI Imagen 4 (intensity-calibrated by exposure level) |
| Database | Firestore (sessions, hierarchies, progress tracking) |
| Secrets | Google Secret Manager |
| Backend hosting | Cloud Run (FastAPI + WebSocket) |
| Frontend hosting | Firebase Hosting (React 19 + Vite) |
| Infrastructure as Code | Terraform (Cloud Run, Firestore, APIs, IAM, Secret Manager) |
| CI/CD | Cloud Build (7-step pipeline) |

**Zero external dependencies.** Every service is Google Cloud native.

---

## Challenges we ran into

**Making an LLM *not* reassure.** LLMs are trained to be helpful, and reassurance *feels* helpful. One layer of defense wasn't enough — the model kept finding creative ways to be reassuring. We ended up needing three layers: the system prompt, the `reassurance_guard` tool checking output, and an `after_model_callback` intercepting raw model responses at the framework level. Even then, subtle edge cases slip through ("you're doing great" vs. "that was courageous effort"). Calibrating the 170+ patterns without false positives on legitimate therapeutic language (like "the timer is done") required careful regex tuning.

**Gemini Live transcription noise.** Native audio transcription from Gemini includes `<noise>` tags, stray non-Latin characters from misrecognition, and very short meaningless fragments. We had to build a cleaning pipeline (regex-based tag removal, character whitelisting, minimum length filtering) while keeping the raw text available for the Crisis Guard — because safety checks must run on unprocessed input.

**WebSocket drops during anxiety peaks.** A connection drop mid-exposure session isn't just a UX annoyance — it's clinically harmful. Losing context when someone is at peak anxiety could cause real distress. We built reconnection with exponential backoff (1s, 2s, 4s, 3 retries) and session state re-injection: on reconnect, the agent sends the current ERP phase, exposure level, and recent anxiety readings back to Gemini so it picks up exactly where it left off.

**Imagen safety filters vs. therapeutic content.** ERP requires generating images of situations that trigger anxiety — dirty surfaces for contamination OCD, unlocked doors for checking OCD. Some of these legitimately trigger Imagen's safety filters. We tuned `safety_filter_level` to `block_few` and crafted prompts that describe everyday situations realistically without crossing into genuinely harmful content. The negative prompt blocks gore, violence, and other non-therapeutic imagery.

**VAD sensitivity for anxious speech.** Default voice activity detection cuts speakers off after short pauses. But people in an anxiety crisis pause frequently — 3 to 5 seconds of silence while they gather courage. We configured `END_SENSITIVITY_LOW` so Gemini waits through these pauses instead of interrupting, which completely changed the feel of the interaction.

---

## Accomplishments that we're proud of

**The Anti-Reassurance Guard actually works.** Building an AI agent that consistently refuses to do what humans instinctively want it to do — reassure — felt almost paradoxical. The three-layer defense (system prompt + ADK tool + after_model_callback) catches the vast majority of reassurance patterns while still allowing warm, empathetic therapeutic language. The rotating redirect responses feel natural rather than robotic.

**Interleaved audio + image is genuinely immersive.** When the agent says "I'm going to show you a scene... breathe..." and the Imagen-generated exposure image fades in while the voice continues coaching, it creates an experience that feels closer to real in-vivo ERP than anything text-based could achieve. Background pre-generation of upcoming levels makes the progression seamless.

**The Crisis Guard runs on raw transcription.** Safety-critical detection doesn't wait for clean text. If someone expresses suicidal ideation mid-sentence with background noise, the system catches it immediately and surfaces the 3114 redirect. This was a deliberate architectural decision — the crisis pipeline is separate from and runs before the display pipeline.

**100% Google Cloud, zero external dependencies.** Every single service — from voice to image generation to database to CI/CD — runs on Google Cloud. No third-party APIs, no external dependencies, no vendor lock-in surprises.

**Clinically grounded design.** Every feature maps to a real ERP protocol: the exposure hierarchy mirrors clinical practice, the intensity calibration matches how therapists graduate in-vivo exposure, the anti-reassurance rule is the single most important principle in OCD treatment, and the Socratic dialogue prompts come from established CBT methodology.

---

## What we learned

**Anti-reassurance is a design principle, not a feature.** We started by treating it as a filter. We ended up realizing it needs to be embedded at every level — the prompt, the tools, the callbacks, even the choice of celebratory phrases ("that was courageous effort" instead of "great job"). It changed how we think about alignment: sometimes the most helpful thing an AI can do is refuse to help in the way the user expects.

**Voice-first changes everything for mental health.** OCD crises don't happen at a desk with a keyboard. They happen at the door, at the sink, in the car. Gemini Live's bidirectional audio with configurable VAD sensitivity makes the agent feel like a coach standing next to you. The low end-of-speech sensitivity — waiting through anxious silences — was a small configuration change with massive UX impact.

**Image calibration is clinical calibration.** Showing a hyper-realistic close-up of a contamination trigger at level 1 would be counterproductive. The intensity band system (mapping exposure levels to camera distance, color saturation, framing) mirrors how real therapists graduate exposure. Level 2 is a muted wide-angle shot; level 9 is a vivid close-up. The technical parameter maps directly to clinical methodology.

**Reconnection isn't optional in therapeutic contexts.** In a standard chat app, a dropped connection is annoying. In a therapy session at peak anxiety, it's harmful. Building robust reconnection with state re-injection wasn't a nice-to-have — it was a clinical requirement that shaped our entire WebSocket architecture.

**Google ADK's callback system is powerful for safety.** The `after_model_callback` pattern — intercepting model output before it reaches the user — turned out to be the most reliable layer of the anti-reassurance system. It catches things the system prompt and tools miss, acting as a final safety net. This pattern could apply to any domain where certain model outputs must be prevented.

---

## What's next for Anchor

**Therapist dashboard.** Firestore already logs every session (exposure levels, anxiety peaks, compulsion resistance). The next step is a web dashboard where licensed therapists can review their patients' between-session ERP practice, see longitudinal progress, and adjust the hierarchy remotely.

**Vision-based compulsion detection.** The camera feed component is stubbed in the frontend. Using Gemini's vision capabilities, Anchor could detect repetitive behaviors (hand washing, checking, counting) in real-time and gently open a conversation about what's happening — not accusatory, just curious.

**Multi-language support.** The reassurance guard and crisis guard already cover French and English. Extending to Spanish, German, and Arabic would dramatically increase reach. Each language requires culturally adapted patterns — reassurance doesn't sound the same in every culture.

**Longitudinal adaptation.** Using session history from Firestore, Anchor could adapt its approach over time — remembering which exposure levels were hardest, which Socratic questions were most effective, and progressively challenging the user based on their actual trajectory rather than a generic ladder.

**Clinical validation study.** Partner with OCD research centers to conduct a controlled study comparing ERP practice with Anchor vs. standard between-session homework. The Firestore logs provide all the quantitative data needed for analysis.
