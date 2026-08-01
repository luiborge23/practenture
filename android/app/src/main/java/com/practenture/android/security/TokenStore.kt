package com.practenture.android.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

interface TokenStore {
    var accessToken: String?
    var refreshToken: String?
    fun clear()
}

class InMemoryTokenStore(
    override var accessToken: String? = null,
    override var refreshToken: String? = null,
) : TokenStore {
    override fun clear() {
        accessToken = null
        refreshToken = null
    }
}

/** Persists OAuth/JWT material encrypted by a non-exportable Android Keystore key. */
class SecureTokenStore(context: Context) : TokenStore {
    private val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }

    override var accessToken: String?
        @Synchronized get() = read(ACCESS_TOKEN)
        @Synchronized set(value) = write(ACCESS_TOKEN, value)

    override var refreshToken: String?
        @Synchronized get() = read(REFRESH_TOKEN)
        @Synchronized set(value) = write(REFRESH_TOKEN, value)

    @Synchronized
    override fun clear() {
        preferences.edit { clear() }
    }

    private fun secretKey(): SecretKey {
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).run {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setRandomizedEncryptionRequired(true)
                    .build()
            )
            generateKey()
        }
    }

    private fun write(name: String, value: String?) {
        if (value.isNullOrBlank()) {
            preferences.edit { remove(name) }
            return
        }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        cipher.updateAAD(name.toByteArray(StandardCharsets.UTF_8))
        val payload = cipher.iv + cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        preferences.edit { putString(name, Base64.encodeToString(payload, Base64.NO_WRAP)) }
    }

    private fun read(name: String): String? {
        val encoded = preferences.getString(name, null) ?: return null
        return try {
            val payload = Base64.decode(encoded, Base64.NO_WRAP)
            if (payload.size <= IV_LENGTH_BYTES) error("Invalid encrypted token")
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                secretKey(),
                GCMParameterSpec(TAG_LENGTH_BITS, payload.copyOfRange(0, IV_LENGTH_BYTES)),
            )
            cipher.updateAAD(name.toByteArray(StandardCharsets.UTF_8))
            String(cipher.doFinal(payload.copyOfRange(IV_LENGTH_BYTES, payload.size)), StandardCharsets.UTF_8)
        } catch (_: Exception) {
            preferences.edit { remove(name) }
            null
        }
    }

    private companion object {
        const val PREFERENCES = "practenture_secure_tokens"
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "practenture.auth.tokens.v1"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val ACCESS_TOKEN = "access_token"
        const val REFRESH_TOKEN = "refresh_token"
        const val IV_LENGTH_BYTES = 12
        const val TAG_LENGTH_BITS = 128
    }
}
