package com.kabir.unlox_hackethon.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.kabir.unlox_hackethon.R

/** Design tokens from the Figma file "NOTES - Kabir Edition" (1 dp = 3.968 px in the export). */
object U {
    val BgApp = Color(0xFF0B0B0D)
    val Surface = Color(0xFF1D1D20)
    val Raised = Color(0xFF2A2A2E)
    val Glass = Color(0xFF2E2E31)
    val GlassStrong = Color(0xFF3C3C3F)
    val GlassFaint = Color(0xFF17171A)
    val BorderGlass = Color(0xFF2A2A2D)
    val BorderStrong = Color(0xFF626265)
    val Bar = Color(0xFF0A0A0D)                 // tab bar and segmented control
    val Muted = Color(0xFF5E5E64)
    val IndicatorOff = Color(0xFF545457)
    val Inverse = Color.White
    val OnInverse = Color(0xFF0B0B0D)
    val TextPrimary = Color.White
    val TextSecondary = Color(0xFFB4B4BA)
    val TextTertiary = Color(0xFF8C8C93)
    val TextAccent = Color(0xFFD9C3A0)
    val Sage = Color(0xFF5F8371)
    val Cobalt = Color(0xFF2F4FB0)
    val Accent = Color(0xFFB89A6E)
    val Rust = Color(0xFFB4523A)
    val Orchid = Color(0xFFB05C97)
    val Live = Color(0xFFE5484D)
    val Online = Color(0xFF7DBE6A)
    val Rainbow = listOf(Color(0xFFE34A4D), Color(0xFFF2994D), Color(0xFFF2D966), Color(0xFF7DBF6B), Color(0xFF5E8CF2), Color(0xFF996BD9))
}

private fun urbanist(weight: Int) = Font(R.font.urbanist, FontWeight(weight), variationSettings = FontVariation.Settings(FontVariation.weight(weight)))

val Urbanist = FontFamily(urbanist(400), urbanist(500), urbanist(600))

/** Type scale read off the frames: display 34, hero 44, title 24 / 18, body 14, sub 13, chip 13, caption 11. */
object T {
    private fun s(size: Int, weight: Int, line: Float, track: Float = 0f) =
        TextStyle(fontFamily = Urbanist, fontWeight = FontWeight(weight), fontSize = size.sp, lineHeight = (size * line).sp, letterSpacing = track.em)

    val Hero = s(44, 400, 1.05f, -0.034f)
    val Display = s(34, 500, 1.1f, -0.03f)
    val Headline = s(24, 600, 1.2f, -0.02f)
    val Title = s(18, 600, 1.25f, -0.011f)
    val Body = s(14, 500, 1.4f)
    val BodyRegular = s(14, 400, 1.4f)
    val Input = s(16, 400, 1.45f)
    val Sub = s(13, 400, 1.4f)
    val Chip = s(13, 600, 1.2f, 0.002f)
    val Caption = s(11, 500, 1.2f, 0.027f)
    val Number = s(34, 500, 1f, -0.007f)
}
