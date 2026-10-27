package com.kabir.unlox_hackethon.ui.screens

import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.data.Answer
import com.kabir.unlox_hackethon.data.Graph
import com.kabir.unlox_hackethon.data.LANGS
import com.kabir.unlox_hackethon.ui.components.Chip
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.IconWell
import com.kabir.unlox_hackethon.ui.components.SectionHeader
import com.kabir.unlox_hackethon.ui.components.SwipePill
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

// ---------------------------------------------------------------- homework

/** Reads a picked photo at a small size (off the main thread) so four thumbnails never stall the screen. */
private suspend fun android.content.Context.thumb(uri: Uri): Bitmap? = withContext(Dispatchers.IO) {
    runCatching { ImageDecoder.decodeBitmap(ImageDecoder.createSource(contentResolver, uri)) { d, info, _ ->
        val s = maxOf(info.size.width, info.size.height) / 1600
        if (s > 1) d.setTargetSampleSize(s)
        d.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
    } }.getOrNull()
}

/** Homework helper: photograph or type the questions, then watch the answers arrive one by one. */
@Composable
fun HomeworkScreen(onBack: () -> Unit, onSolve: (typed: String) -> Unit) {
    val context = LocalContext.current
    val photos = remember { mutableStateListOf<Bitmap>() }
    var typed by rememberSaveable { mutableStateOf("") }
    val picked = remember { mutableStateListOf<Uri>() }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(4)) { uris -> picked.addAll(uris.take(4 - photos.size)) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { b -> if (b != null && photos.size < 4) photos.add(b) }
    LaunchedEffect(picked.size) {
        while (picked.isNotEmpty()) {
            val u = picked.removeAt(0)
            context.thumb(u)?.let { if (photos.size < 4) photos.add(it) }
        }
    }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
        Text("Homework", style = T.Display, color = U.TextPrimary)
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                ActionTile("Take a photo", R.drawable.ic_captions, U.Accent, Modifier.weight(1f)) { camera.launch(null) }
                ActionTile("From gallery", R.drawable.ic_layers, U.Raised, Modifier.weight(1f)) { gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
            }
            AnimatedVisibility(photos.isNotEmpty(), enter = fadeIn() + expandVertically()) {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    photos.forEachIndexed { i, b ->
                        Box {
                            Image(b.asImageBitmap(), "Photo ${i + 1}", Modifier.size(96.dp).clip(RoundedCornerShape(20.dp)), contentScale = ContentScale.Crop)
                            IconBtn(R.drawable.ic_x, "Remove photo ${i + 1}", Modifier.align(Alignment.TopEnd).padding(4.dp), bg = Color.Black.copy(alpha = 0.6f), size = 28.dp, iconSize = 14.dp) { photos.removeAt(i) }
                        }
                    }
                }
            }
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(horizontal = 20.dp, vertical = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("OR TYPE IT", style = T.Caption, color = U.TextTertiary)
                Box(Modifier.heightIn(min = 56.dp)) {
                    if (typed.isEmpty()) Text("Paste or write the questions here", style = T.Input, color = U.TextTertiary)
                    BasicTextField(typed, { typed = it }, textStyle = T.Input.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary), modifier = Modifier.fillMaxWidth())
                }
            }
            Text("The photos are read on this phone and never leave it.", style = T.Sub, color = U.TextTertiary)
        }
        SwipePill("Swipe to solve", R.drawable.ic_sparkles, U.Accent) {
            if (photos.isNotEmpty() || typed.isNotBlank()) { Graph.homework.photos = photos.toList(); onSolve(typed) }
        }
    }
}

@Composable
private fun ActionTile(label: String, icon: Int, bg: Color, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.height(112.dp).clip(RoundedCornerShape(28.dp)).background(bg).clickable(onClick = onClick).padding(12.dp), verticalArrangement = Arrangement.SpaceBetween) {
        IconWell(icon, if (bg == U.Accent) U.Inverse else U.BorderGlass, 48.dp, 24.dp, if (bg == U.Accent) U.OnInverse else U.TextPrimary)
        Text(label, style = T.Body, color = U.TextPrimary)
    }
}

