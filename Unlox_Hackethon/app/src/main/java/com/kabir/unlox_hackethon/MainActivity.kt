package com.kabir.unlox_hackethon

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.kabir.unlox_hackethon.ui.UnloxApp
import com.kabir.unlox_hackethon.ui.theme.Unlox_HackethonTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // dark app: light status and navigation icons on a transparent bar
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT), navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT))
        setContent { Unlox_HackethonTheme { UnloxApp() } }
    }
}
