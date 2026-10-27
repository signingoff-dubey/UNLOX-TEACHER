package com.kabir.unlox_hackethon.data

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import java.io.File

/** The application: creates the one [Graph] that every screen shares. */
class ChanakyaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Graph.init(this)
    }
}

/**
 * Everything the screens use, created once: the learner's profile, the models on this phone, the engines that run them (all off the
 * main thread), and the stores for lessons and progress. Nothing here talks to the network except ML Kit's one-time language packs.
 */
object Graph {
    lateinit var app: Application
        private set
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val models by lazy { ModelStore(app) }
    val profile by lazy { Profile(app) }
    val llm by lazy { Llm(models, File(app.cacheDir, "litertlm").apply { mkdirs() }) }
    val tts by lazy { Tts(app, models) }
    val stt by lazy { Stt(models) }
    val translator by lazy { Translator(llm) }
    val lessons by lazy { LessonStore(app) }
    val rewards by lazy { Rewards(app) }
    val creator by lazy { Creator(llm, translator, tts, lessons, rewards, profile) }
    val tutor by lazy { LlmTutor(llm, profile) }
    val study by lazy { StudyBuilder(llm, lessons) }
    val homework by lazy { LlmHomework(app, llm, profile) }
    val player by lazy { ScenePlayer(app) }

    fun init(application: Application) { app = application }
}

/** The learner's name and age, kept on the phone and used to pitch every explanation. */
class Profile(context: Context) {
    private val sp = context.getSharedPreferences("profile", Context.MODE_PRIVATE)
    var name by mutableStateOf(sp.getString("name", "") ?: "")
        private set
    var age by mutableIntStateOf(sp.getInt("age", 0))
        private set

    fun save(name: String, age: Int) {
        this.name = name.trim().take(30)
        this.age = age.coerceIn(0, 120)
        sp.edit().putString("name", this.name).putInt("age", this.age).apply()
    }

    var speak by mutableStateOf(sp.getBoolean("speak", true))
        private set
    var captions by mutableStateOf(sp.getBoolean("captions", true))
        private set
    var intro by mutableStateOf(sp.getBoolean("intro", true))
        private set

    fun setPref(key: String, on: Boolean) {
        when (key) { "speak" -> speak = on; "captions" -> captions = on; "intro" -> intro = on }
        sp.edit().putBoolean(key, on).apply()
    }

    /** What to call the learner in a sentence. */
    val callName get() = name.ifBlank { "there" }

    /** A short instruction that tells the model who it is talking to. */
    fun audience(): String = buildString {
        if (age > 0) append("The learner is $age years old: use words and examples that suit that age. ")
        if (name.isNotBlank()) append("Their name is $name. ")
    }
}
