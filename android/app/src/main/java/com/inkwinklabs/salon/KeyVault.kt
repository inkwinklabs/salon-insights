package com.inkwinklabs.salon

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Keeps the owner's Claude API key safe on the phone.
 *
 * On the laptop the key sits in a private .env file. A phone has no such file,
 * so we use the Android Keystore: Android makes a secret lock that never
 * leaves the phone's secure hardware, and we use it to scramble (encrypt) the
 * API key before saving it. Even someone who copies the saved file gets nonsense.
 *
 * The key is never written to the log and never shown on screen.
 */
object KeyVault {
    private const val LOCK_NAME = "salon_ai_key_lock"
    private const val FILE = "ai_key"
    private lateinit var appContext: Context

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    /** The lock itself. Created the first time, then reused. */
    private fun lock(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(LOCK_NAME, null) as? SecretKey)?.let { return it }
        val maker = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        maker.init(
            KeyGenParameterSpec.Builder(LOCK_NAME, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return maker.generateKey()
    }

    /** Scramble and save the API key. An empty key removes it. Called from Python (android_main.py). */
    @JvmStatic
    fun save(apiKey: String) {
        val prefs = appContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        if (apiKey.isEmpty()) {
            prefs.edit().clear().apply()
            return
        }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, lock()) }
        val scrambled = cipher.doFinal(apiKey.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString("data", Base64.encodeToString(scrambled, Base64.NO_WRAP))
            .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .apply()
    }

    /** The saved API key, or "" if there isn't one (or it can't be unlocked any more). */
    fun load(): String {
        val prefs = appContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val data = prefs.getString("data", null) ?: return ""
        val iv = prefs.getString("iv", null) ?: return ""
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, lock(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
            String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (e: Exception) {
            ""   // e.g. the app's data was restored onto a different phone: ask for the key again
        }
    }
}
