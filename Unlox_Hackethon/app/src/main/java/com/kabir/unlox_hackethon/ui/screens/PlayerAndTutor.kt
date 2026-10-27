package com.kabir.unlox_hackethon.ui.screens

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

data class Scene(val title: String, val kind: String, val seconds: Int, val caption: String, val items: List<String> = emptyList())

private fun clock(s: Int) = "${s / 60}:${(s % 60).toString().padStart(2, '0')}"

/** 05 Lesson player: the scene on a coloured card with captions and controls, language tabs, the scene list, and the tutor. */
@Composable
fun PlayerScreen(
    title: String, scene: Int, onScene: (Int) -> Unit, playing: Boolean, onPlaying: (Boolean) -> Unit, elapsed: Int,
    language: Int, onLanguage: (Int) -> Unit, onBack: () -> Unit, onAskTutor: (Offset) -> Unit, onStudy: () -> Unit,
    scenes: List<Scene>, languages: List<String>, episodes: Int = 1, episode: Int = 0, onEpisode: (Int) -> Unit = {},
) {
    val total = scenes.sumOf { it.seconds }
    val current = scenes[scene]
    val ask = remember { mutableStateOf(Offset.Zero) }
    var captions by remember { mutableStateOf(com.kabir.unlox_hackethon.data.Graph.profile.captions) }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(top = 12.dp)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                IconBtn(R.drawable.ic_arrow_left, "Back", onClick = onBack)
                IconBtn(R.drawable.ic_download, "Save as video") {}
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = T.Headline, color = U.TextPrimary, maxLines = 2)
                Text("${scenes.size} scenes · $total s", style = T.Sub, color = U.TextTertiary, maxLines = 1)
            }
            if (episodes > 1) Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                repeat(episodes) { Chip("Part ${it + 1}", selected = it == episode) { onEpisode(it) } }
            }
            PlayerCard(current, scene, playing, onPlaying, elapsed, total, captions) { captions = !captions }
            if (languages.size > 1) Segmented(languages, language, onLanguage)
            SectionHeader("Scenes", trailing = "${scene + 1} of ${scenes.size}")
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                scenes.forEachIndexed { i, s ->
                    LessonRow(s.title, "Scene ${i + 1} · ${s.kind}", clock(s.seconds), active = i == scene, playing = playing) { onScene(i) }
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
                Text("Ask the tutor", style = T.Chip.copy(letterSpacing = T.Chip.letterSpacing), color = U.TextPrimary)
            }
            IconBtn(R.drawable.ic_layers, "Study tools", onClick = onStudy)
            IconBtn(R.drawable.ic_captions, if (captions) "Captions on" else "Captions off", off = !captions) { captions = !captions }
        }
    }
}

@Composable
private fun PlayerCard(scene: Scene, index: Int, playing: Boolean, onPlaying: (Boolean) -> Unit, elapsed: Int, total: Int, captions: Boolean, onCaptions: () -> Unit) {
    Box(Modifier.fillMaxWidth().height(280.dp).clip(RoundedCornerShape(36.dp)).background(U.Cobalt)) {
        // quiet concentric rings, the same as the artwork in the design, without tying every lesson to one picture
        Canvas(Modifier.fillMaxSize()) {
            for (i in 0 until 6) drawCircle(Color.White.copy(alpha = 0.07f), (160 - i * 24).dp.toPx(), Offset(size.width, size.height * 0.55f), style = Stroke(12.dp.toPx()))
        }
        Text(scene.title, Modifier.offset(20.dp, 20.dp).fillMaxWidth(0.9f), style = T.Title, color = U.TextPrimary, maxLines = 2)
        Text("Scene ${index + 1} · ${scene.kind.replaceFirstChar { it.uppercase() }}", Modifier.offset(20.dp, 74.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.22f)).padding(horizontal = 10.dp, vertical = 6.dp),
            style = T.Caption, color = U.TextPrimary, maxLines = 1)
        Column(Modifier.offset(20.dp, 112.dp).fillMaxWidth(0.85f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            scene.items.take(3).forEach { Text("•  $it", style = T.Sub, color = U.TextPrimary.copy(alpha = 0.9f), maxLines = 1) }
        }
        if (captions) Text(scene.caption, Modifier.offset(20.dp, 168.dp).fillMaxWidth(0.9f).clip(RoundedCornerShape(12.dp)).background(Color.Black.copy(alpha = 0.55f)).padding(horizontal = 12.dp, vertical = 6.dp),
            style = T.Sub.copy(color = U.TextPrimary), color = U.TextPrimary, maxLines = 2)
        Row(
            Modifier.offset(12.dp, 224.dp).fillMaxWidth().padding(end = 24.dp).height(52.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.55f)).padding(start = 6.dp, end = 14.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            IconBtn(if (playing) R.drawable.ic_pause else R.drawable.ic_play, if (playing) "Pause" else "Play", bg = U.Inverse, size = 40.dp, iconSize = 24.dp) { onPlaying(!playing) }
            Box(Modifier.weight(1f).height(4.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.25f))) {
                Box(Modifier.fillMaxWidth((elapsed.toFloat() / total.coerceAtLeast(1)).coerceIn(0f, 1f)).fillMaxHeight().clip(CircleShape).background(Color.White))
            }
            Text("${clock(elapsed)} / ${clock(total)}", style = T.Caption, color = U.TextPrimary, maxLines = 1)
            Box(Modifier.size(28.dp).clip(CircleShape).clickable(onClickLabel = "Captions", onClick = onCaptions).drawWithContent { drawContent(); if (!captions) slash(U.TextPrimary) }, contentAlignment = Alignment.Center) {
                Glyph(R.drawable.ic_captions, Modifier.alpha(if (captions) 1f else 0.45f), U.TextPrimary, 20.dp, if (captions) "Captions on" else "Captions off")
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
