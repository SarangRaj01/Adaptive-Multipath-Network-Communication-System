"""
Unit tests for Packet formatting, serialization, and CRC32 verification.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.packet import Packet, PacketType, QoSClass

class TestPacket(unittest.TestCase):
    def test_packet_creation_and_checksum(self):
        pkt = Packet(seq_num=10, pkt_type=PacketType.DATA, payload="Hello Multipath")
        self.assertEqual(pkt.seq_num, 10)
        self.assertTrue(pkt.verify_checksum())

    def test_serialization_and_deserialization(self):
        original = Packet(
            seq_num=42,
            pkt_type=PacketType.DATA,
            payload="Sensitive payload test",
            path_id="R2",
            qos_class=QoSClass.HIGH
        )
        raw = original.serialize()
        restored = Packet.deserialize(raw)
        
        self.assertEqual(restored.seq_num, original.seq_num)
        self.assertEqual(restored.payload, original.payload)
        self.assertEqual(restored.path_id, original.path_id)
        self.assertEqual(restored.qos_class, original.qos_class)
        self.assertTrue(restored.verify_checksum())

    def test_tamper_detection(self):
        pkt = Packet(seq_num=1, payload="Original Data")
        # Tamper payload without updating checksum
        pkt.payload = "Tampered Data"
        self.assertFalse(pkt.verify_checksum())

if __name__ == "__main__":
    unittest.main()
