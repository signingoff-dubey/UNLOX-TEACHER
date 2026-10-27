package com.kabir.unlox_hackethon.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.data.Graph
import com.kabir.unlox_hackethon.data.LANGS
import com.kabir.unlox_hackethon.data.LessonMeta
import com.kabir.unlox_hackethon.ui.components.Chip
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.IconWell
import com.kabir.unlox_hackethon.ui.components.LessonRow
import com.kabir.unlox_hackethon.ui.components.MetricTile
import com.kabir.unlox_hackethon.ui.components.SectionHeader
import com.kabir.unlox_hackethon.ui.components.Segmented
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import java.time.LocalDate

private val WD = listOf("M", "T", "W", "T", "F", "S", "S")

/** 07 Progress: streak heatmap, totals, and XP per day, all from what the learner actually did on this phone. */
@Composable
fun ProgressScreen(bottomInset: Dp, onSettings: () -> Unit) {
    val rewards = Graph.rewards
    rewards.version                                              // read, so the screen updates when XP is earned
    var range by rememberSaveable { mutableIntStateOf(0) }
    val heat = rewards.history(90)
    val days = listOf(7, 28, 364)[range]
    val window = rewards.history(days)
    val buckets = window.chunked(days / 7)
    val bars = buckets.map { it.sumOf { d -> d.xp } }
    val labels = buckets.map { b -> if (range == 0) WD[LocalDate.parse(b.last().day).dayOfWeek.value - 1] else LocalDate.parse(b.last().day).let { "${it.dayOfMonth}/${it.monthValue}" } }
    val top = bars.indices.maxByOrNull { bars[it] } ?: 0
    val maxBar = (bars.maxOrNull() ?: 0).coerceAtLeast(1)
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = bottomInset),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Your progress", style = T.Display, color = U.TextPrimary, modifier = Modifier.weight(1f))
            IconBtn(R.drawable.ic_settings, "Settings", onClick = onSettings)
        }
        Segmented(listOf("Week", "Month", "Year"), range, { range = it })
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                IconWell(R.drawable.ic_flame, U.Rust, 44.dp, 20.dp)
                Column {
                    Text(if (rewards.streak == 1) "1-day streak" else "${rewards.streak}-day streak", style = T.Title, color = U.TextPrimary)
                    Text("${rewards.lessonsMade} lessons made · best ${rewards.bestStreak} days", style = T.Sub, color = U.TextTertiary, maxLines = 1)
                }
            }
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                heat.chunked(5).forEach { col ->
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        col.forEach { d ->
                            val tone = when { d.xp >= 50 -> U.Accent; d.xp >= 20 -> U.Sage; d.xp > 0 -> U.GlassStrong; else -> U.Glass }
                            Box(Modifier.size(14.dp).clip(RoundedCornerShape(4.dp)).background(tone))
                        }
                    }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MetricTile("Lessons", "${rewards.lessonsMade}", "made", U.Sage, Modifier.weight(1f), 100.dp)
            MetricTile("Right answers", "${rewards.quizRight}", "in quizzes", U.Orchid, Modifier.weight(1f), 100.dp)
        }
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Rust).padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("XP per ${if (range == 0) "day" else if (range == 1) "4 days" else "52 days"}", style = T.Title, color = U.TextPrimary, modifier = Modifier.weight(1f))
                Text("${window.sumOf { it.xp }} XP", style = T.Caption, color = U.TextPrimary)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Bottom) {
                bars.forEachIndexed { i, v ->
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Box(Modifier.width(18.dp).height((6 + 64f * v / maxBar).dp).clip(RoundedCornerShape(9.dp)).background(if (i == top && v > 0) U.Inverse else Color.White.copy(alpha = 0.45f)))
                        Text(labels[i], style = T.Caption, color = U.TextPrimary, maxLines = 1)
                    }
                }
            }
        }
    }
}

private fun ago(t: Long): String {
    val m = (System.currentTimeMillis() - t) / 60000
    return when { m < 1 -> "just now"; m < 60 -> "$m min ago"; m < 1440 -> "${m / 60} h ago"; m < 2880 -> "yesterday"; else -> "${m / 1440} days ago" }
}

/** 08 Library: search, filters, and every lesson made on this phone. */
@Composable
fun LibraryScreen(lessons: List<LessonMeta>, bottomInset: Dp, onOpenLesson: (String) -> Unit, onDelete: (String) -> Unit, onAdd: () -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableIntStateOf(0) }
    val filters = listOf("All", "Lessons", "My PDFs")
    val shown = if (filter == 2) emptyList() else lessons.filter { it.title.contains(query, ignoreCase = true) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = bottomInset),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Library", style = T.Display, color = U.TextPrimary, modifier = Modifier.weight(1f))
            IconBtn(R.drawable.ic_plus, "New lesson", bg = U.Inverse, onClick = onAdd)
        }
        Row(
            Modifier.fillMaxWidth().clip(CircleShape).background(U.Surface).border(1.dp, U.BorderGlass, CircleShape).padding(start = 20.dp, top = 14.dp, end = 20.dp, bottom = 14.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Glyph(R.drawable.ic_search, tint = U.TextTertiary, size = 20.dp)
            Box(Modifier.weight(1f)) {
                if (query.isEmpty()) Text("Search lessons and PDFs", style = T.Input, color = U.TextTertiary, maxLines = 1)
                BasicTextField(query, { query = it }, singleLine = true, textStyle = T.Input.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary), modifier = Modifier.fillMaxWidth())
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            filters.forEachIndexed { i, f -> Chip(f, selected = i == filter) { filter = i } }
        }
        if (shown.isNotEmpty()) {
            SectionHeader("Recent lessons", trailing = "${shown.size}")
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                shown.forEach { l ->
                    val names = l.languages.joinToString(" · ") { c -> LANGS.first { it.code == c }.name }
                    LessonRow(l.title, "$names · ${ago(l.created)}", "${l.seconds} s") { onOpenLesson(l.id) }
                }
            }
        } else {
            Text(
                when { filter == 2 -> "PDFs you add will show here."; lessons.isEmpty() -> "No lessons yet. Tap + to make your first one."; else -> "Nothing matches. Try another word." },
                style = T.Body, color = U.TextTertiary,
            )
        }
    }
}
