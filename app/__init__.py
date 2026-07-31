"""Novel Generator application package."""
import os


def _sanitize_cert_env() -> None:
    """Drop CA-bundle env vars that point to non-existent files.

    Conda and some setups export ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` pointing to a
    path that does not exist in the current context. httpx (used by the Ollama and OpenAI
    clients) then fails to build its SSL context with ``[Errno 2] No such file or directory``
    even for plain-HTTP localhost calls. Removing the stale var lets httpx fall back to its
    bundled certifi CA store.
    """
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and not os.path.isfile(path):
            os.environ.pop(var, None)


_sanitize_cert_env()
