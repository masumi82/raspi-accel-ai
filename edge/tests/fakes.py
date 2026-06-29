from edge.mqtt_client import Publisher


class FakePublisher(Publisher):
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []
        self.connected = False

    def connect(self):
        self.connected = True

    def publish(self, topic, payload):
        if self.fail:
            raise ConnectionError("offline")
        self.published.append((topic, payload))

    def disconnect(self):
        self.connected = False
