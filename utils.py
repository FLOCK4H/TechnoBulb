from scapy.all import ARP, Ether, srp
import time

def get_ip_from_mac(target_mac, ip_range, timeout=2, retry_delay=5, max_attempts=None):
    attempts = 0

    # Install npcap to make srp work.
    while max_attempts is None or attempts < max_attempts:
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip_range), timeout=timeout, verbose=False)
        
        for _, rcv in ans:
            if rcv[Ether].src == target_mac:
                return rcv[ARP].psrc
        
        time.sleep(retry_delay)
        attempts += 1
        print("Couldn't find the bulb!")

    return None