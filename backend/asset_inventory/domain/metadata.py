"""Cloud and Kubernetes metadata envelopes."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field, field_validator

from models.common import FortiBaseModel
from asset_inventory.domain.enums import CloudProvider


class CloudMetadata(FortiBaseModel):
    """Provider-agnostic cloud resource metadata."""

    provider: CloudProvider = Field(default=CloudProvider.NONE)
    account_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Cloud account / subscription / project id.",
    )
    region: Optional[str] = Field(default=None, max_length=64)
    availability_zone: Optional[str] = Field(default=None, max_length=64)
    resource_id: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Native resource id (ARN, Azure ID, GCP selfLink).",
    )
    resource_name: Optional[str] = Field(default=None, max_length=256)
    resource_group: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Azure resource group or equivalent.",
    )
    vpc_id: Optional[str] = Field(default=None, max_length=128)
    subnet_ids: List[str] = Field(default_factory=list)
    instance_type: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Instance / SKU / machine type.",
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Cloud-native tags mirrored for search.",
    )

    @field_validator("subnet_ids")
    @classmethod
    def limit_subnets(cls, value: List[str]) -> List[str]:
        if len(value) > 64:
            raise ValueError("subnet_ids limited to 64")
        return value

    @field_validator("tags")
    @classmethod
    def limit_tags(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 64:
            raise ValueError("cloud tags limited to 64")
        return value


class KubernetesMetadata(FortiBaseModel):
    """Kubernetes workload / object metadata."""

    cluster_name: Optional[str] = Field(default=None, max_length=256)
    cluster_id: Optional[str] = Field(default=None, max_length=256)
    namespace: Optional[str] = Field(default=None, max_length=253)
    kind: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Pod, Deployment, Service, Node, etc.",
    )
    name: Optional[str] = Field(default=None, max_length=253)
    uid: Optional[str] = Field(default=None, max_length=64)
    node_name: Optional[str] = Field(default=None, max_length=253)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    container_images: List[str] = Field(default_factory=list)
    service_account: Optional[str] = Field(default=None, max_length=253)

    @field_validator("labels", "annotations")
    @classmethod
    def limit_maps(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 64:
            raise ValueError("k8s maps limited to 64 entries")
        return value

    @field_validator("container_images")
    @classmethod
    def limit_images(cls, value: List[str]) -> List[str]:
        if len(value) > 128:
            raise ValueError("container_images limited to 128")
        return value
