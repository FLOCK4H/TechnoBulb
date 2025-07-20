import tinytuya

# Device-specific constants
DEVICE_ID_1 = 'XXXXXXXXXXXXXXXXXXXXXXXX'
LOCAL_KEY_1 = "Araaa^2315dfsdf"

DEVICE_ID_2 = 'XXXXXXXXXXXXXXXXXXXX'
LOCAL_KEY_2 = "nufa.Oegfd44r4"

# Proper network scan
print("Scanning for Tuya devices...")
devices = tinytuya.deviceScan()  # RETURNS a dict keyed by IP

# Extract IPs based on DEVICE_IDs
def get_ip_by_device_id(devices: dict, target_id: str) -> str | None:
    for ip, dev in devices.items():
        if dev.get("gwId") == target_id:
            return ip
    return None

# Resolve IPs
IP_DEVICE_1 = get_ip_by_device_id(devices, DEVICE_ID_1)
IP_DEVICE_2 = get_ip_by_device_id(devices, DEVICE_ID_2)

print(f"IP_DEVICE_1: {IP_DEVICE_1}")
print(f"IP_DEVICE_2: {IP_DEVICE_2}")
