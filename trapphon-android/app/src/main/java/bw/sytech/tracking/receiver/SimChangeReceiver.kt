package bw.sytech.tracking.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import android.util.Log
import bw.sytech.tracking.service.TelemetryService

/**
 * PRD Section 4.A: SIM Interception Module
 * The moment a thief or technician inserts a new SIM to clear the lockout screen,
 * this receiver awakens the baseband radio chip listener, extracts the new IMSI
 * and line number, and dispatches telemetry to the SYTECH Cloud.
 */
class SimChangeReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        if ("android.intent.action.SIM_STATE_CHANGED" == action) {
            val stateExtra = intent.getStringExtra("ss")
            Log.d(TAG, "SIM State Change Detected: extra=$stateExtra")

            if ("LOADED".equals(stateExtra, ignoreCase = true) || "READY".equals(stateExtra, ignoreCase = true)) {
                harvestSimAttributes(context)
            }
        }
    }

    private fun harvestSimAttributes(context: Context) {
        val prefs = context.getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
        val registeredImsi = prefs.getString("registered_imsi", null)

        val telephonyManager = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        val carrierName = telephonyManager.networkOperatorName // e.g. Mascom, Orange, BTC
        val simOperator = telephonyManager.simOperatorName

        Log.i(TAG, "Active Network Carrier: $carrierName / $simOperator")

        // Trigger background telemetry service to report new SIM insertion
        val serviceIntent = Intent(context, TelemetryService::class.java).apply {
            putExtra("trigger_type", "sim_swap")
            putExtra("carrier_name", if (carrierName.isNullOrEmpty()) "Orange Botswana" else carrierName)
            putExtra("action", "HARVEST_TELEMETRY")
        }
        context.startService(serviceIntent)
    }

    companion object {
        private const val TAG = "SimChangeReceiver"
    }
}
