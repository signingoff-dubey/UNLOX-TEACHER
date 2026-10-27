# Plan: 2.5-minute videos that build themselves while you watch

Status: draft for review. Nothing here is implemented. Written against commit `7587bbb`.

## The goal

A lesson should be able to run **2:30**, but it should start playing in under 30 seconds and never feel like it is being made.
Making 2.5 minutes in one go does not work: the 7B model loses the thread, one long answer is slow and fragile, nothing can be shown
until the end, and a single failure loses everything. So the video is made in **segments of about 30 seconds**. While segment 1
plays, segment 2 is already being made, and so on. The player shows **2:30** from the first second.

## The idea that makes this cheap

Playback in this app is not a video file. The browser draws the lesson from JSON (scenes, timings, audio clips) with Remotion.
So "rendering while it plays" costs nothing: the only slow parts are **writing** the scenes (LLM), **translating** them and
**recording the voice**. Adding more video is just appending more scenes to the JSON the player already reads. The MP4 is only made
when someone presses Download.

## 1. Making the next part before it is needed

### Storyboard first (about 6 s)
A storyboard agent writes the whole 2:30 outline as small JSON: 5 chapters, each with a goal, a role (hook, idea, example, practice,
recap), a word budget, the visual types it should use (graph, code, flow...) and the key terms it introduces. This gives:
- the **2:30 timer** (word budgets / speaking speed of the language), and chapter ticks on the seek bar from the start;
- coherence: every segment knows what came before and what comes next;
- the quiz and summary placed in the last chapter only, which fixes the "quiz appears early" problem.

### Segment pipeline
Each segment goes through the same agents we already have, but with a small prompt:
`plan (3-4 scenes) -> director -> reviewer/writer -> translate -> voice -> append`.
The planner is told the storyboard row, a running summary of what was already said, the last scene of the previous segment and the
next chapter title (the series mechanism built for courses already does this).

### Staying ahead of playback
Measured today: a whole 6-7 scene lesson takes about 34 s to plan. A 3-4 scene segment is roughly half the tokens, so about 12-15 s of
planning plus a few seconds of translation, with the voices recording on the CPU while the next segment is being planned. The target is
**generation at least 1.5x faster than playback**. How we get there:
- **Short first segment (about 15-20 s):** a hook and the first idea, so playback starts about 25-30 s after the click.
- Plan segment k+1 as soon as segment k has finished planning (do not wait for its voice). Planning uses the GPU, voices use the CPU.
- Adaptive size: 20 s, then 30 s segments.
- **Behind-schedule mode:** if the buffer gets thin, skip the optional agents (writer, director) for the next segment and use the
  cheap path; catch up later.
- Start playing only when the buffer is safe: `ready seconds >= expected time to make the next segment x 1.5`, measured on this laptop.
- A **benchmark gate** in milestone 1: if the sustained rate is under 1.3x real time, shrink prompts, use a faster reviewer, or raise the
  initial buffer before building any UI.

## 2. Joining the parts without a seam

### One continuous timeline
Segments are not separate videos. The composition is one timeline of scenes; a segment is just a batch of scenes added at the end.
The audio timeline is **narration-first**: voice clips exist (with exact durations) before their scenes are added, so the timeline
never changes retroactively and the seek bar never jitters.

### Morphing, not cutting
Transitions work per scene, so a segment boundary looks like any other scene change:
- templates receive `previousScene` and `nextScene`, and animate **in from the previous scene's layout** (heading text slides into the new
  heading; bullet items re-flow to their new positions, the same technique as "FLIP" animations);
- **persistent stage elements** survive between scenes that use the same component: a graph keeps its axes and adds the new curve, a code
  scene keeps its editor frame and appends lines, a diagram keeps its centre node. These are the reusable rendered components you asked for;
- 10-12 frame overlap with an audio crossfade, and a short chapter card (about 0.6 s) at chapter starts that also hides small timing gaps;
- the director agent sees the whole video's visual history, so no three identical templates in a row even across a boundary.

## 3. Nothing laggy

- **Never rebuild the player.** Scenes live in an external store; the player's `durationInFrames` grows in place, the instance keeps its
  identity (no remount, no key change). Past scenes are memoised.
