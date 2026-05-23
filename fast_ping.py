import asyncio
import aiohttp
import aiofiles
import time
import os
import threading
import json

from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, UTC

# =========================================================
# CONFIG
# =========================================================

MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
INTERVAL = 300
LOG_FILE = "uptime_logs.txt"

HEADERS = {
    "User-Agent": "Eye-Uptime-Bot/7.0"
}

TIMEOUT = aiohttp.ClientTimeout(
    total=20,
    connect=5,
    sock_connect=5,
    sock_read=10
)

FAIL_THRESHOLD = 3
MAX_RESULTS_MEMORY = 500

# Max concurrent requests
SEMAPHORE = asyncio.Semaphore(10)

# =========================================================
# GLOBAL STATE
# =========================================================

FAILED_COUNTS = {}

LATEST_RESULTS = deque(
    maxlen=MAX_RESULTS_MEMORY
)

LAST_CHECK_TIME = "Never"

TOTAL_CHECKS = 0
TOTAL_FAILURES = 0

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

        global LAST_CHECK_TIME
        global TOTAL_CHECKS
        global TOTAL_FAILURES

        # =============================================
        # JSON API
        # =============================================

        if self.path == "/api/results":

            results = list(LATEST_RESULTS)

            payload = {
                "results": results,
                "last_check": LAST_CHECK_TIME,
                "checks": TOTAL_CHECKS,
                "failures": TOTAL_FAILURES
            }

            self.send_response(200)

            self.send_header(
                "Content-type",
                "application/json"
            )

            self.end_headers()

            self.wfile.write(
                json.dumps(payload).encode()
            )

            return

        # =============================================
        # HTML DASHBOARD
        # =============================================

        results = list(LATEST_RESULTS)

        success_count = len([
            r for r in results
            if "| 200 |" in r
        ])

        fail_count = len(results) - success_count

        uptime = 100.0

        if TOTAL_CHECKS > 0:

            uptime = round(
                (
                    (TOTAL_CHECKS - TOTAL_FAILURES)
                    / TOTAL_CHECKS
                ) * 100,
                2
            )

        rows = ""

        for line in reversed(results[-100:]):

            css = "ok"

            if "ERROR" in line:
                css = "bad"

            rows += (
                f"<div class='{css}'>{line}</div>"
            )

        html = f"""
        <html>

        <head>

            <title>EYE Monitor</title>

            <meta http-equiv="refresh" content="15">

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
                    box-shadow: 0 0 10px rgba(0,0,0,0.3);
                }}

                .ok {{
                    color: #22c55e;
                    margin-bottom: 5px;
                    word-wrap: break-word;
                }}

                .bad {{
                    color: #ef4444;
                    margin-bottom: 5px;
                    word-wrap: break-word;
                }}

                .recovered {{
                    color: #facc15;
                    margin-bottom: 5px;
                    word-wrap: break-word;
                }}

                h1 {{
                    color: #38bdf8;
                }}

                .stats {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
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
                    <h2>Uptime</h2>
                    <p>{uptime}%</p>
                </div>

                <div class="card">
                    <h2>Last Check</h2>
                    <p>{LAST_CHECK_TIME}</p>
                </div>

            </div>

            <div class="card">

                <h2>Latest Results</h2>

                <div id="results">
                    {rows}
                </div>

            </div>

            <!-- ===================================== -->
            <!-- FRONTEND RETRY SYSTEM -->
            <!-- ===================================== -->

            <script>

            async function retryFailedSites() {{

                const failed = document.querySelectorAll(".bad");

                for (const item of failed) {{

                    const text = item.innerText;

                    const match = text.match(/https:\\/\\/[^\\s|]+/);

                    if (!match) continue;

                    const url = match[0];

                    try {{

                        const start = performance.now();

                        await fetch(url, {{
                            method: "GET",
                            mode: "no-cors",
                            cache: "no-store"
                        }});

                        const latency = (
                            performance.now() - start
                        ).toFixed(2);

                        item.className = "recovered";

                        item.innerHTML +=
                            ` <b>FRONTEND RECOVERED (${latency} ms)</b>`;

                    }}

                    catch (e) {{

                        console.log(
                            "Frontend retry failed:",
                            url
                        );

                    }}
                }}
            }}

            setInterval(
                retryFailedSites,
                30000
            );

            </script>

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

    port = int(
        os.environ.get("PORT", 10000)
    )

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"[WEB] Dashboard running "
        f"on port {port}"
    )

    server.serve_forever()


threading.Thread(
    target=run_web_server,
    daemon=True
).start()

# =========================================================
# CHECK SITE
# =========================================================

async def check_site(session, url):

    global TOTAL_CHECKS
    global TOTAL_FAILURES

    async with SEMAPHORE:

        for attempt in range(3):

            start = time.perf_counter()

            try:

                async with session.get(
                    url,
                    ssl=False,
                    allow_redirects=True
                ) as response:

                    latency = round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        2
                    )

                    if response.status != 200:

                        raise Exception(
                            f"HTTP {response.status}"
                        )

                    FAILED_COUNTS[url] = 0

                    TOTAL_CHECKS += 1

                    result = (
                        f"[{datetime.now(UTC)}] | "
                        f"{url} | "
                        f"{response.status} | "
                        f"{latency} ms"
                    )

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

                TOTAL_CHECKS += 1
                TOTAL_FAILURES += 1

                latency = round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
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

                if (
                    FAILED_COUNTS[url]
                    >= FAIL_THRESHOLD
                ):

                    print(
                        f"[ALERT] "
                        f"{url} failed "
                        f"{FAILED_COUNTS[url]} times"
                    )

                return result

            backoff = 2 ** attempt

            await asyncio.sleep(backoff)

# =========================================================
# STAGGER REQUESTS
# =========================================================

async def staggered_check(
    session,
    url,
    index
):

    await asyncio.sleep(index * 0.15)

    return await check_site(session, url)

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

                print(
                    "[LOG] Rotated log file"
                )

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

    global LAST_CHECK_TIME

    connector = aiohttp.TCPConnector(
        limit=50,
        limit_per_host=5,
        ttl_dns_cache=600,
        enable_cleanup_closed=True,
        force_close=False,
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

                cycle_start = (
                    time.perf_counter()
                )

                tasks = [

                    staggered_check(
                        session,
                        site,
                        i
                    )

                    for i, site
                    in enumerate(SITES)
                ]

                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=False
                )

                LATEST_RESULTS.extend(results)

                await save_logs(results)

                elapsed = round(
                    (
                        time.perf_counter()
                        - cycle_start
                    ),
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

                print(
                    f"[MAIN LOOP ERROR] {e}"
                )

                await asyncio.sleep(5)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print(
        "[SYSTEM] EYE MONITOR STARTED"
    )

    asyncio.run(run_monitor())