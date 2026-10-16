
import os
import ipaddress
import socket
from urllib.parse import urlparse
from flask import Flask, request, Response, render_template_string
import requests
from markupsafe import escape

app = Flask(__name__)

ACCESS_KEY = os.environ.get("PROXY_ACCESS_KEY", "")

HOME = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyProxy</title>
<style>
body {
  background: #0b1020;
  color: white;
  font-family: Arial, sans-serif;
  text-align: center;
  padding: 50px 15px;
}
main {
  max-width: 650px;
  margin: auto;
  background: #151d32;
  padding: 28px;
  border-radius: 18px;
}
input {
  box-sizing: border-box;
  width: 100%;
  padding: 15px;
  margin: 12px 0;
  border-radius: 10px;
  border: 1px solid #34415e;
}
button {
  padding: 14px 22px;
  border: 0;
  border-radius: 10px;
  background: #6b8cff;
  color: white;
  cursor: pointer;
}
</style>
</head>
<body>
<main>
<h1>PyProxy 🚀</h1>
<p>Your Python-powered web viewer</p>
<form action="/fetch" method="get">
<input type="hidden" name="key" value="{{ key }}">
<input type="url" name="url"
placeholder="https://example.com" required>
<button type="submit">Open website</button>
</form>
<p>Some sites and games may not work in this basic viewer.</p>
</main>
</body>
</html>
"""


def validate_url(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Enter a valid HTTP or HTTPS URL.")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are blocked.")

    host = parsed.hostname.lower()

    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValueError("Local destinations are blocked.")

    addresses = {
        item[4][0] for item in socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    }

    if not addresses:
        raise ValueError("No address found.")

    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Private destinations are blocked.")

    return parsed


@app.before_request
def require_key():
    if not ACCESS_KEY:
        return "Server setup error: configure PROXY_ACCESS_KEY.", 503

    if request.args.get("key") != ACCESS_KEY:
        return "Access denied. Check your access key.", 403


@app.get("/")
def home():
    return render_template_string(HOME, key=ACCESS_KEY)


@app.get("/fetch")
def fetch():
    url = request.args.get("url", "")

    try:
        validate_url(url)

        result = requests.get(
            url,
            headers={"User-Agent": "PyProxy/1.0"},
            timeout=12,
            allow_redirects=False
        )

        if 300 <= result.status_code < 400:
            return "Redirects are not supported yet.", 400

        content_type = result.headers.get("Content-Type", "text/plain")

        if not (
            content_type.startswith("text/")
            or "json" in content_type
            or "xml" in content_type
        ):
            return "This viewer only displays text-based content.", 415

        if len(result.content) > 2_000_000:
            return "Page too large (2 MB maximum).", 413

        if "text/html" in content_type:
            page = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>PyProxy Viewer</title>"
                "<h2>Fetched webpage</h2>"
                "<p>HTML is displayed as text for safety.</p><hr>"
                "<pre style='white-space:pre-wrap;overflow-wrap:anywhere'>"
                + str(escape(result.text))
                + "</pre>"
            )
            return Response(page, content_type="text/html; charset=utf-8")

        return Response(result.content, content_type=content_type)

    except (ValueError, requests.RequestException, OSError) as error:
        return f"Could not open website: {escape(str(error))}", 400


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )
