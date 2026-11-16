// How the Android app is put together.
//
// The big idea: we do NOT rewrite the salon app. The same Python files and the
// same screens from the laptop version are copied into the app as they are,
// and a plugin called Chaquopy runs Python inside the phone.

plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "com.inkwinklabs.salon"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.inkwinklabs.salon"
        minSdk = 24          // Android 7 and newer: nearly every phone in use
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        // Which processor types to include Python for:
        // arm64-v8a = real phones, x86_64 = the emulator on a laptop.
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }
}

// ---- The laptop app's files, copied in unchanged ----
// Only what the app needs: no tests, no laptop launcher, and never .env or data/.
val pythonApp = layout.buildDirectory.dir("python-app")
val copyPythonApp = tasks.register<Sync>("copyPythonApp") {
    from(rootProject.file("..")) {
        include("*.py", "settings.toml", "scripts/*.py", "static/**")
        exclude("start.py")
    }
    into(pythonApp)
}

chaquopy {
    defaultConfig {
        version = "3.14"                      // same Python as the laptop
        pip {
            // The same libraries as requirements.txt, minus `anthropic`, which
            // has no Android build yet (claude_http.py stands in for it).
            install("flask>=3.1,<4")
            install("waitress>=3.0,<4")
            install("python-dotenv>=1.2,<2")
        }
    }
    sourceSets {
        getByName("main") { srcDir(pythonApp.get().asFile) }
    }
}

// Copy the Python files before anything else in the build looks for them.
tasks.configureEach {
    if (name == "preBuild" || (name.startsWith("merge") && name.contains("Python"))) dependsOn(copyPythonApp)
}
