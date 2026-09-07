"""
Enterprise Asset Inventory
==========================

Authoritative catalog of all assets known to Xolaris. Every
``SecurityFindingObject.asset_id`` must reference an ``Asset.id`` here.

## Responsibilities

- Persist assets, owners, business units, environments, relationships
- Classification, criticality scoring, internet exposure, compliance tags
- Cloud + Kubernetes metadata for EC2 / Azure VM / GCP VM / Docker /
  Kubernetes / Lambda / S3 / RDS / API Gateway
- Versioning + append-only audit history
- Multi-tenant isolation and search

## HTTP

Read APIs live on the FastAPI app (not inside this package):

- `GET /api/v1/assets?tenant_id=`
- `GET /api/v1/assets/{id}`

## Non-goals

- Does not modify existing platform modules

## Quick start

```python
from uuid import uuid4
from asset_inventory import Asset, AssetInventoryContainer, AssetType

container = AssetInventoryContainer.from_url(
    "postgresql+psycopg://user:pass@localhost:5432/xolaris",
    create_tables=True,
)

asset = Asset(
    tenant_id=uuid4(),
    name="web-01",
    asset_type=AssetType.EC2,
    external_id="i-0abc123",
)

with container.session() as session:
    svc = container.build(session)
    saved = svc.assets.register_asset(asset, actor="discovery")
```

## Layout

```
asset_inventory/
  domain/         # Asset, owners, BU, env, relationships, scoring
  interfaces/     # AssetRepository ABC
  persistence/    # ORM + PostgresAssetRepository
  services/       # AssetService + AuditLogger
  query/          # filters + pagination
  di/             # composition root
```

## Architecture doc

See ``docs/architecture/10-asset-inventory.md``.
"""
