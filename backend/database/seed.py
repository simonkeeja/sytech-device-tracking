"""
Seed script to initialize SYTECH Database with realistic test scenarios:
- User: Kagiso Molefe (Omang: 839210294)
- Device 1: Samsung Galaxy S24 Ultra (IMEI: 359128091823901, Price: BWP 8,000.00, Success Fee: BWP 2,000.00)
- Device 2: HP EliteBook 840 G9 (Serial: 5CD23910KL, Price: BWP 12,000.00, Success Fee: BWP 3,000.00)
- Device 3: iPhone 14 Pro (IMEI: 354890123456789, Price: BWP 10,000.00) - for BSSID cluster at Gaborone Station!
"""
from . import db, schema
from ..services import ocr_service, osint_pipeline

def run_seed():
    import os
    if os.getenv("SYTECH_DEMO_MODE") != "1":
        raise RuntimeError("Demo seeding requires SYTECH_DEMO_MODE=1 and a disposable database")
    schema.init_db()

    # 1. Create Complainant User
    user_id = db.create_user(
        full_name_omang="Kagiso Molefe",
        primary_contact="+267 72 111 222",
        alt_contact="+267 71 333 444",
        password_hash="argon2_hashed_secret"
    )

    # 2. Register Device 1 (Smartphone)
    dev1_id = db.register_device(
        user_id=user_id,
        device_type="smartphone",
        brand="Samsung",
        model="Galaxy S24 Ultra",
        hardware_identifier="359128091823901",
        purchase_price_bwp=8000.00,
        master_backup_pin="7924"
    )
    # Receipt verification
    ocr_service.process_receipt_verification(
        device_id=dev1_id,
        receipt_image_url="https://sytech.co.bw/receipts/orange_receipt_s24.jpg",
        user_omang_name="Kagiso Molefe",
        price_bwp=8000.00,
        store_name="Orange Botswana Shop - Game City"
    )

    # Ingress initial stolen telemetry for Device 1
    intel1_id = db.log_tracking_intel(
        device_id=dev1_id,
        trigger_type="sim_swap",
        local_failed_attempts=3,
        captured_ip="168.167.12.84",
        captured_network_operator="Orange Botswana",
        new_sim_number_imsi="652028912384910",
        new_phone_number="+26771234567",
        nearby_wifi_macs="A4:2B:B0:19:C2:5E,B0:C5:54:12:34:56",
        suspect_photo_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&fit=crop&q=80",
        coarse_latitude=-24.6580,
        coarse_longitude=25.9060
    )
    osint_pipeline.execute_osint_cascade(dev1_id, intel1_id, "+26771234567")

    # 3. Register Device 2 (Laptop)
    dev2_id = db.register_device(
        user_id=user_id,
        device_type="laptop",
        brand="HP",
        model="EliteBook 840 G9",
        hardware_identifier="5CD23910KL",
        purchase_price_bwp=12000.00,
        master_backup_pin="7924"
    )
    ocr_service.process_receipt_verification(
        device_id=dev2_id,
        receipt_image_url="https://sytech.co.bw/receipts/mascom_receipt_hp.jpg",
        user_omang_name="Kagiso Molefe",
        price_bwp=12000.00,
        store_name="Mascom Wireless Store - Riverwalk"
    )

    # 4. Register Device 3 (to form a multi-device cluster at Gaborone Station with BSSID A4:2B:B0:19:C2:5E)
    user2_id = db.create_user(
        full_name_omang="Lorato Boikanyo",
        primary_contact="+267 75 999 888",
        alt_contact="+267 74 888 777",
        password_hash="disabled-demo-account"
    )
    dev3_id = db.register_device(
        user_id=user2_id,
        device_type="smartphone",
        brand="Apple",
        model="iPhone 14 Pro",
        hardware_identifier="354890123456789",
        purchase_price_bwp=10000.00
    )
    ocr_service.process_receipt_verification(
        device_id=dev3_id,
        receipt_image_url="https://sytech.co.bw/receipts/cellcity_receipt.jpg",
        user_omang_name="Lorato Boikanyo",
        price_bwp=10000.00,
        store_name="Cell City Botswana"
    )
    intel3_id = db.log_tracking_intel(
        device_id=dev3_id,
        trigger_type="wifi_captive_connect",
        nearby_wifi_macs="A4:2B:B0:19:C2:5E", # SAME BSSID! Triggering technician hub detection!
        captured_ip="168.167.12.84",
        captured_network_operator="Orange Botswana",
        new_sim_number_imsi="652028999887766",
        new_phone_number="+26772345678",
        coarse_latitude=-24.6580,
        coarse_longitude=25.9060
    )
    osint_pipeline.execute_osint_cascade(dev3_id, intel3_id, "+26772345678")

    print("Seed data initialized successfully.")

if __name__ == "__main__":
    run_seed()
