package com.kabir.unlox_hackethon.data

import android.content.Context
import android.media.MediaMetadataRetriever
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.android.gms.tasks.Task
import com.google.mlkit.common.model.RemoteModelManager
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.TranslateRemoteModel
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.TranslatorOptions
import com.google.mlkit.common.model.DownloadConditions
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import com.k2fsa.sherpa.onnx.OfflineWhisperModelConfig
import com.k2fsa.sherpa.onnx.SpokenLanguageIdentification
import com.k2fsa.sherpa.onnx.SpokenLanguageIdentificationConfig
import com.k2fsa.sherpa.onnx.SpokenLanguageIdentificationWhisperConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

private const val TAG = "Chanakya"

// ---------------------------------------------------------------- the language model

/**
 * Gemma on this phone, through LiteRT-LM. One engine for the whole app; a request runs on an IO thread and waits its turn,
 * so two features never run the model at once and the main thread never waits for it.
 */
class Llm(private val models: ModelStore, private val cacheDir: File) {
    private var engine: Engine? = null
    private val mutex = Mutex()
    @Volatile var backendName = ""
        private set

    private fun ensure(): Engine {
        engine?.let { return it }
        val file = models.llmFile
        require(file.exists()) { "The language model is not on this phone yet. Copy it in Settings > On this phone." }
        val e = Engine(EngineConfig(modelPath = file.path, backend = Backend.CPU(), maxNumTokens = 8192, cacheDir = cacheDir.path))
        e.initialize()
        backendName = "CPU"
        engine = e
        Log.i(TAG, "language model ready on $backendName")
        return e
    }

    /** Load the model now (takes several seconds) so the first question is quick. */
    suspend fun warmUp() = mutex.withLock { withContext(Dispatchers.IO) { runCatching { ensure() }.onFailure { Log.w(TAG, "warm-up: ${it.message}") } } }

    /** Like [ask], but `onText` hears the whole answer so far each time more arrives, so a long answer can show real progress and be used early. */
    suspend fun askStreaming(system: String, user: String, temperature: Double = 0.4, onText: (String) -> Unit): String =
        mutex.withLock {
            withContext(Dispatchers.IO) {
                val e = ensure()
                val config = ConversationConfig(systemInstruction = Contents.of(system), samplerConfig = SamplerConfig(40, 0.95, temperature, 0))
                e.createConversation(config).use { conv ->
                    var acc = ""
                    conv.sendMessageAsync(user).collect { m ->
                        val part = m.contents.contents.filterIsInstance<Content.Text>().joinToString("") { it.text }
                        acc = if (part.startsWith(acc)) part else acc + part               // a message is either the text so far or the next piece
                        onText(acc)
                    }
                    acc.trim()
                }
            }
        }

    /** One answer. `history` is earlier (question, answer) pairs of the same conversation. */
    suspend fun ask(system: String, user: String, temperature: Double = 0.4, history: List<Pair<String, String>> = emptyList()): String =
        mutex.withLock {
            withContext(Dispatchers.IO) {
                val e = ensure()
                val initial = history.flatMap { (q, a) -> listOf(Message.user(q), Message.model(a)) }
                val config = ConversationConfig(systemInstruction = Contents.of(system), initialMessages = initial, samplerConfig = SamplerConfig(40, 0.95, temperature, 0))
                e.createConversation(config).use { conv ->
                    conv.sendMessage(user).contents.contents.filterIsInstance<Content.Text>().joinToString("") { it.text }.trim()
                }
            }
        }
}

/** The JSON object or array inside a model's reply (it may wrap it in prose or a code fence). */
fun extractJson(reply: String): String? {
    val start = reply.indexOfFirst { it == '{' || it == '[' }
    if (start < 0) return null
    val close = if (reply[start] == '{') '}' else ']'
    val end = reply.lastIndexOf(close)
    return if (end > start) reply.substring(start, end + 1) else null
}

// ---------------------------------------------------------------- voices

class Speech(val file: File, val seconds: Float)

/** Piper voices through sherpa-onnx; Tamil and Kannada (no Piper voice) use the phone's own text to speech if it has that voice. */
class Tts(private val context: Context, private val models: ModelStore) {
    private val voices = HashMap<String, OfflineTts>()

