from pyModbusTCP.client import ModbusClient
import time

IP_ROBO = "192.168.1.8"

def scan_range(name, func, start, count):
    print(f"\n--- Escaneando {name} (0-{count}) ---")
    found = []
    for addr in range(start, start + count):
        res = func(addr, 1)
        if res is not None:
            print(f"[{name}] Endereco {addr}: {res[0]}")
            found.append((addr, res[0]))
        # else:
        #    print(f"[{name}] Endereco {addr}: Sem resposta")
    return found

client = ModbusClient(host=IP_ROBO, port=502, auto_open=True, timeout=1.0)

if client.open():
    print(f"Conectado ao Robo em {IP_ROBO}")
    
    # Escaneando Coils (0xxxx)
    scan_range("Coils", client.read_coils, 0, 100)
    
    # Escaneando Discrete Inputs (1xxxx)
    scan_range("Discrete Inputs", client.read_discrete_inputs, 0, 100)
    
    # Escaneando Input Registers (3xxxx)
    scan_range("Input Registers", client.read_input_registers, 0, 100)
    
    # Escaneando Holding Registers (4xxxx)
    scan_range("Holding Registers", client.read_holding_registers, 0, 100)
    
    client.close()
else:
    print(f"Nao foi possivel conectar ao Robo em {IP_ROBO}")
