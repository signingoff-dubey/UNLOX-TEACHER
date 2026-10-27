package com.kabir.unlox_hackethon.ui

import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.toMutableStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.kabir.unlox_hackethon.data.CreationState
import com.kabir.unlox_hackethon.data.Graph
import com.kabir.unlox_hackethon.data.LANGS
import com.kabir.unlox_hackethon.data.Lesson
import com.kabir.unlox_hackethon.data.LessonMeta
import com.kabir.unlox_hackethon.data.detectLanguage
import com.kabir.unlox_hackethon.ui.components.RippleReveal
import com.kabir.unlox_hackethon.ui.components.TabBar
import com.kabir.unlox_hackethon.ui.components.VoiceScreen
import com.kabir.unlox_hackethon.ui.screens.AnswersScreen
import com.kabir.unlox_hackethon.ui.screens.CreateLessonScreen
import com.kabir.unlox_hackethon.ui.screens.FlashcardsScreen
import com.kabir.unlox_hackethon.ui.screens.GeneratingScreen
import com.kabir.unlox_hackethon.ui.screens.HomeScreen
import com.kabir.unlox_hackethon.ui.screens.HomeworkScreen
import com.kabir.unlox_hackethon.ui.screens.LessonRequest
import com.kabir.unlox_hackethon.ui.screens.LibraryScreen
import com.kabir.unlox_hackethon.ui.screens.Made
import com.kabir.unlox_hackethon.ui.screens.Message
import com.kabir.unlox_hackethon.ui.screens.MindMapScreen
import com.kabir.unlox_hackethon.ui.screens.NotesScreen
import com.kabir.unlox_hackethon.ui.screens.OnboardingScreen
import com.kabir.unlox_hackethon.ui.screens.PlayerScreen
import com.kabir.unlox_hackethon.ui.screens.ProfileScreen
import com.kabir.unlox_hackethon.ui.screens.ProgressScreen
import com.kabir.unlox_hackethon.ui.screens.QuizScreen
import com.kabir.unlox_hackethon.ui.screens.RewardsScreen
import com.kabir.unlox_hackethon.ui.screens.PartRef
import com.kabir.unlox_hackethon.ui.screens.SettingsScreen
import com.kabir.unlox_hackethon.ui.screens.Stage
import com.kabir.unlox_hackethon.ui.screens.StageState
import com.kabir.unlox_hackethon.ui.screens.StudyHubScreen
import com.kabir.unlox_hackethon.ui.screens.StudyKind
import com.kabir.unlox_hackethon.ui.screens.TutorChatScreen
import com.kabir.unlox_hackethon.ui.screens.Who
import com.kabir.unlox_hackethon.ui.theme.U
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalTime
import java.time.format.DateTimeFormatter

/** Every screen the back stack can hold. Encoded to text so the stack survives rotation. */
sealed interface Route {
    data object Onboarding : Route
    data object Main : Route
    data class Create(val concept: String) : Route
    data object Generating : Route
    data object Player : Route
    data object Study : Route
    data class Tool(val kind: StudyKind) : Route
    data object Homework : Route
    data class Answers(val typed: String) : Route
    data object Rewards : Route
    data object Settings : Route
}

private fun Route.encode(): String = when (this) {
    Route.Onboarding -> "onboarding"; Route.Main -> "main"; Route.Generating -> "generating"; Route.Player -> "player"
    Route.Study -> "study"; Route.Homework -> "homework"; Route.Rewards -> "rewards"; Route.Settings -> "settings"
    is Route.Create -> "create|$concept"; is Route.Tool -> "tool|${kind.name}"; is Route.Answers -> "answers|$typed"
}

private fun decode(s: String): Route {
    val p = s.split("|", limit = 2)
    return when (p[0]) {
        "main" -> Route.Main; "generating" -> Route.Generating; "player" -> Route.Player; "study" -> Route.Study
        "homework" -> Route.Homework; "rewards" -> Route.Rewards; "settings" -> Route.Settings
        "create" -> Route.Create(p.getOrElse(1) { "" }); "tool" -> Route.Tool(StudyKind.valueOf(p[1]))
        "answers" -> Route.Answers(p.getOrElse(1) { "" })
        else -> Route.Onboarding
    }
}

