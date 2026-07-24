"""
Keep-alive ping — hits the Streamlit app so Community Cloud doesn't idle it to
sleep (the 30-60s cold start). Schedule every ~10 minutes via Task Scheduler.

Caveat: this only keeps the app warm while THIS desktop is powered on. For true
24/7 warmth (awake even when your PC is off), use a free cloud uptime monitor
instead — e.g. UptimeRobot: add an HTTP(s) monitor for the URL below on a
5-minute interval. That pings from the cloud, no desktop needed.

Usage:  py keep_alive.py
"""

import urllib.error
import urllib.request

URL = "https://otp2-dashboard.streamlit.app/"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # One hit to the app URL is enough to count as traffic; don't chase the
    # Streamlit redirect chain (which otherwise loops).
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)
_req = urllib.request.Request(URL, headers={"User-Agent": "keepalive-ping"})
try:
    with _opener.open(_req, timeout=30) as r:
        print(f"pinged {URL} -> {r.status}")
except urllib.error.HTTPError as e:
    print(f"pinged {URL} -> {e.code} (server reached; keep-alive OK)")
except Exception as e:
    print(f"ping failed: {e}")
