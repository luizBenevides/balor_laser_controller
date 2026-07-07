from pyModbusTCP.client import ModbusClient
import time

IP_ROBO = "192.168.1.8"
PORT_ROBO = 502 # Voltou ao normal segundo o usuario

def scan_status():
    print(f"--- Escaneando Status do Robo em {IP_ROBO}:{PORT_ROBO} ---")
    client = ModbusClient(host=IP_ROBO, port=PORT_ROBO, unit_id=1, auto_open=True, timeout=1.0)
    
    if not client.open():
        print("Erro: Nao conectou na porta 502")
        return

    # Se a escrita (Coil/Register) funciona no 100, mas a leitura no 100 nao volta nada,
    # pode ser que o status esteja em Input Registers (3xxxx) ou Discrete Inputs (1xxxx)
    
    print("\n[TESTE] Lendo COILS (0xxxx) ao redor de 100:")
    res = client.read_coils(100, 10)
    print(f"Coils 100-110: {res}")

    print("\n[TESTE] Lendo DISCRETE INPUTS (1xxxx) ao redor de 100:")
    res = client.read_discrete_inputs(100, 10)
    print(f"Inputs 100-110: {res}")

    print("\n[TESTE] Lendo INPUT REGISTERS (3xxxx) ao redor de 100:")
    res = client.read_input_registers(100, 10)
    print(f"InRegs 100-110: {res}")

    print("\n[TESTE] Lendo HOLDING REGISTERS (4xxxx) ao redor de 100:")
    res = client.read_holding_registers(100, 10)
    print(f"HoldRegs 100-110: {res}")

    client.close()

scan_status()
