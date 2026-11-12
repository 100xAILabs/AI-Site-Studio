import pytest
import asyncio
from app.services.dns_verification_service import verify_domain_dns_ownership, PROTECTED_SYSTEM_DOMAINS


@pytest.mark.asyncio
async def test_protected_domain_rejection():
    # Attempting to claim google.com, www.google.com, apple.com must be immediately blocked
    for domain in ["google.com", "www.google.com", "apple.com", "microsoft.com", "site-studio.live"]:
        res = await verify_domain_dns_ownership(domain, expected_token="aisitestudio-verify-fake123")
        assert res["verified"] is False
        assert "Security Block" in res["reason"]


@pytest.mark.asyncio
async def test_unowned_domain_no_txt_token():
    # Attempting to claim an arbitrary real domain without proper TXT challenge record must fail
    res = await verify_domain_dns_ownership("example.com", expected_token="aisitestudio-verify-unmatched-token")
    assert res["verified"] is False
    assert "Ownership verification failed" in res["reason"]