- **Pre-mount the next scene** about 1 s before it starts (Remotion `premountFor`), so its first frame is already painted.
- **Append at scene boundaries, in idle time** (`requestIdleCallback`), O(1) work per arrival. Text-fitting measurements run in a worker.
- **Audio is decoded ahead** as soon as a segment lands (decode once, keep in memory) so a clip never waits on the network or decoder.
- **Compositor-only motion** (transform and opacity), the same rules that fixed the metaverse entrance.
- **Acceptance test with the profiler already built:** no frame over 50 ms while a segment is appended, no audio gap over 20 ms at a boundary,
  while a fake producer delivers segments at 1.2x, 1.0x and 0.8x playback speed.

## 4. What the viewer sees

- Time label: **0:00 / 2:30** from the start. It is the storyboard estimate and is corrected in steps of 5 s as real voice lengths arrive
  (never a visible jump near the end).
- The seek bar has three zones, like a streaming service: played, **ready**, and **planned** (striped, with the chapter titles on hover).
  Seeking into the planned zone goes to the end of the ready zone with a quiet "next part is being prepared" tooltip.
- If playback ever catches up with the buffer, it does **not** freeze: the current scene holds its last frame calmly and a small chapter
  card ("Next: Common mistakes") shows with a gentle pulse, and it resumes by itself when the next scene arrives.
- Other languages: the active language is built first, the others follow; their tabs show a building state like the study-tool buttons.

## 5. Data and API

- `lesson.json` gains `target_duration_s`, `storyboard`, `segments: [{id, status, scene_range, start_s, duration_s}]` and a `revision`.
  Tracks are append-only: `languages[lang].scenes` and `duration_s` only grow.
- `POST /api/lessons {duration_s: 150}` returns the stub (storyboard + segment 1) as soon as it exists; lessons of 90 s or less keep the
  current one-shot path.
- `GET /api/lessons/{id}?since=<revision>` returns only the new scenes; the page follows an event stream (SSE) or polls every second.
- Everything is saved after each segment, so a refresh or a closed tab loses nothing, and generation continues on the server.

## 6. Export

When the last segment lands the full timeline exists, so the MP4 is the usual Remotion render. To make Download instant, segment MP4s are
rendered in the background as segments finish (the render slot is free while the model is not), then joined with ffmpeg with no re-encode,
the same way the course export works.

## Milestones

| # | Deliverable | Done when |
|---|---|---|
| M1 | Storyboard agent, segment pipeline, append-only lesson JSON, delta API, benchmark | 2:30 lesson built; first segment ready within 30 s; sustained generation rate at least 1.3x real time on this laptop |
| M2 | Live scene store, growing player, 2:30 label, three-zone seek bar, hold-and-resume | No frame over 50 ms when appending, at fake producer rates 0.8x to 1.2x |
| M3 | Morph transitions, persistent graph/code/diagram stage, premount, audio crossfade | Boundaries cannot be told from scene changes in a frame-by-frame check |
| M4 | Whole-video director, running-summary memory, role-based chapters | Rust, Python loops, circle: no repeated points, quiz only at the end, vision QA finds no duplicate-looking scenes |
| M5 | Background segment export, docs, cleanup | Download available within seconds of the last segment |

## Risks

| Risk | Mitigation |
|---|---|
| Model slower than playback | short first segment, behind-schedule mode, benchmark gate, larger start buffer |
| GPU contention between planning, translation, study-tool queue | the study-tool queue already yields to lesson jobs; translation and voices already run off the planner's critical path |
| Story drifts over 5 segments | storyboard, running summary, series-style context, last-scene hand-off |
| A segment fails | retry once, then a simpler scene set from the storyboard row; the video never stops |
| Seeking and resuming at odd moments | the ready zone is the only seekable zone; time label is monotonic |
| Long audio memory | decode per segment, release segments far behind the playhead |

## Decisions I need from you
1. Is 2:30 the fixed target, or should the length picker offer 1:00 / 2:30 / 4:00 (the same mechanism scales)?
2. May the first segment be shorter (about 15-20 s) to start sooner?
3. Should courses (5-8 videos) also use this, or keep one-shot videos for courses?
