"""
Packet definitions and serialization for the Adaptive Multipath Communication System.
Author: Sarang Raj (Topology & Packet Structure Lead)
"""

import zlib
import json
import time
from typing import Optional, Dict, Any

class PacketType:
    DATA = "DATA"
    ACK = "ACK"
    NACK = "NACK"
    PROBE = "PROBE"
    PROBE_ACK = "PROBE_ACK"

class QoSClass:
    HIGH = "HIGH"      # Latency-sensitive (e.g., VoIP, Video Streaming)
    NORMAL = "NORMAL"  # Interactive Web / API
    LOW = "LOW"        # Bulk Data Transfer / Background download

class Packet:
    def __init__(
        self,
        seq_num: int,
        pkt_type: str = PacketType.DATA,
        payload: str = "",
        path_id: str = "DIRECT",
        qos_class: str = QoSClass.NORMAL,
        timestamp: Optional[float] = None,
        checksum: Optional[int] = None
    ):
        self.seq_num = seq_num
        self.pkt_type = pkt_type
        self.payload = payload
        self.path_id = path_id
        self.qos_class = qos_class
        self.timestamp = timestamp if timestamp is not None else time.time()
        
        if checksum is None:
            self.checksum = self.calculate_checksum()
        else:
            self.checksum = checksum

    def _content_bytes(self) -> bytes:
        """Returns binary content used to compute and verify the checksum."""
        data_tuple = (self.seq_num, self.pkt_type, self.payload, self.path_id, self.qos_class)
        return json.dumps(data_tuple, sort_keys=True).encode('utf-8')

    def calculate_checksum(self) -> int:
        """Computes a 32-bit CRC32 checksum across header fields and payload."""
        return zlib.crc32(self._content_bytes()) & 0xFFFFFFFF

    def verify_checksum(self) -> bool:
        """Verifies if the packet integrity is intact."""
        return self.checksum == self.calculate_checksum()

    def serialize(self) -> bytes:
        """Serializes the packet into UTF-8 JSON bytes for transmission over UDP."""
        data = {
            "seq_num": self.seq_num,
            "pkt_type": self.pkt_type,
            "payload": self.payload,
            "path_id": self.path_id,
            "qos_class": self.qos_class,
            "timestamp": self.timestamp,
            "checksum": self.checksum
        }
        return json.dumps(data).encode('utf-8')

    @classmethod
    def deserialize(cls, raw_bytes: bytes) -> "Packet":
        """Reconstructs a Packet instance from raw network bytes."""
        data: Dict[str, Any] = json.loads(raw_bytes.decode('utf-8'))
        return cls(
            seq_num=data["seq_num"],
            pkt_type=data["pkt_type"],
            payload=data.get("payload", ""),
            path_id=data.get("path_id", "UNKNOWN"),
            qos_class=data.get("qos_class", QoSClass.NORMAL),
            timestamp=data.get("timestamp", 0.0),
            checksum=data.get("checksum", 0)
        )

    def __repr__(self) -> str:
        return f"<Packet #{self.seq_num} type={self.pkt_type} path={self.path_id} qos={self.qos_class} len={len(self.payload)}>"
