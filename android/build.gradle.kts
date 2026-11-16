// Versions of the two build plugins, in one place.
plugins {
    id("com.android.application") version "9.5.1" apply false   // builds Android apps (Kotlin included)
    id("com.chaquo.python") version "17.2.0" apply false        // Chaquopy: puts Python inside the app
}
