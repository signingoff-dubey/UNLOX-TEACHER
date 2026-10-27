package com.kabir.unlox_hackethon.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

/** One scene of a lesson in one language: what is on the card, what is said, and the narration file. */
@Serializable
data class SceneT(val kind: String, val heading: String, val items: List<String> = emptyList(), val narration: String, val audio: String? = null, val seconds: Float = 8f)

@Serializable
data class Track(val lang: String, val title: String, val scenes: List<SceneT>)

@Serializable
data class Lesson(val id: String, val concept: String, val created: Long, val mode: String = "Explanation", val tracks: List<Track>) {
    fun track(lang: String) = tracks.firstOrNull { it.lang == lang } ?: tracks.first()
    val title get() = tracks.first().title
    val seconds get() = tracks.first().scenes.sumOf { it.seconds.toDouble() }.toInt()
    val languages get() = tracks.map { it.lang }
}

data class LessonMeta(val id: String, val title: String, val languages: List<String>, val seconds: Int, val created: Long)

/** Lessons on this phone: one folder each, with `lesson.json` and the narration files next to it. */
class LessonStore(context: Context) {
    val root = File(context.filesDir, "lessons").apply { mkdirs() }
    val json = Json { ignoreUnknownKeys = true; isLenient = true; encodeDefaults = true }

    fun dir(id: String) = File(root, id).apply { mkdirs() }
    fun audio(id: String, lang: String, n: Int) = File(dir(id), "audio_${lang}_$n.wav")
    fun study(id: String, kind: String) = File(dir(id), "study_$kind.json")

    fun save(l: Lesson) { File(dir(l.id), "lesson.json").writeText(json.encodeToString(l)) }

    fun load(id: String): Lesson? = runCatching { json.decodeFromString<Lesson>(File(root, "$id/lesson.json").readText()) }.getOrNull()

    fun list(): List<LessonMeta> = root.listFiles { f -> f.isDirectory }.orEmpty().mapNotNull { d ->
        load(d.name)?.let { LessonMeta(it.id, it.title, it.languages, it.seconds, it.created) }
    }.sortedByDescending { it.created }

    fun delete(id: String) { File(root, id).deleteRecursively() }
}
