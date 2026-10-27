package com.kabir.unlox_hackethon.ui.components

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.shape.GenericShape
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Density
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.sin
import kotlin.math.sqrt

/** Remembers where on screen a button is, so a screen can grow out of it. */
fun Modifier.rippleOrigin(holder: MutableState<Offset>): Modifier = onGloballyPositioned { holder.value = it.boundsInRoot().center }

/** Where the ripple starts: the button's centre, or the bottom-right corner when it is not known yet. */
private fun Density.centre(size: Size, origin: Offset): Offset =
    if (origin == Offset.Unspecified || origin == Offset.Zero) Offset(size.width - 46.dp.toPx(), size.height - 60.dp.toPx()) else origin

/**
 * A screen that spreads across the display from the button that opened it, as a growing circle with a faint ring on its edge,
 * and shrinks back into it. Only the clip circle animates (on the GPU); the content is composed once it starts to show.
 * Place it at the root, filling the window, so `origin` (from [rippleOrigin]) is in the same coordinates.
 */
@Composable
fun RippleReveal(open: Boolean, origin: Offset, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val reveal = remember { Animatable(if (open) 1f else 0f) }
    LaunchedEffect(open) {
        reveal.animateTo(if (open) 1f else 0f, tween(if (open) 460 else 320, easing = FastOutSlowInEasing))
    }
    val shown by remember { derivedStateOf { reveal.value > 0f } }
    if (!shown) return
    Box(modifier.fillMaxSize()) {
        Box(
            Modifier.fillMaxSize()
                .graphicsLayer {
                    val o = centre(size, origin)
                    val far = maxOf(o.getDistance(), (o - Offset(size.width, 0f)).getDistance(), (o - Offset(0f, size.height)).getDistance(), (o - Offset(size.width, size.height)).getDistance())
                    val r0 = 24.dp.toPx()
                    clip = true
                    shape = GenericShape { _, _ -> addOval(Rect(o, r0 + (far - r0) * reveal.value)) }
                }
                .background(U.BgApp),
        ) { Box(Modifier.fillMaxSize().graphicsLayer { alpha = (reveal.value * 2.5f).coerceIn(0f, 1f) }) { content() } }
        Canvas(Modifier.fillMaxSize()) {
            val o = centre(size, origin)
            val far = maxOf(o.getDistance(), (o - Offset(size.width, 0f)).getDistance(), (o - Offset(0f, size.height)).getDistance(), (o - Offset(size.width, size.height)).getDistance())
            val r0 = 24.dp.toPx()
            val p = reveal.value
            if (p in 0.01f..0.99f) drawCircle(Color.White.copy(alpha = 0.28f * (1f - p)), r0 + (far - r0) * p, o, style = Stroke(2.dp.toPx()))
        }
    }
}

/** What the microphone is hearing right now (a level 0..1 for the waveform) and everything heard so far, as 16 kHz mono samples. */
class Recording {
    val level = FloatArray(1)
    private val chunks = ArrayList<FloatArray>()
    @Synchronized fun add(c: FloatArray) { chunks.add(c) }
    @Synchronized fun samples(): FloatArray { val out = FloatArray(chunks.sumOf { it.size }); var i = 0; for (c in chunks) { c.copyInto(out, i); i += c.size }; return out }
}

/**
 * Records the microphone while `active`, on a background thread, so nothing on the main thread waits for audio. The level updates about
 * 20 times a second; the samples are kept for speech recognition. Without the permission it asks, and stays silent until it is given.
 */
@Composable
fun rememberRecording(active: Boolean): Recording {
    val rec = remember(active) { Recording() }
    val context = LocalContext.current
    var granted by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(active) { if (active && !granted) ask.launch(Manifest.permission.RECORD_AUDIO) }
    LaunchedEffect(active, granted) {
        if (!active || !granted) return@LaunchedEffect
        withContext(Dispatchers.IO) {
            val rate = 16000
            val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val buf = ShortArray(rate / 20)
            val ar = try {
                AudioRecord(MediaRecorder.AudioSource.MIC, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(min, buf.size * 4))
            } catch (_: SecurityException) { null }
            if (ar == null || ar.state != AudioRecord.STATE_INITIALIZED) { ar?.release(); return@withContext }
            try {
                ar.startRecording()
                while (true) {
                    val n = ar.read(buf, 0, buf.size)
                    if (n <= 0) continue
                    val f = FloatArray(n) { buf[it] / 32768f }
                    rec.add(f)
                    var sum = 0.0
                    for (x in f) sum += x * x
                    rec.level[0] = (sqrt(sum / n) * 7.0).toFloat().coerceIn(0f, 1f)
                    kotlinx.coroutines.yield()
                }
            } finally {
                runCatching { ar.stop() }
                ar.release()
                rec.level[0] = 0f
            }
        }
    }
    return rec
}

