package com.kabir.unlox_hackethon.data

import android.util.Log
import com.kabir.unlox_hackethon.ui.screens.LessonRequest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

/** Where a lesson (or a set of videos) being made has got to; the Generating screen shows it. */
data class CreationState(
    val running: Boolean = false, val step: Int = 0, val progress: Float = 0f, val status: String = "",
    val details: List<String> = listOf("", "", "", "", ""), val lessonId: String? = null, val error: String? = null,
    /** How far each of the five stages is for the video being made, 0..1. Translating and narrating run at the same time, so several can move at once. */
    val pct: List<Float> = List(5) { 0f },
    val episode: Int = 0, val episodes: Int = 1, val episodeTitle: String = "",
    /** The player has already been opened on this job's first video. */
    val opened: Boolean = false,
)

/** How much of one video each stage is (they add up to 1). */
private val WEIGHT = listOf(0.02f, 0.30f, 0.20f, 0.42f, 0.06f)

@Serializable
private class CurriculumEpisode(val title: String = "", val focus: String = "")

@Serializable
private class Curriculum(val title: String = "", val episodes: List<CurriculumEpisode> = emptyList())

private val lenient = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true; allowSpecialFloatingPointValues = true }

private val MODE_HINT = mapOf(
    "Explanation" to "Explain the idea clearly from the ground up, with one everyday example.",
    "Study" to "Write exam-ready study material: definitions, key facts, formulas and a memory trick.",
    "Homework" to "Work through the problem step by step, showing each step and the reason for it.",
)

/**
 * Makes a lesson on this phone, or a set of videos: Gemma plans the scenes as data (a template and its slots for each, like the website),
 * each language is translated (ML Kit, Gemma as the fallback), each scene is read aloud, and the result is saved. Translating and narrating
 * run side by side. All of it runs on background threads; the screen only watches the state.
 */
