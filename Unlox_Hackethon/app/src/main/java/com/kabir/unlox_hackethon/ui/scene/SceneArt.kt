package com.kabir.unlox_hackethon.ui.scene

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.State
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kabir.unlox_hackethon.data.CurveT
import com.kabir.unlox_hackethon.data.MarkT
import com.kabir.unlox_hackethon.data.SceneT
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

// The lesson video, drawn in a virtual 1920 x 1080 space (the same layout as the website's Remotion scenes) and scaled to fit. Every
// scene is data (a template and its slots); this file decides how it looks and moves. Time is read only in graphics layers and draw
// blocks, so a playing scene does not recompose.

private val BG = Color(0xFFE2E2E2); private val INK = Color(0xFF1C1C1C); private val MUTED = Color(0xFF6B6B6B); private val CARD = Color(0xFFF6F6F6)
private val LINE = Color(0xFFE9E9E9); private val GRID = Color(0xFFD2D2D2); private val GREEN = Color(0xFF2F8335); private val ORANGE = Color(0xFFE06A1B)
private val BLUE = Color(0xFF4A86C5); private val PINK = Color(0xFFE0457A); private val VIOLET = Color(0xFF7A62C9); private val TEAL = Color(0xFF2E9AA0)
private val PALETTE = listOf(ORANGE, GREEN, BLUE, PINK, VIOLET, TEAL)
private const val W = 1920f
private const val LEFT = 110f
private const val RIGHT = 1810f

// ---------------------------------------------------------------- timing helpers

/** 0 -> 1 with a little overshoot, starting when `t` passes 0 (a spring). */
private fun pop(t: Float): Float = if (t <= 0f) 0f else (1f - exp(-9f * t) * cos(11f * t)).coerceIn(0f, 1.12f)
private fun ease(t: Float, from: Float, to: Float): Float { val x = ((t - from) / (max(to, from + 0.001f) - from)).coerceIn(0f, 1f); return 1f - (1f - x).pow(3) }
/** When item `i` of `n` appears, spread over the spoken part so the picture follows the narration. */
private fun at(i: Float, n: Int, speech: Float, lead: Float = 0.33f) = lead + i * speech * 0.78f / max(n, 1)
private fun fit(text: String, base: Int, comfortable: Int, min: Float = 0.55f) = (base * max(min, min(1f, comfortable.toFloat() / max(text.length, 1)))).roundToInt()
private fun fitAll(texts: List<String>, base: Int, comfortable: Int, min: Float = 0.55f) = fit(texts.maxByOrNull { it.length } ?: "", base, comfortable, min)

private fun Modifier.anim(time: State<Float>, delay: Float = 0f, slideX: Float = 0f, slideY: Float = 0f, scaleFrom: Float = 1f): Modifier = graphicsLayer {
    val p = pop(time.value - delay)
    alpha = p.coerceIn(0f, 1f); translationX = (1f - p) * slideX; translationY = (1f - p) * slideY
    val s = scaleFrom + (1f - scaleFrom) * p; scaleX = s; scaleY = s
}

@Composable
private fun Txt(text: String, size: Int, color: Color = INK, weight: Int = 600, modifier: Modifier = Modifier, align: TextAlign = TextAlign.Start, mono: Boolean = false, lh: Float = 1.3f, maxLines: Int = Int.MAX_VALUE) =
    Text(text, modifier, color, fontSize = size.sp, fontWeight = FontWeight(weight), lineHeight = (size * lh).sp, textAlign = align,
        fontFamily = if (mono) FontFamily.Monospace else FontFamily.SansSerif, maxLines = maxLines, overflow = TextOverflow.Ellipsis)

private fun Modifier.at(x: Float, y: Float) = offset(x.dp, y.dp)

/** The soft card of the website's theme. */
@Composable
private fun CardBox(modifier: Modifier, time: State<Float>, border: (Float) -> Color = { LINE }, fill: (Float) -> Color = { CARD }, content: @Composable androidx.compose.foundation.layout.BoxScope.() -> Unit) {
    val shape = RoundedCornerShape(36.dp)
    Box(modifier.shadow(14.dp, shape, ambientColor = Color(0x14000000), spotColor = Color(0x14000000)).clip(shape)
        .drawBehind { val t = time.value; drawRect(fill(t)); drawRoundRect(border(t), cornerRadius = CornerRadius(36f), style = Stroke(6f)) }) { content() }
}

// ---------------------------------------------------------------- icons (100 x 100 line drawings, as on the website)

private class Part(val path: Path, val fill: Color? = null, val rotate: Float = 0f)

private fun p(d: String) = PathParser().parsePathString(d).toPath()
private fun oval(cx: Float, cy: Float, rx: Float, ry: Float) = Path().apply { addOval(Rect(cx - rx, cy - ry, cx + rx, cy + ry)) }