private const val BARS = 36
private const val STEP = 0.05f   // seconds per bar

/**
 * Waveform that glides: every frame the head eases toward the latest input level and the bars scroll left smoothly.
 * It all happens in the draw phase (the frame clock is read only inside the Canvas), so nothing recomposes.
 */
@Composable
fun Waveform(level: FloatArray, live: Boolean, modifier: Modifier = Modifier, color: Color = Color.White) {
    val bars = remember { FloatArray(BARS) }
    var frame by remember { mutableLongStateOf(0L) }
    val state = remember { floatArrayOf(0f, 0f) }   // [eased head level, scroll phase 0..1]
    LaunchedEffect(live) {
        var last = 0L
        while (true) androidx.compose.runtime.withFrameNanos { now ->
            val dt = if (last == 0L) 0f else ((now - last) / 1e9f).coerceAtMost(0.05f)
            last = now
            val goal = if (live) level[0] else 0.05f + 0.05f * sin(now / 3e8f)
            state[0] += (goal - state[0]) * (1f - exp(-dt * 14f))
            state[1] += dt / STEP
            while (state[1] >= 1f) {
                System.arraycopy(bars, 1, bars, 0, BARS - 1)
                bars[BARS - 1] = state[0]
                state[1] -= 1f
            }
            frame = now
        }
    }
    Canvas(modifier) {
        frame   // redraw every frame without recomposing
        val step = size.width / (BARS - 1)
        val w = step * 0.42f
        for (i in 0 until BARS) {
            val v = if (i == BARS - 1) state[0] else bars[i]
            val h = size.height * v.coerceIn(0.06f, 1f)
            val x = step * (i - state[1])
            if (x < -w) continue
            val fade = 1f - abs(i - BARS / 2f) / (BARS / 2f) * 0.6f
            drawLine(color.copy(alpha = 0.85f * fade), Offset(x, (size.height - h) / 2), Offset(x, (size.height + h) / 2), w, StrokeCap.Round)
        }
    }
}

private val VOICE_LANGS = listOf("Auto") + com.kabir.unlox_hackethon.data.LANGS.map { it.native }

/**
 * Voice mode: opened with [RippleReveal] from the mic button. Language chips (Auto listens and works out the language), the live
 * waveform, cancel on the left and done on the right. `onDone` gets what was recorded; `busy` shows while it is being understood.
 */
@Composable
fun VoiceScreen(onCancel: () -> Unit, busy: Boolean, onDone: (samples: FloatArray, hint: String?) -> Unit) {
    var language by rememberSaveable { mutableStateOf(VOICE_LANGS[0]) }
    val rec = rememberRecording(active = !busy)
    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
    ) {
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            VOICE_LANGS.forEach { l -> Chip(l, selected = l == language) { language = l } }
        }
        Spacer(Modifier.weight(1f))
        Text(
            if (busy) "Understanding…" else "Listening…", style = T.Display, color = U.TextPrimary,
            modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite },
        )
        Text(if (busy) "Working out what you said, on this phone." else "Speak in any language. Tap the tick when you are done.", style = T.Sub, color = U.TextTertiary)
        Waveform(rec.level, live = !busy, modifier = Modifier.fillMaxWidth().height(120.dp))
        Spacer(Modifier.weight(1f))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            IconBtn(R.drawable.ic_x, "Cancel", bg = U.Raised, size = 64.dp, onClick = onCancel)
            IconBtn(R.drawable.ic_check, "Done", bg = U.Inverse, size = 64.dp) {
                if (!busy) onDone(rec.samples(), com.kabir.unlox_hackethon.data.LANGS.firstOrNull { it.native == language }?.code)
            }
        }
    }
}
