package com.kabir.unlox_hackethon.data

import android.app.Application
import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.LocalDate
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.math.sqrt

// ---------------------------------------------------------------- rewards and progress

data class DayStat(val day: String, val xp: Int, val lessons: Int, val quiz: Int, val ask: Int)

/** XP, streak, level and badges, kept on the phone. The same rules as the website: you earn by learning, a day counts at 20 XP. */
class Rewards(context: Context) {
    private val sp = context.getSharedPreferences("rewards", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }
    private var days: MutableMap<String, DayStat> = runCatching { json.decodeFromString<Map<String, DayRow>>(sp.getString("days", "{}")!!).mapValues { (k, v) -> DayStat(k, v.xp, v.lessons, v.quiz, v.ask) }.toMutableMap() }.getOrDefault(mutableMapOf())
    /** Bumped on every change so screens that read the numbers update. */
    var version by mutableIntStateOf(0)
        private set

    @Serializable private class DayRow(val xp: Int = 0, val lessons: Int = 0, val quiz: Int = 0, val ask: Int = 0)

    val xp get() = days.values.sumOf { it.xp }
    val level get() = 1 + sqrt(xp / 50.0).toInt()
    val levelFloor get() = 50 * (level - 1) * (level - 1)
    val nextXp get() = 50 * level * level
    val lessonsMade get() = sp.getInt("lessons", 0)
    val questions get() = sp.getInt("questions", 0)
    val quizRight get() = sp.getInt("quizRight", 0)
    val perfectQuizzes get() = sp.getInt("perfect", 0)
    val homeworkSets get() = sp.getInt("homework", 0)
    val languagesUsed get() = sp.getStringSet("langs", emptySet())!!.size
    val goal = 50

    private fun today() = LocalDate.now().toString()
    fun history(n: Int): List<DayStat> = (n - 1 downTo 0).map { back -> LocalDate.now().minusDays(back.toLong()).toString().let { d -> days[d] ?: DayStat(d, 0, 0, 0, 0) } }

    /** Current streak in days (today may still be to do). */
    val streak: Int get() {
        var d = LocalDate.now()
        if ((days[d.toString()]?.xp ?: 0) < 20) d = d.minusDays(1)
        var n = 0
        while ((days[d.toString()]?.xp ?: 0) >= 20) { n++; d = d.minusDays(1) }
        return n
    }
    val bestStreak: Int get() = maxOf(streak, sp.getInt("best", 0))

    fun award(kind: String, langs: List<String> = emptyList(), perfect: Boolean = false) {
        val gain = when (kind) { "lesson_created" -> 30; "lesson_complete" -> 20; "quiz_correct" -> 10; "card_known" -> 4; "tutor_question" -> 3; "study_tool" -> 5; "homework" -> 25; else -> 0 }
        val cur = days[today()] ?: DayStat(today(), 0, 0, 0, 0)
        if (cur.xp >= 200) return                                    // a daily cap: XP is for learning, not for tapping
        days[today()] = cur.copy(xp = cur.xp + gain, lessons = cur.lessons + if (kind == "lesson_created") 1 else 0, quiz = cur.quiz + if (kind == "quiz_correct") 1 else 0, ask = cur.ask + if (kind == "tutor_question") 1 else 0)
        val e = sp.edit()
        when (kind) {
            "lesson_created" -> { e.putInt("lessons", lessonsMade + 1); e.putStringSet("langs", sp.getStringSet("langs", emptySet())!! + langs) }
            "tutor_question" -> e.putInt("questions", questions + 1)
            "quiz_correct" -> e.putInt("quizRight", quizRight + 1)
            "homework" -> e.putInt("homework", homeworkSets + 1)
        }
        if (perfect) e.putInt("perfect", perfectQuizzes + 1)
        e.putInt("best", maxOf(sp.getInt("best", 0), streak))
        e.putString("days", json.encodeToString(days.mapValues { (_, v) -> DayRow(v.xp, v.lessons, v.quiz, v.ask) })).apply()
        version++
    }
}

// ---------------------------------------------------------------- the tutor

/** Answers questions about the lesson with Gemma, in the language the question was asked in. */
class LlmTutor(private val llm: Llm, private val profile: Profile) {
    suspend fun ask(question: String, lesson: Lesson?, lang: String, scene: Int, history: List<Pair<String, String>>): String {
        val code = detectLanguage(question, lang)
        val name = LANGS.first { it.code == code }.name
        val track = lesson?.track("en")
        val outline = track?.scenes?.mapIndexed { i, s -> "${i + 1}. ${s.heading}: ${s.narration}" }?.joinToString("\n").orEmpty()
        val here = track?.scenes?.getOrNull(scene)
        val system = buildString {
            append("You are Chanakya, a patient, friendly tutor inside a learning app. ${profile.audience()}")
            append("Answer in at most 4 short sentences, in simple words, with one everyday example when it helps. Reply in $name. ")
            append("If you are not sure, say so instead of guessing. ")
            if (track != null) append("\nThe learner is watching the lesson \"${track.title}\":\n$outline\n${if (here != null) "They are on scene ${scene + 1}: ${here.heading}." else ""}")
        }
        return llm.ask(system, question, 0.4, history.takeLast(4))
    }
}

