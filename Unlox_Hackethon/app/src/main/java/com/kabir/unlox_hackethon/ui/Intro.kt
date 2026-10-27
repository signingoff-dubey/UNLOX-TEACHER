package com.kabir.unlox_hackethon.ui

import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Matrix
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.setFrom
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import com.kabir.unlox_hackethon.ui.theme.LogoPaths
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.tan

// The same opening as the web app (web/src/shell/Intro.tsx, from intro-animation/index.html): a book rises closed, its left page flips open,
// sprouts grow, the lockup slides left and the name is wiped in, then the cover lifts away. The whole thing is a pure function of the time t.
private const val SPINE = 342f
private const val BASE = 830f
private const val DUR = 3.7f
private const val LIFT = 0.8f
private val GROUND = Color(0xFFF6F6F6)

private fun clamp(x: Float, a: Float = 0f, b: Float = 1f) = x.coerceIn(a, b)
private fun seg(t: Float, a: Float, b: Float) = clamp((t - a) / (b - a))
private fun io(x: Float) = if (x < 0.5f) 4 * x * x * x else 1 - (-2 * x + 2).pow(3) / 2
private fun out(x: Float) = 1 - (1 - x).pow(3)

private class Shape(val path: Path, val color: Color)

private fun shapes(items: List<Pair<String, String>>): List<Shape> =
    items.map { (fill, d) -> Shape(PathParser().parsePathString(d).toPath(), Color(android.graphics.Color.parseColor(fill))) }

/** SVG's `translate(px+x py+y) rotate(r) skewY(kY) scale(sx sy) translate(-px -py)`. */
private fun tf(px: Float, py: Float, x: Float = 0f, y: Float = 0f, r: Float = 0f, sx: Float = 1f, sy: Float = 1f, kY: Float = 0f): Matrix {
    val m = android.graphics.Matrix()
    m.preTranslate(px + x, py + y)
    m.preRotate(r)
    m.preSkew(0f, tan(Math.toRadians(kY.toDouble())).toFloat())
    m.preScale(sx, sy)
    m.preTranslate(-px, -py)
    return Matrix().also { it.setFrom(m) }
}

private fun DrawScope.fillAll(list: List<Shape>, alpha: Float = 1f) = list.forEach { drawPath(it.path, it.color, alpha) }

/**
 * Plays on every cold start, over everything, then lifts away. A tap or Back skips it. Nothing recomposes while it plays:
 * the time is read only inside the draw and graphics-layer blocks.
 */
@Composable
fun Intro(onFinished: () -> Unit) {
    val left = remember { shapes(LogoPaths.LEFT) }
    val right = remember { shapes(LogoPaths.RIGHT) }
    val sprout = remember { shapes(LogoPaths.SPROUT) }
    val word = remember { shapes(LogoPaths.WORD) }
    var t by remember { mutableFloatStateOf(0f) }
    val finish by rememberUpdatedState(onFinished)
    val context = LocalContext.current
    LaunchedEffect(Unit) {
        // "Remove animations" in the phone's accessibility settings: skip straight to the app
        if (Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f) { finish(); return@LaunchedEffect }
        var start = 0L
        while (t < DUR + LIFT) androidx.compose.runtime.withFrameNanos { now ->
            if (start == 0L) start = now
            t = (now - start) / 1e9f
        }
        finish()
    }
    BackHandler { finish() }
    Box(
        Modifier.fillMaxSize()
            .graphicsLayer { translationY = -io(seg(t, DUR, DUR + LIFT)) * size.height }
            .background(GROUND)
            .pointerInput(Unit) { detectTapGestures { finish() } },
    ) {
        Canvas(Modifier.fillMaxWidth(0.86f).aspectRatio(1070f / 480f).align(Alignment.Center)) {
            val k = size.width / 1070f
            withTransform({ scale(k, k, pivot = Offset.Zero); translate(-150f, -440f) }) {
                withTransform({ translate(344f * (1 - io(seg(t, 2.2f, 3.1f))), 0f) }) {
                    val rise = out(seg(t, 0.15f, 0.85f))
                    val bookAlpha = seg(t, 0.15f, 0.5f)
                    withTransform({ transform(tf(SPINE, BASE, y = (1 - rise) * 40, sx = 0.9f + 0.1f * rise, sy = 0.9f + 0.1f * rise)) }) {
                        // the left page flips about the spine: 180 degrees to 0
                        val th = (PI * (1 - io(seg(t, 0.9f, 2.0f)))).toFloat()
                        withTransform({ transform(tf(SPINE, BASE, sx = cos(th), kY = -9f * sin(th))) }) { fillAll(left, bookAlpha) }
                        fillAll(right, bookAlpha)
                        // sprouts grow up from the junction: the clip opens bottom to top
                        val top = 740f - 240f * out(seg(t, 1.8f, 2.7f))
                        val sw = seg(t, 2.6f, 3.4f)
                        clipRect(200f, top, 520f, 740f) {
                            withTransform({ transform(tf(348f, 690f, r = sin(sw * PI.toFloat() * 2) * 1.2f * (1 - sw))) }) { fillAll(sprout, bookAlpha) }
                        }
                    }
                    // the name is wiped in from the left
                    val w = io(seg(t, 2.5f, 3.5f))
                    clipRect(500f, 560f, 500f + 680f * w + 20f, 860f) {
                        withTransform({ transform(tf(860f, 700f, x = -(1 - w) * 30f)) }) { fillAll(word, seg(t, 2.5f, 2.9f)) }
                    }
                }
            }
        }
    }
}
