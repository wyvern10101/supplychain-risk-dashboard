from prometheus_client import start_http_server, Gauge
import time

APP_UP = Gauge(
    "supplychain_app_up",
    "SupplyChain dashboard application availability"
)

APP_UP.set(1)

start_http_server(8000)

while True:
    time.sleep(60)