// ---------------------------------------------------------------- study tools

@Serializable data class CardT(val front: String, val back: String)
@Serializable data class QuestionT(val text: String, val options: List<String>, val answer: Int, val why: String = "")
@Serializable data class IdeaT(val label: String, val note: String)
@Serializable data class MindMapT(val center: String, val ideas: List<IdeaT>)
@Serializable data class NoteT(val head: String, val items: List<String>)

/** Flashcards, quiz, mind map and notes made from a lesson by Gemma; each is made once and kept with the lesson. */
class StudyBuilder(private val llm: Llm, private val store: LessonStore) {
    private val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }

    private fun context(l: Lesson): String = l.track("en").let { t -> "Lesson \"${t.title}\":\n" + t.scenes.joinToString("\n") { "- ${it.heading}: ${it.narration}" } }
    private val system = "You make study material from a lesson. Reply with JSON only, no other text. Be accurate and keep every line short."

    private suspend inline fun <reified T> make(l: Lesson, kind: String, prompt: String): T {
        val file = store.study(l.id, kind)
        if (file.exists()) runCatching { return json.decodeFromString<T>(file.readText()) }
        repeat(3) {
            val reply = llm.ask(system, "${context(l)}\n\n$prompt", if (it == 0) 0.4 else 0.2)
            val parsed = extractJson(reply)?.let { s -> runCatching { json.decodeFromString<T>(s) }.getOrNull() }
            if (parsed != null) { file.writeText(extractJson(reply)!!); return parsed }
        }
        error("The tutor could not make that. Try again.")
    }

    suspend fun cards(l: Lesson): List<CardT> = make<List<CardT>>(l, "cards", """Make 6 flashcards. JSON: [{"front": "question", "back": "short answer"}]""").filter { it.front.isNotBlank() }
    suspend fun quiz(l: Lesson): List<QuestionT> = make<List<QuestionT>>(l, "quiz", """Make 4 multiple-choice questions with 4 options each. "answer" is the index 0-3 of the right option. JSON: [{"text": "question", "options": ["a","b","c","d"], "answer": 1, "why": "one sentence reason"}]""")
        .filter { it.options.size >= 2 && it.answer in it.options.indices }
    suspend fun mindMap(l: Lesson): MindMapT = make<MindMapT>(l, "mindmap", """Make a mind map: the main idea and 6 ideas around it. JSON: {"center": "main idea", "ideas": [{"label": "one or two words", "note": "one sentence"}]}""")
    suspend fun notes(l: Lesson): List<NoteT> = make<List<NoteT>>(l, "notes", """Write one page of notes in 4 sections. JSON: [{"head": "section title", "items": ["short point", "short point"]}]""")
}

// ---------------------------------------------------------------- homework

private suspend fun <T> com.google.android.gms.tasks.Task<T>.awaitIt(): T = suspendCancellableCoroutine { c ->
    addOnSuccessListener { c.resume(it) }.addOnFailureListener { c.resumeWithException(it) }
}

/** Reads the homework photos with ML Kit, finds the questions, and answers them one by one with Gemma. */
class LlmHomework(private val app: Application, private val llm: Llm, private val profile: Profile) {
    @Volatile var photos: List<Bitmap> = emptyList()

    private suspend fun read(b: Bitmap): String {
        val image = InputImage.fromBitmap(b, 0)
        val latin = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        val deva = TextRecognition.getClient(DevanagariTextRecognizerOptions.Builder().build())
        val a = runCatching { latin.process(image).awaitIt().text }.getOrDefault("")
        val d = runCatching { deva.process(image).awaitIt().text }.getOrDefault("")
        latin.close(); deva.close()
        return if (d.count { it.code in 0x0900..0x097F } > a.length / 4) d else a
    }

    fun solve(typed: String): Flow<Answer> = flow {
        val text = buildString {
            for (b in photos) appendLine(withContext(Dispatchers.Default) { read(b) })
            append(typed)
        }.trim()
        val system = "You are Chanakya, a careful tutor who solves homework. ${profile.audience()}"
        val listed = llm.ask("You find the questions in homework text. Reply with a JSON array of strings only.", "Homework text:\n$text\n\nList every separate question or problem, in order, each as one string. Output only the JSON array.", 0.1)
        val questions = extractJson(listed)?.let { runCatching { Json.decodeFromString(ListSerializer(String.serializer()), it) }.getOrNull() }?.filter { it.isNotBlank() }?.take(12)
            ?: listOf(text.take(600))
        for ((i, q) in questions.withIndex()) {
            val a = llm.ask(system + " Show the steps briefly, then the final answer. Use plain text, no markdown tables.", q, 0.2)
            emit(Answer(if (q.startsWith("Q${i + 1}")) q else "Q${i + 1}. $q", a))
        }
    }.flowOn(Dispatchers.Default)
}
