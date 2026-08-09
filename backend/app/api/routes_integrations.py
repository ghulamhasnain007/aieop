from fastapi import APIRouter

from app.integrations import ADAPTER_REGISTRY
from app.schemas.common import IntegrationHealthItem

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationHealthItem])
def list_integrations():
    results = []
    for provider, adapter in ADAPTER_REGISTRY.items():
        status = adapter.health_check()
        results.append(IntegrationHealthItem(provider=provider, connected=status.connected, detail=status.detail))
    return results


@router.post("/{provider}/test", response_model=IntegrationHealthItem)
def test_integration(provider: str):
    adapter = ADAPTER_REGISTRY.get(provider)
    if not adapter:
        return IntegrationHealthItem(provider=provider, connected=False, detail="Unknown provider")
    status = adapter.health_check()
    return IntegrationHealthItem(provider=provider, connected=status.connected, detail=status.detail)
