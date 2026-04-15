package com.cyberhax.game

object AppConfig {
    // Change this to your permanent live game URL before release if needed.
    const val GAME_URL = "https://cyber-hax-server.onrender.com"
    const val LOCAL_EMULATOR_URL = "http://10.0.2.2:8000/"
    const val LOCAL_DEVICE_URL_TEMPLATE = "http://192.168.1.100:8000/"

    // Internal hosts stay inside the app; everything else opens externally.
    val INTERNAL_HOSTS = setOf(
        "cyber-hax.netlify.app",
        "cyber-hax-server.onrender.com",
        "www.google.com",
        "google.com"
    )
}
