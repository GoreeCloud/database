package com.goreecloud.database

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Saves a bounded, spreadsheet-safe 25-row CSV page without broad file permissions. */
@Composable
internal fun CsvExportButton(client: DatabaseClient, table: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var busy by remember(client, table) { mutableStateOf(false) }
    var error by remember(client, table) { mutableStateOf("") }
    var success by remember(client, table) { mutableStateOf("") }

    val saveCsv = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("text/csv")
    ) { destination ->
        if (destination != null && !busy) {
            busy = true
            error = ""
            success = ""
            scope.launch {
                try {
                    withContext(Dispatchers.IO) {
                        val bytes = client.downloadCsvPage(table)
                        val stream = context.contentResolver.openOutputStream(destination, "w")
                            ?: throw IllegalStateException("Unable to access selected save destination")
                        stream.use { it.write(bytes) }
                    }
                    success = "Current 25-row page saved as CSV."
                } catch (failure: Exception) {
                    error = failure.message ?: "CSV export unavailable"
                } finally {
                    busy = false
                }
            }
        }
    }

    Column {
        TextButton(
            enabled = !busy,
            onClick = {
                error = ""
                success = ""
                saveCsv.launch("app-$table-page.csv")
            }
        ) { Text("Save page CSV") }
        if (busy) LinearProgressIndicator(Modifier.width(94.dp))
        if (error.isNotEmpty()) {
            Text(error, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
        }
        if (success.isNotEmpty()) {
            Text(success, style = MaterialTheme.typography.labelSmall)
        }
    }
}
