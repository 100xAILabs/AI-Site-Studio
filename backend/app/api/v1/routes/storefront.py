"""Server-side shop customer accounts, products, and orders.

All storefront customer and order rows use COMMERCE_DATABASE_URL, never DATABASE_URL.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.commerce_database import get_commerce_db
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.request_limits import enforce_key_limit, enforce_user_limit
from app.models.commerce import (CommerceCustomer, CommerceNotificationSettings, CommerceOrder,
                                 CommerceOrderItem, CommerceProduct, CommerceSession)
from app.models.deployment import Deployment
from app.models.user import User

router = APIRouter()
bearer = HTTPBearer(auto_error=False)
CommerceDB = Annotated[AsyncSession, Depends(get_commerce_db)]
PlatformDB = Annotated[AsyncSession, Depends(get_db)]


class CustomerRegistration(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    password: str = Field(min_length=12, max_length=128)


class CustomerLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    inventory: int = Field(default=0, ge=0)


class OrderLineInput(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)


class OrderInput(BaseModel):
    items: list[OrderLineInput] = Field(min_length=1, max_length=50)


class NotificationSettingsInput(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=16, pattern=r"^\+[1-9]\d{7,14}$")


async def resolve_store(identifier: str, db: AsyncSession) -> Deployment:
    value = identifier.strip().lower().rstrip(".")
    subdomain_name = value.removesuffix(".aisitestudio.com")
    result = await db.execute(select(Deployment).where(
        (Deployment.site_id == value.upper()) |
        (Deployment.subdomain == value) |
        (Deployment.subdomain == subdomain_name) |
        (Deployment.custom_domain == value)
    ).limit(1))
    deployment = result.scalar_one_or_none()
    if not deployment or deployment.is_suspended or deployment.status not in {"live", "active"}:
        raise HTTPException(status_code=404, detail="Store not found or inactive.")
    return deployment


def make_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(derived.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_store_customer(
    identifier: str,
    platform_db: PlatformDB,
    commerce_db: CommerceDB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CommerceCustomer:
    store = await resolve_store(identifier, platform_db)
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in to your store account.", headers={"WWW-Authenticate": "Bearer"})
    result = await commerce_db.execute(
        select(CommerceSession, CommerceCustomer)
        .join(CommerceCustomer, CommerceCustomer.id == CommerceSession.customer_id)
        .where(CommerceSession.site_id == store.site_id, CommerceSession.token_hash == token_hash(credentials.credentials))
    )
    pair = result.first()
    if not pair:
        raise HTTPException(status_code=401, detail="Invalid store session.", headers={"WWW-Authenticate": "Bearer"})
    session, customer = pair
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        await commerce_db.delete(session)
        await commerce_db.commit()
        raise HTTPException(status_code=401, detail="Store session expired.", headers={"WWW-Authenticate": "Bearer"})
    return customer


async def issue_session(db: AsyncSession, site_id: str, customer: CommerceCustomer) -> dict:
    raw_token = secrets.token_urlsafe(48)
    db.add(CommerceSession(site_id=site_id, customer_id=customer.id, token_hash=token_hash(raw_token),
                           expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
    await db.commit()
    return {"access_token": raw_token, "token_type": "bearer", "expires_in": 604800}


@router.post("/{identifier}/auth/register", status_code=status.HTTP_201_CREATED)
async def register_customer(identifier: str, data: CustomerRegistration, request: Request,
                            platform_db: PlatformDB, commerce_db: CommerceDB):
    email = str(data.email).lower()
    ip = request.client.host if request.client else "unknown"
    await enforce_key_limit(ip, "storefront-register-ip", limit=10)
    await enforce_key_limit(email, "storefront-register-email", limit=5)
    store = await resolve_store(identifier, platform_db)
    customer = CommerceCustomer(site_id=store.site_id, full_name=data.full_name.strip(),
                                email=email, phone=data.phone.strip(),
                                password_hash=make_password_hash(data.password))
    commerce_db.add(customer)
    try:
        await commerce_db.flush()
        session = await issue_session(commerce_db, store.site_id, customer)
    except IntegrityError as exc:
        await commerce_db.rollback()
        raise HTTPException(status_code=409, detail="An account already exists for this email at this store.") from exc
    return {"customer": {"id": str(customer.id), "name": customer.full_name, "email": customer.email, "phone": customer.phone}, **session}


@router.post("/{identifier}/auth/login")
async def login_customer(identifier: str, data: CustomerLogin, request: Request,
                         platform_db: PlatformDB, commerce_db: CommerceDB):
    email = str(data.email).lower()
    ip = request.client.host if request.client else "unknown"
    await enforce_key_limit(ip, "storefront-login-ip", limit=10)
    await enforce_key_limit(email, "storefront-login-email", limit=10)
    store = await resolve_store(identifier, platform_db)
    result = await commerce_db.execute(select(CommerceCustomer).where(
        CommerceCustomer.site_id == store.site_id, CommerceCustomer.email == email))
    customer = result.scalar_one_or_none()
    if not customer or not verify_password(data.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    session = await issue_session(commerce_db, store.site_id, customer)
    return {"customer": {"id": str(customer.id), "name": customer.full_name, "email": customer.email, "phone": customer.phone}, **session}


@router.get("/{identifier}/products")
async def list_products(identifier: str, platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    result = await commerce_db.execute(select(CommerceProduct).where(
        CommerceProduct.site_id == store.site_id, CommerceProduct.is_active.is_(True)).order_by(CommerceProduct.name))
    return {"items": [{"id": str(p.id), "sku": p.sku, "name": p.name, "price": str(p.price),
                       "currency": p.currency, "inventory": p.inventory} for p in result.scalars()]}


@router.post("/{identifier}/products", status_code=status.HTTP_201_CREATED)
async def create_product(identifier: str, data: ProductInput, owner: Annotated[User, Depends(get_current_user)],
                         platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    if store.user_id != owner.id:
        raise HTTPException(status_code=403, detail="Only this website's owner can manage its products.")
    product = CommerceProduct(site_id=store.site_id, **data.model_dump())
    commerce_db.add(product)
    try:
        await commerce_db.commit()
    except IntegrityError as exc:
        await commerce_db.rollback()
        raise HTTPException(status_code=409, detail="This SKU already exists in this store.") from exc
    return {"id": str(product.id), "sku": product.sku, "name": product.name, "price": str(product.price), "currency": product.currency}


@router.post("/{identifier}/orders", status_code=status.HTTP_201_CREATED)
async def place_order(identifier: str, data: OrderInput,
                      customer: Annotated[CommerceCustomer, Depends(current_store_customer)],
                      platform_db: PlatformDB, commerce_db: CommerceDB):
    await enforce_user_limit(str(customer.id), "storefront-order", limit=30, window_seconds=3600)
    store = await resolve_store(identifier, platform_db)
    quantities: dict[uuid.UUID, int] = {}
    for line in data.items:
        quantities[line.product_id] = quantities.get(line.product_id, 0) + line.quantity
    result = await commerce_db.execute(select(CommerceProduct).where(
        CommerceProduct.site_id == store.site_id, CommerceProduct.id.in_(quantities.keys()),
        CommerceProduct.is_active.is_(True)).with_for_update())
    products = {product.id: product for product in result.scalars()}
    if len(products) != len(quantities):
        raise HTTPException(status_code=400, detail="One or more products are unavailable.")
    currencies = {product.currency for product in products.values()}
    if len(currencies) != 1:
        raise HTTPException(status_code=409, detail="All items in an order must use the same currency.")
    for product_id, quantity in quantities.items():
        if products[product_id].inventory < quantity:
            raise HTTPException(status_code=409, detail=f"Not enough inventory for {products[product_id].name}.")
    currency = next(iter(currencies))
    total = sum((products[pid].price * qty for pid, qty in quantities.items()), Decimal("0.00"))
    order = CommerceOrder(site_id=store.site_id, customer_id=customer.id, total=total, currency=currency)
    for product_id, quantity in quantities.items():
        product = products[product_id]
        order.items.append(CommerceOrderItem(product_id=product.id, product_name=product.name,
                                             quantity=quantity, unit_price=product.price))
    commerce_db.add(order)
    await commerce_db.commit()
    alert_settings = await commerce_db.get(CommerceNotificationSettings, store.site_id)
    lines = [f"{item.product_name} x {item.quantity} — {item.unit_price * item.quantity} {currency}"
             for item in order.items]
    subject = f"New order {str(order.id)[:8]} received"
    email_body = "\n".join([
        f"New order for {store.subdomain or store.site_id}", f"Order: {order.id}",
        f"Customer: {customer.full_name}", f"Customer phone: {customer.phone}", "Items:", *lines,
        f"Total: {total} {currency}", f"Payment status: {order.payment_status}",
    ])
    sms_body = (f"New order {str(order.id)[:8]}: {customer.full_name}, {customer.phone}. "
                f"{'; '.join(f'{item.product_name} x{item.quantity}' for item in order.items)}. "
                f"Total {total} {currency}.")
    email_sent = sms_sent = False
    if alert_settings:
        from app.services.store_notifications import send_order_email, send_order_sms
        if alert_settings.email:
            email_sent = await send_order_email(alert_settings.email, subject, email_body)
        if alert_settings.phone:
            sms_sent = await send_order_sms(alert_settings.phone, sms_body)
    return {"id": str(order.id), "status": order.status, "payment_status": order.payment_status,
            "total": str(total), "currency": currency,
            "notifications": {"email": "sent" if email_sent else "not_sent",
                               "sms": "sent" if sms_sent else "not_sent"},
            "message": "Order recorded. Payment is still awaiting payment."}


@router.get("/{identifier}/notification-settings")
async def get_notification_settings(identifier: str, owner: Annotated[User, Depends(get_current_user)],
                                    platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    if store.user_id != owner.id:
        raise HTTPException(status_code=403, detail="Only this website's owner can manage notifications.")
    row = await commerce_db.get(CommerceNotificationSettings, store.site_id)
    from app.core.config import settings as app_settings
    return {"email": row.email if row else None, "phone": row.phone if row else None,
            "email_provider_configured": bool(app_settings.ENABLE_EMAIL_DELIVERY and
                                               (app_settings.RESEND_API_KEY or
                                               (app_settings.SMTP_USER and app_settings.SMTP_PASSWORD))),
            "sms_provider_configured": bool(app_settings.TWILIO_ACCOUNT_SID and app_settings.TWILIO_AUTH_TOKEN
                                             and app_settings.TWILIO_FROM_NUMBER)}


@router.put("/{identifier}/notification-settings")
async def save_notification_settings(identifier: str, data: NotificationSettingsInput,
                                     owner: Annotated[User, Depends(get_current_user)],
                                     platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    if store.user_id != owner.id:
        raise HTTPException(status_code=403, detail="Only this website's owner can manage notifications.")
    if data.email is None and data.phone is None:
        raise HTTPException(status_code=422, detail="Provide at least one email address or phone number.")
    row = await commerce_db.get(CommerceNotificationSettings, store.site_id)
    if row is None:
        row = CommerceNotificationSettings(site_id=store.site_id)
        commerce_db.add(row)
    row.email = str(data.email).lower() if data.email else None
    row.phone = data.phone
    await commerce_db.commit()
    from app.core.config import settings as app_settings
    return {"email": row.email, "phone": row.phone,
            "email_provider_configured": bool(app_settings.ENABLE_EMAIL_DELIVERY and
                                               (app_settings.RESEND_API_KEY or
                                               (app_settings.SMTP_USER and app_settings.SMTP_PASSWORD))),
            "sms_provider_configured": bool(app_settings.TWILIO_ACCOUNT_SID and app_settings.TWILIO_AUTH_TOKEN
                                             and app_settings.TWILIO_FROM_NUMBER)}


@router.get("/{identifier}/orders/mine")
async def list_my_orders(identifier: str,
                        customer: Annotated[CommerceCustomer, Depends(current_store_customer)],
                        platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    result = await commerce_db.execute(select(CommerceOrder).where(
        CommerceOrder.site_id == store.site_id, CommerceOrder.customer_id == customer.id)
        .order_by(CommerceOrder.created_at.desc()))
    return {"items": [{"id": str(order.id), "status": order.status,
                       "payment_status": order.payment_status, "total": str(order.total),
                       "currency": order.currency,
                       "items": [{"name": line.product_name, "quantity": line.quantity,
                                  "unit_price": str(line.unit_price)} for line in order.items]}
                      for order in result.scalars().unique()]}


@router.get("/{identifier}/orders")
async def owner_orders(identifier: str, owner: Annotated[User, Depends(get_current_user)],
                       platform_db: PlatformDB, commerce_db: CommerceDB):
    store = await resolve_store(identifier, platform_db)
    if store.user_id != owner.id:
        raise HTTPException(status_code=403, detail="Only this website's owner can view its orders.")
    result = await commerce_db.execute(select(CommerceOrder).where(CommerceOrder.site_id == store.site_id)
                                       .order_by(CommerceOrder.created_at.desc()))
    return {"items": [{"id": str(order.id), "status": order.status,
                       "payment_status": order.payment_status, "total": str(order.total),
                       "currency": order.currency,
                       "customer": {"name": order.customer.full_name, "email": order.customer.email,
                                    "phone": order.customer.phone},
                       "items": [{"name": line.product_name, "quantity": line.quantity,
                                  "unit_price": str(line.unit_price)} for line in order.items]}
                      for order in result.scalars().unique()]}
