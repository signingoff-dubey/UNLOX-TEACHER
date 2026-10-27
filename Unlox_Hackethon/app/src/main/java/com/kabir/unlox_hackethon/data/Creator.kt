package com.kabir.unlox_hackethon.data

import android.util.Log
import com.kabir.unlox_hackethon.ui.screens.LessonRequest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.UUID

/** Where a lesson being made has got to; the Generating screen shows it. */
data class CreationState(
    val running: Boolean = false, val step: Int = 0, val progress: Float = 0f, val status: String = "",
    val details: List<String> = listOf("", "", "", "", ""), val lessonId: String? = null, val error: String? = null,
    /** How far each of the five stages is, 0..1. Translating and narrating run at the same time, so several can be moving at once. */
    val pct: List<Float> = List(5) { 0f },
)

/** How much of the whole job each stage is (they add up to 1). */
private val WEIGHT = listOf(0.02f, 0.30f, 0.20f, 0.42f, 0.06f)

@Serializable
private class PlanScene(val kind: String = "bullets", val heading: String = "", val items: List<String> = emptyList(), val narration: String = "")

@Serializable
private class Plan(val title: String = "", val scenes: List<PlanScene> = emptyList())

private val lenient = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }

private val MODE_HINT = mapOf(
    "Explanation" to "Explain the idea clearly from the ground up, with one everyday example.",
    "Study" to "Write exam-ready study material: definitions, key facts, formulas and a memory trick.",
    "Homework" to "Work through the problem step by step, showing each step and the reason for it.",
)

/**
 * Makes a lesson on this phone: Gemma plans the scenes as JSON, each language is translated (ML Kit, Gemma as the fallback),
 * each scene is read aloud by a voice, and the result is saved. All of it runs on background threads; the screen only watches the state.
 */