    private val dead by lazy { Trace.dead() }

    /** espeak's data in the app's private storage: the phonemizer reads it with plain file calls, which are most reliable there. */
    private fun espeakData(from: File): File {
        val local = File(context.filesDir, "espeak-ng-data")
        if (!File(local, "phontab").exists()) { Trace.mark("copying espeak data"); File(from, "espeak-ng-data").copyRecursively(local, overwrite = true) }
        return local
    }

    private fun voice(dir: File): OfflineTts = synchronized(voices) {
        voices.getOrPut(dir.name) {
            Trace.mark("loading voice ${dir.name}")
            Trace.guard("voice:${dir.name}")
            val vits = OfflineTtsVitsModelConfig().apply {
                model = dir.listFiles { f -> f.extension == "onnx" }!!.first().path
                tokens = File(dir, "tokens.txt").path
                dataDir = espeakData(dir).path
            }
            val config = OfflineTtsConfig().apply { model = OfflineTtsModelConfig().apply { this.vits = vits; numThreads = 3; provider = "cpu"; debug = false } }
            OfflineTts(null, config).also { Trace.done(); Trace.mark("voice ${dir.name} ready") }
        }
    }

    /** Read `text` aloud in `lang` into `out` (a .wav). Null when no voice for that language is available. */
    suspend fun speak(text: String, lang: String, out: File): Speech? = withContext(Dispatchers.Default) {
        val dir = models.voiceDir(lang)?.takeIf { "voice:${it.name}" !in dead }
        runCatching { if (dir != null) piper(dir, text, out) else system(text, lang, out) }.onFailure { Log.w(TAG, "tts $lang: ${it.message}") }.getOrNull()
    }

    private fun piper(dir: File, text: String, out: File): Speech {
        val tts = voice(dir)
        Trace.mark("speaking ${dir.name}: ${text.take(40)}")
        Trace.guard("speak:${dir.name}")
        val t0 = System.nanoTime()
        val audio = tts.generate(text, 0, 1.0f)
        Trace.done()
        Trace.mark("generated ${audio.samples.size} samples at ${audio.sampleRate} Hz (engine ${tts.sampleRate()} Hz, ${tts.numSpeakers()} speakers) in ${(System.nanoTime() - t0) / 1_000_000} ms")
        check(audio.samples.isNotEmpty() && audio.sampleRate > 0) { "the voice made no sound" }
        writeWav(out, audio.samples, audio.sampleRate)
        return Speech(out, audio.samples.size.toFloat() / audio.sampleRate)
    }

    private suspend fun system(text: String, lang: String, out: File): Speech? = suspendCancellableCoroutine { cont ->
        var tts: TextToSpeech? = null
        tts = TextToSpeech(context) { status ->
            val t = tts
            if (status != TextToSpeech.SUCCESS || t == null) { cont.resume(null); return@TextToSpeech }
            val ok = t.setLanguage(java.util.Locale.forLanguageTag(lang))
            if (ok < TextToSpeech.LANG_AVAILABLE) { t.shutdown(); cont.resume(null); return@TextToSpeech }
            t.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    val secs = runCatching { MediaMetadataRetriever().use { it.setDataSource(out.path); (it.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)!!.toFloat()) / 1000f } }.getOrDefault(0f)
                    t.shutdown(); cont.resume(if (secs > 0f) Speech(out, secs) else null)
                }
                @Deprecated("Deprecated in Java") override fun onError(utteranceId: String?) { t.shutdown(); cont.resume(null) }
            })
            t.synthesizeToFile(text, null, out, "u")
        }
        cont.invokeOnCancellation { tts?.shutdown() }
    }
}

