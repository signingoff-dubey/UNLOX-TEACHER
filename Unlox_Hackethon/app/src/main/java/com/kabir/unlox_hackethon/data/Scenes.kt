package com.kabir.unlox_hackethon.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** The ten templates a scene can use; the renderer draws each one. Same set as the website. */
val TEMPLATES = setOf("title", "bullets", "flow", "cycle", "compare", "diagram", "quiz", "summary", "graph", "code")
val ICONS = setOf("lightbulb", "sun", "leaf", "water", "atom", "cell", "heart", "brain", "earth", "bolt", "gear", "book", "flask", "cloud", "magnet", "rocket")
private val CURVES = setOf("line", "parabola", "cubic", "sine", "cosine", "exp", "abs", "sqrt", "reciprocal", "circle", "ellipse")
private val MARKS = setOf("center", "radius", "diameter", "chord", "tangent", "point", "link")

/** What Gemma returns for one scene (JSON, data only). Names match the website's plan so one description of the format serves both. */
@Serializable
class PlanScene(
    val template: String = "bullets", val heading: String = "", val narration: String = "", val items: List<String> = emptyList(), val icon: String = "lightbulb",
    @SerialName("left_title") val leftTitle: String = "", @SerialName("right_title") val rightTitle: String = "",
    val left: List<String> = emptyList(), val right: List<String> = emptyList(), @SerialName("answer_index") val answerIndex: Int = 0,
    val curves: List<CurveT> = emptyList(), val marks: List<MarkT> = emptyList(),
    @SerialName("x_range") val xRange: List<Double> = emptyList(), @SerialName("y_range") val yRange: List<Double> = emptyList(), val equation: String = "",
    @SerialName("code_lang") val codeLang: String = "", val code: List<String> = emptyList(), val highlights: List<Int> = emptyList(), val output: List<String> = emptyList(),
)

@Serializable
class PlanDoc(val title: String = "", val scenes: List<PlanScene> = emptyList())

/** The topic's field, used to steer the planner toward pictures that fit: graphs for maths, code for programming. */
fun domainOf(text: String): String {
    val code = Regex("\\b(python|rust|react|javascript|typescript|java|golang|sql|html|css|c\\+\\+|c#|kotlin|swift|code|coding|programming|loop|function|algorithm|variable|array|class|api|git|linux|bash|regex)\\b", RegexOption.IGNORE_CASE)
    val maths = Regex("\\b(graph|circle|parabola|coordinate|geometry|equation|function|trigonometr|sine|cosine|algebra|angle|triangle|quadratic|linear|slope|line|vector|calculus|derivative|integral|plot|curve|ellipse|exponential|logarithm|polynomial|matrix|maths?|mathematics|physics|projectile|wave)\\w*", RegexOption.IGNORE_CASE)
    return when {
        code.containsMatchIn(text) && !Regex("\\b(graph|coordinate|circle|parabola)\\b", RegexOption.IGNORE_CASE).containsMatchIn(text) -> "code"
        maths.containsMatchIn(text) -> "maths"
        else -> "general"
    }
}

/** The format Gemma is asked for, with what each template needs. */
const val TEMPLATE_GUIDE = """Templates (pick the one that SHOWS the idea):
- title: heading only, with an icon. Use for the first scene.
- graph: plot on x/y axes. curves (1-3), each {"type": line|parabola|cubic|sine|cosine|exp|abs|sqrt|reciprocal|circle|ellipse, "a":..,"b":..,"c":..,"d":..}:
  line y=a*x+b | parabola y=a*x^2+b*x+c | sine y=a*sin(b*x+c)+d | circle centre (a,b) radius c | ellipse centre (a,b) semi-axes c,d.
  marks: {"kind":"point","x":2,"y":3} plots a dot; {"kind":"link","x":4,"y":1} draws a segment from the previous point to this one.
  equation: the formula beside it. items: one short label per curve, then one per mark, in that order.
- code: code_lang, code (3-10 lines under 45 chars), highlights (0-based line numbers in narration order), items (one note per highlight), output (optional).
- flow: items = 3-5 ordered steps.   - cycle: items = 3-5 stages that repeat.
- diagram: heading = the central thing, items = 3-5 labelled parts around it.
- compare: left_title, left (2-4), right_title, right (2-4).
- quiz: heading = the question, items = 3 options, answer_index (0-based).
- summary: items = 3-4 key takeaways.   - bullets: items = 2-5 key points (only when nothing visual fits).
Every scene also has: heading (at most 6 words), narration (what the teacher says, about 22 words, plain sentences), icon (one of lightbulb sun leaf water atom cell heart brain earth bolt gear book flask cloud magnet rocket), and items as short labels (at most 5 words each)."""

/** TEMPLATE_GUIDE without the graph or code templates when the topic cannot use them: a shorter prompt is read sooner, so the first scene comes sooner. */
fun templateGuide(domain: String): String {
    val out = ArrayList<String>()
    var skipping = false
    for (line in TEMPLATE_GUIDE.lines()) {
        if (line.startsWith("- ")) skipping = (line.startsWith("- graph:") && domain != "maths") || (line.startsWith("- code:") && domain != "code")
        else if (!line.startsWith(" ")) skipping = false                       // a line that continues the last template stays with it; anything else is shared
        if (!skipping) out.add(line)
    }
    return out.joinToString("\n")
}

private fun finite(vararg v: Double) = v.all { it.isFinite() && kotlin.math.abs(it) < 1e6 }

private fun pointsFrom(narration: String, limit: Int = 4): List<String> =
    narration.trim().split(Regex("(?<=[.!?।])\\s+")).mapNotNull { sentence ->
        val words = sentence.trim(' ', '.', '!', '?', '।', ',', ';', ':').split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.size >= 2) words.take(5).joinToString(" ") + if (words.size > 5) "…" else "" else null
    }.take(limit)

