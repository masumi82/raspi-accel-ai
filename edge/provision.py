import json
import os


def build_device_policy():
    """Least-privilege IoT policy: a device may connect as its own client id
    and publish only to its own events topic, scoped via policy variables."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": "arn:aws:iot:*:*:client/${iot:Connection.Thing.ThingName}",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Publish",
                "Resource": "arn:aws:iot:*:*:topic/devices/${iot:Connection.Thing.ThingName}/events",
            },
        ],
    }


def _ensure_policy(iot_client, policy_name):
    try:
        iot_client.get_policy(policyName=policy_name)
    except iot_client.exceptions.ResourceNotFoundException:
        iot_client.create_policy(
            policyName=policy_name,
            policyDocument=json.dumps(build_device_policy()),
        )


def provision_device(iot_client, thing_name, policy_name, cert_dir):
    iot_client.create_thing(thingName=thing_name)
    keys = iot_client.create_keys_and_certificate(setAsActive=True)
    cert_arn = keys["certificateArn"]
    _ensure_policy(iot_client, policy_name)
    iot_client.attach_policy(policyName=policy_name, target=cert_arn)
    iot_client.attach_thing_principal(thingName=thing_name, principal=cert_arn)

    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "device.cert.pem")
    key_path = os.path.join(cert_dir, "device.private.key")
    with open(cert_path, "w") as f:
        f.write(keys["certificatePem"])
    with open(key_path, "w") as f:
        f.write(keys["keyPair"]["PrivateKey"])
    os.chmod(key_path, 0o600)
    return {"certificateArn": cert_arn, "cert_path": cert_path, "key_path": key_path}


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import boto3

    parser = argparse.ArgumentParser(description="Provision an IoT device (thing + cert + policy).")
    parser.add_argument("--thing-name", default="raspi-01")
    parser.add_argument("--policy-name", default="raspi-accel-ai-device")
    parser.add_argument("--cert-dir", default="certs")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()
    client = boto3.client("iot", region_name=args.region)
    out = provision_device(client, args.thing_name, args.policy_name, args.cert_dir)
    print(f"certificateArn: {out['certificateArn']}")
    print(f"cert: {out['cert_path']}  key: {out['key_path']}")
    print("Download the Amazon Root CA1 to certs/AmazonRootCA1.pem before connecting.")
