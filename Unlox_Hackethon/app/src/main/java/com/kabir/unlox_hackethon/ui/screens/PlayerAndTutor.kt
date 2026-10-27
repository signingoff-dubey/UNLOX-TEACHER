package com.kabir.unlox_hackethon.ui.screens

import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import android.app.Activity
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import androidx.activity.compose.BackHandler
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.kabir.unlox_hackethon.data.SceneT
import com.kabir.unlox_hackethon.ui.scene.SceneArt
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import com.kabir.unlox_hackethon.ui.components.slash
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.ui.components.Chip
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.LessonRow
import com.kabir.unlox_hackethon.ui.components.SectionHeader
import com.kabir.unlox_hackethon.ui.components.Segmented
import com.kabir.unlox_hackethon.ui.components.pressScale
import com.kabir.unlox_hackethon.ui.components.rippleOrigin
import com.kabir.unlox_hackethon.ui.components.tap
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.delay

/**
 * The seek bar: tap or drag anywhere to jump to that moment of the whole lesson. While you drag, the thumb follows your finger and the jump
 * happens when you let go. A tick marks where each scene starts. TalkBack can move it too.
 */
@Composable
fun SeekBar(elapsed: Int, total: Int, marks: List<Float>, onSeek: (Float) -> Unit, modifier: Modifier = Modifier) {
    var drag by remember { mutableStateOf<Float?>(null) }
    val frac = drag ?: (elapsed.toFloat() / total.coerceAtLeast(1)).coerceIn(0f, 1f)
    Box(
        modifier.height(32.dp)
            .semantics { progressBarRangeInfo = ProgressBarRangeInfo(frac, 0f..1f); contentDescription = "Seek in the lesson"; setProgress { v -> onSeek(v * total); true } }
            .pointerInput(total) { detectTapGestures { o -> onSeek((o.x / size.width).coerceIn(0f, 1f) * total) } }
            .pointerInput(total) {
                detectHorizontalDragGestures(
                    onDragStart = { o -> drag = (o.x / size.width).coerceIn(0f, 1f) },
                    onDragEnd = { drag?.let { onSeek(it * total) }; drag = null },
                    onDragCancel = { drag = null },
                ) { change, _ -> change.consume(); drag = (change.position.x / size.width).coerceIn(0f, 1f) }
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val y = size.height / 2
            drawLine(Color.White.copy(alpha = 0.25f), Offset(0f, y), Offset(size.width, y), 4.dp.toPx(), androidx.compose.ui.graphics.StrokeCap.Round)
            drawLine(Color.White, Offset(0f, y), Offset(size.width * frac, y), 4.dp.toPx(), androidx.compose.ui.graphics.StrokeCap.Round)
            marks.forEach { m -> drawLine(Color.Black.copy(alpha = 0.45f), Offset(size.width * m, y - 3.dp.toPx()), Offset(size.width * m, y + 3.dp.toPx()), 1.5.dp.toPx()) }
            drawCircle(Color.White, if (drag != null) 10.dp.toPx() else 7.dp.toPx(), Offset(size.width * frac, y))
        }
    }
}

/** A part of a set of videos: its title and whether it has been made yet. */
data class PartRef(val title: String, val ready: Boolean)

private fun clock(s: Int) = "${s / 60}:${(s % 60).toString().padStart(2, '0')}"

/**
 * A clock for the scene on screen, in seconds, that moves on every frame while playing. The narration's own position only updates a few
 * times a second, so the clock runs on its own and is nudged back to the audio when they drift apart. Read it only in draw and layer blocks.
 */
@Composable
fun rememberSceneTime(playing: Boolean, key: Any?, positionMs: Int): State<Float> {
    val t = remember(key) { mutableFloatStateOf(positionMs / 1000f) }
    val playingNow by rememberUpdatedState(playing)
    val posNow by rememberUpdatedState(positionMs)
    LaunchedEffect(key) {
        var last = 0L
        while (true) withFrameNanos { now ->
            val dt = if (last == 0L) 0f else ((now - last) / 1e9f).coerceAtMost(0.1f)
            last = now
            if (playingNow) {
                t.floatValue += dt
                val real = posNow / 1000f
                if (real > 0f && kotlin.math.abs(real - t.floatValue) > 0.25f) t.floatValue += (real - t.floatValue) * 0.2f
            } else if (!playingNow && posNow == 0) t.floatValue = 0f
        }
    }
    return t
}

