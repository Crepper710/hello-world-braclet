import threading
import os
import random
from typing import Union, List

from server import create_main_loop
import packets


topics = ["Fußball", "Billard", "Klarinette"]
id = b"test_hwb"

_MAX_PACKET_LEN = 0x10001


class ConnectionData:
    def __init__(self):
        self.id: Union[str, None] = None
        self.topics: Union[List[str], None] = None


def io_cb(obj, fd, conditions):
    try:
        if not hasattr(obj, "data"):
            obj.data = ConnectionData()
        data = obj.data
        packet_bytes = os.read(fd, _MAX_PACKET_LEN)
        packet = packets.BasePacket.from_bytes(packet_bytes)
        if type(packet) is packets.InfoExchangePacket:
            on_info_exchange(data, packet, fd)
        elif type(packet) is packets.NegotiationPacket:
            on_negotionation(data, packet, fd)
        return True
    except:
        return False


def on_info_exchange(data: ConnectionData, packet: packets.InfoExchangePacket, fd):
    print(f"topics from {packet.id.hex()} are:", packet.topics)
    data.id = packet.id
    data.topics = packet.topics
    exchange_packet = packets.InfoExchangePacket(id, topics)
    b = exchange_packet.to_bytes()
    os.write(fd, b)


def on_negotionation(data: ConnectionData, packet: packets.NegotiationPacket, fd):
    if data.id is None:
        exchange_packet = packets.NegotiationPacket(False, "")
        b = exchange_packet.to_bytes()
        os.write(fd, b)
        return

    if packet.communicate:
        print(f"{data.id.hex()} wants to communicate with you about {packet.topic}")
    else:
        print(f"{data.id.hex()} does not want to communicate with you about")
        exchange_packet = packets.NegotiationPacket(False, "")
        b = exchange_packet.to_bytes()
        os.write(fd, b)
        return
    
    if is_communicating() and not is_communicating(with_=data.id):
        exchange_packet = packets.NegotiationPacket(False, "")
        b = exchange_packet.to_bytes()
        os.write(fd, b)
        return
    
    if data.topics is not None:
        if packet.topic not in  data.topics or packet.topic not in topics:
            exchange_packet = packets.NegotiationPacket(False, "")
            b = exchange_packet.to_bytes()
            os.write(fd, b)
            return
    else:
        exchange_packet = packets.NegotiationPacket(False, "")
        b = exchange_packet.to_bytes()
        os.write(fd, b)
        return
    # if every thing is valid a packet with the same content should be send back
    # in other words the exact same packet can be send back
    b = packet.to_bytes()
    os.write(fd, b)
    start_communication(data.id)


_current_communication_partner: Union[bytes, None] = None

def start_communication(partner: bytes):
    global _current_communication_partner
    _current_communication_partner = partner

def end_communication():
    global _current_communication_partner
    _current_communication_partner = None

def is_communicating(*, with_: Union[bytes, None] = None):
    if with_ is None:
        return _current_communication_partner is not None
    else:
        return _current_communication_partner == with_


def main():
    from client import DeviceDiscoverer
    main_loop = create_main_loop(io_cb)
    dd = DeviceDiscoverer()
    server_thread = threading.Thread(target=main_loop.run)
    server_thread.start()
    try:
        dd.run()
        server_thread.join()
    except KeyboardInterrupt:
        print("shuting down due to keyboard interrupt")
        main_loop.quit()
        server_thread.join()


if __name__ == "__main__":
    main()