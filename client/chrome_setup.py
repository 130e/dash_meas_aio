from selenium.webdriver.chrome.options import Options


BIN_DIR = "/data/data/com.termux/files/usr/bin"
CHROMEDRIVER_PATH = BIN_DIR + "/chromedriver"


def build_chrome_options(
    *,
    headless: bool = True,
    host_resolver_map: str | None = None,
    ignore_cert_errors: bool = False,
    disable_quic: bool = False,
    autoplay: bool = False,
) -> Options:
    """Build Selenium Chrome options tuned for Termux/Android runs."""
    options = Options()

    if headless:
        # New headless mode is required for modern Chromium stability.
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")

    if ignore_cert_errors:
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")

    if disable_quic:
        options.add_argument("--disable-quic")
        options.add_argument("--disable-features=HTTP3")
        options.add_argument("--enable-features=NetworkService,AllowHTTP2")

    if host_resolver_map:
        options.add_argument(f"--host-resolver-rules=MAP {host_resolver_map}")

    if autoplay:
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

    return options
