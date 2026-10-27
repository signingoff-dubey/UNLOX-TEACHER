package com.kabir.unlox_hackethon.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.vector.PathParser
import com.kabir.unlox_hackethon.ui.theme.LogoPaths
import com.kabir.unlox_hackethon.ui.theme.U

/**
 * "Chanakya" in the logo's own pixel lettering (the drawing's WORD paths). The drawing is dark letters with a few light patches that
 * cut the counters out of them, so the dark paths take [color] and the light ones take [hole] (the colour behind the text).
 * Give it a height; the width follows.
 */
@Composable
fun Wordmark(modifier: Modifier = Modifier, color: Color = Color.White, hole: Color = U.BgApp) {
    val paths = remember {
        LogoPaths.WORD.map { (fill, d) -> PathParser().parsePathString(d).toPath() to (android.graphics.Color.luminance(android.graphics.Color.parseColor(fill)) > 0.6f) }
    }
    Canvas(modifier.aspectRatio(633f / 138f)) {
        val k = size.width / 633f
        withTransform({ scale(k, k, pivot = Offset.Zero); translate(-520f, -630f) }) { paths.forEach { (path, light) -> drawPath(path, if (light) hole else color) } }
    }
}
