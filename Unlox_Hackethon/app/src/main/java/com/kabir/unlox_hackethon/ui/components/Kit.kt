package com.kabir.unlox_hackethon.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.kabir.unlox_hackethon.R
import com.kabir.unlox_hackethon.ui.theme.T
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@Composable
fun Glyph(@DrawableRes id: Int, modifier: Modifier = Modifier, tint: Color = U.TextPrimary, size: Dp = 24.dp, description: String? = null) {
    Icon(painterResource(id), description, modifier.size(size), tint)
}

/** Presses shrink a little, so every tap target answers right away. */
fun Modifier.pressScale(source: MutableInteractionSource, to: Float = 0.94f): Modifier = composed {
    val pressed by source.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) to else 1f, spring(Spring.DampingRatioMediumBouncy, Spring.StiffnessMedium), label = "press")
    graphicsLayer { scaleX = scale; scaleY = scale }
}

fun Modifier.tap(source: MutableInteractionSource, label: String?, onClick: () -> Unit): Modifier =
    clickable(interactionSource = source, indication = null, role = Role.Button, onClickLabel = label, onClick = onClick)

/** Circular 48 dp icon button. White = primary, raised = secondary, glass over imagery. */
@Composable
fun IconBtn(
    @DrawableRes icon: Int, description: String, modifier: Modifier = Modifier,
    bg: Color = U.Raised, tint: Color = if (bg == U.Inverse) U.OnInverse else U.TextPrimary,
    size: Dp = 48.dp, iconSize: Dp = 24.dp, iconRotation: Float = 0f, off: Boolean = false, onClick: () -> Unit,
) {
    val src = remember { MutableInteractionSource() }
    Box(
        modifier.size(size).pressScale(src).clip(CircleShape).background(if (off) U.Glass else bg).tap(src, description, onClick)
            .drawWithContent { drawContent(); if (off) slash(tint) },
        contentAlignment = Alignment.Center,
    ) { Glyph(icon, Modifier.rotate(iconRotation).alpha(if (off) 0.45f else 1f), tint, iconSize, description) }
}

/** A diagonal cut across a button: it is switched off. */
fun androidx.compose.ui.graphics.drawscope.DrawScope.slash(color: Color) {
    val m = size.minDimension
    drawLine(color.copy(alpha = 0.9f), androidx.compose.ui.geometry.Offset(size.width / 2 - m * 0.22f, size.height / 2 - m * 0.22f),
        androidx.compose.ui.geometry.Offset(size.width / 2 + m * 0.22f, size.height / 2 + m * 0.22f), 2.5.dp.toPx(), androidx.compose.ui.graphics.StrokeCap.Round)
}

@Composable
fun Chip(text: String, selected: Boolean = false, modifier: Modifier = Modifier, onClick: () -> Unit = {}) {
    val src = remember { MutableInteractionSource() }
    Box(
        modifier.pressScale(src).clip(CircleShape).background(if (selected) U.Inverse else U.Raised)
            .clickable(src, null, role = Role.Button, onClick = onClick).semantics { this.selected = selected }
            .padding(horizontal = 16.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = T.Chip, color = if (selected) U.OnInverse else U.TextPrimary, maxLines = 1) }
}

