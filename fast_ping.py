import asyncio
import aiohttp
import aiofiles
import time
import os
import threading

from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, UTC

# =========================================================
# RENDER WEB SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"EYE MONITOR ACTIVE")

    def log_message(self, format, *args):
        return


def run_web_server():

    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"[WEB] Running on port {port}")

    server.serve_forever()


threading.Thread(
    target=run_web_server,
    daemon=True
).start()

# =========================================================
# CONFIG
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

INTERVAL = 300
LOG_FILE = "uptime_logs.txt"

HEADERS = {
    "User-Agent": "Eye-Uptime-Bot/4.0"
}

TIMEOUT = aiohttp.ClientTimeout(
    total=10,
    connect=5
)

# =========================================================
# CHECK SITE
# =========================================================

async def check_site(session, url):

    for attempt in range(2):

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

                print(result)

                return result

        except asyncio.TimeoutError:

            error = "TIMEOUT"

        except Exception as e:

            error = str(e)

        if attempt == 1:

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

            return result

        await asyncio.sleep(1)

# =========================================================
# SAVE LOGS
# =========================================================

async def save_logs(results):

    try:

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

                print(
                    f"\n===== STARTING CHECK "
                    f"{datetime.now(UTC)} =====\n"
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