class Creator(
    private val llm: Llm, private val translator: Translator, private val tts: Tts,
    private val lessons: LessonStore, private val rewards: Rewards, private val profile: Profile,
) {
    private val _state = MutableStateFlow(CreationState())
    val state: StateFlow<CreationState> = _state
    private var job: Job? = null

    fun start(req: LessonRequest) {
        job?.cancel()
        _state.value = CreationState(running = true, status = "Getting ready")
        job = Graph.scope.launch {
            try { make(req) } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                Log.e("Chanakya", "lesson failed", e)
                _state.value = _state.value.copy(running = false, error = e.message ?: e.javaClass.simpleName)
            }
        }
    }

    fun cancel() { job?.cancel(); _state.value = CreationState() }
    fun reset() { _state.value = CreationState() }

    /** Updates one stage's detail line and percentage; the overall progress is the weighted sum of all five, so it only ever moves forward. */
    @Synchronized private fun stage(step: Int, pct: Float? = null, status: String? = null, detail: String? = null) {
        val cur = _state.value
        val d = cur.details.toMutableList()
        if (detail != null) d[step] = detail
        val p = cur.pct.toMutableList()
        if (pct != null) p[step] = maxOf(p[step], pct.coerceIn(0f, 1f))
        val overall = p.indices.sumOf { (p[it] * WEIGHT[it]).toDouble() }.toFloat()
        val firstOpen = p.indexOfFirst { it < 1f }.let { if (it < 0) 4 else it }
        _state.value = cur.copy(step = firstOpen, progress = maxOf(cur.progress, overall), status = status ?: cur.status, details = d, pct = p)
    }

    private suspend fun make(req: LessonRequest) {
        val id = UUID.randomUUID().toString().take(8)
        val langs = req.languages.map { langByName(it).code }.distinct().ifEmpty { listOf("en") }

        stage(0, 0.3f, "Loading the tutor", "From Gemma's own knowledge, on this phone")
        llm.warmUp()
        stage(0, 1f)

        val sceneCount = (req.seconds / 10).coerceIn(3, 8)
        stage(1, 0.02f, "Planning $sceneCount scenes", "Gemma · ${llm.backendName}")
        val plan = plan(req, sceneCount)
        stage(1, 1f)
        val en = Track("en", plan.title, plan.scenes.map { SceneT(it.kind, it.heading, it.items, it.narration) })

        // Translation and narration run side by side: English is read aloud while the next language is still being translated.
        val others = langs.filter { it != "en" }
        val stringsPerLang = 1 + en.scenes.sumOf { 2 + it.items.size }
        val translateTotal = (stringsPerLang * others.size).coerceAtLeast(1)
        val translated = java.util.concurrent.atomic.AtomicInteger(0)
        val narrateTotal = (en.scenes.size * (1 + others.size)).coerceAtLeast(1)
        val narrated = java.util.concurrent.atomic.AtomicInteger(0)
        if (others.isEmpty()) stage(2, 1f, detail = "English only")
        else stage(2, 0.01f, "Translating", others.joinToString(", ") { c -> LANGS.first { it.code == c }.name } + " · ML Kit")

        suspend fun narrate(track: Track): Track {
            val name = LANGS.first { it.code == track.lang }.name
            return track.copy(scenes = track.scenes.mapIndexed { i, sc ->
                stage(3, narrated.get().toFloat() / narrateTotal, "Recording $name narration", "Piper voices · $name")
                val speech = tts.speak(sc.narration, track.lang, lessons.audio(id, track.lang, i))
                stage(3, narrated.incrementAndGet().toFloat() / narrateTotal)
                sc.copy(audio = speech?.file?.name, seconds = ((speech?.seconds ?: (sc.narration.split(' ').size / 2.4f)) + 0.5f))
            })
        }

        val tracks = kotlinx.coroutines.coroutineScope {
            val jobs = ArrayList<kotlinx.coroutines.Deferred<Track>>()
            jobs.add(async(kotlinx.coroutines.Dispatchers.Default) { narrate(en) })
            for (code in others) {
                Trace.mark("translating to $code")
                val t = translate(en, code) { stage(2, translated.incrementAndGet().toFloat() / translateTotal) }
                Trace.mark("translated to $code")
                jobs.add(async(kotlinx.coroutines.Dispatchers.Default) { narrate(t) })
            }
            if (others.isNotEmpty()) stage(2, 1f)
            jobs.awaitAll()
        }

        stage(4, 0.4f, "Putting the scenes together", "${plan.scenes.size} scenes")
        val lesson = Lesson(id, req.concept, System.currentTimeMillis(), req.mode, tracks)
        lessons.save(lesson)
        rewards.award("lesson_created", langs)
        stage(4, 1f, "Ready")
        _state.value = _state.value.copy(running = false, progress = 1f, status = "Ready", lessonId = id)
    }

    private suspend fun plan(req: LessonRequest, n: Int): Plan {
        val system = "You are Chanakya, a teacher who writes short narrated video lessons. ${profile.audience()}${MODE_HINT[req.mode] ?: ""} Reply with one JSON object and nothing else."
        val user = """Write a lesson about "${req.concept}" in exactly $n scenes.
JSON shape: {"title": "short title", "scenes": [{"kind": "title" | "bullets" | "diagram" | "flow", "heading": "at most 6 words", "items": ["2 to 4 phrases, each at most 8 words"], "narration": "about 22 spoken words in plain sentences, no lists, no markdown"}]}
The first scene is kind "title". Be accurate. Output only the JSON."""
        val expected = n * 330f                                              // about how many characters the JSON for n scenes comes to
        repeat(3) { attempt ->
            val reply = llm.askStreaming(system, user, temperature = if (attempt == 0) 0.4 else 0.2) { chars -> stage(1, 0.02f + 0.95f * (chars / expected).coerceAtMost(1f)) }
            val parsed = extractJson(reply)?.let { runCatching { lenient.decodeFromString<Plan>(it) }.getOrNull() }
            if (parsed != null && parsed.scenes.size >= 2 && parsed.scenes.all { it.narration.isNotBlank() }) {
                return Plan(parsed.title.ifBlank { req.concept }, parsed.scenes.take(8).map { it.copy2() })
            }
            Log.w("Chanakya", "plan attempt $attempt not usable: ${reply.take(120)}")
        }
        error("The tutor could not plan that lesson. Try again, or word the topic differently.")
    }

    private fun PlanScene.copy2() = PlanScene(kind.lowercase().takeIf { it in setOf("title", "bullets", "diagram", "flow") } ?: "bullets", heading.trim(), items.map { it.trim() }.filter { it.isNotEmpty() }.take(4), narration.trim())

    private suspend fun translate(en: Track, code: String, onEach: () -> Unit): Track {
        val flat = ArrayList<String>()
        flat.add(en.title)
        en.scenes.forEach { flat.add(it.heading); flat.addAll(it.items); flat.add(it.narration) }
        val out = translator.translate(flat, code, onEach)
        var i = 0
        val title = out[i++]
        val scenes = en.scenes.map { sc ->
            val heading = out[i++]
            val items = sc.items.map { out[i++] }
            SceneT(sc.kind, heading, items, out[i++])
        }
        return Track(code, title, scenes)
    }
}
