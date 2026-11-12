# video make

**From a reference transcript to a finished, narrated documentary for YouTube, plus thumbnails, vertical Shorts and a publishing schedule.**

`video make` is a resumable, file-based pipeline written in Python (orchestration, LLM, TTS, media search, publishing) and [Remotion](https://www.remotion.dev) (React, rendering). You give it the transcript of a video that worked well; it analyses *why* it worked, writes a new original script on the same structure, narrates it, picks or generates an image or clip for every scene, renders the video, and prepares everything to publish.

> 🇧🇷 The prompts, `config.yaml` and most code comments are in **Brazilian Portuguese**, because the channel this was built for is Brazilian. Nothing is hard-wired to that: swap the prompts in [`prompts/`](prompts) and the channel settings in [`config.yaml`](config.yaml) to adapt it to another niche or language. A shorter Portuguese README lives in [README.pt-BR.md](README.pt-BR.md).

---

## Table of contents

1. [What it produces](#what-it-produces)
2. [How it works](#how-it-works)
3. [Quick start](#quick-start)
4. [The stages in detail](#the-stages-in-detail)
5. [Scene templates](#scene-templates)
6. [Data files and formats](#data-files-and-formats)
7. [Configuration reference](#configuration-reference)
8. [External services](#external-services)
9. [Publishing](#publishing)
10. [Architecture](#architecture)
11. [Extending it](#extending-it)
12. [Troubleshooting](#troubleshooting)
13. [What is not in this repository](#what-is-not-in-this-repository)
14. [License](#license)

---

## What it produces

For one project (`projetos/<name>/`) a full run gives you:

| Output | What it is |
|---|---|
| `video_final.mp4` | 1920×1080 narrated video, 30 fps, loudness-normalised |
| `legendas.srt` | subtitles timed from the narration (word timings from the Whisper alignment when available) |
| `youtube.txt` | 3 titles (A/B/C), description, chapters with timestamps, 15+ tags, sources, media credits, an AI-content warning when needed |
| `thumbs/thumb_{A,B,C}.png` | three 1280×720 thumbnails for YouTube's "Test & compare" |
| `shorts/short_01..03.mp4` | 1080×1920 vertical cuts (30–60 s) with big captions, a hook, subscribe CTA and end question, plus two covers each |
| `publicar/` | everything ready to upload, numbered in posting order, with the title in the file name |

---

## How it works

```
reference                                                                    
transcript ─► [analise] ─► [roteiro] ─► [cenas] ─► [narracao] ─► [midia] ─► [video]
(.txt or      structure,    new script   scene-by-   voice per     photo or   Remotion +
 YouTube      hooks,        + anti-copy  scene visual scene, merged clip or AI  ffmpeg mix
 link)        retention     check        plan        into 1 WAV    image      
                                                                                │
                              [shorts] ◄── [publicacao] ◄──────────────────────┘
                              3 vertical   3 titles + 3 thumbs + description + tags
                              cuts + covers
                                   │
        standalone (only with --so):  youtube · instagram · metricas · tendencias
```

Design principles:

- **State lives in files, every stage is idempotent.** Each stage writes its output to `projetos/<name>/` and is **skipped if that output already exists**. To redo a stage, delete its file and run again. Everything between stages is plain text or JSON, so you can review and hand-edit at any point (the script and `cenas.json` are the best places).
- **Cheap invalidation.** Renders, narration and covers are cached by hash (`*.sha1`, `assinatura` fields). Edit one scene's text and only that scene is re-narrated; edit a template and only affected chapters are re-rendered.
- **A human can always step in.** The LLM stage has a *manual mode* (below), and `--ate <stage>` stops after any stage so you can review before spending money on voice and render.
- **Graceful degradation.** Every optional service has a fallback: no GPU box → macOS voice and first stock-photo candidate; no Whisper → narration without verification; no stock keys → Wikimedia Commons only.
- **Nothing is published without `--confirmar`.** Upload stages print a schedule by default and only talk to YouTube/Instagram when you pass the flag.

---

## Quick start

### Requirements

- Python 3.11+
- Node.js 20.19+ (or 22.13+ / 24+) and `ffmpeg` (with `ffprobe`)
- Optional: `yt-dlp` (to use a YouTube URL as the reference), a Claude API key, a Gemini API key, a GPU machine running ComfyUI, a Whisper HTTP service, Google OAuth credentials (YouTube), Telegram bot, Zernio account (Instagram)

### Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd render && npm install && cd ..
cp .env.example .env     # fill in only what you will use
```

### Run

```bash
.venv/bin/python run.py \
  --referencia transcript.txt \
  --modo novo_angulo \
  --tema "your angle" \
  --projeto my-video
```

Useful variations:

```bash
# stop after the scene plan, to review before paying for voice and render
.venv/bin/python run.py --projeto my-video --ate cenas

# keep going later (finished stages are skipped)
.venv/bin/python run.py --projeto my-video

# redo only titles + thumbnails
.venv/bin/python run.py --projeto my-video --so publicacao

# show the YouTube schedule, then actually upload
.venv/bin/python run.py --projeto my-video --so youtube
.venv/bin/python run.py --projeto my-video --so youtube --confirmar
```

Preview and tweak the templates with the Remotion Studio: `cd render && npx remotion studio`.

### CLI reference

| Flag | Meaning |
|---|---|
| `--referencia` | `.txt` transcript or a YouTube URL (captions fetched with `yt-dlp`). Saved to the project on first use. |
| `--modo` | `novo_angulo` (same subject, new angle), `outro_tema` (reuse only the skeleton, new subject), `aprofundar` (one excerpt becomes the whole video). Saved in `projeto.json`. |
| `--tema` | the angle/subject (saved) |
| `--duracao` | target length in minutes (saved; default `video.duracao_alvo_min`) |
| `--formato` | `programa` (TV-show structure) or `documentario` (continuous) (saved) |
| `--lugar` | where the story happens, in English (e.g. `"São Paulo, Brazil"`); steers image searches and makes the vision model reject pictures from other countries (saved) |
| `--projeto` | project slug; default derived from the topic or file name |
| `--ate <etapa>` | last stage to run (`analise roteiro cenas narracao midia video publicacao shorts`) |
| `--so <etapa>` | run only this stage; also enables `youtube instagram metricas tendencias` |
| `--confirmar` | with `--so youtube` / `--so instagram`: really upload |
| `--inicio` | first day of the schedule (`YYYY-MM-DD`) |
| `--reagendar ITEM=DATE…` | change the date of already-uploaded items (e.g. `short_01=2026-10-28T18:00`) |
| `--substituir ITEM…` | re-upload items on the same date and delete the old upload afterwards |
| `--itens ITEM…` | restrict upload/commenting to these items |
| `--voz` | force a TTS provider: `google comfyui openai elevenlabs macos` |

---

## The stages in detail

### 0. `analise` — understand the reference (`pipeline/referencia.py`)

1. **Import.** The transcript is copied to `referencia.txt`. If you pass a URL, `yt-dlp` downloads Portuguese captions and converts VTT into `time` + `text` lines. Plain text without timestamps also works.
2. **Segment.** Lines are grouped into `{t, texto}` segments; noise like `[music]` is stripped.
3. **LLM analysis** ([`prompts/analise_referencia.md`](prompts/analise_referencia.md)). The model extracts the narrative `beats`, retention techniques, CTAs, hooks and a *generic structure*. Output: `referencia.json`. A reusable mould is also saved in `estruturas/<project>.json`.

The retention techniques and hooks found here are later reused to pick Shorts that follow what already went viral.

### 2. `roteiro` — write an original script (`pipeline/roteiro.py`)

- Prompt: [`prompts/roteiro_adaptacao.md`](prompts/roteiro_adaptacao.md), filled with the analysis, the mode, the theme, a word target (`duracao × palavras_por_minuto`) and the number of chapters.
- **Anti-copy check.** The new script is compared with the reference by (a) the longest identical run of words (`adaptacao.max_ngram_igual`, default 8) and (b) the fraction of repeated 5-word shingles (`max_sobreposicao`, default 10%). If it fails, [`prompts/reescrita.md`](prompts/reescrita.md) is called with the offending passages, up to `tentativas_reescrita` times. If it still fails, the stage stops and asks you to edit `roteiro.md` by hand. The result is in `similaridade.json`.
- **TV-show format.** With `video.formato: programa` an extra block is added to the prompt: chapter 1 is a 45–75 s *opening* (a concrete in-progress scene, then 3–4 short "teaser" lines announcing the strongest moments), each following chapter is a *block* with a name, ends with a "coming up" line, and starts with a "welcome back" line. Like/subscribe requests never go in the opening.
- Output: `roteiro.md` (Markdown: `# title`, `## chapter`, `## Sources`) and `roteiro.json`.

### 3. `cenas` — storyboard (`pipeline/decupagem.py`)

The LLM ([`prompts/decupagem.md`](prompts/decupagem.md)) splits the script into scenes of 12–22 words (≈ 5–9 s) and decides each one's visual. For every scene it gives:

- `texto` — the narration, **word-for-word**. The code verifies that concatenating all `texto` reproduces the script (similarity ≥ 98%) and fails otherwise.
- `tipo` — one of the [scene templates](#scene-templates) and the data it needs.
- `busca` — 2–4 short stock-photo queries in English, specific → generic.
- `prompt_imagem` — a 20–40 word description of a realistic photograph, used if stock search fails. Written without negations (image generators draw what you mention).
- `preferencia` — `video`, `foto`, or `ia` (hypothetical/microscopic scenes that no stock library has).
- `overlay` — optional chapter title, TV-show teaser ("escalada") or lower-third.
- `cta` — marks scenes where the narration asks for a subscribe/like/comment (used to time the on-screen button).

Invalid template data (e.g. a chart with 8 points) is downgraded to a plain `midia` scene instead of crashing. With `--lugar`, the first search of every location scene carries the city or country name.

### 4. `narracao` — voice (`pipeline/tts.py`)

One audio file per scene, merged into `narracao.wav`; each scene gets `inicio` and `duracao` (seconds). Key mechanisms:

- **Providers** (`tts.provedor: auto` picks the first available, in this order): Google Gemini TTS, ChatterBox through ComfyUI, ElevenLabs, OpenAI, macOS `say`. Force one with `--voz`. Each writes to its own folder (`audio/google/`, `audio/comfyui/`…), so voices are never mixed in one video.
- **Prosody pass** (`tts.prosodia: true`, Google only). Before narrating, the LLM ([`prompts/prosodia.md`](prompts/prosodia.md)) writes a "spoken version" of each scene into `falas.json`: tags like `<short pause>`, `<sigh>`, `<chuckle>`, punctuation for rhythm, and one or two ALL-CAPS emphasis words. The words may **not** change (otherwise that scene falls back to the original text). Rules learned the hard way are baked in: at most one `<breath>` per ~170 words, tags never at the end of a line (they would be read aloud).
- **Pronunciation map** (`tts.pronuncia`): `Stanford: Stênford` changes what the voice says while subtitles keep the original spelling.
- **Block narration** (`tts.google.blocos: true`). Instead of one request per scene, up to ~700 words (≈ 5 min, never crossing chapters) are narrated in one request for continuous intonation and far fewer API calls. The audio is then cut per scene using Whisper word timings, keeping the voice's natural pauses between scenes. Each scene is verified after cutting and a bad block is regenerated.
- **Verification** (`tts.conferencia`). The Whisper service aligns the audio with the expected text and reports mismatches. A scene with more than 12% wrong words (`wer_maximo`) is regenerated (new seed where the voice varies). Alignments that look guessed (words under 30 ms) trigger a second, hint-free transcription to confirm the error and rebuild per-word timings for subtitles.
- **Quota handling.** Free-tier Gemini quota (10 requests/day/model) falls through the `modelos` list *only before the video starts* — the chosen model is saved in `audio/google/modelo.txt` so the voice never changes mid-video. If every model is exhausted, the *whole* video is narrated by the `reserva` voice (ComfyUI) or the run stops (`reserva: esperar`). Finished blocks are kept: re-running continues where it stopped. On the paid tier (`pago: true`) a 429 is a per-minute limit and the code waits and retries on the same model.
- **Pauses.** `pausa_cena` between scenes, `pausa_capitulo` between chapters, 1.5 s at the end. In TV-show mode the silence at the end of an opening/block is extended by the jingle (`vinheta_seg`) or the block card (`placa_seg`).

### 5. `midia` — pick visuals (`pipeline/midia.py`)

For each scene (and each step of a `fluxo`):

1. **Candidates** from stock providers in `midia.provedores` order (Pixabay, Pexels, Wikimedia Commons). Providers without a key are skipped; requests are rate-limited and retried on 429/5xx. Video is preferred for action scenes, photos for objects/people/science.
2. **Vision scoring.** With ComfyUI online and `midia.visao: true`, **Qwen3-VL 8B** looks at each candidate and the narration and gives a 0–10 score; the best wins. Without it, the first candidate is used.
3. **AI image fallback.** If nothing reaches `nota_minima` (default 6), or the scene says `preferencia: "ia"`, **Z-Image Turbo** generates a realistic 16:9 photo from `prompt_imagem`.

Files go to `media/`, attribution to `creditos.json`. AI-generated images are tracked so `youtube.txt` warns you to tick "altered or synthetic content" in YouTube Studio (the API upload sets the flag itself).

Optional helpers: `pipeline/previa.py` runs media in parallel with narration on a copy (`<project>-midia`) and merges it back; `pipeline/revisao_web.py` serves a local page where you approve or replace each scene's media by hand before rendering.

### 6. `video` — render and mix (`pipeline/montagem.py`)

- **Visual.** One Remotion render per chapter (composition `Documentario`), cached by a SHA-1 of the props, the template source and the *modification time* of every referenced media file. Frame timings are computed without cumulative rounding error. `video.render_concorrencia` and `render_timeout_seg` tame memory use.
- **Audio** is mixed with ffmpeg: narration + background music (`musica.volume`, default 0.12; generated with ACE-Step 1.5 if `assets/musica/` is empty) + synthesised sound effects + jingle and block-card sounds in TV-show mode, then a two-pass `loudnorm`.
- **Sound effects** (`pipeline/sfx.py`) are synthesised in ffmpeg (no voices, no licensing): hits for big-number / punch-line / headline reveals (at least 30 s apart, highest priority wins) and soft "whooshes" on scene cuts, placed only inside real pauses of the speech. Drop `assets/sfx/<name>.wav` to replace a sound; set `"sfx": false` on a scene to silence it.
- **Outputs**: `video_final.mp4`, `legendas.srt`, `youtube.txt` (title, chapters with times, sources, media credits).

### 7. `publicacao` — titles and thumbnails (`pipeline/publicacao.py`)

The LLM ([`prompts/publicacao.md`](prompts/publicacao.md)) proposes three title/thumbnail pairs with different angles — **A** curiosity, **B** the most striking fact or number, **C** consequence or benefit — plus a description whose first sentence uses real search terms, 15–25 tags, and 3 topical hashtags. Thumbnails (`Thumbnail` composition) are huge 2–4 word text with a highlighted word and optional badge on top of the best scene image or an AI-generated one. The decision is saved in `publicacao.json`; edit it and re-run `--so publicacao` to change a text or an image.

### 8. `shorts` — vertical cuts (`pipeline/shorts.py`)

The LLM ([`prompts/shorts.md`](prompts/shorts.md)), informed by the reference's hooks, picks `shorts.quantidade` cuts ranked by a viral score. Each cut has an optional **hook** (one short scene played first) and a **body** of consecutive whole scenes; validation enforces durations and scene boundaries. Each is rendered at 1080×1920 (`Short` composition) with the media full-screen (templates appear in a window in the middle), a fixed headline on top, large 3-word caption blocks highlighting the spoken word, an animated "subscribe" button with a synthesised chime, and, optionally, a **spoken closing question** ("What did you think of…? Tell us below") narrated with the same voice and model as the video. The audio is cut from the already-mixed long video and re-normalised. Two vertical covers (A and B) per Short use the `CapaShort` composition. Output: `shorts/` and `shorts/shorts.txt` (title, description, hashtags).

At the end of `publicacao` and `shorts`, [`pipeline/entrega.py`](pipeline/entrega.py) collects everything into `publicar/`.

---

## Scene templates

Implemented in [`render/src/templates`](render/src/templates). The storyboard picks one per scene following [`prompts/decupagem.md`](prompts/decupagem.md).

| Type | What it shows | Data it needs |
|---|---|---|
| `midia` | full-screen photo (slow zoom) or video; optional chapter title / teaser / lower-third | `busca`, `prompt_imagem` |
| `frase_impacto` | a short punch line on a dark screen, key words highlighted | `frase.texto`, `destaque`, `rotulo` |
| `grafico` | animated line or bar chart (2–6 points) using only numbers said in the narration | `grafico.pontos`, `unidade`, `formato` |
| `numero_destaque` | a huge number that counts up, over a darkened image | `numero.numero`, `texto` |
| `split_topicos` | image on the left, title and 2–4 bullets on the right | `split.titulo`, `topicos` |
| `fluxo` | 2–4 steps with pictures linked by arrows | `fluxo.etapas[]` |
| `manchete` | full-screen image with a news-style headline | `manchete.titulo`, `subtitulo` |

Other building blocks: `Vinheta` (channel jingle), `PlacaBloco` ("BLOCK N" card), `ASeguir` ("coming up" strip), `Escalada` (opening teaser), `SeloInscricao` (subscribe seal), `LowerThird`, `TituloCapitulo`. Brand colours come from `visual.*` in `config.yaml`; brand name placeholders (`SEU CANAL`) live in `render/src/Marca.tsx`, `Vinheta.tsx` and `PlacaBloco.tsx`.

---

## Data files and formats

Everything for one video lives in `projetos/<slug>/`:

```
referencia.txt / referencia.json   input transcript and its analysis
projeto.json                       mode, theme, duration, place, format
roteiro.md / roteiro.json          script
similaridade.json                  anti-copy report
cenas.json                         storyboard (+ timings after narration, + media after midia)
falas.json                         "spoken" text with prosody tags
audio/<provider>/…                 one WAV per scene or block, plus verification JSON
narracao.wav                       whole narration
media/ , creditos.json             chosen media and attribution
render/                            per-chapter renders (+ .sha1 caches)
video_final.mp4 , legendas.srt , youtube.txt
publicacao.json , thumbs/          titles, thumb decisions and PNGs
shorts.json , shorts/              cuts and rendered Shorts
youtube.json                       what was already uploaded (never uploads twice)
publicar/                          ready-to-post package
prompts/                           (manual mode) prompts waiting for your answer
```

A scene in `cenas.json` looks like this (abridged):

```json
{
  "id": 14, "capitulo": 2,
  "texto": "Em menos de dez horas, a enzima desmontou noventa por cento do plástico.",
  "tipo": "numero_destaque",
  "numero": {"numero": "90%", "texto": "do plástico desmontado em dez horas"},
  "busca": ["plastic degradation enzyme", "laboratory petri dish"],
  "prompt_imagem": "realistic documentary photograph of a laboratory ...",
  "preferencia": "foto", "overlay": null, "cta": false,
  "inicio": 61.4, "duracao": 7.1,
  "midia": {"tipo": "imagem", "src": "media/cena_014.jpg"}
}
```

### Manual LLM mode

If there is no `ANTHROPIC_API_KEY` (or `llm.provedor: manual`), each LLM stage writes its prompt to `projetos/<slug>/prompts/<stage>.md` and stops (exit code 2). Paste it into Claude (claude.ai or Claude Code), save the full answer to the file the message names (`<output>.resposta`), and run the same command again. Good for trying the whole thing without an API key, or for reviewing each step.

---

## Configuration reference

All tunables live in [`config.yaml`](config.yaml) (secrets never do — they go in `.env`). Main sections:

| Section | What it controls |
|---|---|
| `video` | target length, words/minute (sizes the script), resolution, fps, `formato` (`programa`/`documentario`), render concurrency and per-frame timeout |
| `programa` | TV-show structure: jingle and block-card length, "coming up" strip, minutes per block, jingle sounds folder |
| `sfx` | sound-effect volume, spacing, scene-cut whooshes |
| `llm` | `provedor` (`auto`/`anthropic`/`manual`), model, reasoning effort |
| `tts` | provider, pauses, verification (WER limit, retries), pronunciation map, prosody, Google (models, voice, blocks, paid mode, fallback), ComfyUI, OpenAI, ElevenLabs, macOS |
| `midia` | provider order, candidates per scene, vision scoring on/off, minimum score, AI image generation |
| `adaptacao` | anti-copy limits and rewrite attempts |
| `visual` | accent/background/text colours, subscribe-seal mode, transition frames |
| `musica` | background track, volume, ACE-Step prompt, BPM, key |
| `shorts` | count, min/max seconds, subscribe CTA, closing question |
| `tendencias` | trending-video search terms, filters (days, views, length, categories) |
| `youtube` | channel guard, time zone, release times, category, language, description footer |
| `instagram` | account guard, time, cover, caption call-to-action, hashtags |
| `publicacao.comentario_manual` | optional call-to-action comment posted on every upload (off by default) |

---

## External services

All optional; each has a fallback.

| Service | Env var | Used for | Without it |
|---|---|---|---|
| Claude API | `ANTHROPIC_API_KEY` | analysis, script, storyboard, prosody, titles, Shorts | manual mode |
| Google Gemini TTS | `GEMINI_API_KEY` (+ `GEMINI_API_KEY_GRATIS`) | default narration voice | ComfyUI → paid APIs → macOS |
| ComfyUI on a GPU box | `COMFY_URL` | ChatterBox voice, ACE-Step music, Qwen3-VL scoring, Z-Image Turbo, MiniMax image-to-video | macOS voice, no scoring, first candidate, no AI images |
| Whisper HTTP service | `ANALISE_URL` | verifies speech, gives word timings for subtitles | narration without verification |
| OpenAI / ElevenLabs | `OPENAI_API_KEY` / `ELEVENLABS_API_KEY` | alternative voices | — |
| Pexels / Pixabay | `PEXELS_API_KEY` / `PIXABAY_API_KEY` | stock photos and videos | Wikimedia Commons only |
| YouTube Data + Analytics | `credenciais/youtube_client.json` | scheduling, metrics, trends | skip publishing |
| Telegram bot | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | notifications when a run finishes, stops or fails | silent |
| Zernio | `ZERNIO_API_KEY` | Instagram Reels | skip |

### ComfyUI

[`workflows/comfy/`](workflows/comfy) holds ComfyUI workflows exported in **API format**, each with a `<name>.manifest.json` mapping parameters to node inputs and naming the output node:

```json
{"inputs": {"text": "2.inputs.text", "seed": ["94.inputs.seed", "3.inputs.seed"]},
 "output": {"node": "3", "kind": "audio"}}
```

`pipeline/comfy.py` submits the graph, polls for completion and downloads the result. Workflows included: `narracao_ptbr_voz` (ChatterBox multilingual), `musica_ace15` (ACE-Step 1.5), `visao_qwen3vl`, `imagem_zimage`, `video_minimax_i2v`. Run ComfyUI with `--listen 0.0.0.0` so another machine can reach it, install the custom nodes/models the workflows reference, and set `COMFY_URL`. The voice reference WAV goes in `assets/vozes/` and is uploaded to ComfyUI automatically.

### Whisper HTTP service contract

The verification service is not part of this repo, but the contract is small. Point `ANALISE_URL` at anything that implements it (e.g. a thin FastAPI wrapper around `faster-whisper`/WhisperX that can read local paths):

| Endpoint | Request | Response |
|---|---|---|
| `GET /health` | — | `200` when ready |
| `POST /align` | `{"path": "/abs/file.wav", "text": "expected text", "language": "pt"}` | `{"words": [{"text", "startMs", "endMs"}], "mismatches": [{"expected", "heard"}]}` |
| `POST /transcribe` | `{"path": "/abs/file.wav", "language": "pt"}` | `{"text": "...", "words": [{"text", "startMs", "endMs"}]}` |

### YouTube setup

1. In Google Cloud, create a project, enable **YouTube Data API v3** (and **YouTube Analytics API** for metrics), create an OAuth client of type *Desktop app*, and save it as `credenciais/youtube_client.json`. Add yourself as a test user while the app is in test mode.
2. The first upload/metrics run opens a browser for consent and writes `credenciais/youtube_token.json`. Both files are git-ignored.
3. Unverified API projects upload videos locked as private until they pass YouTube's API audit (a free form). Plan for that before relying on scheduled publishing.
4. Set `youtube.canal` in `config.yaml` to your channel name: uploads are refused if the authorised account is a different channel.
5. The API accepts only **one** thumbnail per video, so the A/B/C test itself is finished by hand in Studio.

---

## Publishing

### YouTube (`--so youtube`)

Prints the schedule; with `--confirmar` uploads each item as *private with a publish date* (YouTube then publishes it by itself), sets title, description, tags, category, thumbnail/cover, subtitles and the synthetic-content flag, and records it in `youtube.json` so nothing is uploaded twice. Default schedule (all times in `youtube.fuso`):

| Item | When |
|---|---|
| Short #2 (trailer) | the day before, `short_vespera` (18:00) |
| Long video | release day, `hora_video` (12:00, before the 19:00–22:00 peak) |
| Short #1 (strongest) | `short_depois_min` (60) minutes after the long video, so the link already works |
| Remaining Shorts | one per day at `hora_shorts` |

Shorts carry the long video's link in their description (re-linked automatically if you replace the long video). `--reagendar` and `--substituir` fix mistakes without duplicating uploads.

### Instagram (`--so instagram`)

Turns each Short into a Reel through [Zernio](https://zernio.com) using cover B and a caption with title, description, a pointer to the full video, hashtags and the AI notice; only schedules with `--confirmar`.

### Metrics and trends

- `--so metricas`: views, likes, comments (Data API) plus watch time, average view duration and retention (Analytics API) for each video and Short of a project.
- `--so tendencias`: trending videos in your niche for the search terms in `tendencias.termos` (costs ~200 API quota units per term).
- `python -m pipeline.painel [port]` serves a local dashboard (default `http://127.0.0.1:8770`) over the saved results; it reads files only and spends no quota.

### Telegram

`python -m pipeline.telegram "text"` sends a message. `run.py` notifies automatically when a run longer than two minutes finishes, pauses, or fails (with the thumbnail A when it exists).

---

## Architecture

```
run.py                  CLI orchestrator: parses flags, runs stages in order, handles pauses/errors, notifies
config.yaml             all configuration; secrets only in .env
pipeline/
  util.py               paths, config/.env loading, JSON helpers, ffmpeg/ffprobe helpers, EtapaPendente
  llm.py                LLM provider (Claude API with adaptive thinking, or manual mode)
  referencia.py         [0] import + analysis + similarity metric
  roteiro.py            [2] script + anti-copy loop
  decupagem.py          [3] storyboard + validation
  tts.py                [4] voices, prosody, block narration, Whisper verification, timing
  midia.py              [5] stock search, vision scoring, AI images
  montagem.py           [6] Remotion render per chapter + ffmpeg mix + SRT + youtube.txt
  publicacao.py         [7] titles, thumbs, description, tags
  shorts.py             [8] vertical cuts, captions, covers
  entrega.py            publicar/ package
  comfy.py              ComfyUI client driven by workflow manifests
  sfx.py, musica.py     synthesised effects, ACE-Step music
  youtube.py            upload, schedule, comments, re-link
  instagram.py          Reels through Zernio
  metricas.py, tendencias.py, painel.py (+ painel.html)   analytics and dashboard
  revisao_web.py, previa.py                               manual media review, parallel media
  telegram.py           notifications
prompts/                LLM prompts (analysis, script, rewrite, storyboard, prosody, publication, shorts)
workflows/comfy/        ComfyUI workflows + manifests
render/                 Remotion project (React/TypeScript)
  src/Documentario.tsx  long-video composition (chapters → scenes → templates)
  src/Short.tsx         vertical composition
  src/Thumbnail.tsx     thumbnails (Short covers are the CapaShort composition in Root.tsx)
  src/templates/        scene templates
  src/cenas/            shared scene media component
```

**Python ↔ Remotion contract.** Python never draws pixels: it writes a props JSON (scenes with frame-accurate start and duration, media paths, colours, subtitles) and calls `npx remotion render|still src/index.ts <Composition> --props=… --public-dir=<project>`. Remotion reads media from the project folder through `--public-dir`, which is why media paths in `cenas.json` are relative to the project. The audio is not rendered by Remotion; the render is silent video and ffmpeg lays the mix over it.

**Why per-chapter renders?** They keep memory bounded on a laptop, make re-renders after a small edit cheap, and give natural insertion points for the jingle and block cards.

---

## Extending it

- **New scene template.** Add a component under `render/src/templates`, a type in `render/src/tipos.ts`, handle it in `Documentario.tsx`, add its field to the allowed types in `decupagem._checar_template`, and describe when to use it in `prompts/decupagem.md`.
- **New TTS provider.** Add a function `_name(config, text, destination, seed) -> Path` in `tts.py`, register it in `provedor()` and the dispatch, and add a config block under `tts`.
- **Another language or niche.** Translate/adapt the prompts in `prompts/`, `tts.pronuncia`, `tendencias.termos`, the channel texts in `config.yaml` and the Whisper `language`.
- **Another LLM.** Implement a provider next to `_anthropic` in `llm.py`; everything else only calls `llm.gerar(...)`.
- **New ComfyUI model.** Export the graph in API format, write a manifest for its inputs/outputs, and call `comfy.rodar("<name>", {...}, destination)`.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Run stops with `⏸ Modo manual…` | No API key: paste the prompt, save the answer as instructed, run again |
| `O roteiro continua parecido demais…` | Anti-copy limits not met after rewrites: edit `roteiro.md` by hand |
| `As cenas não reproduzem o roteiro fielmente` | The storyboard changed words; delete `cenas.json` and re-run |
| Narration fell back to another voice | Gemini quota exhausted before the video started; see `tts.google.reserva` |
| Gemini 429 mid-run | Paid tier: per-minute limit, it waits. Free tier: daily quota; re-run later, finished blocks are kept |
| Render freezes the machine | Lower `video.render_concorrencia`; 1080p clips are heavy |
| Disk fills during render | Temp files go to `./.tmp` (set via `TMPDIR` in `run.py`); a chapter render can exceed 1 GB |
| Uploaded video stuck private | The Google Cloud project still needs YouTube's API audit |
| Wrong channel refused | `youtube.canal` doesn't match the authorised account; at the Google consent screen pick the right brand account |

---

## What is not in this repository

This repo contains only the generator. Deliberately excluded (see `.gitignore`): `.env` and `credenciais/`, `projetos/` (all generated videos, audio, media), `assets/` (voice reference, music, sounds), channel branding, derived `estruturas/`, and the Remotion `public/` media. Bring your own: a voice reference WAV in `assets/vozes/`, optional music/sounds in `assets/`, and sample images in `render/public/exemplo/` if you want the Studio's demo props (`render/src/Root.tsx`) to show pictures.

Respect the licences and terms of every stock library and API you use, credit media where required (`creditos.json`), and label AI-generated content honestly.

---

## License

[MIT](LICENSE)
