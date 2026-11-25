package com.goreecloud.database

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private data class PersonalNote(
    val id: String,
    val title: String,
    val content: String,
    val timestamp: String
)

/** Never uses preferences, storage permissions, offline caches or user-controlled owner IDs. */
@Composable
internal fun PersonalNotesBrowser(client: DatabaseClient, onClose: () -> Unit) {
    var notes by remember(client) { mutableStateOf(listOf<PersonalNote>()) }
    var title by remember(client) { mutableStateOf("") }
    var content by remember(client) { mutableStateOf("") }
    var edit by remember(client) { mutableStateOf(false) }
    var busy by remember(client) { mutableStateOf(false) }
    var error by remember(client) { mutableStateOf("") }
    var status by remember(client) { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    fun refresh() {
        if (busy) return
        busy = true
        error = ""
        status = ""
        scope.launch {
            try {
                val response = withContext(Dispatchers.IO) { client.get("/v1/me/notes?limit=25") }
                val data = response.getJSONArray("notes")
                notes = (0 until data.length()).map { index ->
                    val entry = data.getJSONObject(index)
                    PersonalNote(
                        id = entry.getString("id"),
                        title = entry.getString("title"),
                        content = entry.getString("content"),
                        timestamp = entry.getString("created_at")
                    )
                }
            } catch (failure: Exception) {
                notes = emptyList()
                error = if (failure.message.orEmpty().contains("401")) {
                    "Private notes require a short-lived, signed OIDC access token, not a shared admin/viewer token."
                } else "Unable to load private notes (" + (failure.message ?: "request failed") + ")"
            } finally {
                busy = false
            }
        }
    }

    fun save() {
        if (busy || title.isBlank() || content.isBlank()) return
        if (title.length > 120 || content.length > 2048 ||
            content.toByteArray(Charsets.UTF_8).size > 8192) {
            error = "Private note exceeds 120 title characters or 2048 body characters."
            return
        }
        busy = true
        error = ""
        status = ""
        scope.launch {
            try {
                withContext(Dispatchers.IO) { client.createPersonalNote(title, content) }
                title = ""
                content = ""
                edit = false
                status = "Note saved to the subject-isolated database."
                val result = withContext(Dispatchers.IO) { client.get("/v1/me/notes?limit=25") }
                val data = result.getJSONArray("notes")
                notes = (0 until data.length()).map { index ->
                    val entry = data.getJSONObject(index)
                    PersonalNote(
                        id = entry.getString("id"),
                        title = entry.getString("title"),
                        content = entry.getString("content"),
                        timestamp = entry.getString("created_at")
                    )
                }
            } catch (failure: Exception) {
                error = failure.message ?: "Unable to save the private note."
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(client) { refresh() }

    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = {
                notes = emptyList()
                title = ""
                content = ""
                onClose()
            }) { Text("← Tables") }
            TextButton(onClick = { refresh() }, enabled = !busy) { Text("Refresh") }
        }
        Text("Personal notes", style = MaterialTheme.typography.titleLarge)
        Text(
            "Signed OIDC only · subject-isolated · no device storage",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(10.dp))
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall)
        if (status.isNotEmpty()) Text(status, style = MaterialTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = { edit = !edit }, enabled = !busy && error.isEmpty()) {
                Text(if (edit) "Cancel editor" else "Create note")
            }
        }
        if (edit) {
            OutlinedTextField(
                value = title,
                onValueChange = { if (it.length <= 120) title = it },
                label = { Text("Title") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = content,
                onValueChange = { if (it.length <= 2048) content = it },
                label = { Text("Private content") },
                minLines = 3,
                maxLines = 5,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            Button(onClick = { save() }, enabled = !busy && title.isNotBlank() && content.isNotBlank()) {
                Text("Save with OIDC write scope")
            }
        }
        Spacer(Modifier.height(12.dp))
        LazyColumn(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(notes, key = { it.id }) { note ->
                ElevatedCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(note.title, style = MaterialTheme.typography.titleSmall)
                        Text(note.timestamp, style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(10.dp))
                        Text(note.content, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            if (!busy && notes.isEmpty() && error.isEmpty()) {
                item { Text("No private notes for this verified subject.", style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
