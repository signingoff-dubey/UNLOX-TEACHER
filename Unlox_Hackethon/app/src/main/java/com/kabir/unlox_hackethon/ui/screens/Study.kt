package com.kabir.unlox_hackethon.ui.screens

import androidx.annotation.DrawableRes
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.data.CardT
import com.kabir.unlox_hackethon.data.MindMapT
import com.kabir.unlox_hackethon.data.NoteT
import com.kabir.unlox_hackethon.data.QuestionT
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.IconWell
import com.kabir.unlox_hackethon.ui.components.ProgressTrack
import com.kabir.unlox_hackethon.ui.components.SectionHeader
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.launch
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

enum class StudyKind(val title: String, val hint: String, @DrawableRes val icon: Int, val tone: Color) {
    FLASHCARDS("Flashcards", "Flip and swipe", R.drawable.ic_layers, U.Accent),
    QUIZ("Quiz", "Check what you learnt", R.drawable.ic_check, U.Sage),
    MINDMAP("Mind map", "See how it connects", R.drawable.ic_globe, U.Cobalt),
    NOTES("Notes", "One page", R.drawable.ic_book, U.Orchid),
}

private data class Idea(val label: String, val note: String, val tone: Color)

/** Runs `load` off the main thread and shows the result; while Gemma works it says so, and a failure can be retried. */
@Composable
fun <T> Made(what: String, onBack: () -> Unit, load: suspend () -> T, content: @Composable (T) -> Unit) {
    var attempt by remember { mutableIntStateOf(0) }
    val state = androidx.compose.runtime.produceState<Result<T>?>(null, attempt) { value = null; value = runCatching { load() } }
    val r = state.value
    when {
        r == null -> ToolFrame(what, "", onBack) {
            Column(Modifier.weight(1f).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                androidx.compose.material3.CircularProgressIndicator(color = U.TextPrimary, strokeWidth = 3.dp)
                Spacer(Modifier.height(16.dp))
                Text("Gemma is making your $what…", style = T.Body, color = U.TextSecondary)
                Text("About half a minute the first time.", style = T.Sub, color = U.TextTertiary)
            }
        }
        r.isFailure -> ToolFrame(what, "", onBack) {
            Column(Modifier.weight(1f).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Text(r.exceptionOrNull()?.message ?: "That did not work.", style = T.Body, color = U.TextSecondary, textAlign = TextAlign.Center)
                Spacer(Modifier.height(16.dp))
                Text("Try again", style = T.Chip, color = U.OnInverse, modifier = Modifier.clip(CircleShape).background(U.Inverse).clickable { attempt++ }.padding(horizontal = 22.dp, vertical = 14.dp))
            }
        }
        else -> content(r.getOrThrow())
    }
}

/** The study tools made from the lesson, as tiles. */
@Composable
fun StudyHubScreen(title: String, onBack: () -> Unit, onOpen: (StudyKind) -> Unit) {
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
        Text("Study tools", style = T.Display, color = U.TextPrimary)
        Text("Gemma makes these from “$title”, on this phone, the first time you open one.", style = T.Body, color = U.TextTertiary)
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            StudyKind.entries.chunked(2).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { k ->
                        Column(
                            Modifier.weight(1f).height(144.dp).clip(RoundedCornerShape(28.dp)).background(k.tone).clickable { onOpen(k) }.padding(14.dp),
                            verticalArrangement = Arrangement.SpaceBetween,
                        ) {
                            IconWell(k.icon, Color.White.copy(alpha = 0.22f), 48.dp, 24.dp)
                            Column { Text(k.title, style = T.Title, color = U.TextPrimary); Text(k.hint, style = T.Sub, color = U.TextPrimary.copy(alpha = 0.75f)) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ToolFrame(title: String, trailing: String, onBack: () -> Unit, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
            Text(title, style = T.Title, color = U.TextPrimary, modifier = Modifier.weight(1f))
            Text(trailing, style = T.Sub, color = U.TextTertiary)
        }
        content()
    }
}

/** Flip a card with a tap, then swipe it away (or press a button): right = got it, left = again. */
@Composable
fun FlashcardsScreen(cards: List<CardT>, onBack: () -> Unit, onKnown: () -> Unit = {}) {
    var index by remember { mutableIntStateOf(0) }
    var known by remember { mutableIntStateOf(0) }
    var flipped by remember { mutableStateOf(false) }
    val x = remember { Animatable(0f) }
    val scope = rememberCoroutineScope()
    val width = with(LocalDensity.current) { 420.dp.toPx() }
    val done = index >= cards.size
    fun leave(right: Boolean) = scope.launch {
        x.animateTo(if (right) width else -width, tween(220))
        if (right) { known++; onKnown() }
        index++; flipped = false; x.snapTo(0f)
    }
    ToolFrame("Flashcards", if (done) "Finished" else "${index + 1} of ${cards.size}", onBack) {
        ProgressTrack(index.toFloat() / cards.size)
        Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
            if (done) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("$known of ${cards.size}", style = T.Hero, color = U.TextPrimary)
                    Text("cards you knew", style = T.Body, color = U.TextTertiary)
                    Spacer(Modifier.height(12.dp))
                    Text("Go again", style = T.Chip, color = U.OnInverse, modifier = Modifier.clip(CircleShape).background(U.Inverse).clickable { index = 0; known = 0 }.padding(horizontal = 24.dp, vertical = 14.dp))
                }
            } else {
                val rot by animateFloatAsState(if (flipped) 180f else 0f, tween(320), label = "flip")
                val card = cards[index]
                Box(
                    Modifier.fillMaxWidth().height(360.dp)
                        .offset { IntOffset(x.value.roundToInt(), 0) }
                        .graphicsLayer { rotationZ = x.value / width * 12f; rotationY = rot; cameraDistance = 14f * density; alpha = 1f - abs(x.value) / width * 0.6f }
                        .clip(RoundedCornerShape(36.dp)).background(if (rot > 90f) U.Sage else U.Surface)
                        .pointerInput(index) {
                            detectDragGestures(
                                onDragEnd = { if (abs(x.value) > size.width / 3f) leave(x.value > 0) else scope.launch { x.animateTo(0f, tween(180)) } },
                                onDragCancel = { scope.launch { x.animateTo(0f) } },
                            ) { change, drag -> change.consume(); scope.launch { x.snapTo(x.value + drag.x) } }
                        }
                        .pointerInput(index) { detectTapGestures { flipped = !flipped } },
                    contentAlignment = Alignment.Center,
                ) {
                    // the back face is mirrored by the rotation, so it is flipped back here
                    Text(if (rot > 90f) card.back else card.front, style = T.Headline, color = U.TextPrimary, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(28.dp).graphicsLayer { rotationY = if (rot > 90f) 180f else 0f })
                }
            }
        }
        if (!done) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            IconBtn(R.drawable.ic_x, "Again", size = 64.dp) { leave(false) }
            Text(if (flipped) "Tap to see the question" else "Tap the card to flip", style = T.Sub, color = U.TextTertiary)
            IconBtn(R.drawable.ic_check, "Got it", bg = U.Inverse, size = 64.dp) { leave(true) }
        }
    }
}

