"""
Services Module
Extracted helper functions for analytics, geolocation, and request processing
"""
import ipaddress
import requests as http_requests
from flask import request

from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger

logger = get_logger('services')


def get_client_ip():
    """Get real client IP from X-Forwarded-For header (for proxied requests)
    
    Returns:
        str: Client IP address or '127.0.0.1' if unavailable
    """
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


# Simple in-memory cache for geolocation to save API hits and improve performance
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
                # Simulation mode: Use a default location for local testing so the map isn't empty
                sim_location = ('Buffalo', 'United States') # Tesserae project home
                _geo_cache[ip_address] = sim_location
                return sim_location[0], sim_location[1], ip_address
        except ValueError:
            return None, None, ip_address

        # Provider 1: ipinfo.io
        try:
            response = http_requests.get(f'https://ipinfo.io/{ip_address}/json', timeout=2)
            if response.status_code == 200:
                data = response.json()
                if not data.get('bogon'):
                    country_code = data.get('country')
                    
                    # Common ISO to Full Name Mapping to ensure consistent analytics
                    country_map = {
                        'US': 'United States', 'GB': 'United Kingdom', 'DE': 'Germany',
                        'FR': 'France', 'IT': 'Italy', 'ES': 'Spain', 'CA': 'Canada',
                        'AU': 'Australia', 'NL': 'Netherlands', 'IN': 'India',
                        'CN': 'China', 'JP': 'Japan', 'BR': 'Brazil', 'RU': 'Russia',
                        'CH': 'Switzerland', 'SE': 'Sweden', 'GR': 'Greece', 'TR': 'Turkey'
                    }
                    country = country_map.get(country_code, country_code)
                    
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
               user_id=None, city=None, country=None, client_ip=None):
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
    """
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO search_logs (search_type, language, source_text, target_text, 
                                         query_text, match_type, results_count, cached, user_id,
                                         client_ip, city, country)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (search_type, language, source_text, target_text, query_text, 
                  match_type, results_count, cached, user_id, client_ip, city, country))
    except Exception as e:
        logger.warning(f"Failed to log search: {e}")

