package com.cyberhax.game

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.core.view.updateLayoutParams
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.net.toUri
import androidx.core.view.isVisible
import androidx.core.content.edit
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.ViewCompat
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewFeature
import com.cyberhax.game.databinding.ActivityMainBinding
import java.net.URI

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private var initialPageLoaded = false
    private var pageLoadFailed = false
    private var pendingUrl: String = AppConfig.GAME_URL
    private val preferences by lazy { getSharedPreferences(PREFS_NAME, MODE_PRIVATE) }
    private val handler = Handler(Looper.getMainLooper())
    private val coldStartTimeout = 20000L // 20 seconds
    private val coldStartRunnable = Runnable {
        binding.loadingMessage.text = getString(R.string.status_loading_message_cold_start)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        val splashScreen = installSplashScreen()
        var keepSplashVisible = true
        splashScreen.setKeepOnScreenCondition { keepSplashVisible }
        super.onCreate(savedInstanceState)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        keepSplashVisible = false
        pendingUrl = currentConfiguredUrl()

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        configureWebView()
        configureUi()
        restoreOrLoad(savedInstanceState)
        applyEdgeToEdgePadding()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                when {
                    binding.connectionLabOverlay.isVisible -> toggleConnectionLab(false)
                    binding.webView.canGoBack() -> binding.webView.goBack()
                    else -> finish()
                }
            }
        })
    }

    override fun onResume() {
        super.onResume()
        enterImmersiveMode()
        binding.webView.onResume()
    }

    override fun onPause() {
        binding.webView.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        handler.removeCallbacks(coldStartRunnable)
        binding.webView.apply {
            stopLoading()
            webChromeClient = null
            // We don't set webViewClient to null here anymore because it is now marked as @NonNull in API 35+
            // Instead, we just destroy the view.
            destroy()
        }
        super.onDestroy()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        binding.webView.saveState(outState)
        outState.putBoolean(KEY_INITIAL_PAGE_LOADED, initialPageLoaded)
        outState.putString(KEY_PENDING_URL, pendingUrl)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) enterImmersiveMode()
    }

    private fun configureUi() {
        updateHostLabels(currentConfiguredUrl())
        binding.loadingProgressLabel.text = getString(R.string.status_loading_progress_percent, 0)

        binding.retryButton.setOnClickListener { loadGame(forceReload = true) }
        binding.openBrowserButton.setOnClickListener { openExternalUri(pendingUrl.toUri()) }
        binding.closeButton.setOnClickListener { finish() }

        val labVisibility = if (BuildConfig.ALLOW_LOCAL_TESTING) View.VISIBLE else View.GONE
        binding.loadingConnectionLabButton.visibility = labVisibility
        binding.errorConnectionLabButton.visibility = labVisibility

        binding.loadingConnectionLabButton.setOnClickListener { toggleConnectionLab(true) }
        binding.errorConnectionLabButton.setOnClickListener { toggleConnectionLab(true) }
        binding.connectionLabCancelButton.setOnClickListener { toggleConnectionLab(false) }
        binding.connectionLabUseLiveButton.setOnClickListener {
            binding.connectionLabUrlInput.setText(AppConfig.GAME_URL)
        }
        binding.connectionLabUseEmulatorButton.setOnClickListener {
            binding.connectionLabUrlInput.setText(AppConfig.LOCAL_EMULATOR_URL)
        }
        binding.connectionLabUseLanButton.setOnClickListener {
            binding.connectionLabUrlInput.setText(AppConfig.LOCAL_DEVICE_URL_TEMPLATE)
        }
        binding.connectionLabResetButton.setOnClickListener {
            preferences.edit { remove(KEY_CUSTOM_URL) }
            pendingUrl = AppConfig.GAME_URL
            updateHostLabels(pendingUrl)
            toggleConnectionLab(false)
            loadGame(forceReload = true)
        }
        binding.connectionLabSaveButton.setOnClickListener { saveConnectionOverride() }
    }

    private fun configureWebView() {
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(binding.webView, true)
        }

        if (BuildConfig.DEBUG) WebView.setWebContentsDebuggingEnabled(true)

        binding.webView.apply {
            // Match the game's dark theme to prevent white/black flashes
            setBackgroundColor(Color.parseColor("#081118"))
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER
            isFocusable = true
            isFocusableInTouchMode = true
            isNestedScrollingEnabled = true
            requestFocus()
        }

        binding.webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(true)
            builtInZoomControls = true
            displayZoomControls = false
            setSupportMultipleWindows(false)
            javaScriptCanOpenWindowsAutomatically = false
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            allowFileAccess = true
            allowContentAccess = true
            textZoom = 100
            userAgentString = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        }

        if (WebViewFeature.isFeatureSupported(WebViewFeature.SAFE_BROWSING_ENABLE)) {
            WebSettingsCompat.setSafeBrowsingEnabled(binding.webView.settings, true)
        }

        binding.webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                binding.progressBar.progress = newProgress
                binding.progressBar.visibility = if (newProgress in 1..99) View.VISIBLE else View.GONE
                binding.loadingProgressLabel.text =
                    getString(R.string.status_loading_progress_percent, newProgress.coerceIn(0, 100))
            }

            override fun onConsoleMessage(consoleMessage: android.webkit.ConsoleMessage?): Boolean {
                val message = consoleMessage?.message() ?: "null"
                val sourceId = consoleMessage?.sourceId() ?: "unknown"
                val lineNumber = consoleMessage?.lineNumber() ?: 0
                android.util.Log.d("WebViewConsole", "[$sourceId:$lineNumber] $message")
                return true
            }
        }

        binding.webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return false
                val scheme = uri.scheme?.lowercase().orEmpty()
                if (scheme !in setOf("http", "https")) return openExternalUri(uri)
                val host = uri.host?.lowercase().orEmpty()
                
                // Broaden the check to allow subdomains of our known internal hosts
                val internalHosts = resolveInternalHosts()
                val isInternal = internalHosts.any { internalHost ->
                    host == internalHost || host.endsWith(".$internalHost")
                }

                return if (isInternal) {
                    pendingUrl = uri.toString()
                    updateHostLabels(pendingUrl)
                    false
                } else {
                    openExternalUri(uri)
                }
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                android.util.Log.d("WebViewState", "onPageStarted: $url")
                pageLoadFailed = false
                pendingUrl = url ?: pendingUrl
                updateHostLabels(pendingUrl)
                showLoading(getString(R.string.status_loading_message))
                
                handler.removeCallbacks(coldStartRunnable)
                handler.postDelayed(coldStartRunnable, coldStartTimeout)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                android.util.Log.d("WebViewState", "onPageFinished: $url")
                handler.removeCallbacks(coldStartRunnable)
                pendingUrl = url ?: pendingUrl
                updateHostLabels(pendingUrl)
                
                // Inject CSS and a Heartbeat for monitoring
                view?.evaluateJavascript(
                    "(function() { " +
                    "  var style = document.createElement('style');" +
                    "  style.innerHTML = 'html, body { background-color: #081118 !important; }';" +
                    "  document.head.appendChild(style);" +
                    "  if (!window.hbStarted) {" +
                    "    window.hbStarted = true;" +
                    "    setInterval(function() { console.log('JS Heartbeat: OK - Game UI is Active'); }, 5000);" +
                    "  }" +
                    "})()", null
                )
                
                // Force visibility and focus to ensure rendering starts
                view?.visibility = View.VISIBLE
                view?.requestFocus()
                
                // Post to ensure the UI thread is ready before hiding
                handler.post {
                    hideOverlays()
                    initialPageLoaded = true
                    pageLoadFailed = false
                }
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                super.onReceivedError(view, request, error)
                android.util.Log.e("WebViewState", "onReceivedError: ${error?.description} (code: ${error?.errorCode}) for ${request?.url}")
                if (request?.isForMainFrame == true) {
                    handler.removeCallbacks(coldStartRunnable)
                    pageLoadFailed = true
                    showNetworkFailure()
                }
            }

            override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, errorResponse: WebResourceResponse?) {
                super.onReceivedHttpError(view, request, errorResponse)
                if (request?.isForMainFrame == true) {
                    pageLoadFailed = true
                    showFailureState(
                        getString(R.string.status_error_badge_default),
                        getString(R.string.error_title),
                        getString(R.string.http_error_message, errorResponse?.statusCode ?: 0),
                        getString(R.string.status_error_hint_default)
                    )
                }
            }

            override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, error: SslError?) {
                handler?.cancel()
                pageLoadFailed = true
                showFailureState(
                    getString(R.string.status_error_badge_secure),
                    getString(R.string.status_ssl_title),
                    getString(R.string.ssl_error_message),
                    getString(R.string.status_error_hint_secure)
                )
            }

            override fun onRenderProcessGone(view: WebView?, detail: RenderProcessGoneDetail?): Boolean {
                pageLoadFailed = true
                showFailureState(
                    getString(R.string.status_error_badge_renderer),
                    getString(R.string.status_renderer_title),
                    getString(R.string.renderer_error_message),
                    getString(R.string.status_error_hint_renderer)
                )
                return true
            }
        }
    }

    private fun restoreOrLoad(savedInstanceState: Bundle?) {
        if (savedInstanceState == null) {
            loadGame(forceReload = false)
            return
        }

        initialPageLoaded = savedInstanceState.getBoolean(KEY_INITIAL_PAGE_LOADED, false)
        pendingUrl = savedInstanceState.getString(KEY_PENDING_URL, currentConfiguredUrl()) ?: currentConfiguredUrl()
        updateHostLabels(pendingUrl)
        val restored = binding.webView.restoreState(savedInstanceState)
        when {
            restored == null -> loadGame(forceReload = false)
            initialPageLoaded -> hideOverlays()
            else -> showLoading(getString(R.string.status_loading_message))
        }
    }

    private fun loadGame(forceReload: Boolean) {
        if (!isOnline()) {
            showOfflineState()
            return
        }

        val targetUrl = currentConfiguredUrl()
        showLoading(getString(R.string.status_loading_message))
        if (forceReload) {
            pendingUrl = targetUrl
            updateHostLabels(pendingUrl)
            binding.webView.stopLoading()
            binding.webView.clearHistory()
            binding.webView.loadUrl(targetUrl)
        } else {
            binding.webView.loadUrl(pendingUrl.ifBlank { targetUrl })
        }
    }

    private fun showLoading(message: String) {
        binding.loadingTitle.text = if (initialPageLoaded) {
            getString(R.string.status_loading_title_retry)
        } else {
            getString(R.string.status_loading_title)
        }
        binding.loadingSubtitle.text = getString(R.string.status_loading_subtitle)
        binding.loadingMessage.text = message
        binding.loadingOverlay.visibility = View.VISIBLE
        binding.errorOverlay.visibility = View.GONE
        animateCard(binding.loadingCard)
    }

    private fun hideOverlays() {
        binding.loadingOverlay.visibility = View.GONE
        binding.errorOverlay.visibility = View.GONE
        binding.connectionLabOverlay.visibility = View.GONE
    }

    private fun showFailureState(badge: String, title: String, message: String, hint: String) {
        pageLoadFailed = true
        binding.errorBadge.text = badge
        binding.errorTitle.text = title
        binding.errorMessage.text = message
        binding.errorHint.text = hint
        binding.loadingOverlay.visibility = View.GONE
        binding.errorOverlay.visibility = View.VISIBLE
        animateCard(binding.errorCard)
    }

    private fun showNetworkFailure() {
        if (isOnline()) {
            showFailureState(
                getString(R.string.status_error_badge_default),
                getString(R.string.error_title),
                getString(R.string.load_failed_message),
                getString(R.string.status_error_hint_default)
            )
        } else {
            showOfflineState()
        }
    }

    private fun showOfflineState() {
        showFailureState(
            getString(R.string.status_error_badge_offline),
            getString(R.string.status_offline_title),
            getString(R.string.offline_message),
            getString(R.string.status_error_hint_offline)
        )
    }

    private fun toggleConnectionLab(show: Boolean) {
        if (!BuildConfig.ALLOW_LOCAL_TESTING) return
        if (show) {
            binding.connectionLabUrlLayout.error = null
            binding.connectionLabUrlInput.setText(currentConfiguredUrl())
            binding.connectionLabOverlay.visibility = View.VISIBLE
            animateCard(binding.connectionLabCard)
        } else {
            binding.connectionLabOverlay.visibility = View.GONE
        }
    }

    private fun saveConnectionOverride() {
        val candidate = binding.connectionLabUrlInput.text?.toString()?.trim().orEmpty()
        if (!isValidUrl(candidate)) {
            binding.connectionLabUrlLayout.error = getString(R.string.status_connection_lab_invalid_url)
            return
        }

        binding.connectionLabUrlLayout.error = null
        if (candidate == AppConfig.GAME_URL) {
            preferences.edit { remove(KEY_CUSTOM_URL) }
        } else {
            preferences.edit { putString(KEY_CUSTOM_URL, candidate) }
        }

        pendingUrl = currentConfiguredUrl()
        updateHostLabels(pendingUrl)
        toggleConnectionLab(false)
        loadGame(forceReload = true)
    }

    private fun currentConfiguredUrl(): String {
        return if (BuildConfig.ALLOW_LOCAL_TESTING) {
            preferences.getString(KEY_CUSTOM_URL, null)?.takeIf { it.isNotBlank() } ?: AppConfig.GAME_URL
        } else {
            AppConfig.GAME_URL
        }
    }

    private fun resolveInternalHosts(): Set<String> {
        val dynamicHosts = listOf(currentConfiguredUrl(), pendingUrl).mapNotNull { extractHost(it) }.toSet()
        return AppConfig.INTERNAL_HOSTS + dynamicHosts
    }

    private fun updateHostLabels(url: String) {
        val hostLabel = extractHostLabel(url)
        binding.loadingHostValue.text = hostLabel
        binding.errorHostValue.text = hostLabel
    }

    private fun extractHostLabel(url: String): String = extractHost(url) ?: url

    private fun extractHost(url: String): String? {
        return try {
            URI(url).host?.removePrefix("www.")
        } catch (_: Exception) {
            null
        }
    }

    private fun animateCard(view: View) {
        view.alpha = 0f
        view.translationY = 24f
        view.animate().alpha(1f).translationY(0f).setDuration(180).start()
    }

    private fun isValidUrl(candidate: String): Boolean {
        return try {
            val uri = URI(candidate)
            uri.host != null && uri.scheme?.lowercase() in setOf("http", "https")
        } catch (_: Exception) {
            false
        }
    }

    private fun isOnline(): Boolean {
        val connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    private fun openExternalUri(uri: Uri): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW, uri).apply { addCategory(Intent.CATEGORY_BROWSABLE) }
            startActivity(intent)
            true
        } catch (_: ActivityNotFoundException) {
            false
        }
    }

    private fun applyEdgeToEdgePadding() {
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
            
            // Apply margins to the overlay containers which ARE direct children of the root FrameLayout
            val overlays = listOf(binding.loadingOverlay, binding.errorOverlay, binding.connectionLabOverlay)
            overlays.forEach { overlay ->
                overlay.updateLayoutParams<FrameLayout.LayoutParams> {
                    topMargin = insets.top
                    bottomMargin = insets.bottom
                    leftMargin = insets.left
                    rightMargin = insets.right
                }
            }
            windowInsets
        }
    }

    private fun enterImmersiveMode() {
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.hide(WindowInsetsCompat.Type.systemBars())
        controller.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        // Note: Manual status/navigation bar colors are deprecated in API 35
        // as the system enforces edge-to-edge.
    }

    companion object {
        private const val KEY_INITIAL_PAGE_LOADED = "initial_page_loaded"
        private const val KEY_PENDING_URL = "pending_url"
        private const val KEY_CUSTOM_URL = "custom_url"
        private const val PREFS_NAME = "cyber_hax_app_prefs"
    }
}
