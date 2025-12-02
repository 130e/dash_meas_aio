import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Basic test for selenium
# Run in termux shell

CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"

if len(sys.argv) != 2:
    print("Usage: python client_browser_https_test.py <server_ip>")
    sys.exit(1)

options = Options()
options.add_argument("--ignore-certificate-errors")
options.add_argument("--disable-quic")
options.add_argument("--disable-features=HTTP3")
options.add_argument(f"--host-resolver-rules=MAP vodtest.local {sys.argv[1]}")
options.add_argument("--headless=new")

driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
driver.get("https://vodtest.local:5202/index.html")
driver.quit()
