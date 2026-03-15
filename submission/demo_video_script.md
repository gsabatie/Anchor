# Anchor — Demo Video Script (< 4 minutes)

> Instructions: Record screen with QuickTime/OBS. Generate voiceover with Google Cloud TTS or NotebookLM. Combine in iMovie/CapCut.

---

## SCENE 1 — The Problem (0:00 – 0:30)

**Screen:** Black background with white text appearing line by line (use CapCut/iMovie text overlays)

**Text on screen:**
> OCD affects 2–3% of the world.
>
> The gold-standard treatment is ERP — Exposure with Response Prevention.
>
> But every AI assistant makes it worse.
>
> They all reassure you.
>
> "It's fine." "Don't worry." "Nothing bad will happen."
>
> Reassurance is itself a compulsion. It feeds the cycle.
>
> I have OCD. I built Anchor because no tool like it existed.

**Voiceover:**
"OCD affects 2 to 3 percent of the world's population. The gold-standard treatment is ERP — Exposure with Response Prevention. But every AI assistant I tried during a crisis made it worse. They all reassure you — 'it's fine', 'don't worry', 'nothing bad will happen'. The problem is, reassurance is itself a compulsion. It feeds the OCD cycle. I have OCD, and I built Anchor because the tool I needed didn't exist."

---

## SCENE 2 — What Anchor Is (0:30 – 0:50)

**Screen:** Show the Anchor app landing screen / UI. Then show the architecture diagram.

**Voiceover:**
"Anchor is a real-time voice agent that guides you through ERP therapy sessions. It listens to you describe your OCD through Gemini Live's bidirectional audio, builds a personalized exposure hierarchy, generates calibrated exposure images with Imagen 4, and coaches you through the anxiety — all in real-time. Everything runs on Google Cloud. Zero external dependencies."

---

## SCENE 3 — Live Demo: Intake (0:50 – 1:30)

**Screen:** Screen recording of you opening Anchor and starting a session. Click the microphone button. Speak to Anchor (or type via TextInput) describing an OCD trigger. Show the transcript appearing in real-time. Show Anchor responding vocally.

**Voiceover:**
"Let me show you a session. I open Anchor and describe my OCD trigger. Gemini Live processes my speech in real-time — you can see the transcript appearing. Anchor responds with follow-up questions to understand the type of OCD, the specific triggers, and the compulsions. Notice the tone — warm but grounded. No 'don't worry', no 'it's fine'."

**[Let Anchor's actual voice play here — reduce voiceover and let the app speak for ~15 seconds]**

---

## SCENE 4 — Live Demo: Hierarchy + Anti-Reassurance (1:30 – 2:10)

**Screen:** Show the hierarchy being generated (10 levels appearing). Then show yourself asking for reassurance — "Tell me it's going to be okay" — and Anchor refusing and redirecting.

**Voiceover:**
"Anchor generates a 10-level exposure hierarchy calibrated to my specific fears — from the least anxiety-provoking to the most intense. Now watch what happens when I ask for reassurance."

**[Let the app play — you say or type "Tell me it's going to be okay" or "Dis-moi que ça va aller"]**

**[Anchor's voice responds with an ERP redirect — let this play naturally for ~10 seconds]**

**Voiceover:**
"This is the key differentiator. The Anti-Reassurance Guard intercepts 170 patterns in French and English across three layers — the system prompt, an ADK tool, and an after-model callback. It refuses to reassure, and redirects toward ERP techniques instead."

---

## SCENE 5 — Live Demo: Interleaved Exposure (2:10 – 3:00)

**Screen:** Show an exposure starting. Anchor announces the level vocally. The Imagen 4 image fades in on screen while the voice continues narrating. Show the anxiety meter slider. Show the ERP timer starting.

**Voiceover:**
"Now the exposure. Anchor announces the level and starts narrating the scene. While it speaks, Imagen 4 generates a calibrated image of the triggering situation — and it appears on screen while the voice continues. This is the interleaved output: audio and image arriving simultaneously."

**[Let Anchor's voice play over the image appearing — ~10 seconds of the actual app]**

**Voiceover:**
"The image intensity is calibrated to the exposure level. Level 2 is a distant, muted shot. Level 8 is a vivid close-up. This mirrors how real therapists graduate in-vivo exposure. The ERP timer starts, and Anchor coaches you through the anxiety wave — checking in, encouraging you to stay with the discomfort, never reassuring."

**[Show the anxiety meter being adjusted, the timer counting down, coaching prompts appearing]**

---

## SCENE 6 — Tech + Safety (3:00 – 3:30)

**Screen:** Show the architecture diagram. Then briefly show the Cloud Run console or backend logs (proof of GCP deployment). Then show a crisis detection moment (optional — can use text overlay instead).

**Voiceover:**
"Under the hood: Gemini 2.5 Flash Live for bidirectional audio, Google ADK for agent orchestration with 5 custom tools, Vertex AI Imagen 4 for exposure images, Firestore for session tracking, all deployed on Cloud Run with Terraform and Cloud Build CI/CD. A separate Crisis Guard monitors every message for suicidal ideation in real-time and immediately redirects to the 3114 — France's suicide prevention hotline."

---

## SCENE 7 — Closing (3:30 – 3:50)

**Screen:** Anchor logo / name centered. Then text: "Built for the Google Hackathon 2025 — Live Agents & Creative Storyteller"

**Voiceover:**
"Anchor is the agent that refuses to do what you ask — and helps you because of it. It's the tool I needed and couldn't find. Built entirely on Google Cloud, for the people who need it most."

**[Fade to black]**

---

## Production Notes

- **Total runtime target:** 3:50 (under the 4-minute limit)
- **Let the app speak:** Scenes 3, 4, and 5 should include Anchor's actual voice from Gemini Live. Lower the voiceover and let the app audio play. This proves it's real, not a mockup.
- **Screen recording:** Use QuickTime (Cmd+Shift+5 on Mac) or OBS. Record at 1080p minimum.
- **Voiceover generation:** Paste each scene's voiceover text into Google Cloud TTS or NotebookLM. Use a calm, steady voice.
- **Editing:** iMovie (free on Mac) or CapCut (free) for combining screen recording + voiceover + text overlays.
- **Music:** Optional low ambient background music. Keep it minimal — the app's voice is the star.