private val ICONS: Map<String, List<Part>> by lazy {
    mapOf(
        "lightbulb" to listOf(Part(p("M50 12a26 26 0 0 0-15 47c4 3 6 7 6 11h18c0-4 2-8 6-11a26 26 0 0 0-15-47z"), Color(0xFFFFE28A)), Part(p("M41 80h18M43 89h14"))),
        "sun" to listOf(Part(oval(50f, 50f, 18f, 18f), Color(0xFFFFC94A))) + (0 until 8).map { i -> val a = i * PI.toFloat() / 4f
            Part(Path().apply { moveTo(50 + 28 * cos(a), 50 + 28 * sin(a)); lineTo(50 + 40 * cos(a), 50 + 40 * sin(a)) }) },
        "leaf" to listOf(Part(p("M18 82C18 40 45 16 84 16c0 40-24 66-66 66z"), Color(0xFF8FD18A)), Part(p("M18 82L62 38M40 60h16M32 52V38"))),
        "water" to listOf(Part(p("M50 12C38 32 24 46 24 62a26 26 0 0 0 52 0c0-16-14-30-26-50z"), Color(0xFF8CC8F2))),
        "atom" to listOf(Part(oval(50f, 50f, 40f, 15f)), Part(oval(50f, 50f, 40f, 15f), rotate = 60f), Part(oval(50f, 50f, 40f, 15f), rotate = -60f), Part(oval(50f, 50f, 7f, 7f), PINK)),
        "cell" to listOf(Part(oval(50f, 50f, 40f, 32f), Color(0xFFCDEBC6)), Part(oval(56f, 46f, 12f, 12f), Color(0xFF9C84DB)), Part(oval(30f, 58f, 3f, 3f), INK), Part(oval(40f, 68f, 3f, 3f), INK), Part(oval(72f, 64f, 3f, 3f), INK)),
        "heart" to listOf(Part(p("M50 84S14 62 14 36a18 18 0 0 1 36-4 18 18 0 0 1 36 4c0 26-36 48-36 48z"), Color(0xFFF29AAE))),
        "brain" to listOf(Part(p("M48 18c-10-6-26 0-26 14-10 6-10 22 0 28 0 14 14 22 26 16zM52 18c10-6 26 0 26 14 10 6 10 22 0 28 0 14-14 22-26 16z"), Color(0xFFF6B8C8)), Part(p("M34 40c6 0 8 6 8 10M66 40c-6 0-8 6-8 10"))),
        "earth" to listOf(Part(oval(50f, 50f, 38f, 38f), Color(0xFF8CC8F2)), Part(p("M28 30c8 2 10 10 18 10s6 12-2 16-10 12-14 18M64 20c-2 8 6 12 12 12M62 62c6-4 14 0 16 6"), Color(0xFF8FD18A))),
        "bolt" to listOf(Part(p("M56 8L22 56h24l-6 36 36-50H52z"), Color(0xFFFFD84A))),
        "gear" to (0 until 8).map { i -> Part(p("M46 8h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2z"), Color(0xFFC9D3E6), rotate = i * 45f) } +
            listOf(Part(oval(50f, 50f, 27f, 27f), Color(0xFFC9D3E6)), Part(oval(50f, 50f, 10f, 10f), BG)),
        "book" to listOf(Part(p("M50 26C40 18 24 18 12 22v56c12-4 28-4 38 4 10-8 26-8 38-4V22c-12-4-28-4-38 4z"), Color(0xFFFFE7C2)), Part(p("M50 26v56"))),
        "flask" to listOf(Part(p("M40 12h20M43 12v26L20 80a6 6 0 0 0 5 8h50a6 6 0 0 0 5-8L57 38V12"), Color.White), Part(p("M30 62h40l10 18a6 6 0 0 1-5 8H25a6 6 0 0 1-5-8z"), Color(0xFF9FE0C9))),
        "cloud" to listOf(Part(p("M28 76a18 18 0 0 1-2-36 24 24 0 0 1 46-6 20 20 0 0 1 4 42z"), Color(0xFFE6EEF9))),
        "magnet" to listOf(Part(p("M22 18v34a28 28 0 0 0 56 0V18H60v34a10 10 0 0 1-20 0V18z"), Color(0xFFF08A8A)), Part(p("M22 18h18v14H22zM60 18h18v14H60z"), Color(0xFFE3E8F0))),
        "rocket" to listOf(Part(p("M50 8c18 14 22 40 14 62H36C28 48 32 22 50 8z"), Color(0xFFE6EEF9)), Part(oval(50f, 38f, 8f, 8f), Color(0xFF8CC8F2)), Part(p("M36 58L22 74v10l16-10M64 58l14 16v10L62 74M42 76l8 16 8-16"), Color(0xFFF7A65A))),
    )
}