class Creator(
    private val llm: Llm, private val translator: Translator, private val tts: Tts, private val lessons: LessonStore,
    private val rewards: Rewards, private val profile: Profile, private val pdfs: PdfStore, private val study: StudyBuilder,
) {
    private val _state = MutableStateFlow(CreationState())
    val state: StateFlow<CreationState> = _state
    private var job: Job? = null
    private var epIndex = 0
    private var epCount = 1

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

    /** The screen has opened the first video: forget its id so it is not opened twice, but keep reporting the rest. */
    fun opened() { _state.value = _state.value.copy(lessonId = null, opened = true) }
    fun reset() { if (!_state.value.running) _state.value = CreationState() else opened() }

    private fun resetStages() { _state.value = _state.value.copy(pct = List(5) { 0f }, details = listOf("", "", "", "", ""), step = 0) }

    /** Updates one stage's detail line and percentage; the overall progress counts finished videos plus the weighted stages of this one, so it only moves forward. */
    @Synchronized private fun stage(step: Int, pct: Float? = null, status: String? = null, detail: String? = null) {
        val cur = _state.value
        val d = cur.details.toMutableList()
        if (detail != null) d[step] = detail
        val p = cur.pct.toMutableList()
        if (pct != null) p[step] = maxOf(p[step], pct.coerceIn(0f, 1f))
        val within = p.indices.sumOf { (p[it] * WEIGHT[it]).toDouble() }.toFloat()
        val firstOpen = p.indexOfFirst { it < 1f }.let { if (it < 0) 4 else it }
        val overall = ((epIndex + within) / epCount)
        _state.value = cur.copy(step = firstOpen, progress = maxOf(cur.progress, overall), status = status ?: cur.status, details = d, pct = p)
    }

    private suspend fun make(req: LessonRequest) {
        val codes = req.languages.map { langByName(it).code }.distinct().ifEmpty { listOf("en") }
        val pdf = req.source.removePrefix("pdf:").takeIf { req.source.startsWith("pdf:") }?.let { pdfs.get(it) }
        val topic = req.concept.ifBlank { pdf?.name?.removeSuffix(".pdf") ?: "Your lesson" }
        val wanted = req.videos.toIntOrNull() ?: 0                       // 0 = Auto: the tutor decides

        stage(0, 0.3f, "Loading the tutor", if (pdf != null) "From ${pdf.name}" else "From Gemma's own knowledge, on this phone")
        llm.warmUp()
        stage(0, 1f)

        // One video, or a set of videos: every video is a lesson of the chosen length
        var outline: List<Pair<String, String>> = listOf(topic to "")
        var courseTitle = topic
        if (wanted != 1) {
            val chapters = pdf?.let { pdfs.chapters(it.id) }.orEmpty()
            if (wanted == 0 && chapters.size >= 2) {
                outline = chapters.take(8).map { it.title to it.title }
            } else {
                stage(1, 0.02f, "Planning the videos", "Gemma · ${llm.backendName}")
                val cur = curriculum(topic, wanted, pdf?.let { pdfs.retrieve(it.id, topic, 1500) }.orEmpty())
                courseTitle = cur.first
                outline = cur.second
            }
        }
        epCount = outline.size
        val courseId = if (epCount > 1) UUID.randomUUID().toString().take(8) else ""
        var course = if (courseId.isNotEmpty()) Course(courseId, topic, courseTitle, System.currentTimeMillis(), outline.mapIndexed { i, (t, f) -> EpisodeRef(i, t, f) }) else null
        course?.let { lessons.saveCourse(it) }

        val made = ArrayList<Lesson>()
        for ((i, o) in outline.withIndex()) {
            epIndex = i
            resetStages()
            _state.value = _state.value.copy(episode = i, episodes = epCount, episodeTitle = o.first)
            stage(0, 1f, detail = pdf?.let { "From ${it.name}" } ?: "From Gemma's own knowledge, on this phone")
            val series = if (epCount > 1) "This is video ${i + 1} of $epCount in the course \"$courseTitle\". " +
                (if (i > 0) "Earlier videos: ${outline.take(i).joinToString("; ") { it.first }}. " else "") +
                "This video teaches: ${o.second.ifBlank { o.first }}. " + (outline.getOrNull(i + 1)?.let { "The next video is \"${it.first}\"; do not cover it. " } ?: "") else ""
            val subject = if (epCount > 1) "$topic: ${o.first}" else topic
            val lesson = try {
                makeLesson(req, codes, subject, series, pdf, o.second.ifBlank { o.first }, courseId, i, if (epCount > 1) o.first else "", announce = i == 0)
            } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                if (epCount == 1) throw e
                Log.e("Chanakya", "video ${i + 1} failed", e)
                course = course?.copy(episodes = course!!.episodes.map { if (it.index == i) it.copy(status = "failed", error = e.message ?: "") else it })?.also { lessons.saveCourse(it) }
                continue
            }
            made.add(lesson)
            course = course?.copy(episodes = course!!.episodes.map { if (it.index == i) it.copy(lessonId = lesson.id, status = "ready") else it })?.also { lessons.saveCourse(it) }
            rewards.award("lesson_created", codes)
            if (made.size == 1 && !_state.value.opened) _state.value = _state.value.copy(lessonId = lesson.id)   // (normally already opened on its first scene)
        }
        require(made.isNotEmpty()) { "None of the videos could be made." }
        _state.value = _state.value.copy(running = false, progress = 1f, status = "Ready", pct = List(5) { 1f })
        Graph.scope.launch { made.forEach { study.prebuild(it) } }                                 // flashcards, quiz, mind map and notes, made in the background
    }

    /** One video: the first language is made scene by scene while Gemma writes the plan (so it can be watched at once); the other languages follow, in parallel. */
    private suspend fun makeLesson(
        req: LessonRequest, codes: List<String>, subject: String, series: String, pdf: PdfMeta?, focus: String, courseId: String, episode: Int, episodeTitle: String, announce: Boolean,
    ): Lesson {
        val id = UUID.randomUUID().toString().take(8)
        val sceneCount = (req.seconds / 10).coerceIn(3, 16)
        stage(1, 0.02f, "Planning $sceneCount scenes", "Gemma · ${llm.backendName}")
        val material = pdf?.let { pdfs.retrieve(it.id, "$focus $subject") }.orEmpty()
        val first = codes.first()
        val firstName = LANGS.first { it.code == first }.name
        val preview = ScenePreview(Graph.scope, id, subject, first, codes, sceneCount, lessons, translator, tts, req.mode, req.source, courseId, episode, episodeTitle,
            onNarrated = { n -> stage(3, n.toFloat() / (sceneCount * codes.size).coerceAtLeast(1), "Recording $firstName narration", "Piper voices · $firstName") },
            onFirst = { if (announce) _state.value = _state.value.copy(lessonId = id) })              // the player opens on scene 1 now
        val (title, planScenes) = try {
            plan(req, subject, series, material, sceneCount) { preview.feed(it) }
        } catch (e: Throwable) { preview.cancel(); throw e }
        stage(1, 1f)
        val en = Track("en", title, planScenes)
        val firstTrack = preview.finish(planScenes)                      // null when the finished plan differs from what was shown (then it is made again)

        // The other languages: translate one after another and narrate each as soon as it is translated, side by side.
        val todo = codes.filter { firstTrack == null || it != first }
        val toTranslate = todo.filter { it != "en" }
        val perLang = 1 + en.scenes.sumOf { it.texts().size }
        val translateTotal = (perLang * toTranslate.size).coerceAtLeast(1)
        val translated = AtomicInteger(0)
        val narrateTotal = (en.scenes.size * codes.size).coerceAtLeast(1)
        val narrated = AtomicInteger(if (firstTrack != null) en.scenes.size else 0)
        if (toTranslate.isEmpty()) stage(2, 1f, detail = "No translation needed")
        else stage(2, 0.01f, "Translating", toTranslate.joinToString(", ") { c -> LANGS.first { it.code == c }.name } + " · ML Kit")

        val done = ArrayList<Track>()
        firstTrack?.let { done.add(it) }
        val publishLock = kotlinx.coroutines.sync.Mutex()
        suspend fun publish(final: Boolean) = publishLock.withLock {
            val sorted = done.sortedBy { codes.indexOf(it.lang) }
            lessons.save(Lesson(id, subject, System.currentTimeMillis(), req.mode, sorted.ifEmpty { listOf(en) }, plan = en, courseId = courseId, episode = episode, episodeTitle = episodeTitle,
                source = req.source, building = !final, scenesTotal = en.scenes.size, pending = codes.filter { c -> sorted.none { it.lang == c } }))
        }

        suspend fun narrate(track: Track): Track {
            val name = LANGS.first { it.code == track.lang }.name
            return track.copy(scenes = track.scenes.mapIndexed { i, sc ->
                stage(3, narrated.get().toFloat() / narrateTotal, "Recording $name narration", "Piper voices · $name")
                val speech = tts.speak(sc.narration, track.lang, lessons.audio(id, track.lang, i))
                stage(3, narrated.incrementAndGet().toFloat() / narrateTotal)
                sc.copy(audio = speech?.file?.name, seconds = ((speech?.seconds ?: (sc.narration.split(' ').size / 2.4f)) + 0.6f))
            })
        }

        coroutineScope {
            val jobs = ArrayList<Deferred<Unit>>()
            for (code in todo) {
                Trace.mark("translating to $code")
                val t = if (code == "en") en else translate(en, code) { stage(2, translated.incrementAndGet().toFloat() / translateTotal) }
                Trace.mark("translated to $code")
                jobs.add(async(Dispatchers.Default) { val voiced = narrate(t); synchronized(done) { done.add(voiced) }; publish(false) })      // each language appears as its tab is ready
            }
            if (toTranslate.isNotEmpty()) stage(2, 1f)
            jobs.awaitAll()
        }

        stage(4, 0.4f, "Putting the scenes together", "${planScenes.size} scenes")
        publish(true)
        stage(4, 1f, "Ready")
        return lessons.load(id)!!
    }

    /** The outline of a set of videos: one idea each, building up. `wanted` 0 lets the tutor choose how many. */
    private suspend fun curriculum(topic: String, wanted: Int, material: String): Pair<String, List<Pair<String, String>>> {
        val how = if (wanted > 0) "exactly $wanted videos" else "between 3 and 6 videos, one per idea the learner must understand"
        val system = "You design short video courses. Reply with one JSON object and nothing else."
        val user = "Design a course of $how that teaches: $topic.\nEach video teaches ONE clear idea and builds on the one before. The first gives the big picture, the last is a recap. Titles are at most 6 words and name the idea (not 'Part 2'). Each focus is one sentence.\n" +
            (if (material.isNotBlank()) "Material from the learner:\n$material\n" else "") +
            """JSON: {"title": "course title", "episodes": [{"title": "...", "focus": "..."}]}"""
        repeat(3) { attempt ->
            val reply = llm.ask(system, user, if (attempt == 0) 0.4 else 0.2)
            val cur = extractJson(reply)?.let { runCatching { lenient.decodeFromString<Curriculum>(it) }.getOrNull() }
            val eps = cur?.episodes?.filter { it.title.isNotBlank() }.orEmpty()
            if (eps.size >= 2) return (cur!!.title.ifBlank { topic }) to eps.take(if (wanted > 0) wanted else 8).map { it.title.trim() to it.focus.trim() }
        }
        val steps = listOf("The big picture", "The core idea", "A worked example", "Common mistakes", "Going one step further", "Putting it together", "Practice time", "Recap")
        val n = if (wanted > 0) wanted else 4
        return topic to (steps.take(n - 1) + steps.last()).take(n).map { it to "$it of $topic" }
    }

    private suspend fun plan(req: LessonRequest, subject: String, series: String, material: String, n: Int, onText: (String) -> Unit = {}): Pair<String, List<SceneT>> {
        val hint = when (domainOf(subject)) {
            "maths" -> "This is a maths topic: use graph scenes with real, correct curves and points."
            "code" -> "This is a programming topic: use code scenes with a tiny correct snippet, plus flow or diagram scenes for ideas."
            else -> "Prefer flow, cycle, diagram and compare scenes when they fit the idea."
        }
        val system = "You are Chanakya, a teacher who writes short narrated video lessons as data. ${profile.audience()}${MODE_HINT[req.mode] ?: ""} Reply with one JSON object and nothing else."
        val user = buildString {
            append("Write a lesson about \"$subject\" in exactly $n scenes.\n")
            if (series.isNotBlank()) append(series).append('\n')
            if (material.isNotBlank()) append("Use only facts from this material from the learner's own document:\n").append(material.take(3200)).append("\n\n")
            append(hint).append('\n').append(TEMPLATE_GUIDE).append('\n')
            append("""JSON shape: {"title": "short title", "scenes": [{"template": "title", "heading": "...", "narration": "...", "icon": "lightbulb", "items": []}, ...]}""").append('\n')
            append("Scene 1 is template \"title\". Use at least ${minOf(4, n)} different templates so it is not all bullets. The last scene is \"summary\" or \"quiz\". Be accurate. Output only the JSON.")
        }
        val expected = n * 430f                                              // about how many characters the JSON for n scenes comes to
        repeat(3) { attempt ->
            val reply = llm.askStreaming(system, user, temperature = if (attempt == 0) 0.4 else 0.2) { text -> onText(text); stage(1, 0.02f + 0.95f * (text.length / expected).coerceAtMost(1f)) }
            val doc = extractJson(reply)?.let { runCatching { lenient.decodeFromString<PlanDoc>(it) }.getOrNull() }
            if (doc != null && doc.scenes.size >= 2) {
                runCatching { return normalizePlan(PlanDoc(doc.title.ifBlank { subject }, doc.scenes)) }.onFailure { Log.w("Chanakya", "plan not usable: ${it.message}") }
            }
            Log.w("Chanakya", "plan attempt $attempt not usable: ${reply.take(160)}")
        }
        error("The tutor could not plan that lesson. Try again, or word the topic differently.")
    }

    private suspend fun translate(en: Track, code: String, onEach: () -> Unit): Track {
        val flat = ArrayList<String>()
        flat.add(en.title)
        en.scenes.forEach { flat.addAll(it.texts()) }
        val out = translator.translate(flat, code, onEach)
        val it = out.iterator()
        val title = it.next()
        val scenes = en.scenes.map { sc -> sc.withTexts { it.next() } }
        return Track(code, title, scenes)
    }
}
