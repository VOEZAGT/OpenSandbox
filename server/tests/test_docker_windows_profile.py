# Copyright 2026 Alibaba Group Holding Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from opensandbox_server.api.schema import PlatformSpec
from opensandbox_server.services.docker_windows_profile import (
    apply_windows_runtime_host_config_defaults,
    inject_windows_user_ports,
    resolve_docker_platform,
    validate_windows_runtime_prerequisites,
)


def test_apply_windows_runtime_host_config_defaults_injects_required_defaults():
    host_cfg = {"network_mode": "host"}
    updated = apply_windows_runtime_host_config_defaults(host_cfg, "sbx-1")

    assert updated["devices"] == ["/dev/kvm", "/dev/net/tun"]
    assert "NET_ADMIN" in updated["cap_add"]
    assert "NET_RAW" in updated["cap_add"]
    assert "opensandbox-win-oem-sbx-1:/oem:rw" in updated["binds"]


def test_apply_windows_runtime_host_config_defaults_removes_net_admin_from_cap_drop():
    host_cfg = {
        "cap_drop": ["NET_ADMIN", "NET_RAW", "SYS_ADMIN"],
        "binds": ["/tmp/data:/data:rw"],
    }
    updated = apply_windows_runtime_host_config_defaults(host_cfg, "sbx-2")

    assert "NET_ADMIN" not in (updated.get("cap_drop") or [])
    assert "NET_RAW" not in (updated.get("cap_drop") or [])
    assert "SYS_ADMIN" in (updated.get("cap_drop") or [])
    assert "/tmp/data:/data:rw" in updated["binds"]


def test_validate_windows_runtime_prerequisites_reports_missing_devices():
    with patch("opensandbox_server.services.docker_windows_profile.os.path.exists", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            validate_windows_runtime_prerequisites()

    assert exc_info.value.status_code == 400
    assert "/dev/kvm" in exc_info.value.detail["message"]
    assert "/dev/net/tun" in exc_info.value.detail["message"]


def test_resolve_docker_platform_skips_windows_profile():
    assert (
        resolve_docker_platform(PlatformSpec(os="windows", arch="amd64"))
        is None
    )


def test_resolve_docker_platform_preserves_linux_profile():
    assert (
        resolve_docker_platform(PlatformSpec(os="linux", arch="arm64"))
        == "linux/arm64"
    )


def test_inject_windows_user_ports_appends_when_missing():
    env = ["VERSION=11"]
    updated = inject_windows_user_ports(env, ["44772", "8080/tcp"])
    assert "VERSION=11" in updated
    assert "USER_PORTS=44772,8080" in updated


def test_inject_windows_user_ports_merges_existing_value():
    env = ["USER_PORTS=3389,44772", "VERSION=11"]
    updated = inject_windows_user_ports(env, ["44772", "8080"])
    assert "USER_PORTS=3389,44772,8080" in updated


