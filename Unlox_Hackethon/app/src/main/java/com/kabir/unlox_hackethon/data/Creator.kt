package com.kabir.unlox_hackethon.data

import android.os.SystemClock
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

private const val LONG_S = 90        // a video longer than this is planned in parts
private const val PART_S = 40        // about how long one part is: a 2 minute video is 3 parts, never more (more parts, a less coherent video)

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
        synchronized(this) { resetLive() }
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

    // What the stages have really reached. The screen is told about it at most every 120 ms (or when something visible changes): the planner
    // reports once per token, and every report used to rebuild the whole app, which is what made the phone stutter while a lesson was made.
    private val livePct = FloatArray(5)
    private val liveDetails = Array(5) { "" }
    private var liveProgress = 0f
    private var lastPublish = 0L
    private var lastPublished = 0f

    private fun resetLive(progress: Float = 0f) { livePct.fill(0f); liveDetails.fill(""); liveProgress = progress; lastPublished = progress }

    private fun resetStages() {
        synchronized(this) {
            livePct.fill(0f); liveDetails.fill("")
            _state.value = _state.value.copy(pct = List(5) { 0f }, details = listOf("", "", "", "", ""), step = 0)
        }
    }

    /** Updates one stage's detail line and percentage; the overall progress counts finished videos plus the weighted stages of this one, so it only moves forward. */
    @Synchronized private fun stage(step: Int, pct: Float? = null, status: String? = null, detail: String? = null) {
        val cur = _state.value
        if (detail != null) liveDetails[step] = detail
        if (pct != null) livePct[step] = maxOf(livePct[step], pct.coerceIn(0f, 1f))
        val within = livePct.indices.sumOf { (livePct[it] * WEIGHT[it]).toDouble() }.toFloat()
        liveProgress = maxOf(liveProgress, (epIndex + within) / epCount)
        val now = SystemClock.uptimeMillis()
        val visible = (status != null && status != cur.status) || (detail != null && detail != cur.details[step]) || (pct != null && pct >= 1f) || liveProgress - lastPublished >= 0.02f
        if (!visible && now - lastPublish < 120) return
        lastPublish = now
        lastPublished = liveProgress
        val firstOpen = livePct.indexOfFirst { it < 1f }.let { if (it < 0) 4 else it }
        _state.value = cur.copy(step = firstOpen, progress = maxOf(cur.progress, liveProgress), status = status ?: cur.status, details = liveDetails.toList(), pct = livePct.toList())
    }

    private suspend fun make(req: LessonRequest) {
        val codes = req.languages.map { langByName(it).code }.distinct().ifEmpty { listOf("en") }
        val pdf = req.source.removePrefix("pdf:").takeIf { req.source.startsWith("pdf:") }?.let { pdfs.get(it) }
        val topic = req.concept.ifBlank { pdf?.name?.removeSuffix(".pdf") ?: "Your lesson" }.let { cleanTopic(it) }       // never "Teach me about ..." in a title or caption
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
                outline = chapters.take(3).map { it.title to it.title }
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
                makeLesson(req, codes, subject, series, pdf, o.second.ifBlank { o.first }, courseId, i, if (epCount > 1) o.first else "", announce = i == 0,
                    onEpisodeFirst = { id -> course = course?.copy(episodes = course!!.episodes.map { if (it.index == i) it.copy(lessonId = id, status = "building") else it })?.also { lessons.saveCourse(it) } })
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
        onEpisodeFirst: (String) -> Unit = {},
    ): Lesson {
        val id = UUID.randomUUID().toString().take(8)
        val sceneCount = (req.seconds / 10).coerceIn(3, 16)
        stage(1, 0.02f, "Planning $sceneCount scenes", "Gemma · ${llm.backendName}")
        val material = pdf?.let { pdfs.retrieve(it.id, "$focus $subject") }.orEmpty()
        val first = codes.first()
        val firstName = LANGS.first { it.code == first }.name
        val preview = ScenePreview(Graph.scope, id, subject, first, codes, sceneCount, lessons, translator, tts, req.mode, req.source, courseId, episode, episodeTitle,
            onNarrated = { n -> stage(3, n.toFloat() / (sceneCount * codes.size).coerceAtLeast(1), "Recording $firstName narration", "Piper voices · $firstName") },
            onFirst = { onEpisodeFirst(id); if (announce) _state.value = _state.value.copy(lessonId = id) })              // the player opens on scene 1 now (and the course lists this video)
        val (title, planScenes) = try {
            if (req.seconds > LONG_S) planParts(req, subject, series, material, preview)
            else plan(req, subject, series, material, sceneCount) { preview.feed(it) }
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

    /**
     * A video longer than [LONG_S] seconds: an outline first, then one part of about 30 seconds at a time ("part k of n of ONE video"), like the website.
     * Part 1 is made scene by scene while it is written; every later part is handed to the player whole, in order, as soon as it is finished.
     */
    private suspend fun planParts(req: LessonRequest, subject: String, series: String, material: String, preview: ScenePreview): Pair<String, List<SceneT>> {
        val n = ((req.seconds + 20) / PART_S).coerceIn(2, 3)
        stage(1, 0.02f, "Outlining $n parts", "Gemma · ${llm.backendName}")
        val (title, parts) = curriculum(subject, n, material, "parts of ONE continuous video")
        val raw = ArrayList<PlanScene>()
        for (k in 0 until n) {
            val goal = parts.getOrNull(k)?.second?.ifBlank { null } ?: parts.getOrNull(k)?.first ?: subject
            val partSeries = series + "This is part ${k + 1} of $n of ONE continuous video titled \"$title\" about $subject. This part teaches only: $goal. " +
                (if (k > 0) "Already covered (do NOT repeat these headings, points, examples or code; build on them and go further):\n${taughtOf(raw)}\nDo NOT start with a title scene or a greeting: continue straight on. " else "") +
                (if (k < n - 1) "No quiz and no summary here: end with one sentence leading into \"${parts[k + 1].first}\". " else "This is the last part: end with a quiz scene and then a summary scene. ")
            plan(req, subject, partSeries, material, if (k == n - 1) 4 else 3, part = k + 1,
                onRaw = { scenes -> raw.addAll(scenes); if (k > 0) preview.addScenes(scenes) },
                progress = { f -> stage(1, 0.05f + 0.95f * (k + f) / n) }) { text -> if (k == 0) preview.feed(text) }
        }
        return normalizePlan(PlanDoc(title, raw))
    }

    /** What the parts written so far really contain (headings, first points, the first line of code), for the next part to build on. */
    private fun taughtOf(scenes: List<PlanScene>): String = scenes.filter { it.template !in setOf("title", "quiz", "summary") }.joinToString("\n") { s ->
        "- ${s.heading}: ${s.items.take(3).joinToString("; ").ifBlank { s.narration.substringBefore('.').take(80) }}" + (s.code.firstOrNull { it.isNotBlank() }?.let { " [code: ${it.trim().take(60)}]" } ?: "")
    }.take(900)

    /** "Make one more video on X", asked in the tutor chat: it joins the lesson's playlist (a lesson on its own becomes video 1 of a new one) and is made scene by scene. Null while another lesson is being made. */
    fun addVideo(base: Lesson, topic: String, seconds: Int, onFirst: (String) -> Unit, onDone: (Lesson?) -> Unit): String? {
        if (_state.value.running) return null
        val codes = base.tracks.map { it.lang }
        val baseTitle = base.tracks.first().title
        var course = base.courseId.takeIf { it.isNotEmpty() }?.let { lessons.loadCourse(it) }
        if (course == null) {
            val cid = UUID.randomUUID().toString().take(8)
            course = Course(cid, base.concept, baseTitle, System.currentTimeMillis(), listOf(EpisodeRef(0, baseTitle, base.concept, base.id, "ready")))
            lessons.saveCourse(course)
            lessons.save(base.copy(courseId = cid, episode = 0, episodeTitle = baseTitle))
        }
        val index = course.episodes.size
        val title = topic.replaceFirstChar { it.uppercase() }
        val courseId = course.id
        lessons.saveCourse(course.copy(episodes = course.episodes + EpisodeRef(index, title, topic, null, "pending")))
        job?.cancel()
        synchronized(this) { resetLive() }
        epIndex = 0; epCount = 1
        _state.value = CreationState(running = true, status = "Making the next video", episodeTitle = title)
        job = Graph.scope.launch {
            fun mark(change: (EpisodeRef) -> EpisodeRef) { lessons.loadCourse(courseId)?.let { c -> lessons.saveCourse(c.copy(episodes = c.episodes.map { if (it.index == index) change(it) else it })) } }
            try {
                val names = codes.map { c -> LANGS.first { it.code == c }.name }
                val req = LessonRequest(topic, names, seconds, "", base.mode)
                llm.warmUp()
                stage(0, 1f, "Making the next video", "From Gemma's own knowledge, on this phone")
                val lesson = makeLesson(req, codes, topic, "", null, topic, courseId, index, title, announce = false,
                    onEpisodeFirst = { id -> mark { it.copy(lessonId = id, status = "building") }; onFirst(id) })
                mark { it.copy(lessonId = lesson.id, status = "ready") }
                rewards.award("lesson_created", codes)
                _state.value = _state.value.copy(running = false, progress = 1f, status = "Ready", pct = List(5) { 1f })
                onDone(lesson)
                Graph.scope.launch { study.prebuild(lesson) }
            } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                Log.e("Chanakya", "extra video failed", e)
                mark { it.copy(status = "failed", error = e.message ?: "") }
                _state.value = _state.value.copy(running = false, error = e.message ?: e.javaClass.simpleName)
                onDone(null)
            }
        }
        return courseId
    }

    /** The outline of a set of videos: one idea each, building up. `wanted` 0 lets the tutor choose how many. */
    private suspend fun curriculum(topic: String, wanted: Int, material: String, noun: String = "videos"): Pair<String, List<Pair<String, String>>> {
        val how = if (wanted > 0) "exactly $wanted $noun" else "2 or 3 videos, one per idea the learner must understand (never more than 3)"
        val system = "You design short video courses. Reply with one JSON object and nothing else."
        val user = "Design a course of $how that teaches: $topic.\nEach video teaches ONE clear idea and builds on the one before. The first gives the big picture, the last is a recap. Titles are at most 6 words and name the idea (not 'Part 2'). Each focus is one sentence.\n" +
            (if (material.isNotBlank()) "Material from the learner:\n$material\n" else "") +
            """JSON: {"title": "course title", "episodes": [{"title": "...", "focus": "..."}]}"""
        repeat(3) { attempt ->
            val reply = llm.ask(system, user, if (attempt == 0) 0.4 else 0.2)
            val cur = extractJson(reply)?.let { runCatching { lenient.decodeFromString<Curriculum>(it) }.getOrNull() }
            val eps = cur?.episodes?.filter { it.title.isNotBlank() }.orEmpty()
            if (eps.size >= 2) return (cur!!.title.ifBlank { topic }) to eps.take(if (wanted > 0) wanted.coerceAtMost(3) else 3).map { it.title.trim() to it.focus.trim() }
        }
        val steps = listOf("The big picture", "The core idea", "A worked example", "Common mistakes", "Going one step further", "Putting it together", "Practice time", "Recap")
        val n = if (wanted > 0) wanted else 4
        return topic to (steps.take(n - 1) + steps.last()).take(n).map { it to "$it of $topic" }
    }

    private suspend fun plan(
        req: LessonRequest, subject: String, series: String, material: String, n: Int, part: Int = 0, onRaw: (List<PlanScene>) -> Unit = {},
        progress: (Float) -> Unit = { stage(1, it) }, onText: (String) -> Unit = {},
    ): Pair<String, List<SceneT>> {
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
            append(hint).append('\n').append(templateGuide(domainOf(subject))).append('\n')
            append("""JSON shape: {"title": "short title", "scenes": [{"template": "title", "heading": "...", "narration": "...", "icon": "lightbulb", "items": []}, ...]}""").append('\n')
            append("Every scene adds NEW information with a specific fact or real example, and the narration is 2-3 full sentences of about 25 words. Never repeat a heading, a point, an example or code that was already shown.").append('\n')
            if (domainOf(subject) == "code") append("Programming: build up in small steps; every code scene shows DIFFERENT code that builds on the one before, only the lines that matter, never a repeated class or main() skeleton.").append('\n')
            if (part == 0) append("Scene 1 is template \"title\". Use at least ${minOf(4, n)} different templates so it is not all bullets. The last scene is \"summary\" or \"quiz\". Be accurate. Output only the JSON.")
            else append("Use different templates for the scenes so it is not all bullets. Be accurate. Output only the JSON.")
        }
        val expected = n * 430f                                              // about how many characters the JSON for n scenes comes to
        repeat(3) { attempt ->
            val reply = llm.askStreaming(system, user, temperature = if (attempt == 0) 0.4 else 0.2) { text -> onText(text); progress(0.02f + 0.95f * (text.length / expected).coerceAtMost(1f)) }
            val doc = extractJson(reply)?.let { runCatching { lenient.decodeFromString<PlanDoc>(it) }.getOrNull() }
            if (doc != null && doc.scenes.size >= 2) {
                runCatching { val done = normalizePlan(PlanDoc(doc.title.ifBlank { subject }, doc.scenes)); onRaw(doc.scenes); return done }.onFailure { Log.w("Chanakya", "plan not usable: ${it.message}") }
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
