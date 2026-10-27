package com.kabir.unlox_hackethon.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import androidx.compose.runtime.mutableStateMapOf
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.math.ln

private suspend fun <T> com.google.android.gms.tasks.Task<T>.wait(): T = suspendCancellableCoroutine { c ->
    addOnSuccessListener { c.resume(it) }.addOnFailureListener { c.resumeWithException(it) }
}

/** Reads the text in a picture with ML Kit, on the phone: Latin script, or Devanagari when that finds more. */
object Ocr {
    suspend fun read(b: Bitmap): String {
        val image = InputImage.fromBitmap(b, 0)
        val latin = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        val deva = TextRecognition.getClient(DevanagariTextRecognizerOptions.Builder().build())
        try {
            val a = runCatching { latin.process(image).wait().text }.getOrDefault("")
            val d = runCatching { deva.process(image).wait().text }.getOrDefault("")
            return if (d.count { it.code in 0x0900..0x097F } > a.length / 4) d else a
        } finally { latin.close(); deva.close() }
    }
}

@Serializable
data class PdfMeta(val id: String, val name: String, val pages: Int, val done: Int, val created: Long)

data class Chapter(val title: String, val firstPage: Int, val lastPage: Int)

/**
 * The learner's own PDFs. Each page is drawn with Android's PdfRenderer and read with ML Kit OCR in the background (so scanned books work
 * as well as digital ones), the text is kept per page, and a lesson built on a PDF is given the pages that match its topic.
 */
class PdfStore(private val context: Context) {
    private val root = File(context.filesDir, "pdfs").apply { mkdirs() }
    private val json = Json { ignoreUnknownKeys = true }
    /** Pages read so far for PDFs being read now (id -> done), so a screen can show progress. */
    val reading = mutableStateMapOf<String, Int>()

    private fun metaFile(id: String) = File(root, "$id/meta.json")
    private fun pagesFile(id: String) = File(root, "$id/pages.json")

    fun list(): List<PdfMeta> = root.listFiles { f -> f.isDirectory }.orEmpty().mapNotNull { runCatching { json.decodeFromString<PdfMeta>(metaFile(it.name).readText()) }.getOrNull() }.sortedByDescending { it.created }
    fun get(id: String): PdfMeta? = runCatching { json.decodeFromString<PdfMeta>(metaFile(id).readText()) }.getOrNull()
    fun delete(id: String) { File(root, id).deleteRecursively(); reading.remove(id) }
    fun pages(id: String): List<String> = runCatching { json.decodeFromString<List<String>>(pagesFile(id).readText()) }.getOrDefault(emptyList())

    /** Copies the chosen PDF into the app and starts reading its pages in the background. Returns at once with its id. */
    suspend fun add(uri: Uri): PdfMeta = withContext(Dispatchers.IO) {
        val id = UUID.randomUUID().toString().take(8)
        val name = context.contentResolver.query(uri, null, null, null, null)?.use { c -> if (c.moveToFirst()) c.getString(c.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else null } ?: "Document.pdf"
        val file = File(root, "$id/file.pdf").apply { parentFile!!.mkdirs() }
        context.contentResolver.openInputStream(uri)!!.use { i -> file.outputStream().use { o -> i.copyTo(o) } }
        val pages = PdfRenderer(ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)).use { it.pageCount }
        val meta = PdfMeta(id, name, pages, 0, System.currentTimeMillis())
        metaFile(id).writeText(json.encodeToString(meta))
        reading[id] = 0
        Graph.scope.launch { readPages(meta) }
        meta
    }

    private suspend fun readPages(meta: PdfMeta) = withContext(Dispatchers.Default) {
        val texts = ArrayList<String>()
        try {
            PdfRenderer(ParcelFileDescriptor.open(File(root, "${meta.id}/file.pdf"), ParcelFileDescriptor.MODE_READ_ONLY)).use { r ->
                for (i in 0 until r.pageCount) {
                    val page = r.openPage(i)
                    val w = 1400
                    val bmp = Bitmap.createBitmap(w, (w * page.height.toFloat() / page.width).toInt().coerceAtLeast(1), Bitmap.Config.ARGB_8888)
                    Canvas(bmp).drawColor(Color.WHITE)
                    page.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    page.close()
                    texts.add(runCatching { Ocr.read(bmp) }.getOrDefault(""))
                    bmp.recycle()
                    reading[meta.id] = i + 1
                    if (i % 4 == 3 || i == r.pageCount - 1) {
                        pagesFile(meta.id).writeText(json.encodeToString<List<String>>(texts))
                        metaFile(meta.id).writeText(json.encodeToString(meta.copy(done = i + 1)))
                    }
                }
            }
        } finally { reading.remove(meta.id) }
    }

    private val stop = setOf("the", "and", "for", "are", "with", "that", "this", "what", "how", "why", "from", "about", "chapter", "unit", "lesson", "explain", "does", "work", "works")
    private fun words(s: String) = Regex("\\p{L}{3,}").findAll(s.lowercase()).map { it.value }.filter { it !in stop }.toList()

    /** Chapters found from headings like "Chapter 4: Light" at the top of a page. Empty when the book has none. */
    fun chapters(id: String): List<Chapter> {
        val pages = pages(id)
        val head = Regex("^(chapter|unit|lesson)\\s+(\\d+|[ivxlc]+)\\b[:.\\-–]?\\s*(.*)$", RegexOption.IGNORE_CASE)
        val starts = ArrayList<Pair<Int, String>>()
        pages.forEachIndexed { i, text ->
            val line = text.lines().map { it.trim() }.filter { it.isNotEmpty() }.take(5).firstNotNullOfOrNull { head.find(it) } ?: return@forEachIndexed
            val title = "${line.groupValues[1].replaceFirstChar { c -> c.uppercase() }} ${line.groupValues[2]}" + line.groupValues[3].trim().takeIf { t -> t.isNotEmpty() }?.let { t -> ": ${t.take(60)}" }.orEmpty()
            if (starts.none { it.second.substringBefore(":") == title.substringBefore(":") }) starts.add(i to title)
        }
        return starts.mapIndexed { k, (first, title) -> Chapter(title, first, (starts.getOrNull(k + 1)?.first ?: pages.size) - 1) }
    }

    /** The text of the pages that best match `query` (or the chapter it names), to give a lesson its facts. */
    fun retrieve(id: String, query: String, maxChars: Int = 3200): String {
        val pages = pages(id)
        if (pages.isEmpty()) return ""
        chapters(id).firstOrNull { c -> query.contains(c.title.substringBefore(":"), ignoreCase = true) || c.title.equals(query, ignoreCase = true) }?.let { c ->
            return pages.subList(c.firstPage, (c.lastPage + 1).coerceAtMost(pages.size)).joinToString("\n").take(maxChars)
        }
        val q = words(query).distinct()
        if (q.isEmpty()) return pages.take(3).joinToString("\n").take(maxChars)
        val df = q.associateWith { t -> pages.count { it.contains(t, ignoreCase = true) } }
        val scored = pages.mapIndexed { i, text ->
            val ws = words(text).groupingBy { it }.eachCount()
            i to q.sumOf { t -> (ws[t] ?: 0).let { tf -> if (tf == 0) 0.0 else (1 + ln(tf.toDouble())) * ln(1.0 + pages.size / (1.0 + (df[t] ?: 0))) } }
        }.filter { it.second > 0 }.sortedByDescending { it.second }.take(4).map { it.first }.sorted()
        return (scored.ifEmpty { listOf(0, 1) }).filter { it < pages.size }.joinToString("\n") { pages[it] }.take(maxChars)
    }
}
