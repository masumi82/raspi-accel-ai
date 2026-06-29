import json


class Publisher:
    def connect(self):
        raise NotImplementedError

    def publish(self, topic, payload):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError


class AwsIotPublisher(Publisher):
    """AWS IoT Core MQTT over mTLS. awsiotsdk is imported lazily so this
    module and class import/construct off-device. Validated against real
    IoT Core, not unit-tested."""

    def __init__(self, *, endpoint, cert_path, key_path, ca_path, client_id):
        self._endpoint = endpoint
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_path = ca_path
        self._client_id = client_id
        self._conn = None

    def connect(self):
        from awsiot import mqtt_connection_builder

        self._conn = mqtt_connection_builder.mtls_from_path(
            endpoint=self._endpoint,
            cert_filepath=self._cert_path,
            pri_key_filepath=self._key_path,
            ca_filepath=self._ca_path,
            client_id=self._client_id,
            clean_session=False,
            keep_alive_secs=30,
        )
        self._conn.connect().result()

    def publish(self, topic, payload):
        if self._conn is None:
            raise RuntimeError("connect() must be called before publish()")
        from awscrt import mqtt

        future, _ = self._conn.publish(
            topic=topic,
            payload=json.dumps(payload, ensure_ascii=False),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
        future.result()

    def disconnect(self):
        if self._conn is not None:
            self._conn.disconnect().result()
            self._conn = None