/** Answers appear question by question as the solver finishes each one. */
@Composable
fun AnswersScreen(typed: String, onBack: () -> Unit) {
    val answers = remember { mutableStateListOf<Answer>() }
    var finished by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        runCatching { Graph.homework.solve(typed).collect { answers.add(it) } }.onFailure { error = it.message }
        finished = true
        if (answers.isNotEmpty()) Graph.rewards.award("homework")
    }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var saved by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
            IconBtn(R.drawable.ic_download, "Save answers as a file", bg = if (finished && answers.isNotEmpty()) U.Inverse else U.Raised) {
                if (finished && answers.isNotEmpty()) scope.launch {
                    withContext(Dispatchers.IO) {
                        val dir = context.getExternalFilesDir("answers") ?: context.filesDir
                        File(dir, "homework-answers.md").writeText(answers.joinToString("\n\n") { "## ${it.question}\n\n${it.answer}" })
                    }
                    saved = "Saved in Android/data/com.kabir.unlox_hackethon/files/answers"
                }
            }
        }
        Text(if (finished) "Your answers" else "Solving…", style = T.Display, color = U.TextPrimary)
        Text(
            when { error != null -> error!!; saved.isNotEmpty() -> saved; finished -> "${answers.size} questions solved on this phone."; else -> "${answers.size} done · each answer shows as soon as it is ready" },
            style = T.Body, color = U.TextTertiary,
        )
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            answers.forEach { a ->
                AnimatedVisibility(true, enter = fadeIn(tween(300)) + slideInVertically(tween(300)) { it / 4 }) {
                    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(U.Surface).padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(a.question, style = T.Title, color = U.TextPrimary)
                        Text(a.answer, style = T.Body, color = U.TextSecondary)
                    }
                }
            }
            if (!finished) Box(Modifier.fillMaxWidth().height(72.dp).clip(RoundedCornerShape(28.dp)).background(U.Raised.copy(alpha = 0.5f)))
        }
    }
}

// ---------------------------------------------------------------- rewards

/** Points, level and badges. Points come from what you do: lessons, quizzes, questions. */
@Composable
fun RewardsScreen(bottomInset: Dp, onBack: (() -> Unit)?) {
    val r = Graph.rewards
    r.version
    val points = r.xp
    val ring by animateFloatAsState(((points - r.levelFloor).toFloat() / (r.nextXp - r.levelFloor)).coerceIn(0f, 1f), tween(900), label = "level")
    data class Award(val title: String, val hint: String, val earned: Boolean, val tone: Color)
    val awards = listOf(
        Award("First lesson", "Made your first lesson", r.lessonsMade >= 1, U.Sage),
        Award("7-day streak", "A week in a row", r.bestStreak >= 7, U.Rust),
        Award("Quiz ace", "Full marks on a quiz", r.perfectQuizzes >= 1, U.Orchid),
        Award("Polyglot", "Lessons in 3 languages", r.languagesUsed >= 3, U.Cobalt),
        Award("Curious", "Ask the tutor 10 questions", r.questions >= 10, U.Accent),
        Award("Homework hero", "Solve 5 homework sets", r.homeworkSets >= 5, U.Muted),
    )
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = bottomInset), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (onBack != null) IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
        Text("Rewards", style = T.Display, color = U.TextPrimary)
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(18.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Box(Modifier.size(96.dp), contentAlignment = Alignment.Center) {
                Canvas(Modifier.fillMaxSize()) {
                    val w = 10.dp.toPx()
                    drawArc(U.Glass, 0f, 360f, false, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), style = Stroke(w))
                    drawArc(U.Accent, -90f, 360f * ring, false, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), style = Stroke(w, cap = StrokeCap.Round))
                }
                Text("${r.level}", style = T.Number, color = U.TextPrimary)
            }
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("Level ${r.level}", style = T.Title, color = U.TextPrimary)
                Text("$points points · ${r.nextXp - points} to level ${r.level + 1}", style = T.Sub, color = U.TextTertiary)
            }
        }
        SectionHeader("Badges", trailing = "${awards.count { it.earned }} of ${awards.size}")
        awards.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { a ->
                    Column(
                        Modifier.weight(1f).height(128.dp).clip(RoundedCornerShape(28.dp)).background(if (a.earned) a.tone else U.Raised).padding(14.dp),
                        verticalArrangement = Arrangement.SpaceBetween,
                    ) {
                        IconWell(if (a.earned) R.drawable.ic_check else R.drawable.ic_clock, Color.White.copy(alpha = if (a.earned) 0.22f else 0.08f), 40.dp, 20.dp, if (a.earned) U.TextPrimary else U.TextTertiary)
                        Column { Text(a.title, style = T.Body, color = if (a.earned) U.TextPrimary else U.TextSecondary); Text(a.hint, style = T.Caption, color = U.TextPrimary.copy(alpha = 0.7f), maxLines = 2) }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- settings

@Composable
private fun Toggle(on: Boolean, onChange: (Boolean) -> Unit) {
    val x by animateFloatAsState(if (on) 1f else 0f, tween(180), label = "toggle")
    Box(
        Modifier.size(52.dp, 30.dp).clip(CircleShape).background(if (on) U.Sage else U.GlassStrong).clickable { onChange(!on) }.padding(3.dp),
    ) { Box(Modifier.padding(start = 22.dp * x).size(24.dp).clip(CircleShape).background(Color.White)) }
}

@Composable
private fun SettingRow(title: String, sub: String, trailing: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(U.Raised).padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f)) { Text(title, style = T.Body, color = U.TextPrimary); Text(sub, style = T.Sub, color = U.TextTertiary) }
        trailing()
    }
}