@Composable
private fun SceneIcon(name: String, size: Int, modifier: Modifier = Modifier) {
    val parts = ICONS[name] ?: ICONS.getValue("lightbulb")
    Canvas(modifier.size(size.dp)) {
        scale(size / 100f, size / 100f, pivot = Offset.Zero) {
            for (part in parts) rotate(part.rotate, Offset(50f, 50f)) {
                part.fill?.let { drawPath(part.path, it, style = Fill) }
                drawPath(part.path, INK, style = Stroke(5f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
    }
}

// ---------------------------------------------------------------- shared pieces

@Composable
private fun Heading(text: String, time: State<Float>, color: Color = ORANGE) {
    Column(Modifier.at(LEFT, 140f).width(1700.dp).anim(time, slideY = 30f)) {
        Txt(text, fit(text, 64, 34), INK, 800, lh = 1.25f)
        Box(Modifier.padding(top = 14.dp).height(8.dp).graphicsLayer { scaleX = ease(time.value, 0.2f, 0.87f); transformOrigin = TransformOrigin(0f, 0.5f) }.width(160.dp).background(color, RoundedCornerShape(4.dp)))
    }
}

/** A line that draws itself as `p` goes 0 -> 1, with an arrow head at the end. */
private fun DrawScope.drawLine(a: Offset, b: Offset, p: Float, color: Color, width: Float = 7f, arrow: Boolean = false) {
    if (p <= 0f) return
    val e = Offset(a.x + (b.x - a.x) * p, a.y + (b.y - a.y) * p)
    drawLine(color, a, e, width, StrokeCap.Round)
    if (arrow && p > 0.95f) {
        val ang = kotlin.math.atan2(b.y - a.y, b.x - a.x)
        val s = 22f
        val path = Path().apply {
            moveTo(b.x + 6f * cos(ang), b.y + 6f * sin(ang))
            lineTo(b.x - s * cos(ang - 0.5f), b.y - s * sin(ang - 0.5f)); lineTo(b.x - s * cos(ang + 0.5f), b.y - s * sin(ang + 0.5f)); close()
        }
        drawPath(path, color)
    }
}

// ---------------------------------------------------------------- the templates

@Composable
private fun TitleScene(s: SceneT, lessonTitle: String, time: State<Float>) {
    val kicker = lessonTitle.isNotBlank() && lessonTitle.trim() != s.heading.trim()
    Column(Modifier.fillMaxSize().padding(start = 110.dp, end = 110.dp, top = 140.dp, bottom = 220.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(36.dp, Alignment.CenterVertically)) {
        Box(Modifier.size(280.dp).graphicsLayer { val pp = pop(time.value - 0.06f); scaleX = pp; scaleY = pp; translationY = sin(time.value * 2.1f) * 8f }
            .clip(CircleShape).background(Brush.radialGradient(listOf(Color(0xFFE18951), Color(0xFFF15F8A), Color(0xFFF589A3), Color(0xFFF0C2C7)))).border(6.dp, ORANGE, CircleShape), contentAlignment = Alignment.Center) {
            SceneIcon(s.icon, 190)
        }
        Column(Modifier.anim(time, 0.33f, slideY = 40f), horizontalAlignment = Alignment.CenterHorizontally) {
            if (kicker) Txt(lessonTitle, 40, TEAL, 700, Modifier.padding(bottom = 12.dp), TextAlign.Center)
            Txt(s.heading, fit(s.heading, 92, 24), INK, 600, Modifier.widthIn1500(), TextAlign.Center, lh = 1.15f)
        }
    }
}

private fun Modifier.widthIn1500() = width(1500.dp)

@Composable
private fun ListScene(s: SceneT, speech: Float, time: State<Float>, checks: Boolean) {
    val n = s.items.size.coerceAtLeast(1)
    val rowH = min(118f, 560f / n)
    Heading(s.heading, time, if (checks) GREEN else ORANGE)
    Column(Modifier.at(LEFT + 40f, 330f).width(1350.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
        s.items.forEachIndexed { i, item ->
            val start = at(i.toFloat(), n, speech)
            val color = if (checks) GREEN else PALETTE[i % PALETTE.size]
            CardBox(Modifier.fillMaxWidth().heightIn(min = (rowH - 22f).dp).anim(time, start, slideX = -80f), time) {
                Row(Modifier.padding(horizontal = 32.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                    Box(Modifier.size(64.dp).clip(CircleShape).background(color), contentAlignment = Alignment.Center) {
                        if (checks) Canvas(Modifier.size(40.dp)) {
                            val pr = ease(time.value, start + 0.15f, start + 0.55f)
                            val path = Path().apply { moveTo(9f, 21f); lineTo(17f, 29f); lineTo(32f, 12f) }
                            val dst = Path(); val m = PathMeasure().apply { setPath(path, false) }; m.getSegment(0f, m.length * pr, dst, true)
                            drawPath(dst, Color.White, style = Stroke(6f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                        } else Txt("${i + 1}", 34, Color.White, 800)
                    }
                    Txt(item, fit(item, 46, 34), INK, 600)
                }
            }
        }
    }
    Box(Modifier.at(W - LEFT - 20f - 260f, 360f).graphicsLayer { alpha = 0.9f; rotationZ = sin(time.value * 1.5f) * 4f }) { SceneIcon(s.icon, 260) }
}

@Composable
private fun FlowScene(s: SceneT, speech: Float, time: State<Float>) {
    val n = s.items.size.coerceAtLeast(1)
    val gap = 80f
    val boxW = min(400f, (RIGHT - LEFT - gap * (n - 1)) / n)
    val total = boxW * n + gap * (n - 1)
    val x0 = (W - total) / 2f
    val y = 470f
    Heading(s.heading, time, ORANGE)
    Canvas(Modifier.fillMaxSize()) {
        for (i in 1 until n) { val st = at(i.toFloat(), n, speech); val xa = x0 + i * boxW + (i - 1) * gap + 12f
            drawLine(Offset(xa, y + 110f), Offset(xa + gap - 30f, y + 110f), ease(time.value, st - 0.33f, st), MUTED, 7f, true) }
    }
    s.items.forEachIndexed { i, item ->
        val color = PALETTE[i % PALETTE.size]
        CardBox(Modifier.at(x0 + i * (boxW + gap), y).width(boxW.dp).heightIn(min = 220.dp).anim(time, at(i.toFloat(), n, speech), scaleFrom = 0.6f), time, { color }) {
            Box(Modifier.align(Alignment.TopCenter).offset(y = (-34).dp).size(68.dp).clip(CircleShape).background(color), contentAlignment = Alignment.Center) { Txt("${i + 1}", 34, Color.White, 800) }
            Box(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 56.dp, bottom = 24.dp), contentAlignment = Alignment.Center) { Txt(item, fitAll(s.items, 42, (boxW / 26f).toInt()), INK, 700, align = TextAlign.Center) }
        }
    }
}

@Composable
private fun CycleScene(s: SceneT, speech: Float, time: State<Float>) {
    val n = s.items.size.coerceAtLeast(3)
    val cx = W / 2; val cy = 545f; val r = 270f
    fun ang(i: Int) = -PI.toFloat() / 2 + 2 * PI.toFloat() * i / n
    fun pt(a: Float) = Offset(cx + r * cos(a) * 1.55f, cy + r * sin(a))
    Heading(s.heading, time, TEAL)
    Canvas(Modifier.fillMaxSize()) {
        for (i in s.items.indices) {
            val st = at(((i + 1) % n).let { if (it == 0) n - 0.4f else it.toFloat() }, n, speech)
            val a1 = ang(i) + 0.42f; val a2 = ang(i + 1) - 0.42f
            val pr = ease(time.value, st - 0.4f, st + 0.13f)
            val steps = 24
            val path = Path(); for (k in 0..steps) { val q = pt(a1 + (a2 - a1) * k / steps); if (k == 0) path.moveTo(q.x, q.y) else path.lineTo(q.x, q.y) }
            val dst = Path(); val m = PathMeasure().apply { setPath(path, false) }; m.getSegment(0f, m.length * pr, dst, true)
            drawPath(dst, TEAL, style = Stroke(7f, cap = StrokeCap.Round))
            if (pr > 0.95f) { val e = pt(a2); val tang = kotlin.math.atan2(pt(a2).y - pt(a2 - 0.05f).y, pt(a2).x - pt(a2 - 0.05f).x)
                drawPath(Path().apply { moveTo(e.x + 8 * cos(tang), e.y + 8 * sin(tang)); lineTo(e.x - 20 * cos(tang - 0.5f), e.y - 20 * sin(tang - 0.5f)); lineTo(e.x - 20 * cos(tang + 0.5f), e.y - 20 * sin(tang + 0.5f)); close() }, TEAL) }
        }
    }
    Box(Modifier.at(cx - 90, cy - 90).graphicsLayer { rotationZ = time.value * 18f }) { SceneIcon(s.icon, 180) }
    s.items.forEachIndexed { i, item ->
        val q = pt(ang(i)); val color = PALETTE[i % PALETTE.size]
        CardBox(Modifier.at(q.x - 180, q.y - 52).width(360.dp).anim(time, at(i.toFloat(), n, speech), scaleFrom = 0.5f), time, { color }) {
            Box(Modifier.padding(horizontal = 20.dp, vertical = 18.dp)) { Txt(item, fitAll(s.items, 40, 16), INK, 700, align = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
        }
    }
}

@Composable
private fun CompareScene(s: SceneT, speech: Float, time: State<Float>) {
    val cols = listOf(Triple(s.leftTitle, s.left, TEAL), Triple(s.rightTitle, s.right, ORANGE))
    val all = s.left.size + s.right.size
    var k = 0
    Heading(s.heading, time, ORANGE)
    cols.forEachIndexed { c, (title, items, color) ->
        CardBox(Modifier.at(if (c == 0) LEFT + 40 else W / 2 + 70, 320f).width((W / 2 - LEFT - 110).dp).heightIn(min = 480.dp).anim(time, c * 0.27f, slideY = 60f), time, { color }) {
            Column {
                Box(Modifier.fillMaxWidth().background(color).padding(horizontal = 36.dp, vertical = 20.dp)) { Txt(title, fit(title, 48, 22), Color.White, 800) }
                Column(Modifier.padding(horizontal = 36.dp, vertical = 26.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                    items.forEach { item ->
                        val st = at((k++).toFloat(), all, speech)
                        Row(Modifier.anim(time, st, slideX = 40f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                            Box(Modifier.size(18.dp).clip(CircleShape).background(color)); Txt(item, fit(item, 44, 26), INK, 600)
                        }
                    }
                }
            }
        }
    }
    Box(Modifier.at(W / 2 - 50, 520f).size(100.dp).anim(time, 0.47f, scaleFrom = 0f).clip(CircleShape).background(INK), contentAlignment = Alignment.Center) { Txt("vs", 38, Color.White, 800) }
}

@Composable
private fun DiagramScene(s: SceneT, speech: Float, time: State<Float>) {
    val n = s.items.size.coerceAtLeast(2)
    val cx = W / 2; val cy = 500f; val r = 150f
    val start = -PI.toFloat() / 2 + PI.toFloat() / n
    fun pos(i: Int): Triple<Float, Float, Float> { val a = start + 2 * PI.toFloat() * i / n; return Triple(a, cx + 610 * cos(a), cy + 270 * sin(a)) }
    Canvas(Modifier.fillMaxSize()) {
        s.items.indices.forEach { i ->
            val (a, x, y) = pos(i); val st = at(i.toFloat(), n, speech)
            drawLine(Offset(cx + (r + 10) * cos(a), cy + (r + 10) * sin(a)), Offset(x, y), ease(time.value, st - 0.27f, st + 0.2f), PALETTE[i % PALETTE.size], 6f)
        }
    }
    Box(Modifier.at(cx - r, cy - r).size((2 * r).dp).anim(time, 0f, scaleFrom = 0f).clip(CircleShape).background(CARD).border(8.dp, INK, CircleShape), contentAlignment = Alignment.Center) { SceneIcon(s.icon, 170) }
    Box(Modifier.at(cx - 300, cy + r + 18).width(600.dp).anim(time, 0.1f), contentAlignment = Alignment.Center) {
        Txt(s.heading, fit(s.heading, 46, 18), Color.White, 800, Modifier.background(INK, RoundedCornerShape(40.dp)).padding(horizontal = 28.dp, vertical = 8.dp), TextAlign.Center)
    }
    s.items.forEachIndexed { i, item ->
        val (_, x, y) = pos(i); val color = PALETTE[i % PALETTE.size]
        CardBox(Modifier.at(x - 170, y - 46).width(340.dp).anim(time, at(i.toFloat(), n, speech), scaleFrom = 0.5f), time, { color }) {
            Box(Modifier.padding(horizontal = 18.dp, vertical = 16.dp)) { Txt(item, fitAll(s.items, 40, 15), INK, 700, align = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
        }
    }
}

@Composable
private fun QuizScene(s: SceneT, speech: Float, time: State<Float>) {
    val n = s.items.size.coerceAtLeast(2)
    val gap = 40f
    val w = min(480f, (RIGHT - LEFT - gap * (n - 1)) / n)
    val x0 = (W - (w * n + gap * (n - 1))) / 2
    val revealAt = speech * 0.6f
    val revealed by remember { derivedStateOf { ease(time.value, revealAt, revealAt + 0.33f) > 0.5f } }
    Heading(s.heading, time, VIOLET)
    s.items.forEachIndexed { i, item ->
        val correct = i == s.answerIndex
        CardBox(Modifier.at(x0 + i * (w + gap), 420f).width(w.dp).heightIn(min = 260.dp)
            .graphicsLayer { val p = pop(time.value - (0.47f + i * 0.2f)); val rv = ease(time.value, revealAt, revealAt + 0.33f)
                alpha = p.coerceIn(0f, 1f) * (if (correct) 1f else 1f - 0.55f * rv); val sc = (0.6f + 0.4f * p) * (if (correct) 1f + 0.06f * rv else 1f); scaleX = sc; scaleY = sc },
            time, { t -> if (correct && ease(t, revealAt, revealAt + 0.33f) > 0f) GREEN else LINE }, { t -> if (correct) Color(0xFF2E9E57).copy(alpha = 0.16f * ease(t, revealAt, revealAt + 0.33f)).compositeOver(CARD) else CARD }) {
            Box(Modifier.align(Alignment.TopStart).padding(18.dp, 18.dp).size(64.dp).clip(RoundedCornerShape(18.dp)).background(if (correct && revealed) GREEN else VIOLET), contentAlignment = Alignment.Center) {
                Txt(if (correct && revealed) "✓" else ('A' + i).toString(), 36, Color.White, 800)
            }
            Box(Modifier.fillMaxWidth().padding(start = 24.dp, end = 24.dp, top = 70.dp, bottom = 30.dp), contentAlignment = Alignment.Center) { Txt(item, fitAll(s.items, 46, (w / 28f).toInt()), INK, 700, align = TextAlign.Center) }
        }
    }
}

// ---------------------------------------------------------------- graph

private fun fnY(c: CurveT, x: Double): Double? = when (c.type) {
    "line" -> c.a * x + c.b; "parabola" -> c.a * x * x + c.b * x + c.c; "cubic" -> c.a * x.pow(3) + c.b * x * x + c.c * x + c.d
    "sine" -> c.a * sin(c.b * x + c.c) + c.d; "cosine" -> c.a * cos(c.b * x + c.c) + c.d; "exp" -> c.a * exp(c.b * x) + c.c
    "abs" -> c.a * abs(x - c.b) + c.c; "sqrt" -> if (x - c.b >= 0) c.a * sqrt(x - c.b) + c.c else null; "reciprocal" -> if (abs(x) < 1e-6) null else c.a / x
    else -> null
}

private fun isRound(c: CurveT) = c.type == "circle" || c.type == "ellipse"
private fun radii(c: CurveT) = if (c.type == "circle") c.c to c.c else c.c to c.d
private fun niceStep(span: Double, target: Int = 8): Double { val raw = span / target; val mag = 10.0.pow(floor(kotlin.math.log10(raw))); val n = raw / mag; return (if (n < 1.5) 1 else if (n < 3.5) 2 else if (n < 7.5) 5 else 10) * mag }
private fun fmt(v: Double) = if (abs(v) < 1e-9) "0" else (Math.round(v * 100) / 100.0).toString().removeSuffix(".0")

private const val PX = LEFT; private const val PY = 260f; private const val PW = 1010f; private const val PH = 590f
private const val PANEL = PX + PW + 50f

@Composable
private fun GraphScene(s: SceneT, speech: Float, time: State<Float>) {
    val curves = s.curves; val marks = s.marks; val steps = curves.size + marks.size
    val measurer = rememberTextMeasurer()
    // ranges that show the curves well; round shapes keep an equal scale so circles look round
    val rng = remember(s) {
        var x0 = s.xRange.getOrNull(0) ?: Double.NaN; var x1 = s.xRange.getOrNull(1) ?: Double.NaN
        var y0 = s.yRange.getOrNull(0) ?: Double.NaN; var y1 = s.yRange.getOrNull(1) ?: Double.NaN
        val round = curves.filter(::isRound); val pts = marks.filter { it.kind == "point" || it.kind == "link" }
        val extX = if (pts.isEmpty()) 0.0 else pts.maxOf { abs(it.x) } + 2; val extY = if (pts.isEmpty()) 0.0 else pts.maxOf { abs(it.y) } + 2
        if (x0.isNaN() || x1.isNaN()) { if (round.isNotEmpty()) { val e = round.maxOf { abs(it.a) + radii(it).first }; x0 = -e * 1.35; x1 = e * 1.35 } else { val e = max(6.0, kotlin.math.ceil(extX)); x0 = -e; x1 = e } }
        if (y0.isNaN() || y1.isNaN()) {
            if (round.isNotEmpty()) { val e = round.maxOf { abs(it.b) + radii(it).second }; y0 = -e * 1.35; y1 = e * 1.35 }
            else {
                val ys = arrayListOf(0.0, -extY, extY)
                for (c in curves) for (i in 0..120) fnY(c, x0 + (x1 - x0) * i / 120)?.let { if (it.isFinite() && abs(it) < 1e4) ys.add(it) }
                val lo = ys.min(); val hi = ys.max(); val pad = max((hi - lo) * 0.12, 0.5)
                y0 = max(lo - pad, -40.0); y1 = min(hi + pad, 40.0); if (y1 - y0 < 2) { y0 -= 1; y1 += 1 }
            }
        }
        if (round.isNotEmpty()) {
            val ratio = PW / PH; val xs = x1 - x0; val ysn = y1 - y0
            if (xs / ysn < ratio) { val m = (x0 + x1) / 2; val h = ysn * ratio / 2; x0 = m - h; x1 = m + h } else { val m = (y0 + y1) / 2; val h = xs / ratio / 2; y0 = m - h; y1 = m + h }
        }
        doubleArrayOf(x0, x1, y0, y1)
    }
    val (x0, x1, y0, y1) = rng.toList()
    fun sx(x: Double) = (PX + (x - x0) / (x1 - x0) * PW).toFloat()
    fun sy(y: Double) = (PY + PH - (y - y0) / (y1 - y0) * PH).toFloat()
    fun colour(k: Int) = PALETTE[k % PALETTE.size]
    fun label(k: Int) = s.items.getOrNull(k).orEmpty()
    val circle = curves.firstOrNull { it.type == "circle" }
    fun onCircle(deg: Double): Pair<Double, Double> { val t = Math.toRadians(deg); return (circle!!.a + circle.c * cos(t)) to (circle.b + circle.c * sin(t)) }

    Heading(s.heading, time, ORANGE)
    Canvas(Modifier.fillMaxSize()) {
        val gridIn = ease(time.value, 0f, 0.67f)
        drawRoundRect(Color.White.copy(alpha = gridIn), Offset(PX, PY), Size(PW, PH), CornerRadius(22f))
        drawRoundRect(LINE.copy(alpha = gridIn), Offset(PX, PY), Size(PW, PH), CornerRadius(22f), style = Stroke(3f))
        val xStep = niceStep(x1 - x0); val yStep = niceStep(y1 - y0, 6)
        val ax = min(max(0.0, x0), x1); val ay = min(max(0.0, y0), y1)
        clipRect(PX, PY, PX + PW, PY + PH) {
            var v = kotlin.math.ceil(x0 / xStep) * xStep; while (v <= x1 + 1e-9) { drawLine(GRID.copy(alpha = gridIn), Offset(sx(v), PY), Offset(sx(v), PY + PH), 2f); v += xStep }
            v = kotlin.math.ceil(y0 / yStep) * yStep; while (v <= y1 + 1e-9) { drawLine(GRID.copy(alpha = gridIn), Offset(PX, sy(v)), Offset(PX + PW, sy(v)), 2f); v += yStep }
            drawLine(INK.copy(alpha = gridIn), Offset(PX, sy(ay)), Offset(PX + PW, sy(ay)), 4f); drawLine(INK.copy(alpha = gridIn), Offset(sx(ax), PY), Offset(sx(ax), PY + PH), 4f)
        }
        val tick = TextStyle(color = MUTED.copy(alpha = gridIn), fontSize = 22.sp)
        var v = kotlin.math.ceil(x0 / xStep) * xStep; while (v <= x1 + 1e-9) { if (abs(v) > 1e-9) { val tl = measurer.measure(fmt(v), tick); drawText(tl, topLeft = Offset(sx(v) - tl.size.width / 2f, min(sy(ay) + 8f, PY + PH - 34f))) }; v += xStep }
        v = kotlin.math.ceil(y0 / yStep) * yStep; while (v <= y1 + 1e-9) { if (abs(v) > 1e-9) { val tl = measurer.measure(fmt(v), tick); drawText(tl, topLeft = Offset(max(sx(ax) - 10f - tl.size.width, PX + 8f), sy(v) - tl.size.height / 2f)) }; v += yStep }
        val axis = TextStyle(color = INK.copy(alpha = gridIn), fontSize = 28.sp, fontWeight = FontWeight.Bold)
        measurer.measure("x", axis).let { drawText(it, topLeft = Offset(PX + PW - 18f - it.size.width, sy(ay) - 12f - it.size.height)) }
        measurer.measure("y", axis).let { drawText(it, topLeft = Offset(sx(ax) + 14f, PY + 8f)) }

        clipRect(PX, PY, PX + PW, PY + PH) {
            curves.forEachIndexed { k, c ->
                val st = at(k.toFloat(), steps, speech)
                val path = Path()
                if (isRound(c)) { val (rx, ry) = radii(c); for (i in 0..120) { val t = i / 120.0 * PI * 2; val px = sx(c.a + rx * cos(t)); val py = sy(c.b + ry * sin(t)); if (i == 0) path.moveTo(px, py) else path.lineTo(px, py) } }
                else { var pen = false; var prev: Double? = null
                    for (i in 0..300) { val x = x0 + (x1 - x0) * i / 300; val y = fnY(c, x)
                        val bad = y == null || !y.isFinite() || y < y0 - (y1 - y0) || y > y1 + (y1 - y0) || (prev != null && abs(y - prev) > (y1 - y0) * 2)
                        if (bad) { pen = false; prev = null; continue }
                        if (pen) path.lineTo(sx(x), sy(y!!)) else path.moveTo(sx(x), sy(y!!)); pen = true; prev = y } }
                val dst = Path(); val m = PathMeasure().apply { setPath(path, false) }; m.getSegment(0f, m.length * ease(time.value, st, st + 1f), dst, true)
                drawPath(dst, colour(k), style = Stroke(8f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
        marks.forEachIndexed { i, m ->
            val k = curves.size + i; val st = at(k.toFloat(), steps, speech); val pr = ease(time.value, st, st + 0.6f); val col = colour(k)
            fun dot(px: Double, py: Double, r: Float = 9f) = drawCircle(col, r * pr, Offset(sx(px), sy(py)))
            fun seg(a: Pair<Double, Double>, b: Pair<Double, Double>) = drawLine(col, Offset(sx(a.first), sy(a.second)), Offset(sx(a.first + (b.first - a.first) * pr), sy(a.second + (b.second - a.second) * pr)), 6f, StrokeCap.Round)
            fun tag(px: Double, py: Double, dx: Float, dy: Float) {
                val text = label(k); if (text.isEmpty()) return
                val tl = measurer.measure(text, TextStyle(color = INK.copy(alpha = pr), fontSize = 30.sp, fontWeight = FontWeight.Bold))
                val w = tl.size.width + 24f
                val x = min(max(sx(px) + dx - 10f, PX + 8f), PX + PW - w - 8f); val y = min(max(sy(py) + dy - 34f, PY + 8f), PY + PH - 54f)
                drawRoundRect(Color.White.copy(alpha = pr), Offset(x, y), Size(w, 46f), CornerRadius(12f)); drawRoundRect(col.copy(alpha = pr), Offset(x, y), Size(w, 46f), CornerRadius(12f), style = Stroke(3f))
                drawText(tl, topLeft = Offset(x + 12f, y + 4f))
            }
            when (m.kind) {
                "link" -> { marks.take(i).lastOrNull { it.kind == "point" || it.kind == "link" }?.let { seg(it.x to it.y, m.x to m.y) }; dot(m.x, m.y); tag(m.x, m.y, 14f, -14f) }
                "point" -> { dot(m.x, m.y); tag(m.x, m.y, 14f, -14f) }
                else -> if (circle != null) { val c = circle.a to circle.b
                    when (m.kind) {
                        "center" -> { dot(c.first, c.second, 11f); tag(c.first, c.second, -190f, 70f) }
                        "radius" -> { val e = onCircle(35.0); seg(c, e); dot(e.first, e.second, 7f); tag((c.first + e.first) / 2, (c.second + e.second) / 2, 10f, -16f) }
                        "diameter" -> { val a = onCircle(155.0); val b = onCircle(335.0); seg(a, b); dot(a.first, a.second, 7f); dot(b.first, b.second, 7f); tag(b.first, b.second, 24f, 56f) }
                        "chord" -> { val a = onCircle(215.0); val b = onCircle(325.0); seg(a, b); dot(a.first, a.second, 7f); dot(b.first, b.second, 7f); tag(c.first, a.second, -40f, 48f) }
                        "tangent" -> { val t = onCircle(60.0); val dx = -sin(Math.toRadians(60.0)); val dy = cos(Math.toRadians(60.0)); val kk = circle.c * 0.7
                            seg((t.first - dx * kk) to (t.second - dy * kk), (t.first + dx * kk) to (t.second + dy * kk)); dot(t.first, t.second, 8f); tag(t.first, t.second, 18f, -16f) }
                    } }
            }
        }
    }
    if (s.equation.isNotBlank()) Box(Modifier.at(PANEL, PY).width((RIGHT - PANEL).dp).graphicsLayer { alpha = ease(time.value, 0.47f, 1.13f) }.clip(RoundedCornerShape(22.dp)).background(INK).padding(horizontal = 26.dp, vertical = 22.dp), contentAlignment = Alignment.Center) {
        Txt(s.equation, fit(s.equation, 54, 22, 0.5f), Color.White, 700, align = TextAlign.Center)
    }
    for (k in 0 until steps) {
        val text = label(k); if (text.isEmpty()) continue
        Row(Modifier.at(PANEL, PY + (if (s.equation.isNotBlank()) 120 else 0) + k * 96).width((RIGHT - PANEL).dp).anim(time, at(k.toFloat(), steps, speech), slideX = 40f)
            .shadow(4.dp, RoundedCornerShape(20.dp)).clip(RoundedCornerShape(20.dp)).background(Color.White).border(3.dp, colour(k), RoundedCornerShape(20.dp)).padding(horizontal = 22.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(18.dp)) {
            Box(Modifier.size(22.dp).clip(CircleShape).background(colour(k))); Txt(text, fit(text, 36, 20, 0.6f), INK, 700)
        }
    }
}

// ---------------------------------------------------------------- code

private val KEYWORDS = setOf("def", "class", "return", "if", "elif", "else", "for", "while", "in", "not", "and", "or", "import", "from", "as", "with", "try", "except", "finally", "raise", "lambda", "pass", "break", "continue",
    "None", "True", "False", "yield", "async", "await", "is", "fn", "let", "mut", "pub", "struct", "enum", "impl", "use", "match", "loop", "const", "var", "function", "new", "extends", "export", "default", "public", "private",
    "static", "void", "int", "long", "double", "float", "boolean", "String", "switch", "case", "do", "throw", "throws", "func", "package", "type", "interface", "map", "go", "defer", "range", "nil", "true", "false", "null",
    "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "JOIN", "AND", "OR", "NOT", "NULL", "LIMIT", "CREATE", "TABLE", "select", "from", "where", "print", "console")
private val C_KW = Color(0xFFC792EA); private val C_STR = Color(0xFF8BD5A0); private val C_NUM = Color(0xFFF5A97F); private val C_COM = Color(0xFF7F8AA8)
private val C_FN = Color(0xFF7DC4FF); private val C_TYPE = Color(0xFFF5CF7D); private val C_PUN = Color(0xFFAAB4CE); private val C_ID = Color(0xFFE8ECF5)

private fun highlight(line: String, lang: String): androidx.compose.ui.text.AnnotatedString = androidx.compose.ui.text.buildAnnotatedString {
    val com = when (lang) { "python", "py" -> "#.*"; "sql" -> "--.*"; else -> "//.*" }
    val re = Regex("($com)|(\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*')|(\\b\\d+(?:\\.\\d+)?\\b)|([A-Za-z_][A-Za-z0-9_]*)|(\\s+)|(.)")
    for (m in re.findAll(line)) {
        val t = m.value
        val (c, italic) = when {
            m.groups[1] != null -> C_COM to true; m.groups[2] != null -> C_STR to false; m.groups[3] != null -> C_NUM to false
            m.groups[4] != null -> (if (t in KEYWORDS) C_KW else if (line.substring(m.range.last + 1).trimStart().startsWith("(")) C_FN else if (t[0].isUpperCase()) C_TYPE else C_ID) to false
            m.groups[5] != null -> C_ID to false; else -> C_PUN to false
        }
        withStyle(androidx.compose.ui.text.SpanStyle(color = c, fontStyle = if (italic) androidx.compose.ui.text.font.FontStyle.Italic else null)) { append(t) }
    }
}

@Composable
private fun CodeScene(s: SceneT, speech: Float, time: State<Float>) {
    val code = s.code; val steps = s.highlights; val n = steps.size
    val lang = s.codeLang.lowercase()
    val fontSize = min(52, min(((1130 - 130) / (max(code.maxOfOrNull { it.length } ?: 16, 16) * 0.62f)).toInt(), ((610 - 110) / (max(code.size, 1) * 1.45f)).toInt()))
    val lineH = (fontSize * 1.45f)
    val active by remember { derivedStateOf { var a = -1; for (k in 0 until n) if (time.value >= at(k.toFloat(), n, speech)) a = k; a } }
    val activeLine = if (active >= 0) steps[active] else -1
    Heading(s.heading, time, TEAL)
    Column(Modifier.at(LEFT, 250f).size(1130.dp, 610.dp).anim(time, 0.13f, slideY = 30f).clip(RoundedCornerShape(26.dp)).background(Color(0xFF1B2338))) {
        Row(Modifier.fillMaxWidth().height(62.dp).background(Color(0xFF141B2E)).padding(horizontal = 24.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            listOf(Color(0xFFFF5F57), Color(0xFFFEBC2E), Color(0xFF28C840)).forEach { Box(Modifier.size(18.dp).clip(CircleShape).background(it)) }
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterEnd) { Txt(if (lang.isNotEmpty()) lang.uppercase() else "CODE", 24, Color(0xFF9AA6C4), 700) }
        }
        Column(Modifier.padding(vertical = 22.dp)) {
            code.forEachIndexed { i, line ->
                val on = i == activeLine
                Row(Modifier.fillMaxWidth().height(lineH.dp).graphicsLayer { alpha = ease(time.value, 0.27f + i * 0.1f, 0.67f + i * 0.1f) * (if (activeLine >= 0 && !on) 0.5f else 1f) }
                    .background(if (on) Color(0x33E98A2E) else Color.Transparent).drawBehind { if (on) drawRect(ORANGE, size = Size(8f, size.height)) }, verticalAlignment = Alignment.CenterVertically) {
                    Txt("${i + 1}", fontSize, Color(0xFF5F6B8A), 400, Modifier.width(70.dp).padding(end = 26.dp), TextAlign.End, mono = true, lh = 1f)
                    Text(highlight(line, lang), fontSize = fontSize.sp, fontFamily = FontFamily.Monospace, maxLines = 1, softWrap = false)
                }
            }
        }
    }
    val sideX = LEFT + 1130 + 40
    Column(Modifier.at(sideX, 250f).size((RIGHT - sideX).dp, 610.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
        if (s.items.isNotEmpty() && n > 0) {
            val k = max(active, 0); val text = s.items.getOrElse(min(k, s.items.size - 1)) { "" }
            Column(Modifier.fillMaxWidth().heightIn(min = 170.dp).anim(time, if (active >= 0) at(active.toFloat(), n, speech) else 0.4f, scaleFrom = 0.94f).clip(RoundedCornerShape(24.dp)).background(Color.White).border(3.dp, ORANGE, RoundedCornerShape(24.dp)).padding(horizontal = 30.dp, vertical = 26.dp)) {
                Txt(if (active >= 0) "Line ${steps[active] + 1}" else "", 26, ORANGE, 800, Modifier.padding(bottom = 10.dp))
                Txt(text, fit(text, 46, 22, 0.6f), INK, 700)
            }
        }
        if (s.output.isNotEmpty()) {
            val outAt = at(n.toFloat(), n + 1, speech)
            Box(Modifier.weight(1f))
            Column(Modifier.fillMaxWidth().graphicsLayer { alpha = ease(time.value, outAt, outAt + 0.47f) }.clip(RoundedCornerShape(24.dp)).background(Color(0xFF0F1526)).padding(horizontal = 26.dp, vertical = 20.dp)) {
                Txt("OUTPUT", 22, Color(0xFF9AA6C4), 800, Modifier.padding(bottom = 10.dp))
                s.output.forEach { Txt("> $it", 34, C_STR, 400, mono = true, lh = 1.2f) }
            }
        }
    }
}

// ---------------------------------------------------------------- the whole picture

/**
 * One scene of the lesson, animated. `time` is seconds since the scene began (driven by the audio and a frame clock), `speech` is how long
 * the narration lasts, so items appear as the narrator names them.
 */
@Composable
fun SceneArt(scene: SceneT, lessonTitle: String, time: State<Float>, speech: Float, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier.aspectRatio(16f / 9f).clip(RoundedCornerShape(24.dp)).background(BG)) {
        val k = constraints.maxWidth / W
        CompositionLocalProvider(LocalDensity provides Density(1f, 1f)) {
            Box(Modifier.requiredSize(1920.dp, 1080.dp).graphicsLayer { scaleX = k; scaleY = k; transformOrigin = TransformOrigin(0f, 0f) }) {
                when (scene.kind) {
                    "title" -> TitleScene(scene, lessonTitle, time)
                    "summary" -> ListScene(scene, speech, time, true)
                    "flow" -> FlowScene(scene, speech, time)
                    "cycle" -> CycleScene(scene, speech, time)
                    "compare" -> CompareScene(scene, speech, time)
                    "diagram" -> DiagramScene(scene, speech, time)
                    "quiz" -> QuizScene(scene, speech, time)
                    "graph" -> GraphScene(scene, speech, time)
                    "code" -> CodeScene(scene, speech, time)
                    else -> ListScene(scene, speech, time, false)
                }
            }
        }
    }
}
