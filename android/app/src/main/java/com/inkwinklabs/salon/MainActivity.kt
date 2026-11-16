package com.inkwinklabs.salon

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.WindowInsets
import android.webkit.CookieManager
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import kotlin.concurrent.thread

/**
 * The whole Android app is this one screen: a full-screen web view showing the
 * same pages as the laptop version, talking to the Python server inside the app.
 */
class MainActivity : Activity() {
    private lateinit var root: FrameLayout
    private lateinit var web: WebView
    private var address: SalonServer.Address? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // A plum "Opening your salon…" screen while Python starts (about a second).
        val brand = getColor(R.color.brand)
        val loading = TextView(this).apply {
            setText(R.string.starting)
            setTextColor(Color.WHITE)
            textSize = 18f
            gravity = Gravity.CENTER
        }
        web = WebView(this).apply {
            alpha = 0f                                   // hidden until the first page has loaded
            settings.javaScriptEnabled = true            // our own screens need JavaScript
            settings.domStorageEnabled = true            // remembers the Light/Dark choice
            webViewClient = Pages()
            webChromeClient = Dialogs()
        }
        root = FrameLayout(this).apply {
            setBackgroundColor(brand)
            addView(web, MATCH_PARENT, MATCH_PARENT)
            addView(loading, MATCH_PARENT, MATCH_PARENT)
        }
        setContentView(root)
        keepClearOfSystemBars()

        // Starting Python takes a moment, so do it off the main thread to keep the app responsive.
        thread(name = "salon-start") {
            try {
                val a = SalonServer.start(this)
                runOnUiThread {
                    address = a
                    // Hand this run's pass-code to our own screen only (see app.py).
                    CookieManager.getInstance().setCookie(a.url, "salon_token=${a.token}; HttpOnly; SameSite=Strict")
                    if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) web.loadUrl(a.url)
                }
            } catch (e: Exception) {
                runOnUiThread { loading.setText(R.string.start_failed) }
            }
        }
    }

    /** New Android versions draw apps behind the status bar and keyboard: add padding so nothing is hidden. */
    private fun keepClearOfSystemBars() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return
        root.setOnApplyWindowInsetsListener { view, insets ->
            val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsets.CONSUMED
        }
    }

    private inner class Pages : WebViewClient() {
        /** Our own pages stay in the app. Anything else (a WhatsApp link) opens in the right app. */
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (request.url.toString().startsWith(address?.url ?: "-")) return false
            try {
                startActivity(Intent(Intent.ACTION_VIEW, request.url))
            } catch (e: ActivityNotFoundException) {
                // No app can open this link: do nothing rather than crash.
            }
            return true
        }

        override fun onPageFinished(view: WebView, url: String) {
            if (web.alpha == 0f) {
                web.alpha = 1f
                root.removeViewAt(1)          // take away the "Opening…" screen
            }
        }
    }

    /** "Are you sure?" questions from the screens, shown as normal Android dialogs. */
    private inner class Dialogs : WebChromeClient() {
        override fun onJsConfirm(view: WebView, url: String, message: String, result: JsResult): Boolean {
            AlertDialog.Builder(this@MainActivity)
                .setMessage(message)
                .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                .setNegativeButton(android.R.string.cancel) { _, _ -> result.cancel() }
                .setOnCancelListener { result.cancel() }
                .show()
            return true
        }

        override fun onJsAlert(view: WebView, url: String, message: String, result: JsResult): Boolean {
            AlertDialog.Builder(this@MainActivity)
                .setMessage(message)
                .setPositiveButton(android.R.string.ok) { _, _ -> result.confirm() }
                .setOnCancelListener { result.confirm() }
                .show()
            return true
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }
}
