# 06. Can LTX generate a "live demo" animation?

## Short answer

- **Live, as in real time while the assistant is talking: no.** Not on an 8 GB laptop GPU.
- **On demand, as a short clip that appears a minute or two after the student asks: possibly, with a small model.** It is not proven on this hardware. A one-day spike decides.
- **For correct teaching, a deterministic animation is the safer primary choice.** The app already renders lessons from templates. Generated video can look good but can be scientifically wrong, and text inside generated video is unreliable.

## What LTX is

LTX is a family of open video models from Lightricks. Two lines matter here.

| Line | Notes | Fit for 8 GB |
|---|---|---|
| **LTX-Video 0.9.x** (the original line, Apache-2.0 code repo) | Variants: 13B dev, 13B distilled, **2B distilled**, FP8 versions of each. The 2B distilled models are described as using light VRAM. Distilled models are recommended at 8 steps. Default output is 1216 by 704 at 30 fps. Resolution should be divisible by 32 and frame count should be a multiple of 8 plus 1 | The 2B distilled and FP8 variants are the only realistic candidates |
| **LTX-2.x** (newer, audio plus video, 22B) | Higher quality, synchronized audio, up to about 10 s clips. The repo describes a 22B transformer, a 12B text encoder, a Quick Start download of about 66 GiB, and offload options | Does not fit 8 GB. See below |

## Findings and sources

### Hardware

