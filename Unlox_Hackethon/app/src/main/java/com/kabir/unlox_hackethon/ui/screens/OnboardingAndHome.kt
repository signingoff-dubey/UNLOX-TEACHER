package com.kabir.unlox_hackethon.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.ui.components.Chip
import com.kabir.unlox_hackethon.ui.components.Glyph
import com.kabir.unlox_hackethon.ui.components.IconBtn
import com.kabir.unlox_hackethon.ui.components.IconWell
import com.kabir.unlox_hackethon.ui.components.MetricTile
import com.kabir.unlox_hackethon.ui.components.ProgressTrack
import com.kabir.unlox_hackethon.ui.components.SwipePill
import com.kabir.unlox_hackethon.ui.components.Wordmark
import com.kabir.unlox_hackethon.ui.components.rippleOrigin
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U

/** 01 Onboarding: three tilted lesson cards, the promise, and a swipe to begin. */
@Composable
fun OnboardingScreen(onStart: () -> Unit, onLanguage: () -> Unit) {
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.clip(RoundedCornerShape(12.dp)).background(Color(0xFFF6F6F6)).padding(8.dp)) {
                androidx.compose.foundation.Image(androidx.compose.ui.res.painterResource(R.drawable.ic_logo_book), "Chanakya logo", Modifier.size(width = 28.dp, height = 32.dp))
            }
            Wordmark(Modifier.height(18.dp))
        }
        Box(Modifier.fillMaxWidth().height(320.dp)) {
            SceneCard("Photosynthesis", "Flow · 6 scenes", U.Sage, R.drawable.ic_sparkles, 7f, cx = 117, cy = 129)
            SceneCard("The water cycle", "Cycle · 5 scenes", U.Cobalt, R.drawable.ic_globe, -6f, cx = 238, cy = 82)
            SceneCard("How a rainbow forms", "Diagram · 6 scenes", U.Accent, R.drawable.ic_layers, 2f, cx = 161, cy = 209)
            Row(
                Modifier.offset(196.dp, 262.dp).clip(CircleShape).background(U.Raised).padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(U.Live))
                Text("Narrating in Hindi", style = T.Caption.copy(fontSize = T.Caption.fontSize), color = U.TextPrimary, maxLines = 1)
            }
        }
        Spacer(Modifier.weight(1f))
        Text("Learn\nanything,\nvisually.", style = T.Hero, color = U.TextPrimary)
        Spacer(Modifier.height(16.dp))
        Text("Type a concept or drop in your textbook. Get a narrated, animated lesson in your language — even offline.",
            style = T.Input.copy(lineHeight = T.Input.fontSize * 1.45f), color = U.TextSecondary)
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.width(22.dp).height(4.dp).clip(CircleShape).background(U.Inverse))
            Box(Modifier.width(8.dp).height(4.dp).clip(CircleShape).background(U.IndicatorOff))
            Box(Modifier.width(8.dp).height(4.dp).clip(CircleShape).background(U.IndicatorOff))
        }
        Spacer(Modifier.height(16.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            IconBtn(R.drawable.ic_globe, "Choose language", bg = U.Glass, onClick = onLanguage)
            SwipePill("Swipe to get started", R.drawable.ic_sparkles, U.BorderGlass, Modifier.weight(1f), onStart)
        }
    }
}

@Composable
private fun SceneCard(title: String, sub: String, bg: Color, icon: Int, tilt: Float, cx: Int, cy: Int) {
    Column(
        Modifier.offset((cx - 120).dp, (cy - 85).dp).rotate(tilt).size(240.dp, 170.dp)
            .shadow(24.dp, RoundedCornerShape(28.dp), ambientColor = Color.Black, spotColor = Color.Black)
            .clip(RoundedCornerShape(28.dp)).background(bg).padding(18.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, style = T.Title, color = U.TextPrimary, maxLines = 1, overflow = TextOverflow.Clip)
            Text(sub, style = T.Sub, color = U.TextPrimary.copy(alpha = 0.75f), maxLines = 1)
        }
        IconWell(icon, Color.White.copy(alpha = 0.22f), 44.dp, 20.dp)
    }
}

