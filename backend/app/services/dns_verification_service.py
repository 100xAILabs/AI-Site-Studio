"""
DNS Ownership & Routing Verification Service.
Guarantees that a user connecting a domain (e.g. 'mybrand.com') actually controls the domain's DNS.
Prevents domain hijacking, fake domain claims (e.g. 'google.com'), and subdomain takeover.
"""
import logging
import socket
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Strictly protected domains that can NEVER be claimed via custom domain linking
PROTECTED_SYSTEM_DOMAINS = {
    "google.com",
    "google.co.in",
    "www.google.com",
    "youtube.com",
    "apple.com",
    "microsoft.com",
    "facebook.com",
    "amazon.com",
    "github.com",
    "cloudflare.com",
    "godaddy.com",
    "aisitestudio.com",
    "site-studio.live",
    "localhost",
}

EDGE_SERVER_IPS = {"149.28.243.12", "127.0.0.1"}
EDGE_CNAME_TARGETS = {"site-studio.live", "aisitestudio.com"}


async def query_public_dns_records(domain: str, record_type: str = "TXT") -> List[str]:
    """
    Queries authoritative public DNS using DNS-over-HTTPS (DoH).
    Primary: Google Public DNS (https://dns.google/resolve)
    Fallback: Cloudflare DNS (https://cloudflare-dns.com/dns-query)
    """
    records: List[str] = []

    # 1. Try Google Public DNS DoH API
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://dns.google/resolve",
                params={"name": domain, "type": record_type},
                headers={"Accept": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                answers = data.get("Answer", [])
                for ans in answers:
                    val = str(ans.get("data", "")).strip().strip('"')
                    if val:
                        records.append(val)
                if records:
                    return records
    except Exception as exc:
        logger.debug("Google DNS DoH query failed for %s (%s): %s", domain, record_type, exc)

    # 2. Try Cloudflare DNS DoH API
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://cloudflare-dns.com/dns-query",
                params={"name": domain, "type": record_type},
                headers={"Accept": "application/dns-json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                answers = data.get("Answer", [])
                for ans in answers:
                    val = str(ans.get("data", "")).strip().strip('"')
                    if val:
                        records.append(val)
                if records:
                    return records
    except Exception as exc:
        logger.debug("Cloudflare DNS DoH query failed for %s (%s): %s", domain, record_type, exc)

    return records


async def verify_domain_dns_ownership(domain: str, expected_token: str) -> Dict[str, Any]:
    """
    Verifies that the caller owns the domain by verifying DNS configuration:
    1. Check against protected high-profile domains (google.com, apple.com, etc.).
    2. Check for DNS TXT record on '_studio-challenge.<domain>' or apex '<domain>' matching expected_token.
    3. Check for DNS A-record pointing to Studio Edge IP or CNAME to site-studio.live.
    """
    clean = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")

    # Check 1: Deny protected system and mega-corp domains immediately
    for protected in PROTECTED_SYSTEM_DOMAINS:
        if clean == protected or clean.endswith(f".{protected}"):
            return {
                "verified": False,
                "reason": (
                    f"Security Block: The domain '{clean}' is a protected global domain and cannot be linked. "
                    "You must connect a custom domain that you personally own and manage."
                ),
                "details": "Protected domain blocklist matched."
            }

    # Check 1b: Developer Sandbox Simulation TLDs (.test, .local, .example)
    # Allows developers and users without a purchased domain to test the full custom domain workflow safely
    if clean.endswith(".test") or clean.endswith(".local") or clean.endswith(".example"):
        return {
            "verified": True,
            "method": "sandbox_simulation",
            "details": f"Developer Sandbox Test Domain '{clean}' verified successfully for testing.",
            "records": ["sandbox-simulation-active"],
        }

    # Normalize TXT challenge host
    txt_subdomain = f"_studio-challenge.{clean}"

    # Check 2: Verify TXT record challenge
    sub_txts = await query_public_dns_records(txt_subdomain, record_type="TXT")
    apex_txts = await query_public_dns_records(clean, record_type="TXT")
    all_txts = set(sub_txts + apex_txts)

    for txt in all_txts:
        if expected_token in txt or txt.strip() == expected_token.strip():
            return {
                "verified": True,
                "method": "txt_challenge",
                "details": f"Found verified DNS TXT record '{expected_token}' on {txt_subdomain}",
                "records": list(all_txts),
            }

    # Check 3: Verify A Record pointing to Studio Edge IP
    a_records = await query_public_dns_records(clean, record_type="A")
    try:
        ip = socket.gethostbyname(clean)
        if ip and ip not in a_records:
            a_records.append(ip)
    except Exception:
        pass

    matching_ips = [ip for ip in a_records if ip in EDGE_SERVER_IPS]
    if matching_ips:
        return {
            "verified": True,
            "method": "a_record",
            "details": f"Domain {clean} A-record correctly points to Studio Edge IP ({matching_ips[0]})",
            "records": a_records,
        }

    # Check 4: Verify CNAME record
    cname_records = await query_public_dns_records(clean, record_type="CNAME")
    matching_cnames = [c for c in cname_records if any(target in c.lower() for target in EDGE_CNAME_TARGETS)]
    if matching_cnames:
        return {
            "verified": True,
            "method": "cname",
            "details": f"Domain {clean} CNAME points to Studio Edge ({matching_cnames[0]})",
            "records": cname_records,
        }

    # If all checks failed:
    found_info = f"Current A-records point to: {', '.join(a_records)}" if a_records else "Domain has no active A records"
    return {
        "verified": False,
        "reason": (
            f"Ownership verification failed for '{clean}'. "
            f"No matching DNS TXT verification record was found at '{txt_subdomain}' with value '{expected_token}'. "
            f"({found_info}). "
            "Please configure the TXT record in your domain registrar's DNS settings, or point the A record to 149.28.243.12."
        ),
        "details": f"TXT searched on {txt_subdomain} (found {len(all_txts)} records). A-records: {a_records}.",
    }

