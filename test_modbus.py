from pyModbusTCP.client import ModbusClient

c = ModbusClient(host="192.168.1.8", port=502, unit_id=1, auto_open=True, timeout=2.0)
print("Connecting to robot...")
if c.open():
    print("TCP connection successful.")
    
    # Test reading Holding Register 100
    regs = c.read_holding_registers(100, 1)
    if regs:
        print(f"Holding Register 100: {regs}")
    else:
        print("Failed to read Holding Register 100")
        
    # Test reading Holding Register 0
    regs = c.read_holding_registers(0, 1)
    if regs:
        print(f"Holding Register 0: {regs}")
    else:
        print("Failed to read Holding Register 0")
        
    # Test reading Coil 100
    coils = c.read_coils(100, 1)
    if coils:
        print(f"Coil 100: {coils}")
    else:
        print("Failed to read Coil 100")

    c.close()
else:
    print("Failed to connect.")
