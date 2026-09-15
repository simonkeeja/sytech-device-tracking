package bw.sytech.tracking.ui

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.view.Window
import android.view.WindowManager
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import bw.sytech.tracking.MainActivity
import bw.sytech.tracking.R

/**
 * PRD Section 4.A & 4.C:
 * Fake Factory Reset / Security Lockdown Screen & Secret 5-Tap Gesture Exit
 */
class HoneypotActivity : Activity() {

    private var logoTapCount = 0
    private val resetTapHandler = Handler(Looper.getMainLooper())
    private val resetTapRunnable = Runnable { logoTapCount = 0 }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Make activity full-screen and cover lock screen
        requestWindowFeature(Window.FEATURE_NO_TITLE)
        window.addFlags(
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        setContentView(R.layout.activity_honeypot)

        val logoIcon = findViewById<ImageView>(R.id.ivHoneypotLogo)
        val warningText = findViewById<TextView>(R.id.tvLockdownWarning)

        warningText.text = getString(R.string.honeypot_warning)

        // 5-Tap Secret Gesture Listener on company logo (The Owner's Exit)
        logoIcon.setOnClickListener {
            handleLogoTap()
        }
    }

    private fun handleLogoTap() {
        logoTapCount++
        resetTapHandler.removeCallbacks(resetTapRunnable)
        resetTapHandler.postDelayed(resetTapRunnable, 3000)

        if (logoTapCount >= 5) {
            logoTapCount = 0
            promptMasterBackupPin()
        }
    }

    private fun promptMasterBackupPin() {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "Enter Master PIN (Default: 7924)"
            textAlignment = View.TEXT_ALIGNMENT_CENTER
        }

        AlertDialog.Builder(this)
            .setTitle("Owner Master Backup Verification")
            .setMessage("Accidental lockdown detected? Enter your 4-digit Master Backup PIN to restore normal device operation.")
            .setView(input)
            .setPositiveButton("Restore") { dialog, _ ->
                val enteredPin = input.text.toString().trim()
                val prefs = getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
                val storedPin = prefs.getString("master_pin", "7924")

                if (enteredPin == storedPin) {
                    Toast.makeText(this, "Master PIN Verified. Restoring normal mode...", Toast.LENGTH_LONG).show()
                    // Clear lockdown state
                    prefs.edit()
                        .putBoolean("is_honeypot_active", false)
                        .putInt("failed_attempts", 0)
                        .apply()

                    // Return to main app
                    val intent = Intent(this, MainActivity::class.java).apply {
                        addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    startActivity(intent)
                    finish()
                } else {
                    Toast.makeText(this, "Incorrect Master PIN. Security Lockdown persists.", Toast.LENGTH_SHORT).show()
                }
                dialog.dismiss()
            }
            .setNegativeButton("Cancel") { dialog, _ -> dialog.dismiss() }
            .show()
    }

    override fun onBackPressed() {
        // Prevent back button dismissal of honeypot lockdown
    }
}
