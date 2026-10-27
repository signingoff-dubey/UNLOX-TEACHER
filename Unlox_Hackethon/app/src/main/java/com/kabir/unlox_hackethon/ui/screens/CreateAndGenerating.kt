package com.kabir.unlox_hackethon.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.ui.components.Chip
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.IconWell
import com.kabir.unlox_hackethon.ui.components.SectionHeader
import com.kabir.unlox_hackethon.ui.components.Segmented
import com.kabir.unlox_hackethon.ui.components.SwipePill
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.roundToInt
import kotlin.math.sin

/** What the learner picked on the Create screen; the pipeline reads it. */
data class LessonRequest(val concept: String, val languages: List<String>, val seconds: Int, val source: String, val mode: String = "Explanation", val videos: String = "Auto")

private val LANGS = listOf("Hindi", "Telugu", "Marathi", "Tamil", "Kannada", "Bengali", "Gujarati", "Malayalam")

/** 03 Create lesson: the concept, where the facts come from, the languages and how long it should be. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CreateLessonScreen(initialConcept: String, onBack: () -> Unit, onSettings: () -> Unit, onGenerate: (LessonRequest) -> Unit) {
    var concept by rememberSaveable { mutableStateOf(initialConcept.ifBlank { "How do vaccines work?" }) }
    var source by rememberSaveable { mutableIntStateOf(0) }
    var picked by rememberSaveable { mutableStateOf(setOf("Hindi", "Telugu")) }
    var length by rememberSaveable { mutableIntStateOf(0) }
    var mode by rememberSaveable { mutableIntStateOf(0) }
    var videos by rememberSaveable { mutableIntStateOf(0) }
    val modes = listOf("Explanation", "Study", "Homework")
    val counts = listOf("Auto", "1", "2", "3", "5", "8")
    val lengths = listOf(30, 60, 90)
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
            IconBtn(R.drawable.ic_settings, "Settings", onClick = onSettings)
        }
        Text("New lesson", style = T.Display, color = U.TextPrimary)
        Column(Modifier.verticalScroll(rememberScrollState()).weight(1f), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(horizontal = 20.dp, vertical = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("CONCEPT", style = T.Caption, color = U.TextTertiary)
                BasicTextField(concept, { concept = it }, textStyle = T.Headline.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary), modifier = Modifier.fillMaxWidth())
                Text("Or type a chapter or page range, e.g. chapter 4", style = T.Sub, color = U.TextTertiary)
            }
            SectionHeader("Source")
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SourceTile("Knowledge base", R.drawable.ic_book, source == 0, Modifier.weight(1f)) { source = 0 }
                SourceTile("Science 8.pdf", R.drawable.ic_file, source == 1, Modifier.weight(1f)) { source = 1 }
            }
            SectionHeader("Languages", trailing = "English always included")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LANGS.forEach { l -> Chip(l, selected = l in picked) { picked = if (l in picked) picked - l else picked + l } }
            }
            SectionHeader("Length")
            Segmented(lengths.map { "$it s" }, length, { length = it })
            SectionHeader("How to teach")
            Segmented(modes, mode, { mode = it })
            SectionHeader("Videos", trailing = "Auto lets the tutor decide")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                counts.forEachIndexed { i, c -> Chip(c, selected = i == videos) { videos = i } }
            }
        }
        SwipePill("Swipe to generate", R.drawable.ic_sparkles, U.Accent) {
            onGenerate(LessonRequest(concept.trim(), listOf("English") + LANGS.filter { it in picked }, lengths[length], if (source == 0) "knowledge base" else "Science 8.pdf", modes[mode], counts[videos]))
        }
    }
}

@Composable
private fun SourceTile(label: String, icon: Int, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Column(
        modifier.height(112.dp).clip(RoundedCornerShape(28.dp)).background(if (selected) U.Accent else U.Raised).clickable(onClick = onClick).padding(12.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        if (selected) IconWell(icon, U.Inverse, 48.dp, 24.dp, U.OnInverse) else IconWell(icon, U.BorderGlass, 48.dp, 24.dp)
        Text(label, style = T.Body, color = U.TextPrimary, maxLines = 1)
    }
}

enum class StageState { DONE, ACTIVE, PENDING }
data class Stage(val title: String, val detail: String, val state: StageState, val pct: Float = 0f)

/** 04 Generating: a 26-tick dial, the percentage, and the five pipeline stages. */
@Composable
fun GeneratingScreen(request: LessonRequest, progress: Float, status: String, stages: List<Stage>, onClose: () -> Unit) {
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        IconBtn(R.drawable.ic_x, "Cancel", onClick = onClose)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Building your\nlesson", style = T.Display, color = U.TextPrimary)
            Text("${request.concept} · ${request.languages.take(3).joinToString(", ")}", style = T.Body, color = U.TextTertiary, maxLines = 2)
        }
        val shown = rememberSteadyProgress(progress, tau = 45f)
        ProgressDial(shown, status)
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) { stages.forEach { StageRow(it) } }
    }
}

