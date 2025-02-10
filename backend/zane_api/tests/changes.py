from .base import AuthAPITestCase
from ..views.helpers import (
    compute_docker_changes_from_snapshots,
    compute_docker_service_snapshot,
)
from ..dtos import DockerServiceSnapshot, DeploymentChangeDto
from ..utils import jprint

current = {
    "created_at": "2025-01-31T18:30:04.436667Z",
    "updated_at": "2025-02-09T20:22:34.654748Z",
    "id": "srv_dkr_Cah22cAvF7e",
    "slug": "nginx-demo",
    "image": "nginxdemos/hello",
    "command": None,
    "healthcheck": None,
    "project_id": "prj_v6nBYFktpca",
    "credentials": None,
    "urls": [
        {
            "id": "url_s2zNUEHw5rw",
            "domain": "hello-nginx.127-0-0-1.sslip.io",
            "base_path": "/",
            "strip_prefix": True,
            "redirect_to": None,
            "associated_port": 80,
        }
    ],
    "volumes": [],
    "deploy_token": "wSbSbaCvt28jaYswwIAy",
    "ports": [],
    "env_variables": [],
    "network_aliases": [
        "zn-demo-Cah22cAvF7e.zaneops.internal",
        "zn-demo-Cah22cAvF7e",
    ],
    "network_alias": "zn-demo-Cah22cAvF7e",
    "unapplied_changes": [],
    "resource_limits": None,
    "system_env_variables": [
        {
            "key": "ZANE",
            "value": "true",
            "comment": "Is the service deployed on zaneops?",
        },
        {
            "key": "ZANE_PRIVATE_DOMAIN",
            "value": "zn-demo-Cah22cAvF7e.zaneops.internal",
            "comment": "The domain used to reach this service on the same project",
        },
        {
            "key": "ZANE_DEPLOYMENT_TYPE",
            "value": "docker",
            "comment": "The type of the service",
        },
        {
            "key": "ZANE_SERVICE_ID",
            "value": "srv_dkr_Cah22cAvF7e",
            "comment": "The service ID",
        },
        {
            "key": "ZANE_SERVICE_NAME",
            "value": "nginx-demo",
            "comment": "The name of this service",
        },
        {
            "key": "ZANE_PROJECT_ID",
            "value": "prj_v6nBYFktpca",
            "comment": "The id for the project this service belongs to",
        },
        {
            "key": "ZANE_DEPLOYMENT_SLOT",
            "value": "{{deployment.slot}}",
            "comment": "The slot for each deployment it can be `blue` or `green`, this is also sent as the header `x-zane-dpl-slot`",
        },
        {
            "key": "ZANE_DEPLOYMENT_HASH",
            "value": "{{deployment.hash}}",
            "comment": "The hash of each deployment, this is also sent as a header `x-zane-dpl-hash`",
        },
    ],
    "configs": [],
}

# Old version of the snapshot
target = {
    "created_at": "2025-01-31T18:30:04.436667Z",
    "updated_at": "2025-01-31T18:31:17.138274Z",
    "id": "srv_dkr_Cah22cAvF7e",
    "slug": "demo",
    "image": "nginxdemos/hello",
    "command": None,
    "healthcheck": None,
    "project_id": "prj_v6nBYFktpca",
    "credentials": None,
    "healthcheck": {
        "id": "htc_MtmB4YDWF3m",
        "type": "PATH",
        "value": "/",
        "timeout_seconds": 30,
        "interval_seconds": 5,
        "associated_port": None,
    },
    "urls": [
        {
            "id": "url_drf3NEFiri8",
            "domain": "hello-nginx.127-0-0-1.sslip.io",
            "base_path": "/",
            "strip_prefix": True,
            "redirect_to": None,
        }
    ],
    "volumes": [],
    "deploy_token": "wSbSbaCvt28jaYswwIAy",
    "ports": [
        {
            "id": "prt_JKEjTkBXf9y",
            "host": None,
            "forwarded": 80,
        },
    ],
    "env_variables": [],
    "network_aliases": [
        "zn-demo-Cah22cAvF7e.zaneops.internal",
        "zn-demo-Cah22cAvF7e",
    ],
    "network_alias": "zn-demo-Cah22cAvF7e",
    "unapplied_changes": [],
    "resource_limits": None,
    "system_env_variables": [
        {
            "key": "ZANE",
            "value": "true",
            "comment": "Is the service deployed on zaneops?",
        },
        {
            "key": "ZANE_PRIVATE_DOMAIN",
            "value": "zn-demo-Cah22cAvF7e.zaneops.internal",
            "comment": "The domain used to reach this service on the same project",
        },
        {
            "key": "ZANE_DEPLOYMENT_TYPE",
            "value": "docker",
            "comment": "The type of the service",
        },
        {
            "key": "ZANE_SERVICE_ID",
            "value": "srv_dkr_Cah22cAvF7e",
            "comment": "The service ID",
        },
        {
            "key": "ZANE_SERVICE_NAME",
            "value": "demo",
            "comment": "The name of this service",
        },
        {
            "key": "ZANE_PROJECT_ID",
            "value": "prj_v6nBYFktpca",
            "comment": "The id for the project this service belongs to",
        },
        {
            "key": "ZANE_DEPLOYMENT_SLOT",
            "value": "{{deployment.slot}}",
            "comment": "The slot for each deployment it can be `blue` or `green`, this is also sent as the header `x-zane-dpl-slot`",
        },
        {
            "key": "ZANE_DEPLOYMENT_HASH",
            "value": "{{deployment.hash}}",
            "comment": "The hash of each deployment, this is also sent as a header `x-zane-dpl-hash`",
        },
        {
            "key": "ZANE_DEPLOYMENT_URL",
            "value": "{{deployment.url}}",
            "comment": "The url of each deployment, this is empty for services that don't have any url.",
        },
    ],
}


class DockerDeploymentChangesTests(AuthAPITestCase):

    def test_compute_redeploy_changes_correctly(self):
        changes = compute_docker_changes_from_snapshots(current, target)
        current_snapshot = DockerServiceSnapshot.from_dict(current)

        new_snapshot = compute_docker_service_snapshot(
            current_snapshot,
            [
                DeploymentChangeDto.from_dict(
                    dict(
                        type=change.type,
                        field=change.field,
                        new_value=change.new_value,
                        old_value=change.old_value,
                        item_id=change.item_id,
                    )
                )
                for change in changes
            ],
        )
        jprint(new_snapshot)
        for url in new_snapshot.urls:
            if url.redirect_to is None:
                self.assertIsNotNone(url.associated_port)
        for port in new_snapshot.ports:
            self.assertNotIn(port.host, [None, 80, 443])
        if (
            new_snapshot.healthcheck is not None
            and new_snapshot.healthcheck.type == "PATH"
        ):
            self.assertIsNotNone(new_snapshot.healthcheck.associated_port)
