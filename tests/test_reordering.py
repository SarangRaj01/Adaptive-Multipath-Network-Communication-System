"""
Unit tests for Sliding Window Reordering Buffer.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.packet import Packet
from core.reordering_buffer import ReorderingBuffer

class TestReorderingBuffer(unittest.TestCase):
    def setUp(self):
        self.buf = ReorderingBuffer()

    def test_in_order_stream(self):
        pkts = [Packet(seq_num=i, payload=f"p{i}") for i in range(5)]
        delivered = []
        for p in pkts:
            delivered.extend(self.buf.push(p))
            
        self.assertEqual([p.seq_num for p in delivered], [0, 1, 2, 3, 4])
        self.assertEqual(self.buf.in_order_count, 5)
        self.assertEqual(self.buf.out_of_order_count, 0)

    def test_out_of_order_stream(self):
        # Arrive in order: 0, 2, 3, 1
        p0 = Packet(seq_num=0)
        p1 = Packet(seq_num=1)
        p2 = Packet(seq_num=2)
        p3 = Packet(seq_num=3)

        d0 = self.buf.push(p0)
        self.assertEqual([p.seq_num for p in d0], [0])

        # p2 arrives: out of order, buffered
        d2 = self.buf.push(p2)
        self.assertEqual(len(d2), 0)
        self.assertEqual(self.buf.current_buffer_size(), 1)

        # p3 arrives: out of order, buffered
        d3 = self.buf.push(p3)
        self.assertEqual(len(d3), 0)
        self.assertEqual(self.buf.current_buffer_size(), 2)

        # p1 arrives: gap filled! Should release p1, p2, p3
        d1 = self.buf.push(p1)
        self.assertEqual([p.seq_num for p in d1], [1, 2, 3])
        self.assertEqual(self.buf.current_buffer_size(), 0)
        self.assertEqual(self.buf.expected_seq, 4)

    def test_duplicate_packets(self):
        p0 = Packet(seq_num=0)
        self.buf.push(p0)
        # Duplicate p0
        dup = self.buf.push(p0)
        self.assertEqual(len(dup), 0)
        self.assertEqual(self.buf.duplicate_count, 1)

if __name__ == "__main__":
    unittest.main()
