class PageRedirect(Exception):
    """
    Raised when a dependency requires a page redirect (e.g. auth failure on HTML route).
    """
    def __init__(self, url: str):
        self.url = url
