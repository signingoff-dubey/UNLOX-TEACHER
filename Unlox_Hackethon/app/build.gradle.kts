plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.kabir.unlox_hackethon"
    compileSdk {
        version = release(37) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.kabir.unlox_hackethon"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Target device is arm64 (OnePlus 13R); keeps the APK small.
        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
    }

    packaging {
        jniLibs {
            // Extract native libs to disk so LiteRT-LM / sherpa-onnx / ONNX Runtime can dlopen them.
            useLegacyPackaging = true
            // sherpa-onnx (static-link AAR) ships a stray x86 libonnxruntime.so that clashes with onnxruntime-android.
            pickFirsts += "**/libonnxruntime.so"
        }
    }

    // Never compress model files if any are ever bundled or pushed as assets.
    androidResources {
        noCompress += listOf("litertlm", "tflite", "onnx", "task", "bin", "ort", "txt", "json")
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)

    // Lifecycle / navigation / background work
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)

    // Lessons storage
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // On-device AI
    implementation(libs.litertlm.android)              // Gemma 4 E2B via LiteRT-LM
    implementation(libs.mlkit.translate)               // offline translation (models download once)
    implementation(libs.mlkit.text.recognition)        // OCR, Latin
    implementation(libs.mlkit.text.recognition.devanagari) // OCR, Devanagari (Hindi, Marathi)
    // onnxruntime-android is not added: sherpa-onnx 1.13.8 ships its own libonnxruntime.so and two copies would clash. MiniLM embeddings will run through sherpa-onnx's runtime.
    // implementation(libs.onnxruntime.android)           // MiniLM embeddings (direct ORT use)
    // sherpa-onnx (Whisper STT + Piper/VITS TTS): GitHub release AAR with onnxruntime statically linked,
    // so it does not clash with onnxruntime-android's libonnxruntime.so.
    implementation(files("libs/sherpa-onnx-1.13.8.aar"))

    // Speech to text for English, Hindi, Telugu, Gujarati (same engine and version as the N Dial recorder; 0.3.75 is the 16 KB page-aligned build)
    implementation("com.alphacephei:vosk-android:0.3.75")

    // MP4 export + images
    implementation(libs.androidx.media3.transformer)
    implementation(libs.androidx.media3.effect)
    implementation(libs.androidx.media3.common)
    implementation(libs.coil.compose)

    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}