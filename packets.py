from typing import List

_MAX_STR_LEN = 255

class BasePacket:
    @classmethod
    def from_bytes(cls, b: bytes) -> "BasePacket":
        packet_id = b[0]
        b = b[1:]
        if packet_id == InfoExchangePacket.packet_id:
            return InfoExchangePacket.from_bytes(b)
        elif packet_id == NegotiationPacket.packet_id:
            return NegotiationPacket.from_bytes(b)
        
    def to_bytes(self) -> bytes:
        if not hasattr(self, "packet_id"):
            raise NotImplementedError("This function should be called from a subclass, which has packet_id set as an attribute")
        return self.packet_id.to_bytes(1, "big", signed=False)


class InfoExchangePacket(BasePacket):
    packet_id = 1

    @classmethod
    def from_bytes(cls, b: bytes) -> "InfoExchangePacket":
        # deserialize id
        id_length = b[0]
        b = b[1:]
        id = b[0:id_length]
        b = b[id_length:]

        # deserialize topics
        topic_count = b[0]
        b = b[1:]
        topics = ["" for i in range(topic_count)]
        for i in range(topic_count):
            topic_length = b[0]
            b = b[1:]
            topic_name = b[0:topic_length].decode()
            b = b[topic_length:]

            topics[i] = topic_name

        return InfoExchangePacket(id, topics)

    
    def __init__(self, id: bytes, topics: List[str]):
        super().__init__()
        self.id = id
        self.topics = topics

    def to_bytes(self) -> bytes:
        b = super().to_bytes()
        
        # serialize id
        id = self.id[:255]
        b += len(id).to_bytes(1, "big", signed=False)
        b += id

        # serialize topics
        b += len(self.topics).to_bytes(1, "big", signed=False)
        for topic in self.topics:
            topic = topic.encode()[:255]
            b += len(topic).to_bytes(1, "big", signed=False)
            b += topic
        
        return b


class NegotiationPacket(BasePacket):
    packet_id = 2

    @classmethod
    def from_bytes(cls, b: bytes) -> "NegotiationPacket":
        communicate = b[0] != 0
        b = b[1:]
        topic_length = b[0]
        b = b[1:]
        topic = b[0:topic_length].decode()
        b = b[topic_length:]
        return NegotiationPacket(communicate, topic)
    
    def __init__(self, communicate: bool, topic: str):
        super().__init__()
        self.communicate = communicate
        self.topic = topic

    def to_bytes(self) -> bytes:
        b = super().to_bytes()
        if self.communicate:
            b += b"\x01"
        else:
            b += b"\x00"
        topic = self.topic.encode()[:255]
        b += len(topic).to_bytes(1, "big", signed=False)
        b += topic
        return b
