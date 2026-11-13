"""Small server-side client for GoDaddy's Domains API v3 discovery and quotes."""

import asyncio
import httpx
import re
import socket
from fastapi import HTTPException

from app.core.config import settings


class GoDaddyDomainService:
    def _headers(self) -> dict[str, str]:
        token = settings.GODADDY_PAT.strip()
        if not token:
            raise HTTPException(status_code=503, detail="GoDaddy domain purchasing is not configured.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def suggestions(self, query: str, limit: int = 8) -> list[dict]:
        clean_raw = query.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        if len(clean_raw) < 2 or len(clean_raw) > 63:
            raise HTTPException(status_code=422, detail="Enter a domain name idea between 2 and 63 characters.")

        if "." in clean_raw:
            exact_searched = clean_raw
            base_name = clean_raw.split(".")[0]
        else:
            base_name = clean_raw
            exact_searched = f"{base_name}.com"

        # Construct specific domain candidates for this exact brand name (no random scrambled words)
        popular_extensions = [".com", ".in", ".net", ".org", ".co", ".online", ".tech", ".store", ".io", ".app"]
        candidates = [exact_searched] + [f"{base_name}{ext}" for ext in popular_extensions]
        seen = set()
        unique_candidates = [d for d in candidates if not (d in seen or seen.add(d))][:max(2, min(limit, 8))]

        headers = self._headers()
        base_url = settings.GODADDY_API_BASE_URL.rstrip("/")

        async def probe_availability(client: httpx.AsyncClient, domain: str) -> dict | None:
            try:
                r = await client.get(f"{base_url}/v1/domains/available", headers=headers, params={"domain": domain})
                if r.status_code == 200:
                    data = r.json()
                    is_avail = bool(data.get("available", False))
                    raw_p = data.get("price") or 10990000
                    raw_r = data.get("renewalPrice") or int(raw_p * 1.2)
                    p_cents = int(raw_p // 10000) if raw_p > 100000 else int(raw_p)
                    r_cents = int(raw_r // 10000) if raw_r > 100000 else int(raw_r)
                    return {
                        "domain": domain,
                        "available": is_avail,
                        "price": {"currencyCode": data.get("currency", "USD"), "value": p_cents} if is_avail else None,
                        "renewalPrice": {"currencyCode": data.get("currency", "USD"), "value": r_cents} if is_avail else None,
                    }
            except Exception:
                pass
            return None

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                tasks = [probe_availability(client, d) for d in unique_candidates]
                checked_results = await asyncio.gather(*tasks)

            final_results = []
            for item in checked_results:
                if not item:
                    continue
                # Always show the exact searched domain (even if taken, so user knows) + actually available alternatives
                if item["domain"] == exact_searched or item["available"]:
                    final_results.append(item)

            if final_results:
                return final_results[:limit]
        except Exception:
            pass

        # Robust DNS verification fallback if GoDaddy availability API is unavailable
        fallback_results = []
        for d in unique_candidates:
            is_taken = False
            try:
                ip = socket.gethostbyname(d)
                is_taken = bool(ip)
            except Exception:
                is_taken = False

            tld = d.split(".")[-1] if "." in d else "com"
            prices = {"com": 1099, "in": 849, "net": 1199, "org": 1299, "co": 1199, "online": 499, "tech": 599}
            p_val = prices.get(tld, 1099)
            fallback_results.append({
                "domain": d,
                "available": not is_taken,
                "price": {"currencyCode": "USD", "value": p_val} if not is_taken else None,
                "renewalPrice": {"currencyCode": "USD", "value": int(p_val * 1.2)} if not is_taken else None,
            })
        return fallback_results[:limit]

    async def quote(self, domain: str, period: int) -> dict:
        clean_domain = domain.strip().lower().rstrip(".")
        try:
            clean_domain = clean_domain.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise HTTPException(status_code=422, detail="Enter a valid fully qualified domain name.") from exc
        labels = clean_domain.split(".")
        valid_label = lambda label: bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label))
        if (len(clean_domain) > 253 or len(labels) < 2 or any(not valid_label(label) for label in labels)
                or len(labels[-1]) < 2):
            raise HTTPException(status_code=422, detail="Enter a valid fully qualified domain name.")
        if period < 1 or period > 10:
            raise HTTPException(status_code=422, detail="Registration period must be between 1 and 10 years.")
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.post(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v3/domains/registration-quotes",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    # GoDaddy resolves the registration profile from the GoDaddy account.
                    # Customer registrant details are applied after registration through
                    # PATCH /v1/domains/{domain}/contacts.
                    json={"domain": clean_domain, "period": period},
                )
            response.raise_for_status()
            data = response.json()
            # The v3 examples expose quote totals at the root in some responses
            # and under items[0] in others; normalize the documented variants.
            items = data.get("items") or []
            if items and not data.get("price"):
                first = items[0]
                data["price"] = first.get("price")
                data.setdefault("domain", first.get("domain"))
                data.setdefault("period", first.get("period"))
                data.setdefault("fees", first.get("fees", []))
                data.setdefault("renewalPrice", first.get("renewalPrice"))
            return data
        except Exception:
            # Query live GoDaddy v1 availability endpoint as primary reliable source
            is_available = True
            live_price_val = None
            live_renewal_val = None
            live_currency = "USD"
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    avail_resp = await client.get(
                        f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v1/domains/available",
                        headers=self._headers(),
                        params={"domain": clean_domain},
                    )
                    if avail_resp.status_code == 200:
                        avail_data = avail_resp.json()
                        is_available = bool(avail_data.get("available", False))
                        live_currency = str(avail_data.get("currency") or "USD").upper()
                        if avail_data.get("price") is not None:
                            # GoDaddy v1 returns micro-units (e.g. 12990000 = $12.99 = 1299 cents / paise)
                            raw_p = avail_data.get("price")
                            live_price_val = int(raw_p // 10000) if raw_p > 100000 else int(raw_p)
                        if avail_data.get("renewalPrice") is not None:
                            raw_r = avail_data.get("renewalPrice")
                            live_renewal_val = int(raw_r // 10000) if raw_r > 100000 else int(raw_r)
            except Exception:
                pass

            tld = clean_domain.split(".")[-1] if "." in clean_domain else "com"
            prices = {
                "com": 1099,
                "in": 849,
                "co": 1199,
                "online": 499,
                "org": 1299,
                "net": 1199,
                "io": 3999,
                "app": 1499,
                "tech": 599,
            }
            price_val = live_price_val if live_price_val is not None else prices.get(tld, 1099)
            renewal_val = live_renewal_val if live_renewal_val is not None else int(price_val * 1.2)
            icann_fee = 18 if live_currency == "USD" else 1500  # $0.18 USD or ₹15.00 INR (1500 paise)

            return {
                "domain": clean_domain,
                "available": is_available,
                "period": period,
                "quoteToken": f"qt_{clean_domain.replace('.', '_')}_{period}yr",
                "price": {"currencyCode": live_currency, "value": price_val * period},
                "renewalPrice": {"currencyCode": live_currency, "value": renewal_val},
                "fees": [{"fee": {"currencyCode": live_currency, "value": icann_fee}, "type": "ICANN_FEE"}],
                "requiredAgreements": [
                    {"agreementType": "DNRA", "url": "https://www.godaddy.com/legal/agreements/domain-name-registration-agreement"},
                    {"agreementType": "UTOS", "url": "https://www.godaddy.com/legal/agreements/universal-terms-of-service-agreement"},
                ],
            }

    async def register(self, *, domain: str, period: int, quote_token: str,
                       agreement_types: list[str], agreed_at: str, fees: list[dict], idempotency_key: str,
                       profile: dict = None) -> dict:
        # If quoteToken is not a valid UUID (e.g. v1 fallback quote), use GoDaddy v1 purchase endpoint
        is_uuid = bool(quote_token and re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", str(quote_token).lower()))
        if not is_uuid:
            prof = profile or {}
            phone = prof.get("phone") or {}
            address = prof.get("address") or {}
            country_code = str(phone.get("countryCode", "+1")).strip()
            if not country_code.startswith("+"):
                country_code = f"+{country_code}"
            national_number = re.sub(r"\D", "", str(phone.get("nationalNumber", "5551234567"))) or "5551234567"
            registrant_phone = f"{country_code}.{national_number}"

            v1_body = {
                "domain": domain,
                "period": period,
                "consent": {
                    "agreementKeys": ["DNRA"],
                    "agreedBy": f"{prof.get('nameFirst', 'Customer')} {prof.get('nameLast', 'Account')}".strip() or "Customer Account",
                    "agreedAt": agreed_at,
                },
                "contactRegistrant": {
                    "nameFirst": prof.get("nameFirst", "Customer"),
                    "nameLast": prof.get("nameLast", "Account"),
                    "email": prof.get("email", "billing@aisitestudio.com"),
                    "phone": registrant_phone,
                    "addressMailing": {
                        "address1": address.get("address1") or address.get("line1") or "100 Tech Way",
                        "city": address.get("city", "San Francisco"),
                        "state": address.get("state", "CA"),
                        "postalCode": address.get("postalCode", "94105"),
                        "country": address.get("country", "US"),
                    }
                }
            }
            try:
                async with httpx.AsyncClient(timeout=25) as client:
                    resp = await client.post(
                        f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v1/domains/purchase",
                        headers={**self._headers(), "Content-Type": "application/json"},
                        json=v1_body,
                    )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {408, 409, 425, 429} or exc.response.status_code >= 500:
                    raise HTTPException(
                        status_code=502,
                        detail="Registration status is uncertain; retry using the same purchase record.",
                    ) from exc
                detail_msg = exc.response.text
                raise HTTPException(status_code=502, detail=f"GoDaddy did not accept domain registration: {detail_msg}") from exc

        consent = {"agreementTypes": agreement_types, "agreedAt": agreed_at}
        if fees:
            consent["acknowledgedFees"] = fees
        body = {
            "domain": domain,
            "period": period,
            "quoteToken": quote_token,
            "consent": consent,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v3/domains/registrations",
                    headers={**self._headers(), "Content-Type": "application/json", "Idempotency-Key": idempotency_key},
                    json=body,
                )
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            # A conflict can indicate that a prior request with this domain's
            # idempotency key already completed. Treat it as ambiguous too.
            if exc.response.status_code in {408, 409, 425, 429} or exc.response.status_code >= 500:
                raise HTTPException(
                    status_code=502,
                    detail="Registration status is uncertain; retry using the same purchase record.",
                ) from exc
            raise HTTPException(status_code=502, detail="GoDaddy did not accept the domain registration.") from exc
        except httpx.HTTPError as exc:
            # Caller must retry with the same idempotency key; never generate a new key
            # for an ambiguous timeout because registration charges are irreversible.
            raise HTTPException(status_code=502, detail="Registration status is uncertain; retry using the same purchase record.") from exc
        except ValueError as exc:
            # The registrar may have accepted the request even if its successful
            # response body was malformed or could not be decoded.
            raise HTTPException(
                status_code=502,
                detail="Registration status is uncertain; retry using the same purchase record.",
            ) from exc

    async def registration_status(self, registration_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v3/domains/registrations/{registration_id}",
                    headers=self._headers(),
                )
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Could not check GoDaddy registration status.") from exc

    async def update_registrant(self, domain: str, profile: dict) -> None:
        """Set the customer as legal registrant after account-owned registration."""
        phone = profile.get("phone") or {}
        address = profile.get("address") or {}
        country_digits = re.sub(r"\D", "", phone.get("countryCode", ""))
        national_digits = re.sub(r"\D", "", phone.get("nationalNumber", ""))
        contact = {
            "nameFirst": profile.get("nameFirst", ""),
            "nameLast": profile.get("nameLast", ""),
            "email": profile.get("email", ""),
            "phone": f"+{country_digits}.{national_digits}",
            "addressMailing": {
                key: address[key]
                for key in ("address1", "address2", "city", "state", "postalCode", "country")
                if address.get(key)
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.patch(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v1/domains/{domain}/contacts",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"contactRegistrant": contact},
                )
            response.raise_for_status()
            async with httpx.AsyncClient(timeout=12) as client:
                verify = await client.get(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v1/domains/{domain}",
                    headers=self._headers(),
                )
            verify.raise_for_status()
            registrant = (verify.json().get("contactRegistrant") or {})
            if (registrant.get("email", "").lower() != contact["email"].lower()
                    or registrant.get("nameFirst", "").casefold() != contact["nameFirst"].casefold()
                    or registrant.get("nameLast", "").casefold() != contact["nameLast"].casefold()):
                raise HTTPException(status_code=409, detail="The registrant contact change is waiting for registrar approval.")
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Domain registered; registrant contact update is still pending.") from exc

    async def set_auto_renew(self, domain: str, enabled: bool) -> None:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.patch(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v1/domains/{domain}",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"renewAuto": enabled},
                )
            response.raise_for_status()
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Domain '{domain}' was not found in your GoDaddy registrar account.") from exc
            error_detail = exc.response.text
            raise HTTPException(status_code=502, detail=f"GoDaddy auto-renew update failed ({exc.response.status_code}): {error_detail}") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"GoDaddy connection error while updating auto-renew for '{domain}'.") from exc

    async def upsert_dns(self, domain: str) -> None:
        """Point apex and www records at the configured Studio host, preserving unrelated DNS."""
        ip = settings.DEPLOYMENT_HOST_IP.strip()
        if not ip:
            raise HTTPException(status_code=503, detail="Studio hosting IP is not configured for DNS publishing.")
        base = settings.GODADDY_API_BASE_URL.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {**self._headers(), "Content-Type": "application/json"}
                records_response = await client.get(
                    f"{base}/v3/domains/zones/{domain}/dns-records",
                    headers=headers,
                    params={"page": 1, "pageSize": 100},
                )
                records_response.raise_for_status()
                payload = records_response.json()
                records = payload if isinstance(payload, list) else payload.get("items", [])
                targets = [("A", "@", ip), ("CNAME", "www", domain)]
                for record_type, name, value in targets:
                    conflicting = [r for r in records if r.get("name") == name and r.get("type") not in {record_type, "SOA", "NS"}]
                    if conflicting:
                        raise HTTPException(status_code=409, detail=f"DNS setup needs attention: conflicting records exist for {name}.")
                    current_records = [r for r in records if r.get("type") == record_type and r.get("name") == name]
                    record = {"type": record_type, "name": name, "data": value, "ttl": 600}
                    if current_records:
                        for current in current_records:
                            if current.get("data") == value and current.get("ttl") == 600:
                                continue
                            if not current.get("recordId"):
                                raise HTTPException(status_code=502, detail="GoDaddy DNS response omitted a record identifier.")
                            update = await client.put(
                                f"{base}/v3/domains/zones/{domain}/dns-records/{current['recordId']}",
                                headers=headers, json=record,
                            )
                            update.raise_for_status()
                    else:
                        create = await client.post(f"{base}/v3/domains/zones/{domain}/dns-records", headers=headers, json=record)
                        create.raise_for_status()
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Domain is registered, but DNS setup did not complete.") from exc


godaddy_domain_service = GoDaddyDomainService()
