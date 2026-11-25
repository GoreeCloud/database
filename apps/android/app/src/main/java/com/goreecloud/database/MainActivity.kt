package com.goreecloud.database

import android.os.Bundle
import android.animation.ValueAnimator
import com.goreecloud.ui.material3.GoreeCloudExpressiveTheme
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.URL
import java.io.ByteArrayOutputStream
import javax.net.ssl.HttpsURLConnection

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            GoreeCloudExpressiveTheme(
                dynamicWallpaperColors = false,
                reduceMotion = !ValueAnimator.areAnimatorsEnabled()
            ) {
                DatabaseScreen()
            }
        }
    }
}

/** Requires an authorized HTTPS gateway; plaintext connections are intentionally blocked. */
internal class DatabaseClient(private val endpoint: String, private val secret: String) {
    private val base = endpoint.trim().trimEnd('/')
    init {
        val url = URL(base)
        require(url.protocol == "https" && !url.host.isNullOrBlank() && url.userInfo == null && url.query == null && url.ref == null) {
            "Enter an HTTPS management URL (for example https://db.example/api)"
        }
        require(secret.isNotBlank()) { "Administration token is required" }
    }
    fun get(relative: String): JSONObject {
        val connection = URL(base + relative).openConnection() as HttpsURLConnection
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.instanceFollowRedirects = false
        connection.requestMethod = "GET"
        connection.setRequestProperty("Authorization", "Bearer $secret")
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Cache-Control", "no-store")
        try {
            if (connection.responseCode !in 200..299) {
                throw IllegalStateException("Request failed (HTTP ${connection.responseCode})")
            }
            return JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
        } finally {
            connection.disconnect()
        }
    }

    fun createPersonalNote(title: String, content: String) {
        val cleanedTitle = title.trim()
        val cleanedContent = content.trim()
        require(cleanedTitle.length in 1..120 && cleanedContent.length in 1..2048 &&
            cleanedContent.toByteArray(Charsets.UTF_8).size <= 8192) {
            "Private note title or content exceeds preview limits"
        }
        // Owner subject comes ONLY from the backend's signature-verified JWT;
        // never include a caller-supplied owner in the JSON payload.
        val body = JSONObject().put("title", cleanedTitle).put("content", cleanedContent)
            .toString().toByteArray(Charsets.UTF_8)
        val connection = URL(base + "/v1/me/notes").openConnection() as HttpsURLConnection
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.instanceFollowRedirects = false
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer $secret")
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Cache-Control", "no-store")
        try {
            connection.outputStream.use { it.write(body) }
            if (connection.responseCode != 201) {
                throw IllegalStateException(
                    "Private note write unavailable (HTTP ${connection.responseCode}); a scoped OIDC token is required"
                )
            }
        } finally {
            connection.disconnect()
        }
    }

    fun downloadObject(id: String): ByteArray {
        val objectId = java.util.UUID.fromString(id)
        val connection = URL(base + "/v1/objects/" + objectId).openConnection() as HttpsURLConnection
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.instanceFollowRedirects = false
        connection.requestMethod = "GET"
        connection.setRequestProperty("Authorization", "Bearer $secret")
        connection.setRequestProperty("Accept", "application/octet-stream")
        connection.setRequestProperty("Cache-Control", "no-store")
        try {
            if (connection.responseCode !in 200..299) {
                throw IllegalStateException("Download failed (HTTP ${connection.responseCode})")
            }
            if (connection.contentLengthLong > 1_048_576L) {
                throw IllegalStateException("Object exceeds 1 MiB")
            }
            val output = ByteArrayOutputStream()
            connection.inputStream.use { stream ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    if (output.size() + count > 1_048_576) {
                        throw IllegalStateException("Object exceeds 1 MiB")
                    }
                    output.write(buffer, 0, count)
                }
            }
            return output.toByteArray()
        } finally {
            connection.disconnect()
        }
    }

    fun downloadCsvPage(table: String): ByteArray {
        require(Regex("^[a-z_][a-z0-9_]{0,62}$").matches(table)) {
            "Unsupported table identifier"
        }
        val connection = URL(base + "/v1/tables/app/" + table + "/export.csv?limit=25&offset=0")
            .openConnection() as HttpsURLConnection
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.instanceFollowRedirects = false
        connection.requestMethod = "GET"
        connection.setRequestProperty("Authorization", "Bearer $secret")
        connection.setRequestProperty("Accept", "text/csv")
        connection.setRequestProperty("Cache-Control", "no-store")
        try {
            if (connection.responseCode !in 200..299) {
                throw IllegalStateException("CSV export unavailable (HTTP ${connection.responseCode})")
            }
            if (!connection.contentType.orEmpty().startsWith("text/csv")) {
                throw IllegalStateException("Unexpected CSV response type")
            }
            if (connection.contentLengthLong > 2_097_152L) {
                throw IllegalStateException("CSV export exceeds 2 MiB")
            }
            val output = ByteArrayOutputStream()
            connection.inputStream.use { stream ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    if (output.size() + count > 2_097_152) {
                        throw IllegalStateException("CSV export exceeds 2 MiB")
                    }
                    output.write(buffer, 0, count)
                }
            }
            return output.toByteArray()
        } finally {
            connection.disconnect()
        }
    }
}

