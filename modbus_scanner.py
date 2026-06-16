from pyModbusTCP.client import ModbusClient
import time

def scan_device(name, ip):
    print(f"\n{'='*20}")
    print(f"ESCANENDO: {name} ({ip})")
    print(f"{'='*20}")
    
    client = ModbusClient(host=ip, port=502, auto_open=True, timeout=1.0)
    
    if not client.open():
        print(f"ERRO: Nao foi possivel conectar em {ip}")
        return

    # 1. Testar Coils (0xxxx) - Comumente memorias M ou saidas Y
    print("\n--- Testando Coils (0-200) ---")
    coils = client.read_coils(0, 200)
    if coils:
        for i, val in enumerate(coils):
            if val: # Mostra apenas o que esta ON ou alguns vizinhos do 70
                print(f"Addr {i}: {val}")
            elif i == 70:
                print(f"Addr 70: {val} (ALVO)")
    else:
        print("Coils: Sem resposta ou erro de leitura.")

    # 2. Testar Holding Registers (4xxxx) - Comumente memorias D ou Configs
    print("\n--- Testando Holding Registers (0-100) ---")
    regs = client.read_holding_registers(0, 100)
    if regs:
        for i, val in enumerate(regs):
            if val != 0:
                print(f"Reg {i}: {val}")
    else:
        print("Holding Registers: Sem resposta.")

    # 3. Testar enderecos com offset (2118 eh o M70 no padrao Delta)
    if name == "CLP":
        print("\n--- Verificando Offset Delta (2118) ---")
        res = client.read_coils(2118, 1)
        print(f"Addr 2118 (M70 Offset): {res}")

    client.close()

# Executar Scans
scan_device("CLP", "192.168.1.5")
scan_device("Robo", "192.168.1.8")
