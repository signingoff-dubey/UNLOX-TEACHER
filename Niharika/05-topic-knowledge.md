# 05. Knowing the topic

The assistant must answer about what is on screen, from reliable sources, in the student's language, without making things up.

## Context layers

Every answer is built from four layers, in this priority order.

| Layer | Content | Source in the repo | Typical size |
|---|---|---|---|
| 1. Lesson | Title, scene list, narration of every scene in the active language, items, quiz question and answer | `lesson.json` (`pipeline.py`) | 1 to 2k tokens |
| 2. Now | The scene currently on screen, how far into it the student is, whether the quiz has been answered | `sceneIndex` from the player, sent with each message | under 200 tokens |
| 3. Sources | Passages retrieved for the question | `rag/search.py` (preferred) or `knowledge.py` | 1 to 2k tokens |
| 4. Conversation | Last few turns, plus a running summary if long | session | 500 to 1k tokens |

The planner already uses `num_ctx` of 8192. The same budget is enough if retrieval is capped and history is trimmed.

## Retrieval

### Which stack

`rag/` is the better fit: hybrid keyword plus vector search, a cross-encoder reranker, multilingual embeddings (so a Hindi question can find an English passage), and scopes for an uploaded PDF. It is currently unused. Recommendation: wire chat to `rag/` first, then decide whether to migrate the lesson planner from `knowledge.py` so there is one retrieval stack.

### Query rewriting

Short follow-ups ("why is it green?") have no meaning on their own. Before searching, rewrite the question using the lesson title and the current scene, for example "Why are leaves green in photosynthesis?". A cheap rule (append the lesson title) works first; an LLM rewrite is an upgrade if tests show misses.

### Scopes

| Student has | Scope |
|---|---|
| Only a typed concept | `library` |
| An uploaded PDF for this lesson | `both:<sha>` (the PDF first, the library adds background) |

The lesson record should remember which scope it used, so chat uses the same one.

### Reusing the lesson's sources

The lesson already stores the sources it was built from. Seed retrieval with those passages first, then search for more only if the question goes beyond them.

## Prompt design

The system prompt sets the persona and the rules. Content, not code, listed here:

- You are a friendly teacher helping one student with the lesson shown.
- Answer from the lesson and the retrieved passages. If they do not contain the answer, say so plainly and give a short, careful general answer marked as such.
- Speak in 1 to 3 short sentences unless asked for more. No lists, no markdown, no emoji. The answer will be read aloud.
- Use the student's language. Keep technical terms consistent with the lesson's wording.
- Refer to the screen ("as shown in the last step") when helpful.
- Stay on the topic and school-appropriate. Redirect off-topic requests kindly.
- Never reveal the quiz answer before the student has tried, unless asked directly after a wrong attempt.

### Useful behaviours

| Student says | Assistant does |
|---|---|
| "Explain this again" | Re-explains the current scene in simpler words |
| "Why?" or "How?" | Uses the current scene as the subject |
| "Give an example" | Uses an everyday Indian example, like the planner prompt |
| "Quiz me" | Asks a question from the lesson, checks the answer, gives a hint |
| "Show me" | Offers a demo (see `06-ltx-live-demo.md`) |
| "Slower" | Shortens sentences and lowers speech speed |

## Languages

The README records that Qwen 7B mixes scripts in Hindi and is mostly wrong in Telugu. Three ways to answer in Indian languages:

| Approach | Quality | Latency | Complexity |
|---|---|---|---|
| A. LLM answers directly in the target language | Poor for Telugu and several others with the current model | Lowest | Lowest |
| B. LLM answers in English; NLLB translates each sentence; TTS speaks it | Good, matches how lessons are made | Adds about 0.3 to 1 s per sentence | Medium |
| C. Larger or better multilingual model | Possibly best | Higher, may not fit 8 GB | High |

Recommendation: **B**, because it reuses the proven lesson path (English plan, NLLB, voice). Run the translation per sentence inside the streaming loop. Reserve A for Hindi only if tests show it is good enough, and revisit C if a suitable model fits.

The student's question is first turned into English (or retrieved directly, since the embeddings are multilingual), the LLM works in English, and only the final answer is translated.

## Citations

- Each answer carries the sources used, shown as small chips under the message and linked to the passage.
- The spoken answer does not read out source names; the chips are visual.
- If no source supported the answer, show "From general knowledge" so the student knows to double-check.

## Memory and drift

- Keep the last 6 turns verbatim. Summarise older ones into two sentences.
- Reset the conversation when the lesson changes. Offer to keep it when the student replays the same lesson.
- Do not store conversations on disk by default.

## Metaverse tie-in

The metaverse already turns a lesson into stations and quiz gates. The same assistant can be opened at a station: the current station maps to a scene, so "Now" is known. This is optional and should reuse the same chat component, not a copy.

## Evaluation plan

| Test | Method | Pass line (proposal) |
|---|---|---|
| Groundedness | 30 questions per lesson across 5 lessons; reviewer checks each claim against the lesson and sources | At least 90% fully supported |
| Unanswerable questions | 10 questions with no support in sources | Assistant says it does not know or flags general knowledge in at least 9 |
| Follow-ups | 20 two-turn exchanges using pronouns | At least 90% resolve to the right subject |
| Quiz leakage | Ask for the answer before trying | Not revealed in 10 of 10 |
| Language | Same 20 questions in Hindi and Telugu | Native-speaker review: understandable and correct |
| Safety | 10 off-topic or unsafe prompts | Redirected politely in 10 of 10 |
| Latency | Time to first sentence with retrieval and rewrite | Under 1.5 s for English |

## Open questions

- Should the assistant be allowed to answer beyond the lesson and sources at all, or only from them?
- Is a "teacher mode" (the assistant asks the student questions) in scope for the demo, or just question answering?
