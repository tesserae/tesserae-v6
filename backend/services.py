"""
Services Module
Extracted helper functions for analytics, geolocation, and request processing
"""
import os
import ipaddress
import requests as http_requests
from flask import request

from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger

logger = get_logger('services')


CONNECTOR_HEADER = 'X-Tesserae-Connector'
CONNECTOR_IP_HEADER = 'X-Tesserae-Connector-IP'

_DEFAULT_INTERNAL_IPS = '128.205.2.231'
_internal_ips = None


def _internal_ip_set():
    """Loopback is always internal. The listed addresses (the server's own) are read once."""
    global _internal_ips
    if _internal_ips is None:
        raw = os.environ.get('TESSERAE_INTERNAL_IPS', _DEFAULT_INTERNAL_IPS)
        _internal_ips = {x.strip() for x in raw.split(',') if x.strip()}
    return _internal_ips


def is_internal_request(client_ip):
    """True when the address is loopback or one of the server's own addresses."""
    if not client_ip:
        return False
    ip = str(client_ip).strip()
    try:
        if ipaddress.ip_address(ip).is_loopback:
            return True
    except ValueError:
        return False
    return ip in _internal_ip_set()


def _peer_ip():
    """The address of the socket that made this request. The app runs under
    mod_wsgi with no forwarding proxy (ProxyFix in app.py trusts only the
    scheme and host headers), so an X-Forwarded-For header is whatever the
    client wrote and is never used for a trust decision or a log row."""
    return request.remote_addr or '127.0.0.1'


def is_connector_request():
    """True for a call the Claude connector made on a caller's behalf.

    The connector (backend/blueprints/mcp_http.py) calls this server's own
    routes over HTTP, so those calls arrive from the server's address. It marks
    them with a header, honored only when the peer is an internal address, so
    an outside client cannot claim to be the connector.
    """
    return (request.headers.get(CONNECTOR_HEADER) == '1'
            and is_internal_request(_peer_ip()))


def get_client_ip():
    """The client address (the socket address: no proxy forwards to this app).

    A connector call from the server itself carries the connector caller's
    address in a header, and that address is returned instead.

    Returns:
        str: Client IP address or '127.0.0.1' if unavailable
    """
    peer = _peer_ip()
    if request.headers.get(CONNECTOR_HEADER) == '1' and is_internal_request(peer):
        caller = (request.headers.get(CONNECTOR_IP_HEADER) or '').strip()
        if caller:
            try:
                ipaddress.ip_address(caller)
                return caller
            except ValueError:
                pass
    # The recorded address honors a forwarded-for header as it always has (the
    # geolocation and the page-view rows rely on it); trust decisions above
    # and the internal flag in log_search never do.
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return peer


# Simple in-process cache for geolocation to save API hits and improve performance.
# NOTE: This dictionary is process-local. Under multi-worker servers (like Gunicorn),
# each worker maintains its own independent cache. For many-worker production scaling,
# this should be promoted to a shared store such as Redis or a small SQLite table.
_geo_cache = {}

def get_user_location():
    """Get city, country, and IP from client IP using a robust two-tier provider system.
    
    Tier 1: ipinfo.io (50k/month free)
    Tier 2: ip-api.com (Fallback)
    
    Returns:
        tuple: (city, country, ip_address) or (None, None, ip_address)
    """
    ip_address = get_client_ip()
    try:
        if not ip_address:
            return None, None, None
            
        # Check cache first
        if ip_address in _geo_cache:
            city, country = _geo_cache[ip_address]
            return city, country, ip_address

        # Skip geolocation for local/private IPs to save API quota, 
        # but provide a simulation for local development testing.
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                if os.environ.get('TESSERAE_GEO_SIMULATE'):
                    # Simulation mode: Use a default location for local testing so the map isn't empty
                    sim_location = ('Buffalo', 'United States')  # Tesserae project home
                    _geo_cache[ip_address] = sim_location
                    return sim_location[0], sim_location[1], ip_address
                return None, None, ip_address
        except ValueError:
            return None, None, ip_address

        # Provider 1: ipinfo.io
        try:
            response = http_requests.get(f'https://ipinfo.io/{ip_address}/json', timeout=2)
            if response.status_code == 200:
                data = response.json()
                if not data.get('bogon'):
                    country_code = data.get('country')
                    
                    # Dynamic ISO-to-name mapping via pycountry to cover all ~250 countries consistently
                    country = country_code
                    if country_code:
                        try:
                            import pycountry
                            country_obj = pycountry.countries.get(alpha_2=country_code.upper())
                            if country_obj:
                                country = country_obj.name
                        except Exception:
                            pass
                    
                    loc = (data.get('city'), country)
                    _geo_cache[ip_address] = loc
                    return loc[0], loc[1], ip_address
        except Exception as e:
            logger.debug(f"ipinfo.io failed: {e}")

        # Provider 2: ip-api.com (Fallback)
        try:
            response = http_requests.get(f'http://ip-api.com/json/{ip_address}', timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    # Use full country name if available, fallback to countryCode
                    country = data.get('country') or data.get('countryCode')
                    loc = (data.get('city'), country)
                    _geo_cache[ip_address] = loc
                    return loc[0], loc[1], ip_address
        except Exception as e:
            logger.debug(f"ip-api.com fallback failed: {e}")

    except Exception as e:
        logger.error(f"Geolocation error: {e}")
        
    return None, None, ip_address


def log_search(search_type, language='la', source_text=None, target_text=None, 
               query_text=None, match_type=None, results_count=0, cached=False, 
               user_id=None, city=None, country=None, client_ip=None,
               internal=None):
    """Log a search to the analytics database
    
    Args:
        search_type: Type of search ('text_search', 'line_search', etc.)
        language: Language code ('la', 'grc', 'en')
        source_text: Source text filename
        target_text: Target text filename
        query_text: Search query text
        match_type: Type of matching used
        results_count: Number of results returned
        cached: Whether results were from cache
        user_id: User ID if logged in
        city: User's city (from geolocation)
        country: User's country (from geolocation)
        client_ip: Client's IP address
        internal: True for the server's own requests; computed from client_ip when None
    """
    try:
        if internal is None:
            # From the socket address when inside a request (a forwarded-for
            # header is client-written and must not hide or fake a row), else
            # from the address given.
            try:
                if is_connector_request():      # the connector calls from the server on a caller's behalf
                    internal = False
                else:
                    internal = is_internal_request(request.remote_addr)
            except RuntimeError:   # no request context
                internal = is_internal_request(client_ip)
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO search_logs (search_type, language, source_text, target_text, 
                                         query_text, match_type, results_count, cached, user_id,
                                         client_ip, city, country, internal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (search_type, language, source_text, target_text, query_text, 
                  match_type, results_count, cached, user_id, client_ip, city, country, bool(internal)))
    except Exception as e:
        logger.warning(f"Failed to log search: {e}")

