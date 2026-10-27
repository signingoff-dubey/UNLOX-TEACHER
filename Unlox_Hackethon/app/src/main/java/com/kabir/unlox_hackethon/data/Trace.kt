package com.kabir.unlox_hackethon.data

import android.util.Log
import java.io.File

/**
 * Breadcrumbs written to a file as each step starts. A native library that calls exit() leaves nothing in logcat, so the last line of
 * this file says where the app stopped. Also keeps a list of native steps that killed the app, so the next run skips them.
 */
object Trace {
    private val file by lazy { File(Graph.app.filesDir, "trace.log") }
    private val sp by lazy { Graph.app.getSharedPreferences("trace", android.content.Context.MODE_PRIVATE) }

    @Synchronized fun mark(msg: String) {
        Log.i("Chanakya", msg)
        runCatching { file.appendText("${System.currentTimeMillis() % 100000000} $msg\n") }
    }

    /** Call before a native step that might abort the process; call [done] after. If the app dies in between, [dead] reports it next run. */
    fun guard(key: String) { sp.edit().putString("pending", key).commit() }
    fun done() { sp.edit().remove("pending").commit() }

    /** Native steps that killed the app on an earlier run (they are skipped from then on). */
    fun dead(): Set<String> {
        // a new build may have fixed whatever killed the app, so start the list again
        val built = Graph.app.packageManager.getPackageInfo(Graph.app.packageName, 0).lastUpdateTime
        if (sp.getLong("built", 0L) != built) sp.edit().putLong("built", built).remove("dead").remove("pending").commit()
        val pending = sp.getString("pending", null)
        val set = sp.getStringSet("dead", emptySet())!!.toMutableSet()
        if (pending != null) { set.add(pending); sp.edit().putStringSet("dead", set).remove("pending").commit() }
        return set
    }
}