private val TIME = DateTimeFormatter.ofPattern("HH:mm")
private fun now() = LocalTime.now().format(TIME)
private val EASE = FastOutSlowInEasing

/**
 * Navigation, the tab bar and the two overlays that spread out of a button (the tutor chat and voice mode).
 * Everything that thinks runs on a background thread inside the engines in [Graph]; this only holds what is on screen.
 */
@Composable
fun UnloxApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val stack = rememberSaveable(saver = listSaver(save = { it.map(Route::encode) }, restore = { it.map(::decode).toMutableStateList() })) { mutableStateListOf<Route>(Route.Onboarding) }
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var introDone by rememberSaveable { mutableStateOf(!Graph.profile.intro) }      // the opening plays once per launch, not on every rotation
    fun push(r: Route) { stack.add(r) }
    fun pop() { if (stack.size > 1) stack.removeAt(stack.lastIndex) }
    fun replace(r: Route) { stack[stack.lastIndex] = r }
    fun reset(r: Route) { stack.clear(); stack.add(r) }
    val top = stack.last()
    fun toast(t: String) = Toast.makeText(context, t, Toast.LENGTH_SHORT).show()

    // lessons on this phone
    var lessons by remember { mutableStateOf<List<LessonMeta>>(emptyList()) }
    var lesson by remember { mutableStateOf<Lesson?>(null) }
    val creation by Graph.creator.state.collectAsState()
    var request by remember { mutableStateOf(LessonRequest("", listOf("English"), 30, "")) }
    LaunchedEffect(top, creation.lessonId) { lessons = withContext(Dispatchers.IO) { Graph.lessons.list() } }
    LaunchedEffect(Unit) { Graph.llm.warmUp() }                                   // load Gemma while the learner looks around

    // overlays that grow out of a button
    var chatOpen by rememberSaveable { mutableStateOf(false) }
    var voiceOpen by rememberSaveable { mutableStateOf(false) }
    var voiceBusy by remember { mutableStateOf(false) }
    var chatOrigin by remember { mutableStateOf(Offset.Zero) }
    var voiceOrigin by remember { mutableStateOf(Offset.Zero) }
    var voiceForChat by remember { mutableStateOf(false) }

    // player
    var scene by rememberSaveable { mutableIntStateOf(0) }
    var playing by rememberSaveable { mutableStateOf(false) }
    var sceneMs by remember { mutableIntStateOf(0) }
    var language by rememberSaveable { mutableIntStateOf(0) }
    val started = remember { intArrayOf(-1, -1) }
    val seekMs = remember { intArrayOf(0) }                                          // where in the scene the narration should start (after a seek)                                    // [scene whose audio is loaded, language it was loaded in]
    val track = lesson?.let { it.tracks.getOrElse(language) { _ -> it.tracks.first() } }
    val scenes = track?.scenes.orEmpty()

    // A lesson that is still being made: take the scenes and languages that have been added, keeping the learner on the same language.
    LaunchedEffect(lesson?.id, lesson?.building) {
        val id = lesson?.id ?: return@LaunchedEffect
        if (lesson?.building != true) return@LaunchedEffect
        while (true) {
            delay(1200)
            val fresh = withContext(Dispatchers.IO) { Graph.lessons.load(id) } ?: continue
            val cur = lesson ?: return@LaunchedEffect
            if (cur.id != id) return@LaunchedEffect
            val code = cur.tracks.getOrNull(language)?.lang
            lesson = fresh
            if (code != null) language = fresh.tracks.indexOfFirst { it.lang == code }.coerceAtLeast(0)
            if (!fresh.building) break
        }
    }

    // a set of videos: the parts of the course this lesson belongs to (polled while the later ones are still being made)
    var course by remember { mutableStateOf<com.kabir.unlox_hackethon.data.Course?>(null) }
    LaunchedEffect(lesson?.courseId) {
        val cid = lesson?.courseId.orEmpty()
        if (cid.isEmpty()) { course = null; return@LaunchedEffect }
        while (true) {
            course = withContext(Dispatchers.IO) { Graph.lessons.loadCourse(cid) }
            if (course?.episodes?.none { it.status == "pending" } == true) break
            delay(3000)
        }
    }

    LaunchedEffect(playing, scene, language, lesson?.id, top, chatOpen) {
        val l = lesson ?: return@LaunchedEffect
        val t = track ?: return@LaunchedEffect
        if (!playing || top != Route.Player || chatOpen) { Graph.player.pause(); return@LaunchedEffect }
        val sc = t.scenes.getOrNull(scene) ?: return@LaunchedEffect
        val file = sc.audio?.let { File(Graph.lessons.dir(l.id), it) }?.takeIf { it.exists() }
        var finished = false
        if (file != null) {
            if (started[0] != scene || started[1] != language) { val from = seekMs[0]; seekMs[0] = 0; sceneMs = from; Graph.player.play(file, from) { finished = true }; started[0] = scene; started[1] = language } else Graph.player.resume()
            while (!finished) { delay(200); sceneMs = Graph.player.positionMs }
        } else {                                                                      // no voice for this language: show the scene for as long as it would take to read
            started[0] = scene; started[1] = language
            while (sceneMs < sc.seconds * 1000) { delay(200); sceneMs += 200 }
            finished = true
        }
        if (finished) {
            started[0] = -1
            fun known() = lesson?.tracks?.getOrNull(language)?.scenes?.size ?: 0
            if (scene + 1 < t.scenes.size) { scene += 1; sceneMs = 0 }
            else {
                // caught up with the scenes made so far: wait for the next one instead of ending
                while (lesson?.building == true && known() <= scene + 1) delay(400)
                if (known() > scene + 1) { scene += 1; sceneMs = 0 } else { playing = false; sceneMs = 0; Graph.rewards.award("lesson_complete") }
            }
        }
    }
    /** Jump to a moment of the whole lesson (in seconds): the scene it falls in, and the place inside that scene. */
    fun seekTo(sec: Float) {
        var acc = 0f; var idx = scenes.lastIndex
        for (i in scenes.indices) { val d = scenes[i].seconds.coerceAtLeast(1f); if (sec < acc + d) { idx = i; break }; acc += d }
        scene = idx.coerceAtLeast(0); sceneMs = ((sec - acc).coerceAtLeast(0f) * 1000).toInt(); seekMs[0] = sceneMs
        started[0] = -1; Graph.player.stop()
    }
    fun openLessonObj(l: Lesson) { Graph.player.stop(); started[0] = -1; lesson = l; scene = 0; sceneMs = 0; playing = false; language = 0 }
    fun openLesson(id: String) = scope.launch {
        val l = withContext(Dispatchers.IO) { Graph.lessons.load(id) }
        if (l == null) toast("That lesson could not be opened.") else { openLessonObj(l); push(Route.Player) }
    }
    /** The lesson the study tools work on: the one on screen, else the newest. */
    suspend fun studyLesson(): Lesson? = lesson ?: withContext(Dispatchers.IO) { Graph.lessons.list().firstOrNull()?.let { Graph.lessons.load(it.id) } }.also { if (it != null) lesson = it }

    // tutor
    val messages = remember { mutableStateListOf(Message(Who.TUTOR, "Hi ${Graph.profile.callName}! Ask me anything about the lesson. I know every scene.", now())) }
    var thinking by remember { mutableStateOf(false) }
    fun ask(q: String) {
        if (q.isBlank() || thinking) return
        playing = false
        messages.add(Message(Who.STUDENT, q, now()))
        thinking = true
        val history = messages.dropLast(1).drop(1).chunked(2).mapNotNull { if (it.size == 2 && it[0].who == Who.STUDENT) it[0].text to it[1].text else null }
        scope.launch {
            val reply = runCatching { Graph.tutor.ask(q, lesson, LANGS[0].code, scene, history) }.getOrElse { "I could not think of an answer just now: ${it.message}" }
            messages.add(Message(Who.TUTOR, reply, now()))
            thinking = false
            Graph.rewards.award("tutor_question")
            if (Graph.profile.speak) Graph.tts.speak(reply, detectLanguage(reply), File(context.cacheDir, "reply.wav"))?.let { Graph.player.play(it.file) {} }
        }
    }

    // generating: the creator reports its own progress; when the lesson is saved it opens
    LaunchedEffect(creation.lessonId) {
        val id = creation.lessonId ?: return@LaunchedEffect
        val l = withContext(Dispatchers.IO) { Graph.lessons.load(id) } ?: return@LaunchedEffect
        Graph.creator.opened()
        openLessonObj(l)
        if (stack.last() == Route.Generating) replace(Route.Player)
    }

    BackHandler(enabled = voiceOpen || chatOpen || stack.size > 1 || (top == Route.Main && tab != 0)) {
        when {
            voiceOpen -> voiceOpen = false
            chatOpen -> chatOpen = false
            stack.size > 1 -> {
                if (top == Route.Player) { playing = false; Graph.player.stop(); started[0] = -1 }
                if (top == Route.Generating) Graph.creator.cancel()
                pop()
            }
            else -> tab = 0
        }
    }

    val navBar = 68.dp + 16.dp + 24.dp     // the tab bar, its gap, and some air above it
    val depth = remember { intArrayOf(stack.size) }
    SideEffect { depth[0] = stack.size }

    Box(Modifier.fillMaxSize().background(U.BgApp)) {
        AnimatedContent(
            targetState = top,
            transitionSpec = {
                val pushed = stack.size > depth[0]
                val popped = stack.size < depth[0]
                val move = tween<IntOffset>(320, easing = EASE)
                val fade = tween<Float>(240, easing = EASE)
                when {
                    pushed -> (slideInHorizontally(move) { it / 4 } + fadeIn(fade)) togetherWith (slideOutHorizontally(move) { -it / 6 } + fadeOut(tween(180)))
                    popped -> (slideInHorizontally(move) { -it / 6 } + fadeIn(fade)) togetherWith (slideOutHorizontally(move) { it / 4 } + fadeOut(tween(180)))
                    else -> (fadeIn(tween(300)) + scaleIn(tween(300), 0.96f)) togetherWith fadeOut(tween(200))
                }.also { it.targetContentZIndex = if (popped) -1f else 1f }
            },
            label = "route",
        ) { route ->
            when (route) {
                Route.Onboarding -> OnboardingScreen(onStart = { reset(Route.Main) }, onLanguage = { push(Route.Settings) })
                Route.Main -> Box(Modifier.fillMaxSize()) {
                    AnimatedContent(tab, transitionSpec = { (fadeIn(tween(220)) + scaleIn(tween(220), 0.98f)) togetherWith fadeOut(tween(120)) }, label = "tab") { t ->
                        when (t) {
                            0 -> HomeScreen(
                                last = lessons.firstOrNull(),
                                onAsk = { push(Route.Create(it)) },
                                onVoice = { o -> voiceOrigin = o; voiceForChat = false; voiceOpen = true },
                                onContinue = { lessons.firstOrNull()?.let { openLesson(it.id) } }, onProfile = { tab = 4 }, bottomInset = navBar,
                            )
                            1 -> LibraryScreen(lessons, navBar, onOpenLesson = { openLesson(it) }, onDelete = { Graph.lessons.delete(it) }, onAdd = { push(Route.Create("")) })
                            3 -> ProgressScreen(navBar, onSettings = { push(Route.Settings) })
                            else -> ProfileScreen(navBar, { push(Route.Rewards) }, { push(Route.Homework) }, { push(Route.Settings) }, { push(Route.Study) })
                        }
                    }
                    Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(150.dp).background(Brush.verticalGradient(listOf(Color.Transparent, U.BgApp.copy(alpha = 0.92f), U.BgApp))))
                    TabBar(tab, { if (it == 2) push(Route.Create("")) else tab = it },
                        Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(start = 16.dp, end = 16.dp, bottom = 16.dp))
                }
                is Route.Create -> CreateLessonScreen(route.concept, onBack = ::pop, onSettings = { push(Route.Settings) }, onGenerate = {
                    if (it.concept.isBlank()) toast("Type what you want to learn first.") else { request = it; Graph.creator.start(it); push(Route.Generating) }
                })
                Route.Generating -> GeneratingScreen(request, creation.progress, creation.error?.let { "Could not finish: $it" } ?: creation.status, stagesFor(creation)) { Graph.creator.cancel(); pop() }
                Route.Player -> PlayerScreen(
                    lesson?.title ?: "", scenes, scene, { scene = it; sceneMs = 0; seekMs[0] = 0; started[0] = -1; Graph.player.stop(); playing = true },
                    playing, { playing = it }, sceneMs, language, lesson?.tracks?.map { t -> LANGS.first { it.code == t.lang }.name }.orEmpty(),
                    { language = it; sceneMs = 0; started[0] = -1; Graph.player.stop() },
                    onBack = { playing = false; Graph.player.stop(); started[0] = -1; pop() },
                    onAskTutor = { o -> chatOrigin = o; chatOpen = true }, onStudy = { push(Route.Study) }, onSeek = ::seekTo,
                    making = lesson?.takeIf { it.building }?.let { "${creation.status.ifBlank { "Making the rest" }} · ${(creation.progress * 100).toInt()}%" },
                    scenesTotal = lesson?.scenesTotal ?: 0,
                    parts = course?.episodes?.map { PartRef(it.title, it.lessonId != null) }.orEmpty(), part = lesson?.episode ?: 0,
                    onPart = { i -> course?.episodes?.getOrNull(i)?.lessonId?.let { id -> scope.launch { withContext(Dispatchers.IO) { Graph.lessons.load(id) }?.let { openLessonObj(it) } } } },
                )
                Route.Study -> StudyHubScreen(lesson?.title ?: lessons.firstOrNull()?.title ?: "your lesson", onBack = ::pop, onOpen = { k ->
                    scope.launch { if (studyLesson() == null) toast("Make a lesson first.") else { Graph.rewards.award("study_tool"); push(Route.Tool(k)) } }
                })
                is Route.Tool -> lesson?.let { l ->
                    when (route.kind) {
                        StudyKind.FLASHCARDS -> Made("flashcards", ::pop, { Graph.study.cards(l) }) { FlashcardsScreen(it, ::pop, onKnown = { Graph.rewards.award("card_known") }) }
                        StudyKind.QUIZ -> Made("quiz", ::pop, { Graph.study.quiz(l) }) { q -> QuizScreen(q, ::pop, onRight = { Graph.rewards.award("quiz_correct") }) { s, n -> Graph.rewards.award("quiz_done", perfect = s == n); pop() } }
                        StudyKind.MINDMAP -> Made("mind map", ::pop, { Graph.study.mindMap(l) }) { m -> MindMapScreen(m, ::pop) { q -> chatOrigin = Offset.Zero; ask(q); chatOpen = true } }
                        StudyKind.NOTES -> Made("notes", ::pop, { Graph.study.notes(l) }) { NotesScreen(l.title, it, ::pop) }
                    }
                }
                Route.Homework -> HomeworkScreen(::pop, onSolve = { typed -> push(Route.Answers(typed)) })
                is Route.Answers -> AnswersScreen(route.typed, ::pop)
                Route.Rewards -> RewardsScreen(24.dp, ::pop)
                Route.Settings -> SettingsScreen(::pop)
            }
        }

        // The tutor grows out of the "Ask the tutor" button; voice mode grows out of the mic that was tapped, over the chat if it is open.
        RippleReveal(chatOpen, chatOrigin) {
            TutorChatScreen(
                "Scene ${scene + 1} · ${scenes.getOrNull(scene)?.heading ?: ""}", messages, thinking, Graph.profile.speak, {
                    val on = !Graph.profile.speak
                    Graph.profile.setPref("speak", on)
                    if (!on) Graph.player.stop()                                  // muting also silences what is being said now
                }, ::ask,
                onVoice = { o -> voiceOrigin = o; voiceForChat = true; voiceOpen = true }, onBack = { chatOpen = false },
            )
        }
        if (!introDone) Intro { introDone = true }
        RippleReveal(voiceOpen, voiceOrigin) {
            VoiceScreen(onCancel = { voiceOpen = false }, busy = voiceBusy) { samples, hint ->
                scope.launch {
                    voiceBusy = true
                    val heard = Graph.stt.transcribe(samples, hint)
                    voiceBusy = false
                    voiceOpen = false
                    when {
                        heard.text.isBlank() -> toast("I did not catch that. Try again a little closer.")
                        voiceForChat -> ask(heard.text)
                        else -> push(Route.Create(heard.text))
                    }
                }
            }
        }
    }
}

private val STEPS = listOf("Retrieve facts", "Plan scenes", "Translate", "Narrate", "Animate")

private fun stagesFor(c: CreationState): List<Stage> = STEPS.mapIndexed { i, title ->
    val state = when { c.pct[i] >= 1f -> StageState.DONE; c.pct[i] > 0f && c.error == null -> StageState.ACTIVE; else -> StageState.PENDING }
    Stage(title, c.details[i].ifBlank { "Waiting" }, state, c.pct[i])
}