/** 05 Lesson player: the animated scene, its controls, language tabs, the scene list, and the tutor. Turn the phone sideways, or tap the corner button, for full screen. */
@Composable
fun PlayerScreen(
    title: String, scenes: List<SceneT>, scene: Int, onScene: (Int) -> Unit, playing: Boolean, onPlaying: (Boolean) -> Unit, sceneMs: Int,
    language: Int, languages: List<String>, onLanguage: (Int) -> Unit, onBack: () -> Unit, onAskTutor: (Offset) -> Unit, onStudy: () -> Unit,
    onSeek: (Float) -> Unit, making: String? = null, scenesTotal: Int = 0, parts: List<PartRef> = emptyList(), part: Int = 0, onPart: (Int) -> Unit = {},
) {
    val total = scenes.sumOf { it.seconds.toInt().coerceAtLeast(1) }
    val current = scenes.getOrNull(scene) ?: return
    val elapsed = scenes.take(scene).sumOf { it.seconds.toInt().coerceAtLeast(1) } + sceneMs / 1000
    val ask = remember { mutableStateOf(Offset.Zero) }
    var captions by remember { mutableStateOf(com.kabir.unlox_hackethon.data.Graph.profile.captions) }
    var full by rememberSaveable { mutableStateOf(false) }
    val landscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE
    val time = rememberSceneTime(playing, scene * 31 + language, sceneMs)
    val marks = remember(scenes) { var acc = 0f; scenes.dropLast(1).map { acc += it.seconds.coerceAtLeast(1f); acc / total.coerceAtLeast(1) } }
    val speech = (current.seconds - 0.6f).coerceAtLeast(1f)
    if (full || landscape) {
        FullPlayer(current, title, time, speech, playing, onPlaying, elapsed, total, marks, onSeek, { onScene((scene - 1).coerceAtLeast(0)) }, { onScene((scene + 1).coerceAtMost(scenes.size - 1)) }, captions, { captions = !captions }, exit = landscape.not()) { full = false }
        BackHandler(enabled = full) { full = false }
        return
    }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(top = 12.dp)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
                IconBtn(R.drawable.ic_download, "Save as video") {}
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = T.Headline, color = U.TextPrimary, maxLines = 2)
                Text(if (making != null) "${scenes.size} of about ${maxOf(scenesTotal, scenes.size)} scenes ready" else "${scenes.size} scenes · $total s", style = T.Sub, color = U.TextTertiary, maxLines = 1)
            }
            if (making != null) Row(Modifier.clip(CircleShape).background(U.Raised).padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                androidx.compose.material3.CircularProgressIndicator(Modifier.size(14.dp), color = U.TextPrimary, strokeWidth = 2.dp)
                Text("Playing while it is made · $making", style = T.Sub, color = U.TextSecondary, maxLines = 1)
            }
            if (parts.size > 1) Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                parts.forEachIndexed { i, pr -> Chip(if (pr.ready) "Part ${i + 1}" else "Part ${i + 1} · making…", selected = i == part) { if (pr.ready) onPart(i) } }
            }
            // the video, then its controls underneath
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(U.Surface)) {
                Box {
                    SceneArt(current, title, time, speech, Modifier.fillMaxWidth())
                    if (captions) Text(current.narration, Modifier.align(Alignment.BottomCenter).padding(10.dp).clip(RoundedCornerShape(10.dp)).background(Color.Black.copy(alpha = 0.6f)).padding(horizontal = 10.dp, vertical = 5.dp),
                        style = T.Sub.copy(fontSize = 12.sp, lineHeight = 16.sp), color = Color.White, maxLines = 3, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                }
                // the seek bar: drag or tap anywhere to jump, with a tick where each scene starts
                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp)) {
                    SeekBar(elapsed, total, marks, onSeek, Modifier.fillMaxWidth())
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(clock(elapsed), style = T.Caption, color = U.TextSecondary); Text(clock(total), style = T.Caption, color = U.TextSecondary)
                    }
                    Row(Modifier.fillMaxWidth().padding(top = 2.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        IconBtn(R.drawable.ic_captions, if (captions) "Captions on" else "Captions off", bg = Color.Transparent, size = 40.dp, iconSize = 20.dp, off = !captions) { captions = !captions }
                        Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                IconBtn(R.drawable.ic_chevron_right, "Previous scene", bg = Color.Transparent, size = 40.dp, iconSize = 22.dp, iconRotation = 180f) { onScene((scene - 1).coerceAtLeast(0)) }
                                IconBtn(if (playing) R.drawable.ic_pause else R.drawable.ic_play, if (playing) "Pause" else "Play", bg = U.Inverse, size = 48.dp, iconSize = 24.dp) { onPlaying(!playing) }
                                IconBtn(R.drawable.ic_chevron_right, "Next scene", bg = Color.Transparent, size = 40.dp, iconSize = 22.dp) { onScene((scene + 1).coerceAtMost(scenes.size - 1)) }
                            }
                        }
                        IconBtn(R.drawable.ic_maximize, "Full screen", bg = Color.Transparent, size = 40.dp, iconSize = 20.dp) { full = true }
                    }
                }
            }
            if (languages.size > 1) Segmented(languages, language, onLanguage)
            SectionHeader("Scenes", trailing = if (making != null) "${scene + 1} of ~${maxOf(scenesTotal, scenes.size)}" else "${scene + 1} of ${scenes.size}")
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                scenes.forEachIndexed { i, s ->
                    LessonRow(s.heading, "Scene ${i + 1}", clock(s.seconds.toInt().coerceAtLeast(1)), active = i == scene, playing = playing) { onScene(i) }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            val src = remember { MutableInteractionSource() }
            Row(
                Modifier.weight(1f).rippleOrigin(ask).pressScale(src).clip(CircleShape).background(U.Accent).tap(src, "Ask the tutor") { onAskTutor(ask.value) }.padding(vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
            ) {
                Glyph(R.drawable.ic_hand, size = 20.dp)
                Text("Ask the tutor", style = T.Chip, color = U.TextPrimary)
            }
            IconBtn(R.drawable.ic_layers, "Study tools", onClick = onStudy)
        }
    }
}

