package com.practenture.android

import com.practenture.android.data.PractentureRepository
import com.practenture.android.network.ApiFactory
import com.practenture.android.network.PlayerDecision
import com.google.gson.JsonParser
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import java.util.concurrent.TimeUnit

class BackendAuthoritativeContractTest {
    private lateinit var server: MockWebServer
    private lateinit var repository: PractentureRepository

    @Before
    fun setUp() {
        server = MockWebServer().also { it.start() }
        repository = PractentureRepository(ApiFactory.create(server.url("/").toString()))
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun loginDecodesBackendCamelCaseResponse() = runTest {
        enqueueJson(
            """{
                "accessToken":"access-123","refreshToken":"refresh-456","tokenType":"bearer",
                "role":"student","userId":"student-7","mfaRequired":false,
                "mustChangePassword":true,"professorCodeRequired":false
            }""".trimIndent()
        )

        val login = repository.login("student7", "secret")

        assertEquals("access-123", login.accessToken)
        assertEquals("refresh-456", login.refreshToken)
        assertEquals("bearer", login.tokenType)
        assertEquals("student", login.role)
        assertEquals("student-7", login.userId)
        assertFalse(login.mfaRequired)
        assertTrue(login.mustChangePassword)
        assertFalse(login.professorCodeRequired)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/auth/login", request.path)
        val body = JsonParser.parseString(request.body.readUtf8()).asJsonObject
        assertEquals("password", body["provider"].asString)
        assertEquals("student7", body["username"].asString)
        assertEquals("secret", body["password"].asString)
    }

    @Test
    fun joinPreservesBackendAuthoritativeTeamNameAndIdForSubmission() = runTest {
        enqueueJson(
            """{"teamId":"backend-team-42","teamName":"Backend Canonical Name","round":3,"state":"active"}"""
        )
        server.enqueue(MockResponse().setResponseCode(204))

        val joined = repository.join("biz-test", "Client Draft Name", "student-7")
        assertEquals("backend-team-42", joined.teamId)
        assertEquals("Backend Canonical Name", joined.teamName)
        assertEquals(3, joined.round)

        val joinRequest = server.takeRequest()
        assertEquals("PUT", joinRequest.method)
        assertEquals("/api/sessions/BIZ-TEST/join", joinRequest.path)
        assertEquals(
            "Client Draft Name",
            JsonParser.parseString(joinRequest.body.readUtf8()).asJsonObject["teamName"].asString
        )

        val response = repository.submit("biz-test", joined.round, joined.teamName, PlayerDecision())
        assertTrue(response.isSuccessful)
        val submitBody = JsonParser.parseString(server.takeRequest().body.readUtf8()).asJsonObject
        assertEquals("Backend Canonical Name", submitBody["teamId"].asString)
    }

    @Test
    fun submitSendsCompleteModernPlayerDecision() = runTest {
        server.enqueue(MockResponse().setResponseCode(204))
        val decision = PlayerDecision(
            wholesalePrice = 81.0,
            internetPrice = 92.0,
            amazonPrice = 87.0,
            privateLabelBidPrice = 46.0,
            privateLabelMaxUnits = 51,
            amazonAdBudget = 101.0,
            materialsQuality = "superior",
            stylingBudget = 3001.0,
            modelsOffered = 4,
            tqmInvestment = 2001.0,
            advertisingBudget = 8001.0,
            celebrityEndorsement = "local",
            retailOutlets = 21,
            mailInRebate = 2.0,
            deliveryTime = "fast",
            freeShippingThreshold = 99.0,
            tiktokBudget = 11.0,
            instagramBudget = 12.0,
            youtubeBudget = 13.0,
            influencerTier = "micro",
            baseWage = 25001.0,
            incentivePay = 0.6,
            trainingHours = 21.0,
            bestPracticesInvestment = 1001.0,
            productionQuantity = 201,
            overtimePercent = 1.0,
            csrInvestment = 2002.0,
            dividendsPerShare = 0.6,
            newLoanAmount = 100.0,
            sharesBuyback = 2,
            sharesIssued = 3,
            fulfillmentMethod = "fba"
        )

        val response = repository.submit("biz-modern", 4, "Canonical Team", decision)

        assertTrue(response.isSuccessful)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/sessions/BIZ-MODERN/submit_decision", request.path)
        val root = JsonParser.parseString(request.body.readUtf8()).asJsonObject
        assertEquals(4, root["round"].asInt)
        assertEquals("Canonical Team", root["teamId"].asString)
        val sent = root["decision"].asJsonObject
        val expectedModernFields = setOf(
            "wholesalePrice", "internetPrice", "amazonPrice", "privateLabelBidPrice",
            "privateLabelMaxUnits", "amazonAdBudget", "materialsQuality", "stylingBudget",
            "modelsOffered", "tqmInvestment", "advertisingBudget", "celebrityEndorsement",
            "retailOutlets", "mailInRebate", "deliveryTime", "freeShippingThreshold",
            "tiktokBudget", "instagramBudget", "youtubeBudget", "influencerTier", "baseWage",
            "incentivePay", "trainingHours", "bestPracticesInvestment", "productionQuantity",
            "overtimePercent", "csrInvestment", "dividendsPerShare", "newLoanAmount",
            "sharesBuyback", "sharesIssued", "fulfillmentMethod"
        )
        assertEquals(expectedModernFields, sent.keySet())
        assertEquals(81.0, sent["wholesalePrice"].asDouble, 0.0)
        assertEquals("superior", sent["materialsQuality"].asString)
        assertEquals(4, sent["modelsOffered"].asInt)
        assertEquals("local", sent["celebrityEndorsement"].asString)
        assertEquals(21.0, sent["trainingHours"].asDouble, 0.0)
        assertEquals(201, sent["productionQuantity"].asInt)
        assertEquals("fba", sent["fulfillmentMethod"].asString)
        assertFalse(sent.has("numModels"))
        assertFalse(sent.has("celebrityType"))
        assertFalse(sent.has("trainingBudget"))
        assertFalse(sent.has("socialMediaBudget"))
    }

    @Test
    fun statusUsesBearerAuthentication() = runTest {
        val authenticatedRepository = PractentureRepository(
            ApiFactory.create(server.url("/").toString(), "jwt-status-token")
        )
        enqueueJson(
            """{
                "sessionId":"session-1","code":"BIZ-AUTH","state":"active","currentRound":2,
                "totalRounds":8,"teamsSubmitted":3,"totalTeams":4
            }""".trimIndent()
        )

        val status = authenticatedRepository.status("biz-auth")

        assertEquals(2, status.currentRound)
        val request = server.takeRequest()
        assertEquals("GET", request.method)
        assertEquals("/api/sessions/BIZ-AUTH/status", request.path)
        assertEquals("Bearer jwt-status-token", request.getHeader("Authorization"))
        assertEquals("application/json", request.getHeader("Accept"))
    }

    @Test
    fun professorProcessRoundCallsAtomicEndpointExactlyOnceAndNeverAdvance() = runTest {
        enqueueJson(
            """{
                "round":1,
                "results":[{
                    "teamId":"Backend Canonical Name","round":1,"awarenessScore":0.8,
                    "profit":1234.5,"demand":{"totalSold":100.0}
                }]
            }""".trimIndent()
        )

        val result = repository.processRoundAsProfessor("biz-test")

        assertEquals(1, result.round)
        assertEquals(0.8, result.results.single().awarenessScore, 0.0001)
        assertEquals(1234.5, result.results.single().profit, 0.0001)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/sessions/BIZ-TEST/process_round", request.path)
        assertEquals(1, server.requestCount)
        assertNull(server.takeRequest(100, TimeUnit.MILLISECONDS))
        assertFalse(request.path.orEmpty().contains("advance", ignoreCase = true))
    }

    @Test
    fun resultsDecodeBackendJsonWithoutClientSimulation() = runTest {
        enqueueJson(
            """{
                "sessionId":"session-1","round":2,
                "results":[{"teamId":"Backend Team","round":2,"profit":999.5,"totalScore":77.25}]
            }""".trimIndent()
        )

        val results = repository.results("biz-results").asJsonObject

        assertEquals("session-1", results["sessionId"].asString)
        assertEquals(2, results["round"].asInt)
        assertEquals(999.5, results["results"].asJsonArray[0].asJsonObject["profit"].asDouble, 0.0)
        assertEquals("/api/sessions/BIZ-RESULTS/results", server.takeRequest().path)
    }

    @Test
    fun leaderboardDecodesBackendRankingAndMetrics() = runTest {
        enqueueJson(
            """{
                "sessionId":"session-1","round":2,
                "leaderboard":[{
                    "rank":1,"teamId":"team-1","teamName":"Backend Team","totalScore":91.2,
                    "eps":4.5,"roe":0.22,"stockPrice":123.4,"imageRating":8.7,"marketShare":0.31
                }]
            }""".trimIndent()
        )

        val response = repository.leaderboard("biz-board")

        assertEquals("session-1", response.sessionId)
        assertEquals(2, response.round)
        val leader = response.leaderboard.single()
        assertEquals(1, leader.rank)
        assertEquals("team-1", leader.teamId)
        assertEquals("Backend Team", leader.teamName)
        assertEquals(91.2, leader.totalScore, 0.0)
        assertEquals(8.7, leader.imageRating, 0.0)
        assertEquals("/api/sessions/BIZ-BOARD/leaderboard", server.takeRequest().path)
    }

    @Test
    fun loginHttpFailureSurfacesStatusAndErrorBody() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(401).setHeader("Content-Type", "application/json")
                .setBody("""{"detail":"Invalid credentials"}""")
        )

