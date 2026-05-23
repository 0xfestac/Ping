import asyncio
import aiohttp
import aiofiles
import time
import os
import threading

from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, UTC

# =========================================================
# CONFIG
# =========================================================

MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
INTERVAL = 300
LOG_FILE = "uptime_logs.txt"

HEADERS = {
    "User-Agent": "Eye-Uptime-Bot/5.0"
}

TIMEOUT = aiohttp.ClientTimeout(
    total=10,
    connect=5
)

FAIL_THRESHOLD = 3

# =========================================================
# GLOBAL STATE
# =========================================================

FAILED_COUNTS = {}
LATEST_RESULTS = []
LAST_CHECK_TIME = "Never"

# =========================================================
# SITES
# =========================================================

SITES = [

    "https://eye-8gem.onrender.com",
    "https://eye-1-0v3q.onrender.com",
    "https://eye-2-7dgq.onrender.com",
    "https://eye-3-dg1e.onrender.com",
    "https://eye-4-nzoc.onrender.com",
    "https://eye-5-3qi3.onrender.com",
    "https://eye-6-hh4w.onrender.com",
    "https://eye-7-ox1q.onrender.com",
    "https://eye-8-qog0.onrender.com",
    "https://eye-9-eatj.onrender.com",
    "https://eye-10-ccvz.onrender.com",
    "https://eye-11-zy42.onrender.com",
    "https://eye-12-ghkj.onrender.com",
    "https://eye-13-8ie1.onrender.com",
    "https://eye-14-ogw7.onrender.com",
    "https://eye-15-uqks.onrender.com",
    "https://eye-16.onrender.com",
    "https://eye-17.onrender.com",
    "https://eye-18.onrender.com",
    "https://eye-19.onrender.com",
    "https://eye-20.onrender.com",
    "https://eye-21.onrender.com",
    "https://eye-22.onrender.com",
    "https://eye-23.onrender.com",
    "https://ping-4wzk.onrender.com",
    "https://eye-o8vu.onrender.com",
    "https://eye-1-lgnc.onrender.com",
    "https://eye-2-aky4.onrender.com",
    "https://eye-3-xpix.onrender.com",
    "https://eye-4-10wh.onrender.com",
    "https://eye-5-av01.onrender.com",
    "https://eye-6-czod.onrender.com",
    "https://eye-7-uyhl.onrender.com",
    "https://eye-8-ziiv.onrender.com"
]

# =========================================================
# DASHBOARD WEB SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        global LATEST_RESULTS
        global LAST_CHECK_TIME

        success_count = len([
            r for r in LATEST_RESULTS
            if "| 200 |" in r
        ])

        fail_count = len(LATEST_RESULTS) - success_count

        rows = ""

        for line in LATEST_RESULTS[-100:]:

            css = "ok"

            if "ERROR" in line:
                css = "bad"

            rows += f"<div class='{css}'>{line}</div>"

        html = f"""
        <html>
        <head>
            <title>EYE Monitor</title>

            <style>

                body {{
                    background: #0f172a;
                    color: white;
                    font-family: Arial;
                    padding: 20px;
                }}

                .card {{
                    background: #111827;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                }}

                .ok {{
                    color: #22c55e;
                    margin-bottom: 4px;
                }}

                .bad {{
                    color: #ef4444;
                    margin-bottom: 4px;
                }}

                h1 {{
                    color: #38bdf8;
                }}

                .stats {{
                    display: flex;
                    gap: 20px;
                    flex-wrap: wrap;
                }}

            </style>
        </head>

        <body>

            <h1>EYE MONITOR DASHBOARD</h1>

            <div class="stats">

                <div class="card">
                    <h2>Total Sites</h2>
                    <p>{len(SITES)}</p>
                </div>

                <div class="card">
                    <h2>Online</h2>
                    <p>{success_count}</p>
                </div>

                <div class="card">
                    <h2>Offline</h2>
                    <p>{fail_count}</p>
                </div>

                <div class="card">
                    <h2>Last Check</h2>
                    <p>{LAST_CHECK_TIME}</p>
                </div>

            </div>

            <div class="card">
                <h2>Latest Results</h2>
                {rows}
            </div>

        </body>
        </html>
        """

        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/html"
        )
        self.end_headers()

        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        return


