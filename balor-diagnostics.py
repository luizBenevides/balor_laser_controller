#!/usr/bin/env python3
import balor.sender
import time
import sys

def run_diagnostics():
    print("=== Balor Laser Diagnostic Tool ===")
    machine = balor.sender.Sender(debug=True)
    
    try:
        print("\n1. Attempting to open connection...")
        machine.open(machine_index=0)
        print("✓ Connection successful!")
        
        print(f"\n2. Device Info:")
        print(f"   Serial: {machine.serial_number}")
        print(f"   Version: {machine.version}")
        
        print("\n3. Testing Red Light (Laser Pointer)...")
        print("   Activating for 3 seconds...")
        machine.light_on()
        time.sleep(3)
        print("   Deactivating...")
        machine.light_off()
        print("✓ Red light test completed.")
        
        print("\n4. Testing Galvo Movement...")
        print("   Moving to center (0x8000, 0x8000)...")
        machine.set_xy(0x8000, 0x8000)
        time.sleep(1)
        print("   Moving to top-left (0x4000, 0x4000)...")
        machine.set_xy(0x4000, 0x4000)
        time.sleep(1)
        print("   Returning to center...")
        machine.set_xy(0x8000, 0x8000)
        print("✓ Galvo movement test completed.")
        
        print("\n=== All basic tests passed! ===")
        
    except Exception as e:
        print(f"\n[!] DIAGNOSTIC FAILED: {e}")
        print("\nPossible solutions:")
        print("1. Ensure EzCAD is CLOSED.")
        print("2. Run as Administrator.")
        print("3. Check if driver was replaced with WinUSB via Zadig (ID 9588 9899).")
    finally:
        machine.close()

if __name__ == "__main__":
    run_diagnostics()
