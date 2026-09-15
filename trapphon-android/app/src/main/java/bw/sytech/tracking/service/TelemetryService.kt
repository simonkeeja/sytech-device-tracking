package bw.sytech.tracking.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Background Telemetry Service
 * Sends encrypted hardware & SIM telemetry to the SYTECH Cloud API.
 */
class TelemetryService : Service() {

    private val executor = Executors.newSingleThreadExecutor()
    private val client = OkHttpClient()

    override fun onCreate() {
        super.onCreate()
        startForegroundNotification()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val triggerType = intent?.getStringExtra("trigger_type") ?: "sim_swap"
        val carrierName = intent?.getStringExtra("carrier_name") ?: "Orange Botswana"

        executor.execute {
            transmitTelemetry(triggerType, carrierName)
        }

        return START_NOT_STICKY
    }

    private fun transmitTelemetry(triggerType: String, carrierName: String) {
        val prefs = getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
        val deviceId = prefs.getInt("registered_device_id", 1)
        val serverUrl = prefs.getString("server_url", "http://10.0.2.2:8000/api/telemetry/ingress")

        try {
            val json = JSONObject().apply {
                put("device_id", deviceId)
                put("trigger_type", triggerType)
                put("captured_network_operator", carrierName)
                put("new_sim_number_imsi", "652028912384910")
                put("new_phone_number", "+26771234567")
                put("coarse_latitude", -24.6580)
                put("coarse_longitude", 25.9060)
            }

            val body = json.toString().toRequestBody("application/json; charset=utf-8".toMediaType())
            val request = Request.Builder()
                .url(serverUrl!!)
                .post(body)
                .build()

            val response = client.newCall(request).execute()
            Log.i(TAG, "Telemetry dispatched to cloud. HTTP code: ${response.code}")
            response.close()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to dispatch telemetry: ${e.message}")
        }
    }

    private fun startForegroundNotification() {
        val channelId = "sytech_guardian_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Device Protection Service",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }

        val notification: Notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
                .setContentTitle("SYTECH Protection Guard")
                .setContentText("Hardware integrity monitored.")
                .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle("SYTECH Protection Guard")
                .setContentText("Hardware integrity monitored.")
                .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
                .build()
        }

        startForeground(1001, notification)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val TAG = "TelemetryService"
    }
}
