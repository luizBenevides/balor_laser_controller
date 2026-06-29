import argparse
import time
from pyModbusTCP.client import ModbusClient

IP_ROBO = "192.168.1.8"
PORT_ROBO = 502
DEFAULT_UNITS = [1]

READ_TESTS = [
    ("coils (0)", 0, 8),
    ("coils (100)", 100, 4),
    ("discrete_inputs (0)", 10000, 8),
    ("discrete_inputs (100)", 10100, 4),
    ("holding_registers (0)", 40000, 4),
    ("holding_registers (100)", 40100, 4),
    ("input_registers (0)", 30000, 4),
    ("input_registers (100)", 30100, 4),
]

def map_address(logical_addr):
    if logical_addr < 10000:
        return "coils", logical_addr
    elif logical_addr < 30000:
        return "discrete_inputs", logical_addr - 10000
    elif logical_addr < 40000:
        return "input_registers", logical_addr - 30000
    else:
        return "holding_registers", logical_addr - 40000

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default=IP_ROBO)
    parser.add_argument("--port", type=int, default=PORT_ROBO)
    parser.add_argument("--unit", type=int, action="append", help="Slave/Unit ID; pode repetir. Default: 1")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    units = args.unit or DEFAULT_UNITS
    print(f"[TCP] alvo {args.ip}:{args.port}; slave_ids={units}; timeout={args.timeout}s")

    client = ModbusClient(host=args.ip, port=args.port, auto_open=True, timeout=args.timeout)
    
    if not client.open():
        print(f"FALHA TCP FATAL: Não foi possível conectar ao IP {args.ip} na porta {args.port}.")
        print("O robô pode estar desligado, o cabo desconectado, ou o serviço Modbus travado.")
        return
        
    print(f"TCP Conectado com sucesso! Mantendo a conexão aberta para testar os Unit IDs...")

    for unit in units:
        print(f"\n=== UNIT {unit} ===")
        client.unit_id = unit
        any_reply = False
        
        for name, logical_addr, count in READ_TESTS:
            mem_type, wire_addr = map_address(logical_addr)
            
            result = None
            if mem_type == "coils":
                result = client.read_coils(wire_addr, count)
            elif mem_type == "discrete_inputs":
                result = client.read_discrete_inputs(wire_addr, count)
            elif mem_type == "holding_registers":
                result = client.read_holding_registers(wire_addr, count)
            elif mem_type == "input_registers":
                result = client.read_input_registers(wire_addr, count)
                
            if result is not None:
                any_reply = True
                print(f"[READ] uid={unit:3d} {name:25s} (wire_addr={wire_addr:4d}) count={count:2d} -> OK: {result}")
            else:
                print(f"[READ] uid={unit:3d} {name:25s} (wire_addr={wire_addr:4d}) count={count:2d} -> ERRO: Modbus Error/Timeout")
                
            time.sleep(0.05)
            
        if not any_reply:
            print(f"[UNIT {unit}] Nenhuma leitura funcionou para este Unit ID.")
            
    client.close()

if __name__ == "__main__":
    main()