/** The six rainbow rings, centred at (cx, cy) in dp, outermost first. */
fun androidx.compose.ui.graphics.drawscope.DrawScope.rainbow(cx: Float, cy: Float, outer: Float, step: Float, stroke: Float) {
    U.Rainbow.forEachIndexed { i, c ->
        val r = (outer - i * step).dp.toPx()
        drawCircle(c.copy(alpha = 0.9f), r, Offset(cx.dp.toPx(), cy.dp.toPx()), style = Stroke(stroke.dp.toPx()))
    }
}

/** 02 Home: ask for any concept (typed or spoken), pick up where you stopped, today's numbers. */
@Composable
fun HomeScreen(last: com.kabir.unlox_hackethon.data.LessonMeta?, onAsk: (String) -> Unit, onVoice: (Offset) -> Unit, onContinue: () -> Unit, onProfile: () -> Unit, bottomInset: androidx.compose.ui.unit.Dp) {
    val profile = com.kabir.unlox_hackethon.data.Graph.profile
    val rewards = com.kabir.unlox_hackethon.data.Graph.rewards
    rewards.version
    var concept by remember { mutableStateOf("") }
    val mic = remember { mutableStateOf(Offset.Zero) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = bottomInset),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.weight(1f)) { Wordmark(Modifier.height(22.dp)) }
            IconBtn(R.drawable.ic_bell, "Notifications") {}
            IconBtn(R.drawable.ic_user, "Profile", onClick = onProfile)
        }
        Text("What do you want\nto learn today?", style = T.Display, color = U.TextPrimary)
        Row(
            Modifier.fillMaxWidth().clip(CircleShape).background(U.Surface).border(1.dp, U.BorderGlass, CircleShape)
                .padding(start = 20.dp, top = 6.dp, end = 6.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Glyph(R.drawable.ic_search, tint = U.TextTertiary, size = 20.dp)
            Box(Modifier.weight(1f)) {
                if (concept.isEmpty()) Text("Type a concept, e.g. tides", style = T.Input, color = U.TextTertiary, maxLines = 1)
                BasicTextField(
                    concept, { concept = it }, singleLine = true, textStyle = T.Input.copy(color = U.TextPrimary), cursorBrush = SolidColor(U.TextPrimary),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go), keyboardActions = KeyboardActions(onGo = { if (concept.isNotBlank()) onAsk(concept.trim()) }),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            IconBtn(R.drawable.ic_mic, "Ask by voice", Modifier.rippleOrigin(mic), bg = U.Inverse) { onVoice(mic.value) }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Photosynthesis", "Newton's third law", "Fractions", "Tides", "Vaccines").forEach { Chip(it) { onAsk(it) } }
        }
        if (profile.name.isBlank() || profile.age == 0) Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(U.Surface).clickable(onClick = onProfile).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(Modifier.weight(1f)) { Text("Tell Chanakya about you", style = T.Body, color = U.TextPrimary); Text("Add your name and age so lessons suit you.", style = T.Sub, color = U.TextTertiary) }
            Glyph(R.drawable.ic_chevron_right, tint = U.TextTertiary, size = 20.dp)
        }
        if (last != null) ContinueCard(last, onContinue)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MetricTile("Streak", "${rewards.streak}", if (rewards.streak == 1) "day" else "days", U.Sage, Modifier.weight(1f))
            MetricTile("Lessons", "${rewards.lessonsMade}", "made", U.Cobalt, Modifier.weight(1f))
        }
    }
}

@Composable
private fun ContinueCard(last: com.kabir.unlox_hackethon.data.LessonMeta, onContinue: () -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(36.dp)).background(U.Surface).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Continue", style = T.Title, color = U.TextPrimary, modifier = Modifier.weight(1f))
            Chip(com.kabir.unlox_hackethon.data.LANGS.first { it.code == last.languages.last() }.name, selected = true)
        }
        Box(Modifier.fillMaxWidth().height(104.dp).clip(RoundedCornerShape(28.dp)).background(U.Raised)) {
            Canvas(Modifier.fillMaxSize()) { rainbow(cx = 240f, cy = 190f, outer = 144f, step = 14f, stroke = 12f) }
            IconBtn(R.drawable.ic_play, "Open the lesson", Modifier.padding(start = 16.dp, top = 28.dp), bg = U.Inverse, onClick = onContinue)
        }
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(last.title, style = T.Body, color = U.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${last.languages.size} language${if (last.languages.size == 1) "" else "s"} · ${last.seconds} s", style = T.Sub, color = U.TextTertiary, maxLines = 1)
        }
    }
}
