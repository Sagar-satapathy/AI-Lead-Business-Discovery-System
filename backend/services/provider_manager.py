"""
backend/services/provider_manager.py - Provider Selection & Management Subsystem

Manages external search discovery providers under strict ₹0 budget constraints:
- Tavily: Primary configurable free provider (1,000 free searches/month).
- Serper: Optional external provider (used ONLY if explicitly configured).
- Mwmbl: Optional keyless open-source search engine.
- Static Benchmark: Zero-network fallback for predefined demonstration benchmarks.

Rules:
1. Never automatically switch to a paid provider.
2. Never initiate paid requests.
3. When free credits are exhausted, report it gracefully without silently falling back to static mode.
"""

from typing import Tuple, Dict, Any, Optional
from backend.config import settings
from backend.services.tavily_provider import TavilyProvider
from backend.services.serper_provider import SerperProvider
from backend.services.mwmbl_provider import MwmblProvider

SUPPORTED_PROVIDERS = ["tavily", "serper", "mwmbl", "static_benchmark", "auto"]


def get_active_discovery_provider() -> Tuple[str, Any]:
    """
    Resolves the active discovery provider based on DISCOVERY_PROVIDER setting.
    Returns (provider_name: str, provider_instance: Optional[Any]).
    """
    configured_pref = (settings.DISCOVERY_PROVIDER or "auto").lower().strip()

    if configured_pref == "tavily":
        return "tavily", TavilyProvider()

    elif configured_pref == "serper":
        return "serper", SerperProvider()

    elif configured_pref == "mwmbl":
        return "mwmbl", MwmblProvider()

    elif configured_pref == "static_benchmark":
        return "static_benchmark", None

    elif configured_pref == "auto":
        # Rule 4 & 5: Tavily is the primary configurable provider for free discovery.
        tavily = TavilyProvider()
        if tavily.is_configured():
            return "tavily", tavily

        # Serper is optional and used ONLY when explicitly configured.
        serper = SerperProvider()
        if serper.is_configured():
            return "serper", serper

        # Mwmbl is a keyless public search provider. Use it before demonstration
        # benchmarks so AUTO mode performs live discovery without requiring a key.
        mwmbl = MwmblProvider()
        if mwmbl.is_configured():
            return "mwmbl", mwmbl

        # Static benchmarks are used only when no live provider is available.
        return "static_benchmark", None

    # Fallback to static benchmarks for unknown strings
    return "static_benchmark", None


def get_all_providers_status() -> Dict[str, Any]:
    """
    Returns unified health and status report across all discovery providers.
    """
    active_name, active_instance = get_active_discovery_provider()
    tavily = TavilyProvider()
    serper = SerperProvider()
    mwmbl = MwmblProvider()

    live_configured = bool(active_instance and active_instance.is_configured())
    operational = bool(active_instance and active_instance.is_operational())
    has_executed = bool(active_instance and active_instance.has_executed_live_search())

    return {
        "active_provider": active_name,
        "configured_preference": (settings.DISCOVERY_PROVIDER or "auto").lower(),
        "live_search_configured": live_configured,
        "operational": operational,
        "live_search_executed": has_executed,
        "mode": "live_search" if live_configured else "static_benchmark",
        "providers": {
            "tavily": tavily.get_status(),
            "serper": serper.get_status(),
            "mwmbl": mwmbl.get_status(),
            "static_benchmark": {
                "name": "Predefined Demonstration Benchmarks",
                "configured": True,
                "operational": True,
                "free_tier": True,
            },
        },
    }
