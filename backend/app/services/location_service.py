"""
Location detection service using IP geolocation & currency mapping.
Automatically detects country, city, country code, client IP, and default currency.
"""

import logging
import ipaddress
from typing import Optional, Dict, Any
import httpx
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)

COUNTRY_TO_CURRENCY = {
    "IN": "INR",
    "US": "USD",
    "GB": "GBP",
    "CA": "CAD",
    "AU": "AUD",
    "JP": "JPY",
    "CN": "CNY",
    "AE": "AED",
    "NZ": "NZD",
    "SG": "SGD",
    "CH": "CHF",
    "BR": "BRL",
    "MX": "MXN",
    "ZA": "ZAR",
    "KR": "KRW",
    # Eurozone
    "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR",
    "BE": "EUR", "AT": "EUR", "IE": "EUR", "PT": "EUR", "FI": "EUR",
    "GR": "EUR", "CY": "EUR", "EE": "EUR", "LV": "EUR", "LT": "EUR",
    "LU": "EUR", "MT": "EUR", "SK": "EUR", "SI": "EUR", "HR": "EUR"
}


def is_private_or_local_ip(ip_str: str) -> bool:
    """Return True if IP is loopback, local, or private RFC1918 address."""
    if not ip_str or ip_str in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
    except ValueError:
        return True


def extract_client_ip(request: Optional[Request]) -> Optional[str]:
    """Extract real client IP address from HTTP request headers."""
    if not request:
        return None

    # Check proxy / cloud headers first
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip", "fastly-client-ip"):
        value = request.headers.get(header)
        if value:
            # X-Forwarded-For can be a comma separated list of IPs
            first_ip = value.split(",")[0].strip()
            if first_ip and not is_private_or_local_ip(first_ip):
                return first_ip

    if request.client and request.client.host:
        return request.client.host
    return None


async def detect_location(request: Optional[Request] = None, explicit_ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Detect user location (country, country_code, city, currency, ip) via external IP geolocation API.
    Handles localhost/development gracefully by querying public WAN IP.
    """
    target_ip = explicit_ip or extract_client_ip(request)
    use_specific_ip = target_ip and not is_private_or_local_ip(target_ip)

    url = (
        f"http://ip-api.com/json/{target_ip}?fields=status,message,country,countryCode,city,currency,query"
        if use_specific_ip
        else "http://ip-api.com/json/?fields=status,message,country,countryCode,city,currency,query"
    )

    result = {
        "country": "United States",
        "country_code": "US",
        "city": "Unknown",
        "currency": "USD",
        "detected_ip": target_ip or "127.0.0.1",
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    country_code = (data.get("countryCode") or "US").upper()
                    result["country"] = data.get("country") or "United States"
                    result["country_code"] = country_code
                    result["city"] = data.get("city") or "Unknown"
                    result["detected_ip"] = data.get("query") or target_ip or "127.0.0.1"

                    # Determine currency: mapped > API currency > default USD
                    mapped_currency = COUNTRY_TO_CURRENCY.get(country_code)
                    api_currency = (data.get("currency") or "").upper()
                    result["currency"] = mapped_currency or (api_currency if len(api_currency) == 3 else "USD")

                    logger.info(f"[LOCATION DETECTED] IP: {result['detected_ip']} | Country: {result['country']} ({result['country_code']}) | Currency: {result['currency']}")
                    return result
    except Exception as err:
        logger.warning(f"Primary IP geolocation failed ({err}). Trying fallback service...")

    # Fallback lookup via ipapi.co
    try:
        fallback_url = f"https://ipapi.co/{target_ip}/json/" if use_specific_ip else "https://ipapi.co/json/"
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(fallback_url)
            if resp.status_code == 200:
                fb_data = resp.json()
                country_code = (fb_data.get("country_code") or "US").upper()
                result["country"] = fb_data.get("country_name") or result["country"]
                result["country_code"] = country_code
                result["city"] = fb_data.get("city") or result["city"]
                result["detected_ip"] = fb_data.get("ip") or result["detected_ip"]
                
                mapped_currency = COUNTRY_TO_CURRENCY.get(country_code)
                api_currency = (fb_data.get("currency") or "").upper()
                result["currency"] = mapped_currency or (api_currency if len(api_currency) == 3 else "USD")
    except Exception as err:
        logger.warning(f"Fallback geolocation failed ({err}). Using default USD.")

    return result


async def update_user_location(
    user: User,
    db: AsyncSession,
    request: Optional[Request] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Populates user location & currency in database if not set or if forced.
    Returns the updated location dictionary.
    """
    # If user already has location set and not forcing, return existing
    if not force and user.country and user.currency and user.country_code:
        return {
            "country": user.country,
            "country_code": user.country_code,
            "city": user.city or "Unknown",
            "currency": user.currency,
            "detected_ip": user.detected_ip or "127.0.0.1",
        }

    location_data = await detect_location(request=request)
    user.country = location_data["country"]
    user.country_code = location_data["country_code"]
    user.city = location_data["city"]
    user.currency = location_data["currency"]
    user.detected_ip = location_data["detected_ip"]

    await db.flush()
    await db.commit()
    await db.refresh(user)

    logger.info(f"[USER LOCATION UPDATED] User ID: {user.id} | Email: {user.email} -> {user.country} ({user.currency})")
    return location_data
