package com.goreecloud.database

import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.security.MessageDigest

private data class ObjectItem(
    val id: String,
    val filename: String,
    val size: Int,
    val mediaType: String,
    val sha256: String,
)

private val safeObjectFilename = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

/**
 * Native read-only small-object browser. The user chooses the destination
 * through Android's Storage Access Framework; no broad storage permissions
 * or persistent credentials are requested.
 */
@Composable
internal fun ObjectBrowser(client: DatabaseClient, onClose: () -> Unit) {
    val context: Context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var objects by remember { mutableStateOf(listOf<ObjectItem>()) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var pending by remember { mutableStateOf<ObjectItem?>(null) }

    val saveDocument = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/octet-stream"),
    ) { target ->
        val item = pending
        pending = null
        if (target != null && item != null) {
            busy = true
            message = ""
            coroutineScope.launch {
                try {
                    withContext(Dispatchers.IO) {
                        val bytes = client.downloadObject(item.id)
                        if (bytes.size != item.size || bytes.size > 1_048_576) {
                            throw IllegalStateException("Object size verification failed")
                        }
                        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
                            .joinToString("") { byte -> (byte.toInt() and 0xff).toString(16).padStart(2, '0') }
                        if (digest != item.sha256) throw IllegalStateException("Object checksum verification failed")
                        val stream = context.contentResolver.openOutputStream(target, "w")
                            ?: throw IllegalStateException("Could not open selected destination")
                        stream.use { it.write(bytes) }
                    }
                    message = "Saved the selected object."
                } catch (e: Exception) {
                    message = e.message ?: "Could not save object."
                } finally {
                    busy = false
                }
            }
        }
    }

    fun refresh() {
        if (busy) return
        busy = true
        message = ""
        coroutineScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { client.get("/v1/objects?limit=50") }
                val array = result.getJSONArray("objects")
                objects = (0 until array.length()).map { index ->
                    val row = array.getJSONObject(index)
                    ObjectItem(
                        id = row.getString("id"),
                        filename = row.getString("filename"),
                        size = row.getInt("size_bytes"),
                        mediaType = row.getString("media_type"),
                        sha256 = row.getString("sha256"),
                    )
                }
            } catch (e: Exception) {
                message = e.message ?: "Unable to load objects"
                objects = emptyList()
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(client) { refresh() }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onClose) { Text("← Tables") }
            TextButton(onClick = { refresh() }, enabled = !busy) { Text("Refresh objects") }
        }
        Text("Small objects", style = MaterialTheme.typography.titleLarge)
        Text("Private schema · max 1 MiB · every viewer token can access these files",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(12.dp))
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (message.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Text(message, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(10.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(objects, key = { it.id }) { item ->
                ElevatedCard(onClick = {
                    if (!busy && safeObjectFilename.matches(item.filename)) {
                        pending = item
                        saveDocument.launch(item.filename)
                    }
                }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(15.dp)) {
                        Text(item.filename, style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(4.dp))
                        Text("${item.size} bytes · ${item.mediaType}", style = MaterialTheme.typography.bodySmall)
                        Text("Tap to save to a location you choose", style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}