/** One question at a time; the answer is marked the moment it is chosen, with the reason underneath. */
@Composable
fun QuizScreen(quiz: List<QuestionT>, onBack: () -> Unit, onRight: () -> Unit = {}, onFinished: (score: Int, total: Int) -> Unit) {
    var q by remember { mutableIntStateOf(0) }
    var picked by remember { mutableIntStateOf(-1) }
    var score by remember { mutableIntStateOf(0) }
    val done = q >= quiz.size
    ToolFrame("Quiz", if (done) "Finished" else "${q + 1} of ${quiz.size}", onBack) {
        ProgressTrack(q.toFloat() / quiz.size, fill = U.Sage)
        if (done) {
            Column(Modifier.weight(1f).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Text("$score / ${quiz.size}", style = T.Hero, color = U.TextPrimary)
                Text(when { score == quiz.size -> "Perfect. Nothing to revise."; score >= 2 -> "Good. Ask the tutor about the ones you missed."; else -> "Watch the lesson once more, then try again." }, style = T.Body, color = U.TextTertiary)
                Spacer(Modifier.height(20.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Try again", style = T.Chip, color = U.TextPrimary, modifier = Modifier.clip(CircleShape).background(U.Raised).clickable { q = 0; picked = -1; score = 0 }.padding(horizontal = 22.dp, vertical = 14.dp))
                    Text("Done", style = T.Chip, color = U.OnInverse, modifier = Modifier.clip(CircleShape).background(U.Inverse).clickable { onFinished(score, quiz.size) }.padding(horizontal = 22.dp, vertical = 14.dp))
                }
            }
        } else {
            AnimatedContent(q, Modifier.weight(1f), transitionSpec = { (slideInVertically { it / 6 } + fadeIn(tween(220))) togetherWith fadeOut(tween(120)) }, label = "question") { n ->
                val qq = quiz[n]
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(qq.text, style = T.Headline, color = U.TextPrimary, modifier = Modifier.padding(bottom = 8.dp))
                    qq.options.forEachIndexed { i, o ->
                        val tone = when { picked < 0 -> U.Raised; i == qq.answer -> U.Sage; i == picked -> U.Rust; else -> U.Raised }
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(tone).clickable(enabled = picked < 0) { picked = i; if (i == qq.answer) { score++; onRight() } }.padding(horizontal = 18.dp, vertical = 16.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Text("${'A' + i}", style = T.Chip, color = U.TextPrimary.copy(alpha = 0.7f))
                            Text(o, style = T.Body, color = U.TextPrimary, modifier = Modifier.weight(1f))
                            if (picked >= 0 && i == qq.answer) Glyph(R.drawable.ic_check, size = 20.dp)
                        }
                    }
                    AnimatedVisibility(picked >= 0, enter = fadeIn() + slideInVertically { it / 4 }, exit = fadeOut()) {
                        Text(qq.why, style = T.Body, color = U.TextSecondary, modifier = Modifier.padding(top = 6.dp))
                    }
                }
            }
            AnimatedVisibility(picked >= 0, enter = fadeIn(), exit = fadeOut()) {
                Text(if (q == quiz.size - 1) "See my score" else "Next question", style = T.Chip, color = U.OnInverse, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().clip(CircleShape).background(U.Inverse).clickable { q++; picked = -1 }.padding(vertical = 18.dp))
            }
        }
    }
}

