from pyModbusTCP.client import ModbusClient
import time

IP_ROBO = "192.168.1.8"
PORT_ROBO = 8000

def scan_robot():
    print(f"--- Escaneando Robo em {IP_ROBO}:{PORT_ROBO} ---")
    client = ModbusClient(host=IP_ROBO, port=PORT_ROBO, unit_id=1, auto_open=True, timeout=1.0)
    
    if not client.open():
        print("Erro: Nao conectou na porta 8000")
        return

    # No teste anterior read_coils(0,1) deu None. Vamos tentar Holding Registers (4xxxx)
    print("\n--- Testando Holding Registers (4xxxx) 0-100 ---")
    for i in range(0, 100):
        res = client.read_holding_registers(i, 1)
        if res:
            print(f"Reg {i}: {res[0]}")
            
    print("\n--- Testando Input Registers (3xxxx) 0-100 ---")
    for i in range(0, 100):
        res = client.read_input_registers(i, 1)
        if res:
            print(f"InReg {i}: {res[0]}")

    print("\n--- Testando Coils (0xxxx) 0-100 ---")
    for i in range(0, 100):
        res = client.read_coils(i, 1)
        if res:
            print(f"Coil {i}: {res[0]}")

    client.close()

scan_robot()
