import os
import stat

import boto3
from moto import mock_aws

from edge.provision import build_device_policy, provision_device


def test_build_device_policy_scopes_to_thing():
    pol = build_device_policy()
    assert pol["Version"] == "2012-10-17"
    actions = [s["Action"] for s in pol["Statement"]]
    assert "iot:Connect" in actions
    assert "iot:Publish" in actions
    # publish is scoped to the device's own events topic via a policy variable
    pub = next(s for s in pol["Statement"] if s["Action"] == "iot:Publish")
    assert "${iot:Connection.Thing.ThingName}" in pub["Resource"]
    assert "/events" in pub["Resource"]


@mock_aws
def test_provision_device_creates_thing_cert_and_files(tmp_path):
    client = boto3.client("iot", region_name="ap-northeast-1")
    result = provision_device(
        client, thing_name="raspi-01", policy_name="raspi-accel-ai-device",
        cert_dir=str(tmp_path),
    )
    # thing exists
    assert client.describe_thing(thingName="raspi-01")["thingName"] == "raspi-01"
    # certificate arn returned and files written
    assert result["certificateArn"]
    assert os.path.exists(result["cert_path"])
    assert os.path.exists(result["key_path"])
    # principal attached to thing
    principals = client.list_thing_principals(thingName="raspi-01")["principals"]
    assert len(principals) == 1
    # private key must be created owner-read/write only (0o600)
    assert stat.S_IMODE(os.stat(result["key_path"]).st_mode) == 0o600
