"""Outbound HTTP for the course importer, hardened against server-side request forgery (SSRF).

Every request, including every redirect hop and robots.txt, goes through `Fetcher.get`, which:
- accepts only http(s) URLs on the default ports, without credentials, and with a public DNS name (no IP literals);
- resolves the name once, requires every resolved address to be globally routable (no loopback, private,
  link-local/cloud-metadata, carrier-grade NAT, multicast or reserved ranges), then connects to that exact
  address so a second DNS answer cannot redirect the connection (DNS rebinding);
- follows at most MAX_REDIRECTS redirects, validating each target the same way;
- never uses environment proxies, sends no cookies or credentials, and verifies TLS certificates;
- bounds response size (before and after decompression), per-request time and the whole import's time and
  request count;
- honours robots.txt and stops at sign-in pages, rate limits and bot challenges instead of working around them.
"""
import http.client
import ipaddress
import re
import socket
import ssl
import time
import zlib
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = 'ShimentoX-CourseImporter/1.0 (internal LMS course import; honours robots.txt)'
ROBOTS_AGENT = 'ShimentoX-CourseImporter'
MAX_URL_LENGTH = 2000
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = 12
DEFAULT_PORTS = {'http': 80, 'https': 443}
# Names that point at the local machine, the local network, or cloud instance metadata services.
BLOCKED_NAMES = {'localhost', 'metadata', 'metadata.google.internal', 'metadata.azure.com', 'instance-data', 'instance-data.ec2.internal', 'kubernetes.default', 'kubernetes.default.svc'}
BLOCKED_SUFFIXES = ('.localhost', '.local', '.localdomain', '.internal', '.intranet', '.lan', '.home', '.corp', '.private', '.arpa', '.test', '.invalid', '.example', '.onion', '.svc', '.cluster.local')
# Interstitial pages shown instead of content. Ordinary pages can load a provider's scripts, so only the page
# title and markers that appear on the challenge page itself are used.
CHALLENGE_TITLE = re.compile(r'^\s*(just a moment|attention required|access denied|verify you are human|are you a robot|security check|captcha|human verification|pardon our interruption)', re.I)
CHALLENGE_MARKER = re.compile(r'cf-browser-verification|cf_chl_opt|_incapsula_resource|px-captcha|captcha-delivery\.com', re.I)
TEXT_TYPES = ('text/html', 'application/xhtml+xml')


class FetchError(Exception):
    """A URL or page that cannot be imported. `kind` is shown to administrators as the reason category."""

    def __init__(self, message, kind='unreachable'):
        super().__init__(message)
        self.kind = kind


class Page:
    def __init__(self, url, status, content_type, text):
        self.url, self.status, self.content_type, self.text = url, status, content_type, text


def validate_url(url):
    """Return the URL in normal form, or raise FetchError. Performs no network access."""
    if not isinstance(url, str):
        raise FetchError('Enter a web address that starts with https://', 'invalid')
    url = url.strip()
    if not 8 <= len(url) <= MAX_URL_LENGTH or any(c in url for c in '\r\n\t\x00 '):
        raise FetchError('Enter a valid web address of at most 2000 characters.', 'invalid')
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise FetchError('This web address is not valid.', 'invalid')
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        raise FetchError('Only http:// and https:// web addresses can be imported.', 'invalid')
    if parts.username is not None or parts.password is not None or '@' in parts.netloc:
        raise FetchError('Web addresses containing user names or passwords are not allowed.', 'blocked')
    if port is not None and port != DEFAULT_PORTS[scheme]:
        raise FetchError('Only standard web ports (80 for http, 443 for https) are allowed.', 'blocked')
    host = (parts.hostname or '').rstrip('.')
    if not host:
        raise FetchError('This web address has no site name.', 'invalid')
    try:
        ipaddress.ip_address(host)
        raise FetchError('Use the site name rather than an IP address.', 'blocked')
    except ValueError:
        pass
    try:
        host = host.encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise FetchError('This site name is not valid.', 'invalid')
    labels = host.split('.')
    # A public site name has at least two labels and an alphabetic top-level domain. This also rejects
    # numeric host forms such as 2130706433 or 0x7f.1 that some resolvers map to loopback addresses.
    if len(labels) < 2 or not all(re.fullmatch(r'[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?', label) for label in labels) or not re.fullmatch(r'(xn--)?[a-z][a-z0-9-]*', labels[-1]):
        raise FetchError('Enter the address of a public website.', 'blocked')
    if host in BLOCKED_NAMES or host.endswith(BLOCKED_SUFFIXES):
        raise FetchError('Internal, local and cloud-metadata addresses cannot be imported.', 'blocked')
    return urlunsplit((scheme, host, parts.path or '/', parts.query, ''))