@Composable
private fun DatabaseScreen() {
    var endpoint by remember { mutableStateOf("") }
    var inputToken by remember { mutableStateOf("") }
    // Never persisted through rememberSaveable, local preferences, backup or logcat.
    var client by remember { mutableStateOf<DatabaseClient?>(null) }
    var tableNames by remember { mutableStateOf(listOf<String>()) }
    var showObjects by remember { mutableStateOf(false) }
    var showPersonal by remember { mutableStateOf(false) }
    var showSchema by remember { mutableStateOf(false) }
    var chosenTable by remember { mutableStateOf<String?>(null) }
    var columns by remember { mutableStateOf(listOf<String>()) }
    var tableRows by remember { mutableStateOf(listOf<Map<String, String>>()) }
    var error by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun connect() {
        val next = try {
            DatabaseClient(endpoint, inputToken)
        } catch (e: IllegalArgumentException) {
            error = e.message ?: "Invalid endpoint"
            return
        }
        client = next
        inputToken = ""
        busy = true
        error = ""
        scope.launch {
            try {
                val result = withContext(Dispatchers.IO) { next.get("/v1/tables") }
                val arr = result.getJSONArray("tables")
                tableNames = (0 until arr.length()).map { arr.getJSONObject(it).getString("name") }
                chosenTable = null
                showObjects = false
                showPersonal = false
                showSchema = false
            } catch (e: Exception) {
                error = e.message ?: "Could not connect"
            } finally {
                busy = false
            }
        }
    }

    fun loadTable(name: String) {
        val current = client ?: return
        chosenTable = name
        showSchema = false
        busy = true
        error = ""
        scope.launch {
            try {
                val result = withContext(Dispatchers.IO) { current.get("/v1/tables/app/$name/rows?limit=25") }
                val cols = result.getJSONArray("columns")
                val values = result.getJSONArray("rows")
                columns = (0 until cols.length()).map { cols.getString(it) }
                tableRows = (0 until values.length()).map { i ->
                    val item = values.getJSONObject(i)
                    columns.associateWith { key -> if (item.isNull(key)) "NULL" else item.optString(key) }
                }
            } catch (e: Exception) {
                error = e.message ?: "Unable to load rows"
                tableRows = emptyList()
            } finally {
                busy = false
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(20.dp)) {
        Text("GOREECLOUD · SELF-HOSTED", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall)
        Spacer(Modifier.height(12.dp))
        Text("Database", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("Native management preview", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(20.dp))
        if (client == null) {
            OutlinedTextField(value = endpoint, onValueChange = { endpoint = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text("HTTPS API base URL") }, singleLine = true, placeholder = { Text("https://db.example/api") })
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(value = inputToken, onValueChange = { inputToken = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text("Admin, viewer, or signed OIDC token") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
            Spacer(Modifier.height(16.dp))
            Button(onClick = { connect() }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Connect securely") }
            Spacer(Modifier.height(14.dp))
            Text("Only HTTPS connections are permitted. Configure a trusted TLS gateway before connecting a phone. Credentials remain in memory.", color = SoftText)
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("app schema", style = MaterialTheme.typography.titleMedium)
                TextButton(onClick = {
                    client = null
                    chosenTable = null
                    showObjects = false
                    showPersonal = false
                    showSchema = false
                    tableNames = emptyList()
                    tableRows = emptyList()
                    error = ""
                }) { Text("Disconnect") }
            }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
            if (showPersonal) {
                client?.let { current -> PersonalNotesBrowser(client = current, onClose = { showPersonal = false }) }
            } else if (showObjects) {
                client?.let { current -> ObjectBrowser(client = current, onClose = { showObjects = false }) }
            } else if (chosenTable == null) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Tables", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = { showObjects = true }, enabled = !busy) { Text("Small objects") }
                }
                TextButton(onClick = { showPersonal = true }, enabled = !busy) {
                    Text("Personal notes (signed OIDC)")
                }
                Spacer(Modifier.height(10.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(tableNames) { table ->
                        ElevatedCard(onClick = { loadTable(table) }, modifier = Modifier.fillMaxWidth()) {
                            Text(table, modifier = Modifier.padding(20.dp), fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            } else if (showSchema) {
                val current = client
                val table = chosenTable
                if (current != null && table != null) {
                    SchemaBrowser(client = current, table = table, onClose = { showSchema = false })
                }
            } else {
                TextButton(onClick = { chosenTable = null; showSchema = false }) { Text("← All tables") }
                Text(chosenTable ?: "", style = MaterialTheme.typography.titleLarge)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { chosenTable?.let { loadTable(it) } }, enabled = !busy) {
                        Text("Refresh rows")
                    }
                    TextButton(onClick = { showSchema = true }, enabled = !busy) {
                        Text("Inspect schema")
                    }
                }
                chosenTable?.let { name -> client?.let { active ->
                    CsvExportButton(client = active, table = name)
                } }
                Spacer(Modifier.height(10.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(tableRows) { row ->
                        Card(shape = RoundedCornerShape(18.dp)) {
                            Column(Modifier.padding(16.dp)) {
                                columns.forEach { col ->
                                    Text(col, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall)
                                    Text(row[col] ?: "NULL", style = MaterialTheme.typography.bodyMedium)
                                    Spacer(Modifier.height(9.dp))
                                }
                            }
                        }
                    }
                }
            }
        }
        if (error.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}
