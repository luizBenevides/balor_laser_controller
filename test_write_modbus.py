import time
from pyModbusTCP.client import ModbusClient

IP_ROBO = "192.168.1.8"
PORT_ROBO = 502

client = ModbusClient(host=IP_ROBO, port=PORT_ROBO, auto_open=True, timeout=1.0)

if not client.open():
    print(f"FALHA TCP FATAL no IP {IP_ROBO}.")
    exit(1)

client.unit_id = 1
print("TCP Conectado! (A bolinha verde confirmou isso no painel!)")
print("Varrendo as Coils de 0 a 100 para descobrir qual o robô aceita...\n")

sucesso = False
for addr in range(100):
    result = client.write_single_coil(addr, True)
    
    if result:
        print(f"✅ SUCESSO ABSOLUTO! O robô ACEITOU a escrita na Coil {addr}!")
        sucesso = True
        break
    else:
        err = client.last_error_as_txt
        exc = client.last_except_as_txt
        # Só imprime se for diferente de Timeout para não poluir
        if "Timeout" not in err:
            print(f"Coil {addr} recusada. Motivo: {err} (Exception: {exc})")

if not sucesso:
    print("\nNenhuma Coil de 0 a 100 foi aceita. O problema é de mapeamento (Illegal Address).")

client.close()