def public_address(value):
    address = ipaddress.ip_address(value.split('%')[0])
    if address.version == 6 and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast and not address.is_reserved


def resolve_public(host, port):
    """Resolve once and return an address to connect to; every answer must be a public address."""
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        raise FetchError(f'The site {host} could not be found.', 'unreachable')
    addresses = [a[4][0] for a in answers]
    if not addresses:
        raise FetchError(f'The site {host} could not be found.', 'unreachable')
    for value in addresses:
        try:
            ok = public_address(value)
        except ValueError:
            ok = False
        if not ok:
            raise FetchError('This address points to a private, local or reserved network and cannot be imported.', 'blocked')
    return addresses[0]


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class RawResponse:
    """Status, lower-case headers, and a chunk reader. Tests substitute their own transport returning these."""

    def __init__(self, status, headers, read, close=lambda: None):
        self.status, self.headers, self.read, self.close = status, headers, read, close


def network_transport(url, address, timeout):
    parts = urlsplit(url)
    connection = (PinnedHTTPSConnection if parts.scheme == 'https' else PinnedHTTPConnection)(parts.hostname, address, DEFAULT_PORTS[parts.scheme], timeout)
    path = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
    try:
        connection.request('GET', path, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.1',
                                                 'Accept-Language': 'en', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'close'})
        response = connection.getresponse()
    except (OSError, http.client.HTTPException, ssl.SSLError) as error:
        connection.close()
        raise FetchError(f'The site did not respond ({type(error).__name__}).', 'timeout' if isinstance(error, TimeoutError) else 'unreachable')
    headers = {k.lower(): v for k, v in response.getheaders()}

    def close():
        response.close()
        connection.close()
    return RawResponse(response.status, headers, response.read, close)


# Replaced in tests with an in-memory site; production always uses the pinned network connections above.
TRANSPORT = network_transport
RESOLVER = resolve_public


def decode(body, content_type):
    match = re.search(r'charset=["\']?([\w.:-]+)', content_type, re.I) or re.search(rb'<meta[^>]+charset=["\']?([\w.:-]+)', body[:4096], re.I)
    charset = match.group(1) if match else 'utf-8'
    charset = charset.decode('ascii', 'ignore') if isinstance(charset, bytes) else charset
    try:
        return body.decode(charset, errors='replace')
    except LookupError:
        return body.decode('utf-8', errors='replace')