/** 16-bit mono PCM wave file. */
fun writeWav(file: File, samples: FloatArray, sampleRate: Int) {
    file.parentFile?.mkdirs()
    RandomAccessFile(file, "rw").use { f ->
        f.setLength(0)
        val data = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (s in samples) data.putShort((s.coerceIn(-1f, 1f) * 32767f).toInt().toShort())
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray()).putInt(36 + data.capacity()).put("WAVE".toByteArray()).put("fmt ".toByteArray())
            .putInt(16).putShort(1).putShort(1).putInt(sampleRate).putInt(sampleRate * 2).putShort(2).putShort(16)
            .put("data".toByteArray()).putInt(data.capacity())
        f.write(header.array()); f.write(data.array())
    }
}

// ---------------------------------------------------------------- speech to text

class Heard(val text: String, val lang: String)

/**
 * Speech to text, built the way the N Dial recorder does it: Whisper first names the language that was spoken, then the best engine for
 * that language reads it. Vosk's small models do English, Hindi, Telugu and Gujarati (they beat Whisper base on those); Whisper base
 * (sherpa-onnx, 16 kHz mono in) reads Tamil, Kannada, Malayalam, Marathi and Bengali, which Vosk has no small model for.
 */
class Stt(private val models: ModelStore) {
    private var whisper: OfflineRecognizer? = null
    private var lid: SpokenLanguageIdentification? = null
    private val vosk = HashMap<String, org.vosk.Model>()

    private val voskDirs = mapOf("en" to "vosk-model-small-en-in", "hi" to "vosk-model-small-hi", "te" to "vosk-model-small-te", "gu" to "vosk-model-small-gu")
    private val ours = LANGS.map { it.code }.toSet()

    private fun whisperFile(suffix: String) = models.whisperDir.listFiles { f -> f.name.endsWith(suffix) }!!.first().path

    private fun recognizer(): OfflineRecognizer = synchronized(this) {
        whisper ?: run {
            val w = OfflineWhisperModelConfig().apply { encoder = whisperFile("encoder.int8.onnx"); decoder = whisperFile("decoder.int8.onnx"); language = ""; task = "transcribe" }
            val mc = OfflineModelConfig().apply { this.whisper = w; tokens = whisperFile("tokens.txt"); numThreads = 4; provider = "cpu" }
            val cfg = OfflineRecognizerConfig().apply { featConfig = FeatureConfig().apply { sampleRate = 16000; featureDim = 80 }; modelConfig = mc }
            OfflineRecognizer(null, cfg).also { whisper = it }
        }
    }

    /** Which language was spoken: Whisper's own language detection on the first seconds, kept to the nine we support (Urdu is Hindi here). */
    private fun identify(samples: FloatArray): String = synchronized(this) {
        val id = lid ?: run {
            val w = SpokenLanguageIdentificationWhisperConfig().apply { encoder = whisperFile("encoder.int8.onnx"); decoder = whisperFile("decoder.int8.onnx"); tailPaddings = -1 }
            val cfg = SpokenLanguageIdentificationConfig().apply { whisper = w; numThreads = 2; provider = "cpu" }
            SpokenLanguageIdentification(null, cfg).also { lid = it }
        }
        val stream = id.createStream()
        try {
            stream.acceptWaveform(samples.copyOf(minOf(samples.size, 16000 * 6)), 16000)
            when (val code = id.compute(stream)) { "ur" -> "hi"; in ours -> code; else -> "en" }
        } finally { stream.release() }
    }

    private fun voskText(dir: File, samples: FloatArray): String {
        val model = synchronized(vosk) { vosk.getOrPut(dir.name) { org.vosk.Model(dir.path) } }
        val bytes = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (x in samples) bytes.putShort((x.coerceIn(-1f, 1f) * 32767f).toInt().toShort())
        org.vosk.Recognizer(model, 16000f).use { r ->
            val parts = ArrayList<String>()
            val data = bytes.array()
            var i = 0
            while (i < data.size) {
                val n = minOf(8000, data.size - i)
                if (r.acceptWaveForm(data.copyOfRange(i, i + n), n)) parts.add(org.json.JSONObject(r.result).optString("text"))
                i += n
            }
            parts.add(org.json.JSONObject(r.finalResult).optString("text"))
            return parts.filter { it.isNotBlank() }.joinToString(" ").trim()
        }
    }

