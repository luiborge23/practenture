package com.practenture.android.network

import com.practenture.android.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import com.practenture.android.security.InMemoryTokenStore
import com.practenture.android.security.TokenStore

object ApiFactory {
    fun create(baseUrl: String = BuildConfig.PRACTENTURE_BASE_URL, token: String? = null): PractentureApi =
        createAuthenticated(baseUrl, InMemoryTokenStore(accessToken = token))

    fun createAuthenticated(baseUrl: String, tokenStore: TokenStore): PractentureApi {
        val clientBuilder = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val builder = chain.request().newBuilder().header("Accept", "application/json")
                tokenStore.accessToken?.takeIf { it.isNotBlank() }
                    ?.let { builder.header("Authorization", "Bearer $it") }
                chain.proceed(builder.build())
            }
            .authenticator { _, response -> refreshAndRetry(baseUrl, tokenStore, response) }
        if (BuildConfig.DEBUG) {
            clientBuilder.addInterceptor(
                HttpLoggingInterceptor().apply {
                    redactHeader("Authorization")
                    level = HttpLoggingInterceptor.Level.BASIC
                }
            )
        }
        val client = clientBuilder.build()
        return Retrofit.Builder().baseUrl(baseUrl).client(client)
            .addConverterFactory(GsonConverterFactory.create()).build().create(PractentureApi::class.java)
    }

    private fun refreshAndRetry(baseUrl: String, tokenStore: TokenStore, response: Response): Request? {
        if (response.request.url.encodedPath.endsWith("/api/auth/refresh") || responseCount(response) > 1) {
            return null
        }
        val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")
        synchronized(tokenStore) {
            val currentToken = tokenStore.accessToken
            if (!currentToken.isNullOrBlank() && currentToken != failedToken) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $currentToken")
                    .build()
            }
            val refreshToken = tokenStore.refreshToken?.takeIf { it.isNotBlank() } ?: return null
            val refreshService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(
                    OkHttpClient.Builder().addInterceptor { chain ->
                        chain.proceed(chain.request().newBuilder().header("Accept", "application/json").build())
                    }.build()
                )
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(RefreshService::class.java)
            val refreshResponse = try {
                refreshService.refresh(RefreshTokenRequest(refreshToken)).execute()
            } catch (_: Exception) {
                return null
            }
            if (!refreshResponse.isSuccessful) {
                if (refreshResponse.code() in setOf(400, 401, 403)) tokenStore.clear()
                refreshResponse.errorBody()?.close()
                return null
            }
            val refreshed = refreshResponse.body() ?: return null
            tokenStore.accessToken = refreshed.accessToken
            tokenStore.refreshToken = refreshed.refreshToken
            return response.request.newBuilder()
                .header("Authorization", "Bearer ${refreshed.accessToken}")
                .build()
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count += 1
            prior = prior.priorResponse
        }
        return count
    }

    private interface RefreshService {
        @POST("api/auth/refresh")
        fun refresh(@Body request: RefreshTokenRequest): retrofit2.Call<RefreshTokenResponse>
    }
}
