package com.kabir.unlox_hackethon.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

@Serializable
data class CurveT(val type: String = "line", val a: Double = 1.0, val b: Double = 0.0, val c: Double = 0.0, val d: Double = 0.0)

@Serializable
data class MarkT(val kind: String = "point", val x: Double = 0.0, val y: Double = 0.0)

/**
 * One scene of a lesson in one language, as data: which template draws it (`kind`) and the slots that template fills, the narration,
 * and the narration file. The renderer (ui/scene) decides how it looks and moves; nothing here is ever run.
 */
@Serializable
data class SceneT(
    val kind: String, val heading: String, val items: List<String> = emptyList(), val narration: String, val audio: String? = null, val seconds: Float = 8f,
    val icon: String = "lightbulb", val leftTitle: String = "", val rightTitle: String = "", val left: List<String> = emptyList(), val right: List<String> = emptyList(),
    val answerIndex: Int = 0, val curves: List<CurveT> = emptyList(), val marks: List<MarkT> = emptyList(), val xRange: List<Double> = emptyList(),
    val yRange: List<Double> = emptyList(), val equation: String = "", val codeLang: String = "", val code: List<String> = emptyList(),
    val highlights: List<Int> = emptyList(), val output: List<String> = emptyList(),
)

@Serializable
data class Track(val lang: String, val title: String, val scenes: List<SceneT>)

/** A lesson. `plan` is the English text the tutor and the study tools read, kept even when English is not one of the languages shown. */
@Serializable
data class Lesson(
    val id: String, val concept: String, val created: Long, val mode: String = "Explanation", val tracks: List<Track>,
    val plan: Track? = null, val courseId: String = "", val episode: Int = 0, val episodeTitle: String = "", val source: String = "",
    /** True while the first scenes can be watched and the rest are still being made; `scenesTotal` is about how many there will be, `pending` the languages still to come. */
    val building: Boolean = false, val scenesTotal: Int = 0, val pending: List<String> = emptyList(),
) {
    fun track(lang: String) = tracks.firstOrNull { it.lang == lang } ?: tracks.first()
    /** The English version for the model to read. */
    val planTrack get() = plan ?: tracks.firstOrNull { it.lang == "en" } ?: tracks.first()
    val title get() = tracks.first().title
    val seconds get() = tracks.first().scenes.sumOf { it.seconds.toDouble() }.toInt()
    val languages get() = tracks.map { it.lang }
}

data class LessonMeta(val id: String, val title: String, val languages: List<String>, val seconds: Int, val created: Long, val courseId: String = "", val episode: Int = 0)

/** A set of videos on one topic (or one PDF), each its own lesson of the chosen length. */
@Serializable
data class EpisodeRef(val index: Int, val title: String, val focus: String, val lessonId: String? = null, val status: String = "pending", val error: String = "")

@Serializable
data class Course(val id: String, val topic: String, val title: String, val created: Long, val episodes: List<EpisodeRef>)

/** Lessons on this phone: one folder each, with `lesson.json` and the narration files next to it. */
class LessonStore(context: Context) {
    val root = File(context.filesDir, "lessons").apply { mkdirs() }
    val json = Json { ignoreUnknownKeys = true; isLenient = true; encodeDefaults = true }

    fun dir(id: String) = File(root, id).apply { mkdirs() }
    fun audio(id: String, lang: String, n: Int) = File(dir(id), "audio_${lang}_$n.wav")
    fun study(id: String, kind: String) = File(dir(id), "study_$kind.json")

    /** Written to a temporary file and renamed, so a screen that reloads the lesson while it is being made never reads half of it. */
    @Synchronized fun save(l: Lesson) {
        val f = File(dir(l.id), "lesson.json")
        val tmp = File(f.parentFile, "lesson.tmp")
        tmp.writeText(json.encodeToString(l))
        if (!tmp.renameTo(f)) { f.delete(); tmp.renameTo(f) }
    }

    fun load(id: String): Lesson? = runCatching { json.decodeFromString<Lesson>(File(root, "$id/lesson.json").readText()) }.getOrNull()

    fun list(): List<LessonMeta> = root.listFiles { f -> f.isDirectory }.orEmpty().mapNotNull { d ->
        load(d.name)?.let { LessonMeta(it.id, it.title, it.languages, it.seconds, it.created, it.courseId, it.episode) }
    }.sortedByDescending { it.created }

    fun delete(id: String) { File(root, id).deleteRecursively() }

    private fun courseFile(id: String) = File(root.parentFile, "courses/$id.json").apply { parentFile!!.mkdirs() }
    fun saveCourse(c: Course) { courseFile(c.id).writeText(json.encodeToString(c)) }
    fun loadCourse(id: String): Course? = runCatching { json.decodeFromString<Course>(courseFile(id).readText()) }.getOrNull()
}
