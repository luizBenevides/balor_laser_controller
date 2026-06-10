import usb.core
import libusb_package
import sys

print("Usando libusb-package como backend...")
backend = libusb_package.get_libusb1_backend()

print("\nBuscando dispositivos...")
try:
    devices = usb.core.find(find_all=True, backend=backend)
    found = False
    for dev in devices:
        try:
            vid = hex(dev.idVendor)
            pid = hex(dev.idProduct)
            print(f"Encontrado: ID {vid}:{pid}")
            found = True
        except:
            pass
    if not found:
        print("Nenhum dispositivo encontrado.")
except Exception as e:
    print(f"Erro: {e}")
