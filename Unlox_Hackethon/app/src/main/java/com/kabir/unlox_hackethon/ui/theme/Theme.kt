package com.kabir.unlox_hackethon.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

// The app is dark only (the Figma frames have no light variant), so no dynamic colour.
private val UnloxColors = darkColorScheme(
    primary = U.Inverse, onPrimary = U.OnInverse,
    secondary = U.Accent, onSecondary = U.TextPrimary,
    background = U.BgApp, onBackground = U.TextPrimary,
    surface = U.Surface, onSurface = U.TextPrimary,
    surfaceVariant = U.Raised, onSurfaceVariant = U.TextSecondary,
    outline = U.BorderGlass,
)

@Composable
fun Unlox_HackethonTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = UnloxColors, typography = Typography, content = content)
}
