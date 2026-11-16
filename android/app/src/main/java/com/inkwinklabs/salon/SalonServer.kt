package com.inkwinklabs.salon

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/**
 * Starts the Python server (the very same code as the laptop app) inside this
 * app, once. Turning the phone or reopening the screen reuses the running server.
 */
object SalonServer {
    /** Where the screen should connect: the port, and this run's random pass-code. */
    data class Address(val port: Int, val token: String) {
        val url get() = "http://127.0.0.1:$port"
    }

    @Volatile
    private var address: Address? = null

    @Synchronized
    fun start(context: Context): Address {
        address?.let { return it }
        val app = context.applicationContext
        KeyVault.init(app)
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))

        // The app's private folder: other apps cannot read the customer database here.
        val dataDir = File(app.filesDir, "data").apply { mkdirs() }

        val reply = Python.getInstance().getModule("android_main")
            .callAttr("start", dataDir.absolutePath, KeyVault.load())
            .asList()
        return Address(reply[0].toInt(), reply[1].toString()).also { address = it }
    }
}