def run_web_server():

    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"[WEB] Dashboard running on port {port}")

    server.serve_forever()


threading.Thread(
    target=run_web_server,
    daemon=True
).start()

# =========================================================
# CHECK SITE
# =========================================================

async def check_site(session, url):

    for attempt in range(3):

        start = time.perf_counter()

        try:

            async with session.get(
                url,
                ssl=False,
                allow_redirects=True
            ) as response:

                latency = round(
                    (time.perf_counter() - start) * 1000,
                    2
                )

                result = (
                    f"[{datetime.now(UTC)}] | "
                    f"{url} | "
                    f"{response.status} | "
                    f"{latency} ms"
                )

                FAILED_COUNTS[url] = 0

                print(result)

                return result

        except asyncio.TimeoutError:

            error = "TIMEOUT"

        except Exception as e:

            error = str(e)

        if attempt == 2:

            FAILED_COUNTS[url] = (
                FAILED_COUNTS.get(url, 0) + 1
            )

            latency = round(
                (time.perf_counter() - start) * 1000,
                2
            )

            result = (
                f"[{datetime.now(UTC)}] | "
                f"{url} | "
                f"ERROR | "
                f"{latency} ms | "
                f"{error}"
            )

            print(result)

            if FAILED_COUNTS[url] >= FAIL_THRESHOLD:

                print(
                    f"[ALERT] "
                    f"{url} failed "
                    f"{FAILED_COUNTS[url]} times"
                )

            return result

        backoff = 2 ** attempt

        await asyncio.sleep(backoff)

# =========================================================
# LOGGING
# =========================================================

async def save_logs(results):

    try:

        if os.path.exists(LOG_FILE):

            size = os.path.getsize(LOG_FILE)

            if size >= MAX_LOG_SIZE:

                backup = f"{LOG_FILE}.old"

                if os.path.exists(backup):
                    os.remove(backup)

                os.rename(LOG_FILE, backup)

                print("[LOG] Rotated log file")

        async with aiofiles.open(
            LOG_FILE,
            "a"
        ) as f:

            await f.write(
                "\n".join(results) + "\n"
            )

    except Exception as e:

        print(f"[LOG ERROR] {e}")

# =========================================================
# MAIN LOOP
# =========================================================

async def run_monitor():

    global LATEST_RESULTS
    global LAST_CHECK_TIME

    connector = aiohttp.TCPConnector(
        limit=100,
        ttl_dns_cache=300,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=TIMEOUT,
        headers=HEADERS
    ) as session:

        while True:

            try:

                LAST_CHECK_TIME = str(
                    datetime.now(UTC)
                )

                print(
                    f"\n===== STARTING CHECK "
                    f"{LAST_CHECK_TIME} =====\n"
                )

                cycle_start = time.perf_counter()

                tasks = [
                    check_site(session, site)
                    for site in SITES
                ]

                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=False
                )

                LATEST_RESULTS = results

                await save_logs(results)

                elapsed = round(
                    time.perf_counter() - cycle_start,
                    2
                )

                print(
                    f"\nFinished checking "
                    f"{len(SITES)} sites in "
                    f"{elapsed} seconds"
                )

                print(
                    f"\n===== SLEEPING "
                    f"{INTERVAL} SECONDS =====\n"
                )

                await asyncio.sleep(INTERVAL)

            except Exception as e:

                print(f"[MAIN LOOP ERROR] {e}")

                await asyncio.sleep(5)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("[SYSTEM] EYE MONITOR STARTED")

    asyncio.run(run_monitor())