    /** What was said, and in which language. `hint` skips the language detection when the learner picked one. */
    suspend fun transcribe(samples: FloatArray, hint: String? = null): Heard = withContext(Dispatchers.Default) {
        runCatching {
            val lang = hint ?: identify(samples)
            val voskDir = voskDirs[lang]?.let { key -> File(models.root, "stt").listFiles { f -> f.isDirectory && f.name.startsWith(key) }?.firstOrNull() }
            val text = if (voskDir != null) voskText(voskDir, samples) else {
                val r = recognizer()
                val s = r.createStream()
                try { s.acceptWaveform(samples, 16000); r.decode(s); r.getResult(s).text.trim() } finally { s.release() }
            }
            Heard(text, lang)
        }.getOrElse { Log.w(TAG, "stt: ${it.message}"); Heard("", hint ?: "en") }
    }
}

// ---------------------------------------------------------------- translation

private suspend fun <T> Task<T>.await(): T = suspendCancellableCoroutine { c ->
    addOnSuccessListener { c.resume(it) }.addOnFailureListener { c.resumeWithException(it) }
}

/** ML Kit translation (its language packs download once, then work with no internet); Gemma translates when a pack is not there yet. */
class Translator(private val llm: Llm) {
    private val tags = mapOf("hi" to TranslateLanguage.HINDI, "te" to TranslateLanguage.TELUGU, "ta" to TranslateLanguage.TAMIL, "mr" to TranslateLanguage.MARATHI,
        "bn" to TranslateLanguage.BENGALI, "gu" to TranslateLanguage.GUJARATI, "kn" to TranslateLanguage.KANNADA)

    private fun remote(lang: String) = tags[lang]?.let { TranslateRemoteModel.Builder(it).build() }

    /** Whether this language's pack is on the phone (so translation works with no internet). */
    suspend fun packReady(lang: String): Boolean = lang == "en" || remote(lang)?.let { runCatching { RemoteModelManager.getInstance().isModelDownloaded(it).await() }.getOrDefault(false) } == true

    /** Downloads this language's pack (about 30 MB, needs internet once). */
    suspend fun downloadPack(lang: String): Boolean {
        val model = remote(lang) ?: return lang == "en"
        return runCatching { RemoteModelManager.getInstance().download(model, DownloadConditions.Builder().build()).await(); true }.getOrDefault(false)
    }

    suspend fun translate(texts: List<String>, lang: String, onEach: () -> Unit = {}): List<String> {
        if (lang == "en" || texts.isEmpty()) return texts
        val tag = tags[lang]
        if (tag != null) {
            val client = Translation.getClient(TranslatorOptions.Builder().setSourceLanguage(TranslateLanguage.ENGLISH).setTargetLanguage(tag).build())
            try {
                client.downloadModelIfNeeded(DownloadConditions.Builder().build()).await()
                return texts.map { (if (it.isBlank()) it else client.translate(it).await()).also { onEach() } }
            } catch (e: Exception) {
                Log.w(TAG, "ML Kit $lang: ${e.message}; using Gemma")
            } finally { client.close() }
        }
        val name = langByName(LANGS.first { it.code == lang }.name).name
        return texts.map { (if (it.isBlank()) it else llm.ask("You translate English into $name. Reply with the translation only, nothing else.", it, 0.1)).also { onEach() } }
    }
}

// ---------------------------------------------------------------- playing a scene

/** Plays one narration file at a time. Starting is asynchronous, so a long file never holds up the main thread. */
class ScenePlayer(private val context: Context) {
    private var mp: MediaPlayer? = null

    fun play(file: File, startMs: Int = 0, onDone: () -> Unit) {
        stop()
        mp = MediaPlayer().apply {
            setDataSource(file.path)
            setOnPreparedListener { if (startMs > 0) it.seekTo(startMs); it.start() }
            setOnCompletionListener { onDone() }
            setOnErrorListener { _, _, _ -> onDone(); true }
            prepareAsync()
        }
    }

    val positionMs: Int get() = runCatching { mp?.currentPosition ?: 0 }.getOrDefault(0)
    fun pause() { runCatching { mp?.pause() } }
    fun resume() { runCatching { mp?.start() } }
    fun stop() { runCatching { mp?.release() }; mp = null }
}
