import sys

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from chrome_setup import CHROMEDRIVER_PATH, build_chrome_options

# Basic test for selenium
# Run in termux shell

if len(sys.argv) != 2:
    print("Usage: python client_browser_https_test.py <server_ip>")
    sys.exit(1)

options = build_chrome_options(
    ignore_cert_errors=True,
    disable_quic=True,
    host_resolver_map=f"vodtest.local {sys.argv[1]}",
)

driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
driver.get("https://vodtest.local:5202/index.html")
driver.quit()
