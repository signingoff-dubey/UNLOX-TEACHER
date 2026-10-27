package com.kabir.unlox_hackethon.data

/** What the learner asked for in the chat: one more video, on `topic` (empty: more of the same topic), about `seconds` long (null: like this one). */
data class VideoIntent(val topic: String, val seconds: Int?)

/**
 * Recognises "generate one more video on black holes", "make another one about volcanoes, 2 minutes", "another lesson on tides" by its words
 * (no model call, so the answer is instant). Questions about videos ("how do I make a video?") and "give me one more example" are left to the tutor.
 * The same rules as the website's chat (backend/app/videochat.py).
 */
object VideoRequest {
    private const val VERB = "(?:generate|make|create|build|produce|record|prepare|render|add|give|get|do|start|show)"
    private const val NOUN = "(?:videos?|lessons?|episodes?|explainers?|clips?|tutorials?)"
    private const val CONNECTOR = "(?:on|about|for|of|regarding|covering|that|which|explain(?:s|ing)?|teach(?:es|ing)?|show(?:s|ing)?|cover(?:s|ing)?|in|with|to explain|to teach)"
    private val OPENER = Regex(
        "^(?:(?:hey|hi|ok|okay|so|now|and|also|then|well)[,\\s]+)*" +
            "(?:(?:can|could|would|will) (?:you|u) (?:please )?|please |pls |kindly |i (?:want|need|would like|'d like|d like) (?:you )?(?:to )?|(?:let's|lets) |go ahead and |you can )*",
        RegexOption.IGNORE_CASE,
    )
    private val WITH_NOUN = Regex(
        "^$VERB\\b(?: me| us)?(?: (?:a|an|the|one|another|one more|a new|new|more|next|different|second|third|short|quick|small|simple|\\d+[- ]?(?:minute|min|second|sec)s?|\\d+))* $NOUN\\b(?<rest>.*)$",
    )
    private val NO_NOUN = Regex("^$VERB\\b(?: me| us)? (?:one more|another one|a new one|another|one)\\b(?<rest>.*)$")
    private val REST_OK = Regex("^\\s*(?:$|[,.!?]|please\\b|thanks\\b|$CONNECTOR\\b)")
    private val NOUN_FIRST = Regex("^(?:another|one more|next|a new) $NOUN\\b(?<rest>.*)$")
    private val QUESTION_WORDS = setOf("how", "what", "why", "when", "where", "who", "which", "is", "are", "does", "did", "was", "can", "could")
    private val NUMBERS = mapOf("one" to 1.0, "two" to 2.0, "three" to 3.0, "four" to 4.0, "five" to 5.0, "half" to 0.5)

    private fun seconds(text: String): Int? {
        val t = text.lowercase()
        Regex("(\\d+(?:\\.\\d+)?|half|one|two|three|four|five)\\s*(?:-\\s*)?(?:minutes?|mins?|min|m)\\b").find(t)?.let { m ->
            val n = NUMBERS[m.groupValues[1]] ?: m.groupValues[1].toDouble()
            return (Math.round(n * 60 / 5) * 5).toInt().coerceIn(30, 240)
        }
        Regex("(\\d+)\\s*(?:-\\s*)?(?:seconds?|secs?|sec|s)\\b").find(t)?.let { m -> return (Math.round(m.groupValues[1].toInt() / 5.0) * 5).toInt().coerceIn(30, 240) }
        return null
    }

    private fun topic(rest: String): String {
        var t = rest.trim().split(Regex("\\s+")).joinToString(" ").trim(' ', ',', '.', '!', '?', ';', ':', '"', '\'')
        t = t.replace(Regex("\\b(?:of |that is |that's |which is |in |for |lasting |about |around )?(?:\\d+(?:\\.\\d+)?|half|one|two|three|four|five)\\s*-?\\s*(?:minutes?|mins?|min|seconds?|secs?|sec)(?: long| each)?\\b", RegexOption.IGNORE_CASE), " ")
        repeat(3) { t = t.trim(' ', ',').replace(Regex("^(?:please\\s*,?\\s*)?(?:that |which )?(?:is |are )?$CONNECTOR\\s+", RegexOption.IGNORE_CASE), "") }
        t = t.trim().replace(Regex("\\s*(?:,?\\s*(?:please|for me|now|thanks|thank you))+$", RegexOption.IGNORE_CASE), "")
        t = t.split(Regex("\\s+")).joinToString(" ").trim(' ', ',', '.', '!', '?', ';', ':', '"', '\'')
        return if (t.length >= 2) t.take(120) else ""
    }

    fun detect(message: String): VideoIntent? {
        val text = message.trim().split(Regex("\\s+")).joinToString(" ")
        val low = text.lowercase().replace(OPENER, "").trim()
        if (low.isEmpty() || low.split(" ").first() in QUESTION_WORDS) return null
        val m = WITH_NOUN.find(low) ?: NOUN_FIRST.find(low) ?: NO_NOUN.find(low)?.takeIf { REST_OK.containsMatchIn(it.groups["rest"]!!.value) } ?: return null
        return VideoIntent(topic(m.groups["rest"]!!.value), seconds(text))
    }
}