/** Drag to move, pinch to zoom, tap an idea to read it and ask the tutor about it. All drawing is on one canvas. */
@Composable
fun MindMapScreen(map: MindMapT, onBack: () -> Unit, onExplain: (String) -> Unit) {
    val ideas = map.ideas.take(8).mapIndexed { i, x -> Idea(x.label, x.note, listOf(U.Accent, U.Cobalt, U.Sage, U.Orchid, U.Rust, U.Muted)[i % 6]) }
    var pan by remember { mutableStateOf(Offset.Zero) }
    var zoom by remember { mutableStateOf(1f) }
    var open by remember { mutableIntStateOf(-1) }
    val view by rememberUpdatedState(pan to zoom)             // the tap handler outlives a recomposition, so it reads the latest
    val measurer = rememberTextMeasurer()
    val labelStyle = T.Chip.copy(color = Color.White)
    Box(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
        Canvas(
            Modifier.fillMaxSize()
                .pointerInput(Unit) { detectTransformGestures { _, p, z, _ -> pan += p; zoom = (zoom * z).coerceIn(0.5f, 2.5f) } }
                .pointerInput(Unit) {
                    detectTapGestures { tap ->
                        val (p0, z0) = view
                        val c = Offset(size.width / 2f, size.height / 2f) + p0
                        val hit = ideas.indices.firstOrNull { i ->
                            val a = 2 * PI * i / ideas.size - PI / 2
                            (tap - (c + Offset(cos(a).toFloat(), sin(a).toFloat()) * 130.dp.toPx() * z0)).getDistance() < 40.dp.toPx() * z0
                        }
                        open = hit ?: -1
                    }
                },
        ) {
            val c = Offset(size.width / 2f, size.height / 2f) + pan
            val ring = 130.dp.toPx() * zoom
            ideas.forEachIndexed { i, idea ->
                val a = 2 * PI * i / ideas.size - PI / 2
                val p = c + Offset(cos(a).toFloat(), sin(a).toFloat()) * ring
                drawLine(U.GlassStrong, c, p, 2.dp.toPx())
                val r = 36.dp.toPx() * zoom
                drawCircle(idea.tone, r, p)
                if (open == i) drawCircle(Color.White, r + 4.dp.toPx(), p, style = Stroke(2.dp.toPx()))
                val t = measurer.measure(idea.label, labelStyle.copy(fontSize = labelStyle.fontSize * zoom))
                drawText(t, topLeft = p - Offset(t.size.width / 2f, t.size.height / 2f))
            }
            drawCircle(U.Inverse, 48.dp.toPx() * zoom, c)
            val t = measurer.measure(map.center.take(14), T.Title.copy(color = U.OnInverse, fontSize = T.Title.fontSize * zoom))
            drawText(t, topLeft = c - Offset(t.size.width / 2f, t.size.height / 2f))
        }
        IconBtn(R.drawable.ic_arrow_left, "Back", Modifier.padding(start = 16.dp, top = 12.dp), onClick = onBack)
        Text("Drag to move · pinch to zoom · tap an idea", style = T.Sub, color = U.TextTertiary, modifier = Modifier.align(Alignment.TopEnd).padding(end = 16.dp, top = 28.dp))
        AnimatedVisibility(open >= 0, Modifier.align(Alignment.BottomCenter), enter = fadeIn() + slideInVertically { it }, exit = fadeOut() + slideOutVertically { it }) {
            val idea = ideas[open.coerceAtLeast(0)]
            Column(Modifier.padding(16.dp).fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(U.Surface).border(1.dp, U.BorderGlass, RoundedCornerShape(28.dp)).padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(idea.label, style = T.Title, color = U.TextPrimary)
                Text(idea.note, style = T.Body, color = U.TextSecondary)
                Text("Explain this", style = T.Chip, color = U.OnInverse, modifier = Modifier.clip(CircleShape).background(U.Inverse).clickable { onExplain("Explain “${idea.label}” again") }.padding(horizontal = 20.dp, vertical = 12.dp))
            }
        }
    }
}

/** The lesson as one page of notes. */
@Composable
fun NotesScreen(title: String, notes: List<NoteT>, onBack: () -> Unit) {
    ToolFrame("Notes", title, onBack) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            notes.map { it.head to it.items }
            .forEach { (head, items) ->
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(U.Surface).padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SectionHeader(head)
                    items.forEach { Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { Box(Modifier.padding(top = 8.dp).size(6.dp).clip(CircleShape).background(U.Accent)); Text(it, style = T.Body, color = U.TextSecondary) } }
                }
            }
        }
    }
}
