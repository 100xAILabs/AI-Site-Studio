"""
Location detection service using edge proxy headers and currency mapping (F-26).
Zero outbound HTTP requests to external geolocation services.
Country and currency are derived directly from trusted edge headers (e.g. CF-IPCountry)
with graceful fallback to default USD/US.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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

COUNTRY_TO_NAME = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "JP": "Japan",
    "SG": "Singapore",
    "AE": "United Arab Emirates",
}


def mask_ip(ip: Optional[str]) -> str:
    """Mask IP address for privacy compliance in logs."""
    if not ip:
        return "unknown"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.***"
    return "masked_ip"


async def detect_location(request: Optional[Request] = None, explicit_ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Detect user location & currency without making outbound HTTP requests (F-26).
    Reads country from edge proxy headers (e.g., Cloudflare CF-IPCountry or GEOIP_COUNTRY_HEADER).
    Never stores or queries external third-party geo-IP APIs.
    """
    country_code = "US"
    city = "Unknown"

    if request:
        header_name = getattr(settings, "GEOIP_COUNTRY_HEADER", "") or ""
        header_val = None
        if header_name:
            header_val = request.headers.get(header_name.lower())
        if not header_val:
            # Check standard cloud CDN edge headers
            header_val = request.headers.get("cf-ipcountry") or request.headers.get("x-country-code")
        
        if header_val and len(header_val.strip()) == 2 and header_val.strip().upper() != "XX":
            country_code = header_val.strip().upper()

        city_val = request.headers.get("cf-ipcity") or request.headers.get("x-city")
        if city_val:
            city = city_val.strip()

    country = COUNTRY_TO_NAME.get(country_code, "United States" if country_code == "US" else country_code)
    currency = COUNTRY_TO_CURRENCY.get(country_code, "USD")

    return {
        "country": country,
        "country_code": country_code,
        "city": city,
        "currency": currency,
        "detected_ip": None,  # F-26: Never expose or store client IP
    }


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
    if not force and user.country and user.currency and user.country_code:
        return {
            "country": user.country,
            "country_code": user.country_code,
            "city": user.city or "Unknown",
            "currency": user.currency,
            "detected_ip": None,
        }

    location_data = await detect_location(request=request)
    user.country = location_data["country"]
    user.country_code = location_data["country_code"]
    user.city = location_data["city"]
    user.currency = location_data["currency"]
    user.detected_ip = None

    await db.flush()
    await db.commit()
    await db.refresh(user)

    logger.info(f"[USER LOCATION UPDATED] User ID: {user.id} -> {user.country} ({user.currency})")
    return location_data