private val MIN_ITEMS = mapOf("bullets" to 2, "flow" to 2, "cycle" to 3, "diagram" to 2, "quiz" to 2, "summary" to 2)

/** Repairs the small mistakes a small model makes, so the renderer never sees bad data (the website's `normalize`). */
fun normalizePlan(doc: PlanDoc): Pair<String, List<SceneT>> {
    val out = ArrayList<SceneT>()
    for (p in doc.scenes.take(24)) {
        val narration = p.narration.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        if (narration.isBlank()) continue
        var kind = p.template.lowercase().takeIf { it in TEMPLATES } ?: "bullets"
        var items = p.items.map { it.trim() }.filter { it.isNotEmpty() }.take(6)
        var left = p.left.map { it.trim() }.filter { it.isNotEmpty() }.take(4)
        var right = p.right.map { it.trim() }.filter { it.isNotEmpty() }.take(4)
        val heading = p.heading.trim().ifBlank { doc.title }
        var curves = p.curves.filter { it.type in CURVES && finite(it.a, it.b, it.c, it.d) }.filter { !(it.type == "circle" && it.c <= 0) && !(it.type == "ellipse" && (it.c <= 0 || it.d <= 0)) }.take(3)
        val hasCircle = curves.any { it.type == "circle" }
        var marks = p.marks.filter { it.kind in MARKS && finite(it.x, it.y) && (hasCircle || it.kind == "point" || it.kind == "link") }.take(6)
        var xr = p.xRange.take(2).let { if (it.size == 2 && finite(it[0], it[1]) && it[0] != it[1]) it.sorted() else emptyList() }
        var yr = p.yRange.take(2).let { if (it.size == 2 && finite(it[0], it[1]) && it[0] != it[1]) it.sorted() else emptyList() }
        var code = p.code.map { it.trimEnd().replace("\t", "    ").take(72) }.filter { it.isNotBlank() }.take(11)
        var output = p.output.map { it.trimEnd().take(72) }.filter { it.isNotBlank() }.take(3)
        var highlights = p.highlights.filter { it in code.indices }.take(6)
        var equation = p.equation.trim().take(60)

        if (kind == "graph" && curves.isEmpty() && marks.none { it.kind == "point" }) kind = if (items.size >= 2) "bullets" else "title"
        if (kind == "graph") {
            val names = curves.map { c -> mapOf("line" to "Line", "parabola" to "Parabola", "cubic" to "Cubic curve", "sine" to "Sine wave", "cosine" to "Cosine wave", "exp" to "Exponential curve", "abs" to "Absolute value", "sqrt" to "Square root", "reciprocal" to "Reciprocal", "circle" to "Circle", "ellipse" to "Ellipse")[c.type] ?: "Curve" } +
                marks.map { m -> if (m.kind == "point") "Point (${"%g".format(m.x)}, ${"%g".format(m.y)})" else m.kind.replaceFirstChar { it.uppercase() } }
            items = items.take(names.size) + names.drop(items.size)
        } else { curves = emptyList(); marks = emptyList(); xr = emptyList(); yr = emptyList(); equation = "" }
        if (kind == "code" && code.isEmpty()) kind = if (items.size >= 2) "bullets" else "title"
        if (kind == "code") {
            if (highlights.isEmpty()) highlights = (0 until minOf(code.size, 6)).toList()
            items = items.take(highlights.size) + highlights.drop(items.size).map { "Line ${it + 1}" }
        } else { code = emptyList(); output = emptyList(); highlights = emptyList() }
        if (kind == "quiz") items = items.filter { !it.all(Char::isDigit) }
        if (kind == "compare" && !(left.isNotEmpty() && right.isNotEmpty())) kind = if (items.size >= 2) "bullets" else "title"
        if (items.size < (MIN_ITEMS[kind] ?: 0)) {
            val points = pointsFrom(narration)
            if (points.size >= 2) { items = points.take(5); if (kind !in setOf("bullets", "flow", "cycle", "diagram", "summary")) kind = "bullets" } else kind = "title"
        }
        val answer = if (kind == "quiz") p.answerIndex.coerceIn(0, (items.size - 1).coerceAtLeast(0)) else 0
        out.add(SceneT(kind, heading, items, narration, icon = p.icon.takeIf { it in ICONS } ?: "lightbulb", leftTitle = p.leftTitle.trim(), rightTitle = p.rightTitle.trim(),
            left = left, right = right, answerIndex = answer, curves = curves, marks = marks, xRange = xr, yRange = yr, equation = equation,
            codeLang = p.codeLang.trim().lowercase().take(12), code = code, highlights = highlights, output = output))
    }
    require(out.isNotEmpty()) { "The tutor could not plan that lesson." }
    if (out[0].kind != "title") out.add(0, SceneT("title", doc.title, emptyList(), "Let's learn about ${doc.title}.", icon = out[0].icon))
    return doc.title to out
}

/** Every string of a scene a viewer sees or hears, in a fixed order: these are what gets translated. */
fun SceneT.texts(): List<String> = listOf(heading, narration, leftTitle, rightTitle) + items + left + right

/** The scene with its texts replaced, taken one by one from `next` in the order [texts] lists them. */
fun SceneT.withTexts(next: () -> String): SceneT {
    val h = next(); val n = next(); val lt = next(); val rt = next()
    return copy(heading = h, narration = n, leftTitle = lt, rightTitle = rt, items = items.map { next() }, left = left.map { next() }, right = right.map { next() })
}