/**
 * Progress that never stops moving while work is going on (the same idea as the website's useSteadyProgress). The engines report in bursts:
 * nothing while Gemma plans, then a jump. Showing that directly makes the dial sit at 10% and snap to 45%. Instead a clock drives it up and
 * slows it down the longer the work takes, real progress can only pull it further ahead, and it glides at a limited speed, never backwards.
 * `tau` is roughly how many seconds the work takes. Read the returned state only in draw blocks, so nothing recomposes per frame.
 */
@Composable
fun rememberSteadyProgress(real: Float, tau: Float = 45f): State<Float> {
    val shown = remember { mutableFloatStateOf(0f) }
    val realNow by rememberUpdatedState(real)
    LaunchedEffect(Unit) {
        var v = 0f; var vel = 0f; var t0 = 0L; var last = 0L
        while (true) withFrameNanos { now ->
            if (t0 == 0L) t0 = now
            val dt = if (last == 0L) 0.016f else ((now - last) / 1e9f).coerceAtMost(0.1f)
            last = now
            if (realNow >= 1f) v += (1f - v) * minOf(dt * 7f, 1f)                                 // finished: glide to the end
            else {
                val clock = 0.93f * (1f - exp(-((now - t0) / 1e9f) / tau))
                val target = minOf(0.985f, maxOf(realNow, minOf(clock, realNow + 0.04f)))                // the clock may only run a little ahead of the real work
                val want = if (target > v) (target - v) * 1.6f + 0.012f else 0f                    // faster when far behind, never zero while behind
                vel += (want - vel) * minOf(dt * 4f, 1f)                                           // the speed itself changes smoothly
                v = minOf(0.985f, v + vel * dt)
            }
            shown.floatValue = v
        }
    }
    return shown
}

@Composable
private fun ProgressDial(progress: State<Float>, status: String) {
    val ticks = 26
    val percent by remember { derivedStateOf { (progress.value * 100).roundToInt() } }
    Box(Modifier.fillMaxWidth().height(190.dp), contentAlignment = Alignment.BottomCenter) {
        Canvas(Modifier.fillMaxSize()) {
            val lit = (progress.value * ticks).roundToInt()
            val centre = Offset(size.width / 2, 149.dp.toPx())
            val radius = 127.dp.toPx()
            val len = 40.dp.toPx()
            val wid = 14.dp.toPx()
            for (i in 0 until ticks) {
                val a = PI * (1.0 - i / (ticks - 1.0))                      // from the left end round to the right end
                val pos = Offset(centre.x + radius * cos(a).toFloat(), centre.y - radius * sin(a).toFloat())
                val color = when { i >= lit -> U.Glass; i >= lit - 3 -> U.Accent; else -> U.Sage }
                rotate(degrees = -(a * 180.0 / PI).toFloat(), pivot = pos) {
                    drawRoundRect(color, Offset(pos.x - len / 2, pos.y - wid / 2), Size(len, wid), CornerRadius(wid / 2))
                }
            }
        }
        Column(Modifier.padding(bottom = 4.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("$percent%", style = T.Hero, color = U.TextPrimary)
            Text(status, style = T.Sub, color = U.TextTertiary, textAlign = TextAlign.Center, maxLines = 1)
        }
    }
}

@Composable
private fun StageRow(s: Stage) {
    val active = s.state == StageState.ACTIVE
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).then(if (active) Modifier.background(U.Raised) else Modifier)
            .padding(start = 10.dp, end = 16.dp, top = 10.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        when (s.state) {
            StageState.DONE -> IconWell(R.drawable.ic_check, U.Sage, 32.dp, 14.dp)
            StageState.ACTIVE -> IconWell(R.drawable.ic_globe, U.Accent, 32.dp, 14.dp)
            StageState.PENDING -> IconWell(R.drawable.ic_clock, U.Glass, 32.dp, 14.dp, U.TextTertiary)
        }
        Column(Modifier.weight(1f)) {
            Text(s.title, style = T.Body, color = if (s.state == StageState.PENDING) U.TextTertiary else U.TextPrimary, maxLines = 1)
            Text(s.detail, style = T.Sub, color = U.TextTertiary, maxLines = 1)
        }
        // a percentage for every stage, gliding rather than jumping
        val pct by androidx.compose.animation.core.animateFloatAsState(if (s.state == StageState.DONE) 1f else s.pct, androidx.compose.animation.core.tween(600, easing = androidx.compose.animation.core.LinearEasing), label = "stage")
        Text("${(pct * 100).roundToInt()}%", style = T.Caption, color = if (s.state == StageState.PENDING && pct == 0f) U.TextTertiary else U.TextPrimary)
    }
}
