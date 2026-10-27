package com.kabir.unlox_hackethon.data

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json

private val sceneJson = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true; allowSpecialFloatingPointValues = true }
private val TITLE_RE = Regex(""""title"\s*:\s*"((?:[^"\\]|\\.)*)"""")
private val SCENES_RE = Regex(""""scenes"\s*:\s*\[""")

/** The title and the scenes that are already complete in a plan's JSON that is still being written (strings and braces inside text are handled). */
fun extractScenes(text: String): Pair<String, List<PlanScene>> {
    val title = TITLE_RE.find(text)?.groupValues?.get(1).orEmpty()
    val key = SCENES_RE.find(text) ?: return title to emptyList()
    val out = ArrayList<PlanScene>()
    var depth = 0; var start = -1; var inStr = false; var esc = false
    var i = key.range.last + 1
    while (i < text.length) {
        val c = text[i]
        if (inStr) {
            if (esc) esc = false else if (c == '\\') esc = true else if (c == '"') inStr = false
        } else when {
            c == '"' -> inStr = true
            c == '{' -> { if (depth == 0) start = i; depth++ }
            c == '}' && depth > 0 -> {
                depth--
                if (depth == 0 && start >= 0) { runCatching { sceneJson.decodeFromString<PlanScene>(text.substring(start, i + 1)) }.getOrNull()?.let { out.add(it) }; start = -1 }
            }
            c == ']' && depth == 0 -> return title to out
        }
        i++
    }
    return title to out
}

/** One scene cleaned the way [normalizePlan] would clean it inside the whole plan. The first scene may bring a title scene in front of it. Empty when it has nothing to say. */
fun normalizeOne(title: String, scene: PlanScene, first: Boolean): List<SceneT> {
    val lead = PlanScene(template = "title", heading = "x", narration = "x")
    val scenes = runCatching { normalizePlan(PlanDoc(title, if (first) listOf(scene) else listOf(lead, scene))).second }.getOrNull() ?: return emptyList()
    return if (first) scenes else if (scenes.size >= 2) listOf(scenes.last()) else emptyList()
}

/**
 * Makes the first language of a lesson scene by scene while Gemma is still writing the plan: each finished scene is cleaned, translated,
 * read aloud and saved to the lesson (marked `building`), so the player can start on scene 1 within seconds and scenes are added as they are made.
 * The scenes are exactly what the finished plan will contain (nothing on the phone rewrites them afterwards), so they are kept as they are.
 */
class ScenePreview(
    private val scope: CoroutineScope, private val id: String, private val concept: String, private val lang: String, private val allLangs: List<String>,
    private val expected: Int, private val lessons: LessonStore, private val translator: Translator, private val tts: Tts, private val mode: String, private val source: String,
    private val courseId: String, private val episode: Int, private val episodeTitle: String,
    private val onNarrated: (Int) -> Unit, private val onFirst: () -> Unit,
) {
    private val queue = Channel<Triple<Int, String, PlanScene>>(Channel.UNLIMITED)
    private var gen = 0
    private var seen = 0
    private var title = concept
    private val english = ArrayList<SceneT>()                        // what was made, in English (to compare with the finished plan)
    private val shown = ArrayList<SceneT>()                          // the same scenes in the learner's language, with their narration files
    @Volatile private var announced = false
    private var lastLen = 0                                          // how much of the text has been looked at (see feed)
    private var worker: Job = scope.launch(Dispatchers.Default) { run() }

    /** Called with the plan's text as it grows. Starts over when the planner does (a retry makes the text shorter than before). */
    fun feed(text: String) {
        // Every token calls this with the whole text so far. A scene can only have finished when a closing brace has arrived since the last look,
        // so most calls cost one search instead of a parse of the whole JSON (that made the phone work harder with every word).
        synchronized(this) {
            if (text.length < lastLen) lastLen = 0                    // the planner started over
            val closed = text.indexOf('}', lastLen) >= 0
            lastLen = text.length
            if (!closed) return
        }
        val (t, scenes) = extractScenes(text)
        synchronized(this) {
            if (t.isNotBlank()) title = t
            if (scenes.size < seen) { gen++; seen = 0; english.clear(); shown.clear() }
            val new = scenes.drop(seen)
            seen = scenes.size
            new.forEach { queue.trySend(Triple(gen, title, it)) }
        }
    }

    /** Whole scenes that are already complete (a finished part of a long video), after everything fed so far, in order. */
    fun addScenes(scenes: List<PlanScene>) {
        synchronized(this) {
            val g = gen
            scenes.forEach { queue.trySend(Triple(g, title, it)) }
            seen += scenes.size
        }
    }

    private suspend fun run() {
        for ((g, ttl, ps) in queue) {
            if (g != gen) continue
            try { one(g, ttl, ps) } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) { Log.w("Chanakya", "preview of a scene failed: ${e.message}") }
        }
    }

    private suspend fun one(g: Int, ttl: String, ps: PlanScene) {
        val fresh = normalizeOne(ttl, ps, first = english.isEmpty())
        for (en in fresh) {
            val local = if (lang == "en") en else { val words = translator.translate(en.texts(), lang).iterator(); en.withTexts { words.next() } }
            val n = shown.size
            val speech = tts.speak(local.narration, lang, lessons.audio(id, lang, n))
            val done = local.copy(audio = speech?.file?.name, seconds = ((speech?.seconds ?: (local.narration.split(' ').size / 2.4f)) + 0.6f))
            synchronized(this) {
                if (g != gen) return
                english.add(en); shown.add(done)
                publish()
            }
            onNarrated(shown.size)
            if (!announced) { announced = true; onFirst() }
        }
    }

    private fun publish() {
        val track = Track(lang, shown.firstOrNull()?.let { title } ?: title, shown.toList())
        lessons.save(Lesson(id, concept, System.currentTimeMillis(), mode, listOf(track), plan = Track("en", title, english.toList()), courseId = courseId, episode = episode,
            episodeTitle = episodeTitle, source = source, building = true, scenesTotal = maxOf(expected, shown.size), pending = allLangs.filter { it != lang }))
    }

    /** The plan is finished: wait for the scene being made, then hand back the first language if it matches the finished plan (else null: make it again). */
    suspend fun finish(finalEn: List<SceneT>): Track? {
        queue.close()
        worker.join()
        val same = english.size == finalEn.size && english.indices.all { english[it].narration == finalEn[it].narration }
        if (!same || shown.isEmpty()) return null
        val translatedTitle = if (lang == "en") title else runCatching { translator.translate(listOf(title), lang).first() }.getOrDefault(title)
        return Track(lang, translatedTitle, shown.toList())
    }

    fun cancel() { queue.close(); worker.cancel() }
}