class Fetcher:
    """One import's network budget: wall-clock deadline, request count, bytes, and cached robots.txt rules."""

    def __init__(self, seconds=75, max_requests=70, max_total_bytes=40 * 1024 * 1024, transport=None, resolver=None):
        self.deadline = time.monotonic() + seconds
        self.max_requests, self.requests = max_requests, 0
        self.max_total_bytes, self.total_bytes = max_total_bytes, 0
        self.transport, self.resolver = transport or TRANSPORT, resolver or RESOLVER
        self.robots = {}

    def remaining(self):
        return self.deadline - time.monotonic()

    def budget_left(self):
        return self.requests < self.max_requests and self.remaining() > 2 and self.total_bytes < self.max_total_bytes

    def get(self, url, accept=TEXT_TYPES, max_bytes=MAX_PAGE_BYTES, robots=True):
        for _ in range(MAX_REDIRECTS + 1):
            url = validate_url(url)
            if robots and not self.allowed(url):
                raise FetchError("The site's robots.txt does not allow automated access to this page.", 'robots')
            if not self.budget_left():
                raise FetchError('Not retrieved: the import reached its time or page limit.', 'limit')
            self.requests += 1
            parts = urlsplit(url)
            address = self.resolver(parts.hostname, DEFAULT_PORTS[parts.scheme])
            response = self.transport(url, address, max(1.0, min(REQUEST_TIMEOUT, self.remaining())))
            try:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('location', '').strip()
                    if not location:
                        raise FetchError('The site sent an invalid redirect.', 'unreachable')
                    url = urljoin(url, location)
                    continue
                return self.read(url, response, accept, max_bytes)
            finally:
                response.close()
        raise FetchError('The site redirected too many times.', 'unreachable')

    def read(self, url, response, accept, max_bytes):
        status, headers = response.status, response.headers
        if status in (401, 407):
            raise FetchError('The page requires sign-in. The importer does not sign in to other sites.', 'restricted')
        if status == 403:
            raise FetchError('The site refused access to this page (HTTP 403). It may require sign-in or block automated access.', 'restricted')
        if status == 429:
            raise FetchError('The site is rate-limiting requests (HTTP 429). Try again later.', 'restricted')
        if status == 451:
            raise FetchError('The page is unavailable for legal reasons (HTTP 451).', 'restricted')
        if status >= 400:
            raise FetchError(f'The page could not be retrieved (HTTP {status}).', 'unreachable')
        if status != 200:
            raise FetchError(f'The site returned an unexpected response (HTTP {status}).', 'unreachable')
        content_type = headers.get('content-type', '')
        base = content_type.split(';')[0].strip().lower()
        if accept and base not in accept:
            raise FetchError(f'This address is not a web page ({base or "unknown content type"}). PDFs, videos and downloads are not imported.', 'unsupported')
        try:
            length = int(headers.get('content-length', '0'))
        except ValueError:
            length = 0
        if length > max_bytes:
            raise FetchError(f'The page is larger than the {max_bytes // (1024 * 1024) or 1} MB import limit.', 'too-large')
        chunks, size = [], 0
        while True:
            if self.remaining() <= 0:
                raise FetchError('Not retrieved: the import reached its time limit.', 'timeout')
            try:
                chunk = response.read(65536)
            except (OSError, http.client.HTTPException) as error:
                raise FetchError(f'The connection failed while reading the page ({type(error).__name__}).', 'unreachable')
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise FetchError(f'The page is larger than the {max_bytes // (1024 * 1024) or 1} MB import limit.', 'too-large')
            chunks.append(chunk)
        body = b''.join(chunks)
        encoding = headers.get('content-encoding', '').strip().lower()
        if encoding in ('gzip', 'x-gzip', 'deflate'):
            # Bounded decompression so a small compressed body cannot expand into an oversized page.
            inflater = zlib.decompressobj(47 if encoding != 'deflate' else zlib.MAX_WBITS)
            try:
                body = inflater.decompress(body, max_bytes + 1)
            except zlib.error:
                raise FetchError('The page could not be decompressed.', 'unreachable')
            if len(body) > max_bytes or inflater.unconsumed_tail:
                raise FetchError(f'The page is larger than the {max_bytes // (1024 * 1024) or 1} MB import limit.', 'too-large')
        elif encoding not in ('', 'identity'):
            raise FetchError(f'The page uses an unsupported encoding ({encoding}).', 'unsupported')
        self.total_bytes += len(body)
        text = decode(body, content_type)
        title = re.search(r'<head[^>]*>.*?<title[^>]*>([^<]*)', text[:30000], re.I | re.S)
        if base in TEXT_TYPES and ((title and CHALLENGE_TITLE.search(title.group(1))) or CHALLENGE_MARKER.search(text[:30000])):
            raise FetchError('The site showed a bot-protection or CAPTCHA check. The importer does not bypass these protections.', 'restricted')
        return Page(url, status, base, text)

    def allowed(self, url):
        """robots.txt rules per RFC 9309: missing (4xx) allows everything; an unreachable file (5xx) allows nothing."""
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            rules = RobotFileParser()
            try:
                page = self.get(origin + '/robots.txt', accept=None, max_bytes=MAX_ROBOTS_BYTES, robots=False)
                rules.parse(page.text.splitlines())
            except FetchError as error:
                if error.kind in ('blocked', 'limit', 'timeout') or error.kind == 'unreachable' and 'HTTP' not in str(error):
                    raise  # Unsafe address, exhausted budget, or a site that cannot be reached at all.
                # 4xx (including sign-in and rate-limit responses) means "no robots.txt"; DNS failures and 5xx mean "unreachable".
                rules.allow_all = error.kind in ('restricted', 'unsupported', 'too-large') or re.search(r'HTTP 4\d\d', str(error)) is not None
                rules.disallow_all = not rules.allow_all
            self.robots[origin] = rules
        return self.robots[origin].can_fetch(ROBOTS_AGENT, url)