- The LTX-2 repository lists no VRAM figure, mentions a 22B model, a Gemma 4 12B text encoder, about 66 GiB of downloads, and suggests FP8 casting with CPU or disk offload when GPU memory is limited ([Lightricks/LTX-2](https://github.com/Lightricks/LTX-2)).
- One ComfyUI guide quotes the only official hardware statement as 32 GB or more VRAM and 100 GB or more free disk, with the 19B dev model at 43.3 GB in BF16, 27.1 GB in FP8 and 20 GB in FP4 ([LTX-2 Local Setup](https://localaimaster.com/blog/ltx-2-local-setup-guide)). Other pages quote lower floors (12 to 16 GB) and an "int8 8 GB path"; these conflict and are not reliable ([LTX 2.5 System Requirements](https://ltx23.app/blog/ltx-2-5-system-requirements), [RunPod guide](https://www.runpod.io/articles/guides/comfyui-ltx-2-runpod)).
- NVFP4 builds exist for RTX 50-series (Blackwell) cards, which includes this laptop's RTX 5060. A community NVFP4 page claims a 10 s, 1280 by 736 clip with audio in about 50 s on an RTX 5090, including model load ([NVFP8 vs NVFP4 comparison](https://crepal.ai/blog/aivideo/blog-nvfp8-vs-nvfp4-ltx-2-comfyui/), [community NVFP4 repo](https://huggingface.co/BennyDaBall/LTX-2.5-22b-distilled-nvfp4-comfy)). That card has 32 GB, so it says nothing about 8 GB.
- For LTX-Video, the repo says a community 8-bit fork generates 720 by 480 by 121 frames in under a minute on an RTX 4060 with 8 GB ([Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video)). That is a desktop card with a different memory profile and an unstated text encoder, so treat it as encouraging, not as a guarantee.
- The same repo says the distilled 13B model makes HD video in about 10 seconds on an H100, and the 2B distilled model is "real time" on an H100. Those are datacenter numbers.
- Search results did not contain a benchmark for a laptop RTX 5060 or any 8 GB laptop card.

### Licence

- The LTX-Video repository is Apache-2.0, but a release note mentions a separate "OpenRail-M" licence for commercial use of one checkpoint, and the repo does not say which licence covers each set of weights ([Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video)).
- LTX-2.x weights are described by one source as under a custom community licence with revenue thresholds, use restrictions and redistribution duties ([LTX-2 review](https://www.therundown.ai/tools/ltx-2)). The terms were not retrievable here.
- Downloads are gated on Hugging Face: accept the model terms and use a read token. That fits the project's rule of downloading models once during setup, then running offline.

**Action:** read the licence on the exact model card before any demo or release, and record it in the repo.

## Feasibility verdict

| Question | Verdict | Confidence |
|---|---|---|
| Real-time generation during conversation | No | High |
| LTX-2.x 22B on this laptop | No: weights are 20 to 27 GB even quantised, and the vendor floor is 32 GB VRAM | High |
| LTX-Video 2B distilled (FP8) producing a 3 to 5 s clip in about 1 to 3 minutes | Plausible | Low until measured |
| Coexisting with the chat LLM in VRAM | No. The LLM must be unloaded first | High |
| Scientifically reliable output | Not guaranteed. Diffusion video invents motion and cannot be trusted for diagrams, labels or exact processes | High |
| Fully offline after setup | Yes, once weights are downloaded | High |

## Recommendation: two tiers

### Tier 1: deterministic demo (recommended primary)

Reuse what the app already does well. Ask the LLM for a small "demo scene" as **data**, in the same spirit as the lesson plan (the model returns JSON, never code): which template to use, the labels, the sequence, the timing. Render it with the existing Remotion templates, or with the three.js world for spatial topics. Properties:

- Fast: seconds, not minutes.
- Correct: labels and numbers come from the lesson, not from a diffusion model.
- Offline, no extra VRAM, no licence question.
- Can be narrated by the same TTS and exported to MP4 like any lesson.

### Tier 2: generated illustration with LTX (optional, behind a flag)

A "Show me an illustration" button that makes a 3 to 5 second clip. Clearly labelled "AI illustration, may not be accurate". Best for atmosphere and analogies (a river, clouds forming, a leaf in sunlight), not for exact mechanisms.

## Integration design for Tier 2

```
 student: "show me" ──► chat decides to offer a demo ──► student confirms
        │
        ▼
 prompt builder: LLM turns {topic, current scene, student question} into one visual sentence
        │          (short, concrete, no text in the image; stay under the model's prompt limit)
        ▼
 job (reuses jobs.py and GET /api/jobs/{id})
        │  1. take the big GPU slot with owner "demo"
        │  2. unload the chat LLM (Ollama keep_alive 0)
        │  3. load the video model, generate, save MP4 under media/demos/<hash>.mp4
        │  4. free the model, release the slot
        ▼
 chat shows progress ("Preparing a short clip, about 2 minutes") and then a small inline player
```

Design rules:

| Rule | Reason |
|---|---|
| Ask before generating | It pauses chat and uses the GPU for minutes |
| Cache by prompt hash | A repeat request is instant |
| Cancel button | Long job; the student may change their mind |
| Label every clip as an illustration | Honesty about accuracy |
| Image-to-video as an option | Start from a frame rendered by the app's own template so labels and layout are correct, and let the model add motion only |
| One clip at a time | Memory |
| Short clips (3 to 5 s), modest resolution (for example 704 by 480) | Time and memory |
| Disable on machines without enough RAM or VRAM | The health endpoint reports `demo.ready` |

### GPU and memory impact

| Resource | Impact |
|---|---|
| VRAM | Chat LLM and Parler unloaded during generation. Chat unavailable for the duration |
| System RAM | Offload to RAM uses a large part of 31.5 GB. Close other heavy apps. Do not run OCR at the same time |
| Disk | Several GB for the 2B models, tens of GB if LTX-2.x were attempted |
| Time | Minutes. Needs a progress bar and a clear "chat paused" state |

## Spike plan (one day, before committing)

Goal: find out, on the demo laptop, whether Tier 2 is worth building.

1. Download one candidate: LTX-Video 2B distilled in FP8 (and, if easy, the 13B distilled FP8 for comparison). Record sizes and licence text.
2. Run it through a standard runner first (a ComfyUI workflow or the model's own scripts), not through the app.
3. Generate clips for three topics: photosynthesis (leaf in sunlight), water cycle (rain over a river), Newton's third law (rocket launch). Use 704 by 480, 5 s, 8 steps.
4. Measure: seconds per clip cold and warm, peak VRAM, peak RAM, whether the LLM can be reloaded afterwards, any out-of-memory events.
5. Have two reviewers rate each clip: relevant, attractive, and not misleading.
6. Repeat once with image-to-video from a Remotion frame.

### Decision gates

| Result | Decision |
|---|---|
| Clip in 2 minutes or less, peak VRAM within 7.5 GB, no crash, at least 2 of 3 topics rated relevant and not misleading | Build Tier 2 behind a flag |
| Works but slow or often misleading | Keep as a lab feature only, or skip. Rely on Tier 1 |
| Out-of-memory or needs more than 24 GB RAM | Drop. Revisit with a bigger GPU or a hosted box on the demo network |

## Alternatives worth a look

- A tiny offline "motion graphics" generator from the lesson data (Tier 1, extended): arrows, labelled parts, flows. Most reliable for science.
- Using the three.js metaverse as the "demo": a station that animates the concept (for example a leaf with light rays). Deterministic and already themed.
- A second, stronger machine on the demo LAN running LTX, with the laptop calling it over HTTP. This breaks "one laptop" and should only be considered if the judges allow it.

## Open questions

- Is a generated clip required for the demo, or is a deterministic animation enough?
- Is a minute or two of waiting acceptable on stage? If not, pre-generate clips for the demo topics during setup and cache them.
- May the project ship model weights under their licences, or must the user download them on their own machine?
