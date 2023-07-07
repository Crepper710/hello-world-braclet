import bluetooth
import socket
import asyncio
import packets
import re
import random


def _get_topics():
    from main import topics
    return topics


def _get_id():
    import main
    return main.id


_NAME_PATTERN = re.compile("^hwb-.+$")


_MAX_PACKET_LEN = 0x10001


class DeviceDiscoverer:
    def __init__(self, search_duration = 8, history_depth = 10) -> None:
        self._running = True
        self._search_duration = search_duration
        self._history = [[] for i in range(history_depth)]

    def run(self):
        while self._running:
            asyncio.run(self._run_once())

    async def _run_once(self):
        from main import start_communication, is_communicating, end_communication
        addrs = bluetooth.discover_devices(duration=self._search_duration, lookup_names=True)
        print("found devices:", *addrs, sep="\n\t")
        # double check because the statment before needs time to be executed
        if self._running and not is_communicating():
            sub_history = []
            for (addr, name) in addrs:
                if _NAME_PATTERN.match(name) and not self._is_in_history(addr):
                    if self._exchange_topics(addr, start_communication, is_communicating, end_communication):
                        sub_history.append(addr)
            self._history.pop(0)
            self._history.append(sub_history)
    
    def _is_in_history(self, addr: str):
        for sub_history in self._history:
            if addr in sub_history:
                return True
        return False
    
    def _exchange_topics(self, addr: str, start_communication, is_communicating, end_communication) -> bool:
        print(f"try talking to {addr}")
        with socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        ) as c:
            try:
                c.connect((addr, 1))
                topics = _get_topics()

                exchange_packet = packets.InfoExchangePacket(_get_id(), topics)
                c.send(exchange_packet.to_bytes())

                packet_bytes = c.recv(_MAX_PACKET_LEN)
                packet = packets.BasePacket.from_bytes(packet_bytes)
                if type(packet) is not packets.InfoExchangePacket:
                    print("expected info exchange packet")
                    return True
                o_exchange_packet = packet
                print(f"topics from {o_exchange_packet.id.hex()} are:", o_exchange_packet.topics)

                matching_topics = []
                for topic in o_exchange_packet.topics:
                    if topic in topics:
                        matching_topics.append(topic)
                
                if len(matching_topics) > 0 and (is_communicating(with_=o_exchange_packet.id) or not is_communicating()):
                    matching_topic = matching_topics[random.randrange(0, len(matching_topics))]
                    communicate = True
                    start_communication(o_exchange_packet.id)
                else:
                    matching_topic = ""
                    communicate = False
                
                negotiate_packet = packets.NegotiationPacket(communicate, matching_topic)
                c.send(negotiate_packet.to_bytes())

                packet_bytes = c.recv(_MAX_PACKET_LEN)
                packet = packets.BasePacket.from_bytes(packet_bytes)
                if type(packet) is not packets.NegotiationPacket:
                    print("expected info negotiate packet")
                    return True
                o_negotiate_packet = packet
                if o_negotiate_packet.communicate:
                    print(f"{o_exchange_packet.id.hex()} wants to communicate with you about {o_negotiate_packet.topic}")
                else:
                    print(f"{o_exchange_packet.id.hex()} does not want to communicate with you about")
                    if communicate:
                        end_communication()
                return True
            except OSError:
                return False