/** The scene alone on a black screen, filling it, with a thin control bar. Hides the status and navigation bars while it is open. */
@Composable
private fun FullPlayer(
    scene: SceneT, title: String, time: State<Float>, speech: Float, playing: Boolean, onPlaying: (Boolean) -> Unit, elapsed: Int, total: Int,
    marks: List<Float>, onSeek: (Float) -> Unit, onPrev: () -> Unit, onNext: () -> Unit,
    captions: Boolean, onCaptions: () -> Unit, exit: Boolean, onExit: () -> Unit,
) {
    val view = LocalView.current
    val activity = LocalContext.current as? Activity
    DisposableEffect(Unit) {
        val window = activity?.window
        val controller = window?.let { WindowCompat.getInsetsController(it, view) }
        controller?.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller?.hide(WindowInsetsCompat.Type.systemBars())
        if (exit) activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        onDispose {
            controller?.show(WindowInsetsCompat.Type.systemBars())
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
        }
    }
    var bar by remember { mutableStateOf(true) }
    Box(Modifier.fillMaxSize().background(Color.Black).clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) { bar = !bar }, contentAlignment = Alignment.Center) {
        SceneArt(scene, title, time, speech, Modifier.fillMaxHeight().aspectRatio(16f / 9f, matchHeightConstraintsFirst = true))
        if (captions) Text(scene.narration, Modifier.align(Alignment.BottomCenter).padding(bottom = 72.dp, start = 48.dp, end = 48.dp).clip(RoundedCornerShape(10.dp)).background(Color.Black.copy(alpha = 0.6f)).padding(horizontal = 14.dp, vertical = 6.dp),
            style = T.Body, color = Color.White, maxLines = 2, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        androidx.compose.animation.AnimatedVisibility(bar, Modifier.align(Alignment.BottomCenter), enter = androidx.compose.animation.fadeIn(), exit = androidx.compose.animation.fadeOut()) {
            Row(Modifier.fillMaxWidth().padding(16.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.55f)).padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IconBtn(R.drawable.ic_chevron_right, "Previous scene", bg = Color.Transparent, size = 36.dp, iconSize = 20.dp, iconRotation = 180f, onClick = onPrev)
                IconBtn(if (playing) R.drawable.ic_pause else R.drawable.ic_play, if (playing) "Pause" else "Play", bg = U.Inverse, size = 40.dp, iconSize = 22.dp) { onPlaying(!playing) }
                IconBtn(R.drawable.ic_chevron_right, "Next scene", bg = Color.Transparent, size = 36.dp, iconSize = 20.dp, onClick = onNext)
                Text(clock(elapsed), style = T.Caption, color = Color.White)
                SeekBar(elapsed, total, marks, onSeek, Modifier.weight(1f))
                Text(clock(total), style = T.Caption, color = Color.White)
                IconBtn(R.drawable.ic_captions, if (captions) "Captions on" else "Captions off", bg = Color.Transparent, size = 36.dp, iconSize = 20.dp, off = !captions, onClick = onCaptions)
                if (exit) IconBtn(R.drawable.ic_minimize, "Exit full screen", bg = Color.Transparent, size = 36.dp, iconSize = 20.dp, onClick = onExit)
            }
        }
    }
}

