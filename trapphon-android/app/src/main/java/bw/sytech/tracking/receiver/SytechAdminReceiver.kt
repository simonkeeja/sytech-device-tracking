package bw.sytech.tracking.receiver

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import bw.sytech.tracking.ui.HoneypotActivity

/**
 * SYTECH Device Admin Policy Receiver
 * Monitors failed password/PIN/pattern attempts.
 * PRD Section 4.A: If failed attempts >= 3, forces device into offline honeypot lockdown.
 */
class SytechAdminReceiver : DeviceAdminReceiver() {

    override fun onPasswordFailed(context: Context, intent: Intent) {
        super.onPasswordFailed(context, intent)
        val prefs = context.getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
        val currentFailed = prefs.getInt("failed_attempts", 0) + 1
        prefs.edit().putInt("failed_attempts", currentFailed).apply()

        Log.w(TAG, "Consecutive failed unlock attempts: $currentFailed")

        if (currentFailed >= 3) {
            Log.e(TAG, "Security threshold exceeded (>=3 failed). Launching Fake Factory Reset Honeypot.")
            // Mark device status as compromised offline
            prefs.edit().putBoolean("is_honeypot_active", true).apply()

            // Launch Honeypot Lockdown Activity
            val honeypotIntent = Intent(context, HoneypotActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            }
            context.startActivity(honeypotIntent)
        }
    }

    override fun onPasswordSucceeded(context: Context, intent: Intent) {
        super.onPasswordSucceeded(context, intent)
        // Reset counter on successful unlock by legitimate owner
        val prefs = context.getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("is_honeypot_active", false)) {
            prefs.edit().putInt("failed_attempts", 0).apply()
        }
    }

    companion object {
        private const val TAG = "SytechAdminReceiver"
    }
}