        val failure = try {
            repository.login("student7", "wrong")
            null
        } catch (error: HttpException) {
            error
        }

        assertNotNull("A 401 response must fail login", failure)
        failure!!
        assertEquals(401, failure.code())
        assertEquals("Invalid credentials", JsonParser.parseString(failure.response()!!.errorBody()!!.string()).asJsonObject["detail"].asString)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun submitHttpFailureRemainsUnsuccessfulAndIsNotRetried() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(422).setHeader("Content-Type", "application/json")
                .setBody("""{"detail":"Decision validation failed"}""")
        )

        val response = repository.submit("biz-test", 1, "Backend Team", PlayerDecision())

        assertFalse(response.isSuccessful)
        assertEquals(422, response.code())
        assertEquals("Decision validation failed", JsonParser.parseString(response.errorBody()!!.string()).asJsonObject["detail"].asString)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun malformedLoginJsonFailsInsteadOfInventingAuthenticationState() = runTest {
        enqueueJson("""{"accessToken":"partial"""")

        val failure = try {
            repository.login("student7", "secret")
            null
        } catch (error: Exception) {
            error
        }
        assertNotNull("Malformed login JSON must fail decoding", failure)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun malformedResultsJsonFailsInsteadOfReturningSyntheticResults() = runTest {
        enqueueJson("""{"results":[{"profit":12.0}]""")

        val failure = try {
            repository.results("biz-test")
            null
        } catch (error: Exception) {
            error
        }
        assertNotNull("Malformed results JSON must fail decoding", failure)
        assertEquals(1, server.requestCount)
    }

    private fun enqueueJson(body: String, responseCode: Int = 200) {
        server.enqueue(
            MockResponse().setResponseCode(responseCode)
                .setHeader("Content-Type", "application/json")
                .setBody(body)
        )
    }
}
