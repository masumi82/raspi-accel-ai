from edge.mqtt_client import Publisher, AwsIotPublisher


def test_aws_publisher_is_a_publisher():
    assert issubclass(AwsIotPublisher, Publisher)


def test_construction_does_not_import_sdk():
    # Must construct without awsiotsdk installed (deferred import in connect/publish).
    pub = AwsIotPublisher(
        endpoint="x.iot.ap-northeast-1.amazonaws.com",
        cert_path="certs/c.pem",
        key_path="certs/k.pem",
        ca_path="certs/ca.pem",
        client_id="raspi-01",
    )
    assert pub is not None


def test_connect_without_sdk_raises_import_error():
    pub = AwsIotPublisher(
        endpoint="x",
        cert_path="c",
        key_path="k",
        ca_path="ca",
        client_id="raspi-01",
    )
    # awsiotsdk is not installed in the dev venv → connect() should surface ImportError.
    import pytest

    with pytest.raises(ModuleNotFoundError):
        pub.connect()
