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
import org.json.JSONObject
import java.net.URLEncoder

private data class DatabaseColumn(
    val name: String,
    val type: String,
    val nullable: Boolean,
    val primaryKey: Boolean,
    val defaultValue: String?
)

private data class DatabaseIndex(val name: String, val definition: String)

/** Read-only PostgreSQL schema browser using the existing authenticated HTTPS client. */
@Composable
internal fun SchemaBrowser(client: DatabaseClient, table: String, onClose: () -> Unit) {
    var columns by remember(client, table) { mutableStateOf(listOf<DatabaseColumn>()) }
    var indexes by remember(client, table) { mutableStateOf(listOf<DatabaseIndex>()) }
    var busy by remember(client, table) { mutableStateOf(false) }
    var error by remember(client, table) { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    fun refresh() {
        if (busy) return
        busy = true
        error = ""
        scope.launch {
            try {
                // Authentication, TLS checks and redirect refusal are enforced by DatabaseClient.
                val escaped = URLEncoder.encode(table, Charsets.UTF_8.name())
                val result: JSONObject = withContext(Dispatchers.IO) {
                    client.get("/v1/tables/app/$escaped/schema")
                }
                val rawColumns = result.getJSONArray("columns")
                val rawIndexes = result.getJSONArray("indexes")
                val nextColumns = (0 until rawColumns.length()).map { i ->
                    val item = rawColumns.getJSONObject(i)
                    DatabaseColumn(
                        name = item.getString("name"),
                        type = item.getString("type"),
                        nullable = item.getBoolean("nullable"),
                        primaryKey = item.getBoolean("primary_key"),
                        defaultValue = if (item.isNull("default")) null else item.optString("default")
                    )
                }
                val nextIndexes = (0 until rawIndexes.length()).map { i ->
                    val item = rawIndexes.getJSONObject(i)
                    DatabaseIndex(item.getString("name"), item.getString("definition"))
                }
                columns = nextColumns
                indexes = nextIndexes
            } catch (failure: Exception) {
                columns = emptyList()
                indexes = emptyList()
                // Never log raw SQL, credentials or server diagnostic payloads.
                error = "Schema inspection unavailable: " + (failure.message ?: "Request failed")
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(client, table) { refresh() }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onClose) { Text("← Table rows") }
            TextButton(onClick = { refresh() }, enabled = !busy) { Text("Refresh schema") }
        }
        Text("app.$table", style = MaterialTheme.typography.titleLarge)
        Text(
            "Read-only columns, primary keys and indexes",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(12.dp))
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (error.isNotEmpty()) {
            Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item { Text("Columns", style = MaterialTheme.typography.titleMedium) }
            items(columns, key = { it.name }) { col ->
                ElevatedCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text(col.name, style = MaterialTheme.typography.titleSmall)
                        Text(col.type, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            (if (col.primaryKey) "Primary key · " else "") +
                                (if (col.nullable) "Nullable" else "Not null"),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        col.defaultValue?.let {
                            Spacer(Modifier.height(4.dp))
                            Text("Default: $it", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            item { Text("Indexes (${indexes.size})", style = MaterialTheme.typography.titleMedium) }
            items(indexes, key = { it.name }) { index ->
                OutlinedCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text(index.name, style = MaterialTheme.typography.titleSmall)
                        Spacer(Modifier.height(6.dp))
                        Text(index.definition, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if (!busy && columns.isEmpty() && error.isEmpty()) {
                item { Text("No columns returned.", style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