enum class Who { TUTOR, STUDENT }
data class Message(val who: Who, val text: String, val time: String)

/** 06 Tutor chat: opened from the "Ask the tutor" button with a ripple. Replies come from the on-device tutor; nothing waits on the main thread. */
@Composable
fun TutorChatScreen(
    sceneLabel: String, messages: SnapshotStateList<Message>, thinking: Boolean, speaking: Boolean, onSpeaker: () -> Unit,
    onSend: (String) -> Unit, onVoice: (Offset) -> Unit, onBack: () -> Unit,
) {
    var text by remember { mutableStateOf("") }
    val mic = remember { mutableStateOf(Offset.Zero) }
    val list = rememberLazyListState()
    LaunchedEffect(messages.size, thinking) { val n = messages.size + if (thinking) 1 else 0; if (n > 0) list.animateScrollToItem(n - 1) }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
            Column(Modifier.weight(1f)) {
                Text("Ask your tutor", style = T.Title, color = U.TextPrimary, maxLines = 1)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(U.Online))
                    Text(sceneLabel, style = T.Sub, color = U.TextTertiary, maxLines = 1)
                }
            }
            IconBtn(R.drawable.ic_volume, if (speaking) "Spoken answers on" else "Spoken answers off", bg = U.Raised, tint = if (speaking) U.TextPrimary else U.TextTertiary, onClick = onSpeaker)
        }
        LazyColumn(Modifier.weight(1f), state = list, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(messages) { Bubble(it) }
            if (thinking) item { TypingBubble() }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Explain this part again", "Quiz me", "Explain like I'm 10").forEach { Chip(it) { onSend(it) } }
        }
        Row(
            Modifier.fillMaxWidth().clip(CircleShape).background(U.Surface).border(1.dp, U.BorderGlass, CircleShape).padding(start = 20.dp, top = 6.dp, end = 6.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(Modifier.weight(1f)) {
                if (text.isEmpty()) Text("Ask in any language…", style = T.Input, color = U.TextTertiary, maxLines = 1)
                BasicTextField(text, { text = it }, textStyle = T.Input.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary), singleLine = true, modifier = Modifier.fillMaxWidth())
            }
            IconBtn(R.drawable.ic_hand, "Ask about the scene on screen") { onSend("Explain this part again") }
            if (text.isBlank()) IconBtn(R.drawable.ic_mic, "Ask by voice", Modifier.rippleOrigin(mic), bg = U.Inverse) { onVoice(mic.value) }
            else IconBtn(R.drawable.ic_arrow_left, "Send", bg = U.Inverse, iconRotation = 180f) { onSend(text.trim()); text = "" }
        }
    }
}

@Composable
private fun Bubble(m: Message) {
    val tutor = m.who == Who.TUTOR
    val shape = if (tutor) RoundedCornerShape(20.dp, 20.dp, 20.dp, 6.dp) else RoundedCornerShape(20.dp, 20.dp, 6.dp, 20.dp)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (tutor) Arrangement.Start else Arrangement.End) {
        Column(
            Modifier.widthIn(max = 282.dp).clip(shape).background(if (tutor) U.Raised else U.Inverse).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(m.text, style = T.Body, color = if (tutor) U.TextPrimary else U.OnInverse)
            Text(m.time, style = T.Caption, color = (if (tutor) U.TextTertiary else U.OnInverse).copy(alpha = 0.6f))
        }
    }
}

@Composable
private fun TypingBubble() {
    val t = rememberInfiniteTransition(label = "typing")
    Row(Modifier.clip(CircleShape).background(U.Raised).padding(horizontal = 14.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        repeat(3) { i ->
            val a by t.animateFloat(0.35f, 1f, infiniteRepeatable(tween(600, delayMillis = i * 150), RepeatMode.Reverse), label = "dot$i")
            Box(Modifier.size(7.dp).alpha(a).clip(CircleShape).background(if (i == 0) U.Inverse else U.TextTertiary))
        }
    }
}
