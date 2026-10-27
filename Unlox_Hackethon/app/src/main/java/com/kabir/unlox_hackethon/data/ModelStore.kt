package com.kabir.unlox_hackethon.data

import android.content.Context
import java.io.File

/** Where the models live on the phone: the app's own external folder (copied there once; no permission needed). */
class ModelStore(context: Context) {
    val root = File(context.getExternalFilesDir(null), "models")

    val llmFile get() = File(root, "llm").listFiles { f -> f.name.endsWith(".litertlm") }?.firstOrNull() ?: File(root, "llm/missing.litertlm")
    val whisperDir get() = File(root, "stt").listFiles { f -> f.isDirectory && f.name.contains("whisper") }?.minByOrNull { it.name } ?: File(root, "stt/none")
    val embeddingsDir get() = File(root, "embeddings")

    /** The voice folder for a language, if a Piper voice for it was copied here. Tamil and Kannada have none: the phone's own voice reads those. */
    fun voiceDir(lang: String): File? {
        val key = mapOf("en" to "en_US", "hi" to "hi_IN", "ml" to "ml_IN", "gu" to "gu_IN", "te" to "te_IN", "mr" to "mr_IN", "bn" to "bn_BD")[lang] ?: return null
        return File(root, "tts").listFiles { f -> f.isDirectory && f.name.contains(key) }?.firstOrNull()?.takeIf { d -> d.listFiles { f -> f.extension == "onnx" }?.isNotEmpty() == true }
    }

    data class Status(val name: String, val detail: String, val ready: Boolean)

    fun status(): List<Status> {
        val voices = listOf("en", "hi", "te", "mr", "bn", "gu", "ml").count { voiceDir(it) != null }
        return listOf(
            Status("Tutor and planner", "Gemma, LiteRT-LM", llmFile.exists()),
            Status("Voices", "Piper, sherpa-onnx · $voices languages", voices > 0),
            Status("Speech to text", "Whisper, sherpa-onnx", whisperDir.isDirectory),
            Status("Search in your PDFs", "MiniLM embeddings", embeddingsDir.isDirectory && embeddingsDir.list()?.isNotEmpty() == true),
        )
    }
}

/** The nine languages of the app: code, English name, name in its own script. */
data class Lang(val code: String, val name: String, val native: String)

val LANGS = listOf(
    Lang("en", "English", "English"), Lang("hi", "Hindi", "हिन्दी"), Lang("te", "Telugu", "తెలుగు"), Lang("ta", "Tamil", "தமிழ்"),
    Lang("mr", "Marathi", "मराठी"), Lang("bn", "Bengali", "বাংলা"), Lang("gu", "Gujarati", "ગુજરાતી"), Lang("kn", "Kannada", "ಕನ್ನಡ"), Lang("ml", "Malayalam", "മലയാളം"),
)

fun langByName(name: String) = LANGS.firstOrNull { it.name == name } ?: LANGS[0]

/** Which language a text is written in, from its script: Telugu letters -> "te". Latin letters -> "en". */
fun detectLanguage(text: String, prefer: String = "en"): String {
    val ranges = listOf(0x0900..0x097F to "hi", 0x0980..0x09FF to "bn", 0x0A80..0x0AFF to "gu", 0x0B80..0x0BFF to "ta", 0x0C00..0x0C7F to "te", 0x0C80..0x0CFF to "kn", 0x0D00..0x0D7F to "ml")
    val counts = HashMap<String, Int>()
    for (ch in text) for ((r, code) in ranges) if (ch.code in r) { counts[code] = (counts[code] ?: 0) + 1; break }
    val best = counts.maxByOrNull { it.value }?.key ?: return "en"
    return if (best == "hi" && prefer == "mr") "mr" else best
}
