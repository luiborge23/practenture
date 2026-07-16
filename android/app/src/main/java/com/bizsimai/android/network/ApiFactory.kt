package com.bizsimai.android.network

import com.bizsimai.android.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiFactory {
    fun create(baseUrl: String = BuildConfig.BIZSIMAI_BASE_URL, token: String? = null): BizSimApi {
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val builder = chain.request().newBuilder().header("Accept", "application/json")
                token?.takeIf { it.isNotBlank() }?.let { builder.header("Authorization", "Bearer $it") }
                chain.proceed(builder.build())
            }
            .addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
            .build()
        return Retrofit.Builder().baseUrl(baseUrl).client(client)
            .addConverterFactory(GsonConverterFactory.create()).build().create(BizSimApi::class.java)
    }
}
