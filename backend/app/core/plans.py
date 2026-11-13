"""
Authoritative Subscription Plans, Entitlements & Pricing Configuration.

Single source of truth for Free, Pro, and Extreme tier specifications,
operation credit costs, and variable infrastructure cost estimations.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, Any, List


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    EXTREME = "extreme"


PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free Starter",
        "badge": "Starter Free",
        "description": "Explore templates, inspect source code, and build your first website with 1 free trial.",
        "monthly_price_usd": Decimal("0.00"),
        "annual_price_usd": Decimal("0.00"),
        "annual_monthly_equivalent_usd": Decimal("0.00"),
        "monthly_price_inr": Decimal("0.00"),
        "annual_price_inr": Decimal("0.00"),
        "included_ai_credits": 0,
        "free_generation_allowance": 1,
        "trial_deployment_days": 7,
        "max_deployment_slots": 1,
        "included_hosted_websites": 0,
        "additional_hosting_price_usd": Decimal("12.00"),
        "custom_domain_allowed": False,
        "custom_domain_allowance": 0,
        "auto_heal_allowed": False,
        "auto_heal_sites_limit": 0,
        "auto_heal_repairs_per_period": 0,
        "deployment_versions_limit": 3,
        "backup_retention_days": 0,
        "token_discount_percent": 0,
        "support_tier": "community",
        "features": [
            "1 Free AI Website Generation (Build your first site 100% free)",
            "1 Free Trial Deployment on Site Studio subdomain for 7 days",
            "Site Studio subdomain only (*.site-studio.live)",
            "Inspect full source code in interactive canvas",
            "Auto-Heal (AI Site Doctor) is disabled",
            "Permanent 1-trial per template limit (trial different templates)",
            "Production hosting after trial requires paid hosting add-on ($12/mo)",
        ],
    },
    "pro": {
        "id": "pro",
        "name": "Pro Plan",
        "badge": "✦ Most Popular for Creators",
        "description": "For creators and web professionals who need clean exports, live hosting, and autonomous healing.",
        "monthly_price_usd": Decimal("19.00"),
        "annual_price_usd": Decimal("190.00"),  # 10 months price = 2 months free
        "annual_monthly_equivalent_usd": Decimal("15.83"),
        "monthly_price_inr": Decimal("1600.00"),
        "annual_price_inr": Decimal("16000.00"),
        "included_ai_credits": 150,
        "free_generation_allowance": 999,
        "trial_deployment_days": 0,  # Full subscription, not a trial
        "max_deployment_slots": 3,
        "included_hosted_websites": 1,
        "additional_hosting_price_usd": Decimal("12.00"),
        "custom_domain_allowed": True,
        "custom_domain_allowance": 1,
        "auto_heal_allowed": True,
        "auto_heal_sites_limit": 1,
        "auto_heal_repairs_per_period": 10,
        "deployment_versions_limit": 10,
        "backup_retention_days": 7,
        "token_discount_percent": 40,
        "support_tier": "standard",
        "features": [
            "150 AI Credits / billing month for website generation & AI edits",
            "Up to 3 active deployment slots",
            "1 active production hosted website included",
            "Additional hosted websites available as paid add-ons ($12/mo)",
            "Custom domain connection for your included hosted website",
            "Autonomous AI Auto-Heal for 1 persistently registered website (10 repairs/mo)",
            "Discounted AI credit top-ups (40% OFF standard rates)",
            "Basic website analytics & SEO meta tools",
            "10 deployment versions & 1-click rollback per hosted site",
            "7-day backup retention",
            "Standard developer email support",
        ],
    },
    "extreme": {
        "id": "extreme",
        "name": "Extreme Plan",
        "badge": "⚡ Extreme — Full Power",
        "description": "Maximum power for agencies and builders: high AI compute, multi-site hosting, and advanced tools.",
        "monthly_price_usd": Decimal("50.00"),
        "annual_price_usd": Decimal("500.00"),  # 10 months price = 2 months free
        "annual_monthly_equivalent_usd": Decimal("41.67"),
        "monthly_price_inr": Decimal("4200.00"),
        "annual_price_inr": Decimal("42000.00"),
        "included_ai_credits": 1000,
        "free_generation_allowance": 999,
        "trial_deployment_days": 0,
        "max_deployment_slots": 999,  # Unlimited projects under fair use
        "included_hosted_websites": 3,
        "additional_hosting_price_usd": Decimal("12.00"),
        "custom_domain_allowed": True,
        "custom_domain_allowance": 3,
        "auto_heal_allowed": True,
        "auto_heal_sites_limit": 3,
        "auto_heal_repairs_per_period": 30,
        "deployment_versions_limit": 30,
        "backup_retention_days": 30,
        "token_discount_percent": 60,
        "support_tier": "priority",
        "features": [
            "1,000 AI Credits / billing month for high-volume creation & edits",
            "Unlimited saved projects & templates under fair-use storage rules",
            "Unlimited deployment updates under fair-use rate limits",
            "3 active production hosted websites included",
            "Additional hosted websites available as paid add-ons ($12/mo)",
            "Custom domain connection for all 3 included hosted websites",
            "Autonomous AI Auto-Heal for up to 3 registered websites (30 repairs/mo)",
            "Deepest AI credit top-up discount (60% OFF lowest rates)",
            "Advanced website traffic analytics & full SEO suite",
            "30 deployment versions & 1-click rollback per hosted site",
            "30-day backup retention",
            "Priority engineering support & direct escalation",
        ],
    },
}

# Alias mapping for backward compatibility
PLAN_ALIASES: Dict[str, str] = {
    "starter": "free",
    "community": "free",
    "pro": "pro",
    "creator_pro": "pro",
    "extreme": "extreme",
    "agency": "extreme",
    "enterprise": "extreme",
}


def normalize_plan_id(plan_id: str) -> str:
    """Normalizes any tier alias to 'free', 'pro', or 'extreme'."""
    clean = str(plan_id or "free").strip().lower()
    return PLAN_ALIASES.get(clean, "free")


def get_plan_config(plan_id: str) -> Dict[str, Any]:
    """Returns the immutable plan dictionary for the given normalized tier."""
    normalized = normalize_plan_id(plan_id)
    return PLANS.get(normalized, PLANS["free"])


# ---------------------------------------------------------------------------
# OPERATION CREDIT COSTS
# ---------------------------------------------------------------------------

AI_OPERATION_CREDIT_COSTS: Dict[str, int] = {
    "website_planning": 1,
    "website_generation": 5,
    "multipage_generation": 8,
    "frontend_generation": 3,
    "backend_generation": 4,
    "database_generation": 2,
    "conversational_edit": 2,
    "prompt_edit": 2,
    "seo_generation": 1,
    "ai_debugging": 2,
    "image_generation": 3,
    "auto_heal": 5,
    "content_generation": 1,
    "color_palette": 1,
}


def get_operation_cost(operation: str) -> int:
    """Returns credit cost for a given operation (defaults to 1 credit)."""
    return AI_OPERATION_CREDIT_COSTS.get(operation, 1)


# ---------------------------------------------------------------------------
# ESTIMATED PROVIDER UNIT COSTS (FOR AUDITING & PROFITABILITY DASHBOARD)
# ---------------------------------------------------------------------------

ESTIMATED_PROVIDER_COSTS: Dict[str, Decimal] = {
    # AI models: cost per average operation execution
    "gemini_flash_operation": Decimal("0.0015"),
    "gemini_pro_operation": Decimal("0.0060"),
    "gemini_embedding": Decimal("0.0001"),
    "openai_gpt4o_operation": Decimal("0.0250"),
    "openai_gpt4o_mini_operation": Decimal("0.0020"),
    "claude_sonnet_operation": Decimal("0.0200"),
    "flux_image_operation": Decimal("0.0350"),
    # Infrastructure: hosting, build, storage, bandwidth
    "hosting_per_active_site_day": Decimal("0.0050"),  # ~$0.15/mo base local edge compute
    "build_minute_cost": Decimal("0.0030"),
    "storage_per_gb_month": Decimal("0.0150"),
    "bandwidth_per_gb": Decimal("0.0500"),
    "auto_heal_avg_cost": Decimal("0.0150"),
}


# ---------------------------------------------------------------------------
# FAIR-USE DEPLOYMENT LIMITS
# ---------------------------------------------------------------------------

FAIR_USE_POLICY: Dict[str, Any] = {
    "max_concurrent_builds_per_user": 2,
    "max_build_minutes_per_month_free": 15,
    "max_build_minutes_per_month_pro": 120,
    "max_build_minutes_per_month_extreme": 500,
    "max_deployment_updates_per_hour": 15,
    "max_storage_mb_per_user_free": 100,
    "max_storage_mb_per_user_pro": 2048,      # 2 GB
    "max_storage_mb_per_user_extreme": 10240,  # 10 GB
    "max_bandwidth_gb_per_month_free": 1,
    "max_bandwidth_gb_per_month_pro": 25,
    "max_bandwidth_gb_per_month_extreme": 100,
    "grace_period_days": 3,
}
