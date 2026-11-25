package com.goreecloud.database

import android.os.Bundle
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
import androidx.compose.ui.graphics.Color
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

private val Canvas = Color(0xFF0D121D)
private val Surface = Color(0xFF171D2A)
private val Brand = Color(0xFFBFB8FF)
private val OnBrand = Color(0xFF272057)
private val SoftText = Color(0xFFCED5E5)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(
                primary = Brand,
                onPrimary = OnBrand,
                background = Canvas,
                surface = Surface,
                onSurface = Color(0xFFF2F4FB),
            )) {
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
}

@Composable
private fun DatabaseScreen() {
    var endpoint by remember { mutableStateOf("") }
    var inputToken by remember { mutableStateOf("") }
    // Never persisted through rememberSaveable, local preferences, backup or logcat.
    var client by remember { mutableStateOf<DatabaseClient?>(null) }
    var tableNames by remember { mutableStateOf(listOf<String>()) }
    var showObjects by remember { mutableStateOf(false) }
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
        Text("GOREECLOUD · SELF-HOSTED", color = Brand, style = MaterialTheme.typography.labelSmall)
        Spacer(Modifier.height(12.dp))
        Text("Database", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("Native management preview", color = SoftText, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(20.dp))
        if (client == null) {
            OutlinedTextField(value = endpoint, onValueChange = { endpoint = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text("HTTPS API base URL") }, singleLine = true, placeholder = { Text("https://db.example/api") })
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(value = inputToken, onValueChange = { inputToken = it }, modifier = Modifier.fillMaxWidth(),
                label = { Text("Admin or viewer token") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
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
                    tableNames = emptyList()
                    tableRows = emptyList()
                    error = ""
                }) { Text("Disconnect") }
            }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
            if (showObjects) {
                client?.let { current -> ObjectBrowser(client = current, onClose = { showObjects = false }) }
            } else if (chosenTable == null) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Tables", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = { showObjects = true }, enabled = !busy) { Text("Small objects") }
                }
                Spacer(Modifier.height(10.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(tableNames) { table ->
                        ElevatedCard(onClick = { loadTable(table) }, modifier = Modifier.fillMaxWidth()) {
                            Text(table, modifier = Modifier.padding(20.dp), fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            } else {
                TextButton(onClick = { chosenTable = null }) { Text("← All tables") }
                Text(chosenTable ?: "", style = MaterialTheme.typography.titleLarge)
                TextButton(onClick = { chosenTable?.let { loadTable(it) } }, enabled = !busy) {
                    Text("Refresh rows")
                }
                Spacer(Modifier.height(10.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(tableRows) { row ->
                        Card(shape = RoundedCornerShape(18.dp)) {
                            Column(Modifier.padding(16.dp)) {
                                columns.forEach { col ->
                                    Text(col, color = Brand, style = MaterialTheme.typography.labelSmall)
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