/** Three-way (or more) segmented control: the picked option sits on a raised pill with a glass edge. */
@Composable
fun Segmented(options: List<String>, selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(14.dp)
    Row(modifier.fillMaxWidth().height(52.dp).clip(shape).background(U.Bar).padding(5.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        options.forEachIndexed { i, label ->
            val on = i == selected
            Box(
                Modifier.weight(1f).fillMaxHeight().clip(CircleShape)
                    .then(if (on) Modifier.background(U.Raised).border(1.dp, U.BorderGlass, CircleShape) else Modifier)
                    .clickable(role = Role.Tab) { onSelect(i) }.semantics { this.selected = on },
                contentAlignment = Alignment.Center,
            ) { Text(label, style = T.Chip, color = if (on) U.TextPrimary else U.TextTertiary, maxLines = 1) }
        }
    }
}

/** Primary call to action: drag the knob across to confirm. A tap through TalkBack or a switch does the same. */
@Composable
fun SwipePill(text: String, @DrawableRes icon: Int, bg: Color, modifier: Modifier = Modifier, onDone: () -> Unit) {
    val knob = 52.dp
    val pad = 6.dp
    val scope = rememberCoroutineScope()
    val x = remember { Animatable(0f) }
    BoxWithConstraints(
        modifier.fillMaxWidth().height(64.dp).clip(CircleShape).background(bg)
            .semantics { contentDescription = text; role = Role.Button; onClick(label = text) { onDone(); true } },
    ) {
        val max = with(LocalDensity.current) { (maxWidth - knob - pad * 2).toPx() }
        val progress = if (max > 0f) (x.value / max).coerceIn(0f, 1f) else 0f
        Row(Modifier.fillMaxWidth().height(64.dp).padding(start = knob + pad * 2, end = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(text, style = T.Body, color = U.TextPrimary, textAlign = TextAlign.Center, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f).alpha(1f - progress))
            Glyph(R.drawable.ic_chevrons_right, Modifier.alpha(1f - progress), U.TextPrimary.copy(alpha = 0.8f))
        }
        Box(
            Modifier.padding(pad).offset { IntOffset(x.value.roundToInt(), 0) }.size(knob).clip(CircleShape).background(U.Inverse)
                .pointerInput(max) {
                    detectHorizontalDragGestures(
                        onDragEnd = {
                            scope.launch {
                                if (x.value > max * 0.7f) { x.animateTo(max); onDone(); x.snapTo(0f) } else x.animateTo(0f, spring(Spring.DampingRatioMediumBouncy))
                            }
                        },
                        onDragCancel = { scope.launch { x.animateTo(0f) } },
                    ) { change, drag -> change.consume(); scope.launch { x.snapTo((x.value + drag).coerceIn(0f, max)) } }
                },
            contentAlignment = Alignment.Center,
        ) { Glyph(icon, tint = U.OnInverse) }
    }
}

/** Floating bottom navigation: Home, Library, Create, Progress, Profile. The active tab is a white circle. */
@Composable
fun TabBar(selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier) {
    val tabs = listOf(R.drawable.ic_home to "Home", R.drawable.ic_book to "Library", R.drawable.ic_sparkles to "Create", R.drawable.ic_chart to "Progress", R.drawable.ic_user to "Profile")
    val shape = RoundedCornerShape(14.dp)
    Row(
        modifier.fillMaxWidth().height(68.dp).clip(shape).background(U.Bar).border(1.dp, U.GlassFaint, shape).padding(horizontal = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically,
    ) {
        tabs.forEachIndexed { i, (icon, name) ->
            val on = i == selected
            val src = remember { MutableInteractionSource() }
            Box(
                Modifier.size(52.dp).pressScale(src, 0.9f).clip(CircleShape).background(if (on) U.Inverse else Color.Transparent)
                    .clickable(src, null, role = Role.Tab) { onSelect(i) }.semantics { this.selected = on },
                contentAlignment = Alignment.Center,
            ) { Glyph(icon, tint = if (on) U.OnInverse else U.TextSecondary, size = 22.dp, description = name) }
        }
    }
}

@Composable
fun SectionHeader(title: String, modifier: Modifier = Modifier, trailing: String? = null) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = T.Title, color = U.TextPrimary, modifier = Modifier.weight(1f))
        if (trailing != null) Text(trailing, style = T.Sub, color = U.TextTertiary)
    }
}

@Composable
fun IconWell(@DrawableRes icon: Int, bg: Color, size: Dp, iconSize: Dp, tint: Color = U.TextPrimary, modifier: Modifier = Modifier) {
    Box(modifier.size(size).clip(CircleShape).background(bg), contentAlignment = Alignment.Center) { Glyph(icon, tint = tint, size = iconSize) }
}

/** A scene, a recent lesson or a playlist entry. The active one is outlined and shows pause. */
@Composable
fun LessonRow(title: String, sub: String, trailing: String, modifier: Modifier = Modifier, active: Boolean = false, playing: Boolean = false, onClick: () -> Unit = {}) {
    val shape = RoundedCornerShape(20.dp)
    Row(
        modifier.fillMaxWidth().height(72.dp).clip(shape).background(if (active) U.BorderGlass else U.Raised)
            .then(if (active) Modifier.border(1.dp, U.BorderStrong, shape) else Modifier)
            .clickable(role = Role.Button, onClick = onClick).padding(start = 12.dp, end = 16.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (active) IconWell(if (playing) R.drawable.ic_pause else R.drawable.ic_play, U.Inverse, 44.dp, 18.5.dp, U.OnInverse)
        else IconWell(R.drawable.ic_play, U.Muted, 44.dp, 18.5.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, style = T.Body, color = U.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(sub, style = T.Sub, color = U.TextTertiary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Text(trailing, style = T.Chip, color = U.TextSecondary, maxLines = 1)
    }
}

@Composable
fun MetricTile(label: String, value: String, unit: String, bg: Color, modifier: Modifier = Modifier, height: Dp = 104.dp) {
    Column(modifier.height(height).clip(RoundedCornerShape(28.dp)).background(bg).padding(16.dp), verticalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = T.Body, color = U.TextPrimary)
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(value, style = T.Number, color = U.TextPrimary)
            Text(unit, style = T.Caption.copy(letterSpacing = 0.01.em), color = U.TextPrimary.copy(alpha = 0.75f), modifier = Modifier.padding(bottom = 4.dp))
        }
    }
}

@Composable
fun ProgressTrack(progress: Float, modifier: Modifier = Modifier, track: Color = U.GlassStrong, fill: Color = U.Accent) {
    Box(modifier.fillMaxWidth().height(4.dp).clip(CircleShape).background(track)) {
        Box(Modifier.fillMaxWidth(progress.coerceIn(0f, 1f)).fillMaxHeight().clip(CircleShape).background(fill))
    }
}
