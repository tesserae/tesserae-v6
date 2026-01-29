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


def get_user_location():
    """Get city and country from client IP using ipinfo.io (free tier: 50k/month)
    
    Returns:
        tuple: (city, country) or (None, None) if unavailable
    """
    try:
        ip_address = get_client_ip()
        if not ip_address:
            return None, None
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                return None, None
        except ValueError:
            return None, None
        response = http_requests.get(f'https://ipinfo.io/{ip_address}/json', timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data.get('bogon'):
                return None, None
            return data.get('city'), data.get('country')
    except Exception:
        pass
    return None, None


def log_search(search_type, language='la', source_text=None, target_text=None, 
               query_text=None, match_type=None, results_count=0, cached=False, 
               user_id=None, city=None, country=None):
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
    """
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO search_logs (search_type, language, source_text, target_text, 
                                         query_text, match_type, results_count, cached, user_id,
                                         city, country)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (search_type, language, source_text, target_text, query_text, 
                  match_type, results_count, cached, user_id, city, country))
    except Exception as e:
        logger.warning(f"Failed to log search: {e}")
