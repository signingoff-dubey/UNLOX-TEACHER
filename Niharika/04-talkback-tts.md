# 04. Talkback: spoken answers (TTS)

## What exists

`backend/app/tts.py` already turns text into a WAV in a given language and caches it by content hash. Engines: Piper on CPU (fast), Indic Parler-TTS on GPU (better coverage, slow), and a silent placeholder. It is designed for lesson narration: one whole scene at a time, written to disk.

Voice coverage today:

| Language | Engine | Speed |
|---|---|---|
| English, Hindi, Telugu, Malayalam, Marathi | Piper | Fast on CPU |
| Kannada, Tamil, Bengali, Gujarati | Indic Parler-TTS (GPU) | Slow, one sentence at a time |

## What talkback needs that narration does not

| Need | Why | Plan |
|---|---|---|
| Start speaking before the answer is finished | Latency | Speak the first sentence as soon as the LLM completes it |
| Stop instantly | The student interrupts | Cancel synthesis and playback on a signal |
| Short, spoken style | Answers are heard, not read | Prompt rules: 1 to 3 sentences, no lists, no markdown |
| Consistent voice | Matches the lesson narrator | Same engine and voice per language as the lesson |
| Text and audio together | Accessibility and noisy rooms | Show each sentence as it is spoken, highlight the current one |
| Never block on a long sentence | Parler can take seconds | Length cap per spoken chunk; split long sentences at commas |

## Streaming design

1. The LLM streams tokens. A segmenter groups them into sentences, reusing `split_sentences` (it already breaks on `. ! ? । ॥`).
2. Each sentence goes to a synthesis queue. One synthesis at a time per engine, because both Piper and Parler hold locks today.
3. The server emits a `sentence` event containing the text and, when ready, a URL for that sentence's audio.
4. The browser keeps a playback queue: it starts the first chunk, preloads the next, and handles gaps so there is no click or double-play.
5. A cancel signal empties the server queue, stops generation, and clears the browser queue.

### Cache and warm-up

- Cache by content hash, as now. Common phrases ("Good question", "Let me check the lesson") become instant.
- Pre-render a few short acknowledgements per language at start-up so the assistant can answer "I am thinking" without waiting for the model.

## Language strategy

| Situation | Approach |
|---|---|
| English, Hindi, Telugu, Malayalam, Marathi | Piper. Expect first audio well under a second after the sentence is ready |
| Kannada, Tamil, Bengali, Gujarati | Parler. Show the text immediately; audio follows a few seconds later. Consider a shorter first sentence for these languages |
| Mixed text (Indic with English terms such as "CO2") | Normalise before synthesis. See below |
| No voice installed | Show text only and say so in the status panel; do not play silence |

## Speech-friendly text

Written text is not always speakable. A normalisation step, per language, before synthesis:

- Remove markdown, bullets, emoji and URLs.
- Expand symbols and units: arrows, "CO2", "m/s", percentages, chemical formulas, fractions.
- Numbers: read as words in the target language, or leave digits if the voice handles them.
- English terms inside Indic sentences: keep them if the voice can pronounce them; otherwise transliterate.
- Keep sentences under a length cap so the voice does not drift (the existing code already notes Parler drifts on long input).

## Interrupting and turn-taking

| Event | Behaviour |
|---|---|
| Student starts speaking while the assistant talks | Stop playback within about 200 ms, cancel generation, start listening (barge-in) |
| Assistant is interrupted mid-sentence | Do not resume automatically. Offer "Continue" if the student asked for it |
| Student presses Stop | Same as barge-in, without listening |
| Lesson video is playing | Lower its volume or pause it while the assistant speaks. Pause on "raise hand" |

### Echo

If the speakers are loud, the microphone hears the assistant and treats it as the student. Mitigations in order of cost: browser echo cancellation (on by default in the capture settings), push-to-talk (which sidesteps the issue), and a recommendation to use headphones for hands-free mode.

## Screen sync

Reuse the caption styling from the lesson player. Each spoken sentence is shown as it starts, the current sentence is highlighted, and finished sentences stay in the transcript. Source chips (see `05-topic-knowledge.md`) appear when the sentence that used them is spoken.

## Controls in the chat panel

- Mic button (hold to talk) and a hands-free toggle.
- Speaker toggle: spoken answers on or off, remembered per device.
- Stop button while speaking.
- Playback speed (0.8x to 1.2x), for students who need slower speech.
- Voice and language shown, with a warning when the language has only a slow voice.

## Evaluation plan

| Test | Pass line (proposal) |
|---|---|
| Time from end of LLM first sentence to first audio, Piper languages | Under 0.5 s |
| Same, Parler languages | Reported; text must appear within 0.5 s regardless |
| Barge-in stop time | Under 300 ms |
| Intelligibility of 20 science sentences per language | Native-speaker review, at least 4 of 5 rated clear |
| Number, unit and formula reading | 20 tricky strings read correctly in English and Hindi |
| Long answer (6 sentences) | No gaps over 400 ms between sentences on Piper |
| Memory | Parler plus LLM resident without out-of-memory, or a clear policy for unloading |

## Open questions

- Is a different, more conversational voice wanted for the assistant than for the lesson narrator, or the same voice for continuity?
- Is the slow Parler path acceptable for Kannada, Tamil, Bengali and Gujarati on demo day, or should the demo languages be limited to the Piper set?
