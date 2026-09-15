"""
TrapLap - Windows Captive Portal Lockout Screen (Version 4.0)
Full-screen authoritative lock screen overlay blocking unauthorized desktop access.
Features:
1. Wi-Fi network connection trigger (harvests BSSIDs upon connect)
2. Secret 5-Click gesture on company logo to open Master Backup PIN dialog (The Owner's Exit)
"""
import tkinter as tk
from tkinter import messagebox, simpledialog
import time
import threading
from typing import Callable, Optional

class CaptiveLockoutOverlay:
    def __init__(self, on_wifi_connect: Optional[Callable] = None, on_master_exit: Optional[Callable] = None):
        self.on_wifi_connect = on_wifi_connect
        self.on_master_exit = on_master_exit
        self.click_count = 0
        self.last_click_time = 0.0

        self.root = tk.Tk()
        self.root.title("SYTECH BootGuard Security Lockdown")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#090D16")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent Alt+F4 closing

        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#090D16")
        main_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 1. Company Logo / Shield (Secret 5-Click Gesture Target)
        logo_label = tk.Label(
            main_frame,
            text="[ 🛡️ SYTECH ]",
            font=("Helvetica", 24, "bold"),
            fg="#0284C7",
            bg="#0C4A6E",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        logo_label.pack(pady=15)
        logo_label.bind("<Button-1>", self._handle_logo_click)

        # 2. Authoritative Lockdown Warning
        title_label = tk.Label(
            main_frame,
            text="SECURITY LOCKDOWN: HARDWARE IDENTITY SUSPENDED",
            font=("Helvetica", 16, "bold"),
            fg="#EF4444",
            bg="#090D16"
        )
        title_label.pack(pady=10)

        warning_text = (
            "System authentication has been temporarily suspended due to consecutive failed credentials\n"
            "or unauthorized boot configuration modifications.\n\n"
            "Operating System license verification required. Please connect to an authorized Wi-Fi network\n"
            "to authenticate hardware telemetry."
        )
        msg_label = tk.Label(
            main_frame,
            text=warning_text,
            font=("Helvetica", 11),
            fg="#E2E8F0",
            bg="#090D16",
            justify=tk.CENTER
        )
        msg_label.pack(pady=15)

        # 3. Wi-Fi Connect Trigger Button (Trapping Mechanism)
        connect_btn = tk.Button(
            main_frame,
            text="Connect to Local Wi-Fi Network",
            font=("Helvetica", 12, "bold"),
            fg="#FFFFFF",
            bg="#0284C7",
            activebackground="#0369A1",
            activeforeground="#FFFFFF",
            padx=25,
            pady=8,
            bd=0,
            command=self._trigger_wifi_trap
        )
        connect_btn.pack(pady=20)

        # Secret Exit Hint (for owner)
        hint_label = tk.Label(
            main_frame,
            text="Emergency Terminal Status: ACTIVE | Hardware Abstraction: SECURED",
            font=("Consolas", 9),
            fg="#64748B",
            bg="#090D16"
        )
        hint_label.pack(pady=10)

    def _handle_logo_click(self, event):
        now = time.time()
        if now - self.last_click_time < 2.5:
            self.click_count += 1
        else:
            self.click_count = 1
        self.last_click_time = now

        if self.click_count >= 5:
            self.click_count = 0
            self._prompt_master_pin()

    def _prompt_master_pin(self):
        pin = simpledialog.askstring(
            "Owner Master Verification",
            "Enter your 4-digit Master Backup PIN (Default: 7924):",
            parent=self.root,
            show="*"
        )
        if pin == "7924":
            messagebox.showinfo("SYTECH Verification", "Master PIN Verified. Lockdown deactivated.")
            if self.on_master_exit:
                self.on_master_exit()
            self.root.destroy()
        elif pin:
            messagebox.showerror("Access Denied", "Invalid Master PIN. Security Lockdown persists.")

    def _trigger_wifi_trap(self):
        messagebox.showinfo(
            "Network Connection Initiated",
            "Connecting to surrounding network infrastructure...\n"
            "Hardware BSSIDs and public IP telemetry will be verified with the central server."
        )
        if self.on_wifi_connect:
            self.on_wifi_connect()

    def start(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = CaptiveLockoutOverlay()
    app.start()
