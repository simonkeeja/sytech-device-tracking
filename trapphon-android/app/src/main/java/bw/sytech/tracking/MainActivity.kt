package bw.sytech.tracking

import android.app.Activity
import android.app.AlertDialog
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import bw.sytech.tracking.receiver.SytechAdminReceiver

/**
 * TrapPhon Main Onboarding & Protection Dashboard
 * Complies with Google Play Store Prominent Disclosure requirements
 * for Device Policy Controller (DPC) & DeviceAdmin permissions.
 */
class MainActivity : Activity() {

    private lateinit var devicePolicyManager: DevicePolicyManager
    private lateinit var adminComponent: ComponentName

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        devicePolicyManager = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        adminComponent = ComponentName(this, SytechAdminReceiver::class.java)

        val etOmangName = findViewById<EditText>(R.id.etOmangName)
        val etContact = findViewById<EditText>(R.id.etContact)
        val etMasterPin = findViewById<EditText>(R.id.etMasterPin)
        val btnActivate = findViewById<Button>(R.id.btnActivateProtection)
        val tvStatus = findViewById<TextView>(R.id.tvProtectionStatus)

        // Load saved state
        val prefs = getSharedPreferences("sytech_prefs", Context.MODE_PRIVATE)
        etOmangName.setText(prefs.getString("user_omang", "Kagiso Molefe"))
        etContact.setText(prefs.getString("user_contact", "+267 72 111 222"))
        etMasterPin.setText(prefs.getString("master_pin", "7924"))

        updateStatus(tvStatus)

        btnActivate.setOnClickListener {
            val omangName = etOmangName.text.toString().trim()
            val contact = etContact.text.toString().trim()
            val masterPin = etMasterPin.text.toString().trim()

            if (omangName.isEmpty() || contact.isEmpty() || masterPin.length < 4) {
                Toast.makeText(this, "Please fill in all details and enter at least a 4-digit Master PIN.", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }

            prefs.edit()
                .putString("user_omang", omangName)
                .putString("user_contact", contact)
                .putString("master_pin", masterPin)
                .apply()

            if (!devicePolicyManager.isAdminActive(adminComponent)) {
                showProminentDisclosureDialog()
            } else {
                Toast.makeText(this, "SYTECH Protection Guard is already ACTIVE.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * Google Play Policy Compliance:
     * Prominently discloses the purpose of Device Admin permissions before prompting the system dialog.
     */
    private fun showProminentDisclosureDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.prominent_disclosure_title)
            .setMessage(R.string.prominent_disclosure_body)
            .setPositiveButton("I Understand & Agree") { dialog, _ ->
                dialog.dismiss()
                requestAdminPermissions()
            }
            .setNegativeButton("Cancel") { dialog, _ ->
                dialog.dismiss()
                Toast.makeText(this, "Device Administrator permission is required to enable Honeypot Protection.", Toast.LENGTH_LONG).show()
            }
            .setCancelable(false)
            .show()
    }

    private fun requestAdminPermissions() {
        val intent = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
            putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComponent)
            putExtra(
                DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                getString(R.string.admin_description)
            )
        }
        startActivityForResult(intent, REQUEST_CODE_ENABLE_ADMIN)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CODE_ENABLE_ADMIN) {
            val tvStatus = findViewById<TextView>(R.id.tvProtectionStatus)
            updateStatus(tvStatus)
            if (devicePolicyManager.isAdminActive(adminComponent)) {
                Toast.makeText(this, "Device Protection Guard successfully activated!", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun updateStatus(tvStatus: TextView) {
        if (devicePolicyManager.isAdminActive(adminComponent)) {
            tvStatus.text = "STATUS: ACTIVE • HONEYPOT ARMED"
            tvStatus.setTextColor(getColor(android.R.color.holo_green_dark))
        } else {
            tvStatus.text = "STATUS: UNPROTECTED (Action Required)"
            tvStatus.setTextColor(getColor(android.R.color.holo_red_dark))
        }
    }

    companion object {
        private const val REQUEST_CODE_ENABLE_ADMIN = 101
    }
}
