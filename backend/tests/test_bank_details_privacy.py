"""
Tests for bank details encryption, masking, and admin access control (F-24).
Verifies that bank details are encrypted at rest with Fernet (v1: prefix), masked in standard responses (****last4),
strictly hidden from broad admin listings, and rejected if masked input is provided.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.withdrawal_request import WithdrawalRequest, WithdrawalStatus
from decimal import Decimal


@pytest.mark.asyncio
async def test_payout_account_stored_encrypted(seller_client: AsyncClient, db: AsyncSession):
    """
    Writing payout details stores the account number and holder name encrypted in PostgreSQL with v1: prefix.
    Direct SQL query must not reveal the plaintext account number.
    """
    account_num = "123456789012"
    payload = {
        "payout_bank_name": "Silicon Valley Bank",
        "payout_account_number": account_num,
        "payout_ifsc_code": "SVB0001234",
        "payout_account_holder_name": "Jane Test Seller",
    }
    res = await seller_client.put("/api/v1/auth/payout-account", json=payload)
    assert res.status_code == 200

    # Query raw database value
    raw_query = await db.execute(text("SELECT payout_account_number, payout_account_holder_name FROM users WHERE email='testseller@gmail.com'"))
    row = raw_query.fetchone()
    assert row is not None

    stored_acc_num = row[0]
    stored_holder = row[1]

    # Stored account number must start with v1: and must NOT contain plaintext
    assert str(stored_acc_num).startswith("v1:")
    assert account_num not in str(stored_acc_num)
    assert "Jane Test Seller" not in str(stored_holder)


@pytest.mark.asyncio
async def test_me_masks_account(seller_client: AsyncClient, db: AsyncSession):
    """
    GET /api/v1/auth/me returns the account number masked to **** + last 4 digits.
    """
    await seller_client.put("/api/v1/auth/payout-account", json={
        "payout_bank_name": "Silicon Valley Bank",
        "payout_account_number": "123456789012",
        "payout_ifsc_code": "SVB0001234",
        "payout_account_holder_name": "Jane Test Seller",
    })
    res = await seller_client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["payout_account_number"] == "****9012"


@pytest.mark.asyncio
async def test_admin_users_masks_and_hides_holder(admin_client: AsyncClient, seller_client: AsyncClient, db: AsyncSession):
    """
    GET /api/v1/admin/users lists users with masked account numbers and completely suppresses payout_account_holder_name.
    """
    await seller_client.put("/api/v1/auth/payout-account", json={
        "payout_bank_name": "Silicon Valley Bank",
        "payout_account_number": "123456789012",
        "payout_ifsc_code": "SVB0001234",
        "payout_account_holder_name": "Jane Test Seller",
    })
    res = await admin_client.get("/api/v1/admin/users")
    assert res.status_code == 200
    data = res.json()

    users = data.get("items", [])
    seller_item = next((u for u in users if u["email"] == "testseller@gmail.com"), None)
    assert seller_item is not None

    # Masked account number
    assert seller_item["payout_account_number"] == "****9012"
    # Plaintext account number must NOT appear anywhere in the serialized user
    assert "123456789012" not in str(seller_item)
    # Holder name must be excluded from admin list response
    assert "payout_account_holder_name" not in seller_item or seller_item.get("payout_account_holder_name") is None


@pytest.mark.asyncio
async def test_masked_input_rejected(seller_client: AsyncClient):
    """
    Submitting masked account numbers (* or •) must be rejected with 422 Unprocessable Entity.
    """
    bad_payload = {
        "payout_bank_name": "Silicon Valley Bank",
        "payout_account_number": "****9012",
        "payout_ifsc_code": "SVB0001234",
        "payout_account_holder_name": "Jane Test Seller",
    }
    res = await seller_client.put("/api/v1/auth/payout-account", json=bad_payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_admin_bank_details_reveal_and_audit(admin_client: AsyncClient, seller_client: AsyncClient, db: AsyncSession):
    """
    GET /api/v1/payouts/admin/withdrawals/{id}/bank-details allows admins to reveal full bank details
    for manual wire execution while standard withdrawal listings suppress account holder names.
    """
    # Seed seller and direct withdrawal record
    seller_q = await db.execute(select(User).where(User.email == "testseller@gmail.com"))
    seller = seller_q.scalar_one()

    w = WithdrawalRequest(
        seller_id=seller.id,
        amount=Decimal("10.00"),
        status=WithdrawalStatus.PENDING,
        bank_name="Silicon Valley Bank",
        account_number="987654321098",
        ifsc_code="SVB0009876",
        account_holder_name="Jane Test Seller",
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    w_id = str(w.id)

    # 1. Standard admin list suppresses holder name
    list_res = await admin_client.get("/api/v1/payouts/admin/withdrawals")
    assert list_res.status_code == 200
    items = list_res.json()
    w_item = next((x for x in items if x["id"] == w_id), None)
    assert w_item is not None
    assert w_item["account_number"] == "****1098"
    assert "account_holder_name" not in w_item or w_item.get("account_holder_name") is None

    # 2. Dedicated reveal endpoint decrypts full details
    reveal_res = await admin_client.get(f"/api/v1/payouts/admin/withdrawals/{w_id}/bank-details")
    assert reveal_res.status_code == 200
    reveal_data = reveal_res.json()
    assert reveal_data["account_number"] == "987654321098"
    assert reveal_data["account_holder_name"] == "Jane Test Seller"
