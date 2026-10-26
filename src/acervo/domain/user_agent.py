# The first match wins: Edge also says Chrome and Safari, Chrome says Safari, an iPhone says "like Mac OS X".
BROWSERS = (
    ("Edg", "Edge"),
    ("OPR", "Opera"),
    ("Firefox", "Firefox"),
    ("FxiOS", "Firefox"),
    ("Chrome", "Chrome"),
    ("CriOS", "Chrome"),
    ("Safari", "Safari"),
)
SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("CrOS", "ChromeOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def device(user_agent: str | None) -> tuple[str | None, str | None]:
    """The browser and the system a user agent names; None for what it does not."""
    agent = user_agent or ""
    browser = next((name for key, name in BROWSERS if key in agent), None)
    return browser, next((name for key, name in SYSTEMS if key in agent), None)
