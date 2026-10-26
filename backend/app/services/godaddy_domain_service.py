"""Small server-side client for GoDaddy's Domains API v3 discovery and quotes."""

import httpx
import re
from fastapi import HTTPException

from app.core.config import settings


class GoDaddyDomainService:
    def _headers(self) -> dict[str, str]:
        token = settings.GODADDY_PAT.strip()
        if not token:
            raise HTTPException(status_code=503, detail="GoDaddy domain purchasing is not configured.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def suggestions(self, query: str, limit: int = 8) -> list[dict]:
        clean_query = query.strip().lower()
        if len(clean_query) < 2 or len(clean_query) > 63:
            raise HTTPException(status_code=422, detail="Enter a domain name idea between 2 and 63 characters.")
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    f"{settings.GODADDY_API_BASE_URL.rstrip('/')}/v3/domains/suggestions",
                    headers=self._headers(),
                    params={"query": clean_query, "limit": max(1, min(limit, 10))},
                )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("suggestions", [])
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail="GoDaddy could not return domain suggestions.") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Could not reach GoDaddy domain services.") from exc

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
            async with httpx.AsyncClient(timeout=15) as client:
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
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            detail = "GoDaddy could not quote this domain. Check its availability and registrant details."
            try:
                provider_message = exc.response.json().get("message")
                if provider_message:
                    detail = str(provider_message)[:500]
            except Exception:
                pass
            raise HTTPException(status_code=422 if exc.response.status_code == 422 else 502, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Could not reach GoDaddy domain services.") from exc

    async def register(self, *, domain: str, period: int, quote_token: str,
                       agreement_types: list[str], agreed_at: str, fees: list[dict], idempotency_key: str) -> dict:
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
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Domain registered; auto-renew setting is still pending.") from exc

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
