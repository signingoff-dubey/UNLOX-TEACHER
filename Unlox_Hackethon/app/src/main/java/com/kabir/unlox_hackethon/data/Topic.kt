package com.kabir.unlox_hackethon.data

/**
 * The subject of what the learner typed: "teach me about dsa in java" is "DSA in Java", "can you make a video on the water cycle please" is "The water cycle".
 * The request words used to go into the lesson with the topic, so every title and caption began with "Teach me ...". Questions ("how do vaccines work") stay as they are;
 * text that is only a request (nothing left after it) is kept whole. Same rules as the backend's content.clean_topic.
 */
private val LEAD = Regex("""^(?:(?:hey|hi|hello|ok|okay|so|now|well|please|pls|kindly)[,\s]+)+""", RegexOption.IGNORE_CASE)
private val WRAP = Regex("""^(?:(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+)?|(?:i|we)\s+(?:want|wanna|need|would\s+like|'d\s+like)\s+(?:you\s+)?(?:to\s+)?|(?:let'?s|lets)\s+|go\s+ahead\s+and\s+)+""", RegexOption.IGNORE_CASE)
private val VERB = Regex(
    """^(?:(?:teach|show|tell|explain|help|walk|guide|train)\s+(?:me|us)\s+(?:about\s+|on\s+|how\s+to\s+|the\s+basics\s+of\s+|the\s+concept\s+of\s+)?""" +
        """|(?:teach|explain|describe|cover|introduce)\s+(?:to\s+me\s+)?(?:about\s+)?""" +
        """|(?:learn|study|understand|know|revise|review)\s+(?:more\s+)?(?:about\s+)?""" +
        """|(?:make|create|generate|build|produce|give|prepare)\s+(?:me\s+|us\s+)?(?:an?\s+|the\s+|one\s+)?(?:short\s+|quick\s+|new\s+)?(?:video|lesson|course|tutorial|explainer|clip)\s*(?:on|about|for|of|regarding|covering)?\s+)""",
    RegexOption.IGNORE_CASE)
private val TAIL = Regex("""[\s,]*(?:please|pls|for me|thanks|thank you)\s*[.!?]*$""", RegexOption.IGNORE_CASE)
private val CASE = mapOf("dsa" to "DSA", "java" to "Java", "python" to "Python", "javascript" to "JavaScript", "typescript" to "TypeScript", "sql" to "SQL", "html" to "HTML",
    "css" to "CSS", "api" to "API", "ai" to "AI", "ml" to "ML", "oop" to "OOP", "dbms" to "DBMS", "c++" to "C++", "kotlin" to "Kotlin", "react" to "React", "git" to "Git", "linux" to "Linux")

fun cleanTopic(text: String): String {
    val original = text.trim().split(Regex("\\s+")).joinToString(" ")
    var t = LEAD.replaceFirst(original, "")
    t = WRAP.replaceFirst(t, "")
    t = VERB.replaceFirst(t, "")
    t = TAIL.replaceFirst(t, "").trim(' ', ',', '.', ':', ';', '!', '?', '"', '\'')
    if (t.length < 2 || t.lowercase() in setOf("me", "us", "it", "this", "that")) return original
    if (t == t.lowercase() || (t == t.uppercase() && t.length > 4)) t = t.split(" ").joinToString(" ") { CASE[it.lowercase()] ?: it }
    return t.replaceFirstChar { it.uppercase() }
}