/** Sound, the opening animation, translation packs and what is installed on this phone. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    val p = Graph.profile
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var status by remember { mutableStateOf(Graph.models.status()) }
    val packs = remember { mutableStateMapOf<String, String>() }          // language -> "ready" | "getting" | "failed" | "missing"
    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) { status = Graph.models.status() }
        LANGS.filter { it.code != "en" }.forEach { l -> packs[l.code] = if (l.code == "ml") "gemma" else if (Graph.translator.packReady(l.code)) "ready" else "missing" }
    }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
        Text("Settings", style = T.Display, color = U.TextPrimary)
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionHeader("Sound and look")
            SettingRow("Spoken answers", "The tutor reads its answers aloud") { Toggle(p.speak) { p.setPref("speak", it) } }
            SettingRow("Captions", "Show the narration as text") { Toggle(p.captions) { p.setPref("captions", it) } }
            SettingRow("Opening animation", "Play the logo when the app starts") { Toggle(p.intro) { p.setPref("intro", it) } }
            SectionHeader("Translation packs", trailing = "download once, then offline")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LANGS.filter { it.code != "en" }.forEach { l ->
                    val s = packs[l.code] ?: "…"
                    Chip(when (s) { "ready" -> "${l.name} ✓"; "gemma" -> "${l.name} · by Gemma"; "getting" -> "${l.name} …"; "failed" -> "${l.name} ✕"; else -> "${l.name} ↓" }, selected = s == "ready" || s == "gemma") {
                        if (s != "ready" && s != "getting" && s != "gemma") { packs[l.code] = "getting"; scope.launch { packs[l.code] = if (Graph.translator.downloadPack(l.code)) "ready" else "failed" } }
                    }
                }
            }
            Text("Until a pack is downloaded, Gemma translates instead (slower). Malayalam has no ML Kit pack, so Gemma always translates it. A failed download needs an internet connection.", style = T.Sub, color = U.TextTertiary)
            SectionHeader("Voice test", trailing = "reads one sentence aloud")
            var voiceNote by remember { mutableStateOf("") }
            SettingRow("Test the voice", voiceNote.ifBlank { "Tap to hear English, then Hindi" }) {
                Text("Play", style = T.Chip, color = U.OnInverse, modifier = Modifier.clip(CircleShape).background(U.Inverse).clickable {
                    scope.launch {
                        voiceNote = "Working…"
                        val out = StringBuilder()
                        for ((lang, text) in listOf("en" to "Hello, this is Chanakya, your tutor.", "hi" to "नमस्ते, मैं चाणक्य हूँ।")) {
                            val sp = Graph.tts.speak(text, lang, File(context.cacheDir, "voice-test-$lang.wav"))
                            out.append(if (sp == null) "$lang: no sound. " else "$lang: ${"%.1f".format(sp.seconds)} s. ")
                            if (sp != null) { Graph.player.play(sp.file) {}; kotlinx.coroutines.delay((sp.seconds * 1000).toLong() + 300) }
                        }
                        voiceNote = out.toString().trim()
                    }
                }.padding(horizontal = 18.dp, vertical = 10.dp))
            }
            SectionHeader("On this phone", trailing = "works with no internet")
            status.forEach { m -> SettingRow(m.name, m.detail) { Text(if (m.ready) "Ready" else "Not installed", style = T.Caption, color = if (m.ready) U.Online else U.TextTertiary) } }
        }
    }
}

// ---------------------------------------------------------------- profile

/** Name and age (they shape how the tutor talks to you), your numbers, and the rest of the app. */
@Composable
fun ProfileScreen(bottomInset: Dp, onRewards: () -> Unit, onHomework: () -> Unit, onSettings: () -> Unit, onStudy: () -> Unit) {
    val p = Graph.profile
    val r = Graph.rewards
    r.version
    var name by rememberSaveable { mutableStateOf(p.name) }
    var age by rememberSaveable { mutableStateOf(if (p.age > 0) p.age.toString() else "") }
    var saved by remember { mutableStateOf(false) }
    fun save() { p.save(name, age.toIntOrNull() ?: 0); saved = true }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = bottomInset), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Profile", style = T.Display, color = U.TextPrimary)
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Box(Modifier.size(56.dp).clip(CircleShape).background(U.Accent), contentAlignment = Alignment.Center) {
                    Text((p.name.firstOrNull() ?: '?').uppercase(), style = T.Headline, color = U.TextPrimary)
                }
                Column { Text(p.name.ifBlank { "Tell me your name" }, style = T.Title, color = U.TextPrimary); Text("Level ${r.level} · ${r.streak}-day streak", style = T.Sub, color = U.TextTertiary) }
            }
            Field("NAME", name, "Your name") { name = it.take(30); saved = false }
            Field("AGE", age, "Your age, e.g. 12", KeyboardType.Number) { age = it.filter(Char::isDigit).take(3); saved = false }
            Text("The tutor uses your age to pick simple words and examples that suit you. It stays on this phone.", style = T.Sub, color = U.TextTertiary)
            Text(if (saved) "Saved ✓" else "Save", style = T.Chip, color = if (saved) U.TextPrimary else U.OnInverse,
                modifier = Modifier.clip(CircleShape).background(if (saved) U.Sage else U.Inverse).clickable { save() }.padding(horizontal = 26.dp, vertical = 14.dp))
        }
        listOf(
            Triple("Rewards", "Points, levels and badges", R.drawable.ic_flame) to onRewards,
            Triple("Homework helper", "Photograph it, get answers", R.drawable.ic_captions) to onHomework,
            Triple("Study tools", "Flashcards, quiz, mind map, notes", R.drawable.ic_layers) to onStudy,
            Triple("Settings", "Sound, translation packs, models", R.drawable.ic_settings) to onSettings,
        ).forEach { (t, go) ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(U.Raised).clickable(onClick = go).padding(start = 12.dp, end = 16.dp, top = 12.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                IconWell(t.third, U.Glass, 44.dp, 20.dp)
                Column(Modifier.weight(1f)) { Text(t.first, style = T.Body, color = U.TextPrimary); Text(t.second, style = T.Sub, color = U.TextTertiary) }
                Glyph(R.drawable.ic_chevron_right, tint = U.TextTertiary, size = 20.dp)
            }
        }
    }
}

@Composable
private fun Field(label: String, value: String, hint: String, type: KeyboardType = KeyboardType.Text, onChange: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(U.Raised).padding(horizontal = 18.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = T.Caption, color = U.TextTertiary)
        Box {
            if (value.isEmpty()) Text(hint, style = T.Input, color = U.TextTertiary)
            BasicTextField(value, onChange, singleLine = true, textStyle = T.Input.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary),
                keyboardOptions = KeyboardOptions(keyboardType = type), modifier = Modifier.fillMaxWidth())
        }
    }
}
