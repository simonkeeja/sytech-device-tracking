package bw.sytech.tracking.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import bw.sytech.tracking.ui.HoneypotActivity

/**
 * Boot Survivability Receiver
 * Ensures that if a phone was compromised/locked prior to a reboot,
 * the Honeypot Lockdown screen immediately reasserts itself upon system boot.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (Intent.ACTION_BOOT_COMPLETED == intent.action || "android.intent.action.QUICKBOOT_POWERON" == intent.action) {
            val prefs = context.getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
            val isHoneypotActive = prefs.getBoolean("is_honeypot_active", false)

            if (isHoneypotActive) {
                Log.w("BootReceiver", "Device was compromised before restart. Relaunching Honeypot Lockdown.")
                val lockIntent = Intent(context, HoneypotActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
                context.startActivity(lockIntent)
            }
        }
    }
}
