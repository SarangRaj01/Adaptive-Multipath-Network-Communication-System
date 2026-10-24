"""
Receiver-Side Sliding Window & Reordering Buffer.
Author: Dev Raj (Spraying & Reordering Lead)
"""

import heapq
from typing import List, Optional, Tuple, Set
from .packet import Packet

class ReorderingBuffer:
    def __init__(self, initial_seq: int = 0):
        self.expected_seq = initial_seq
        self._heap: List[Tuple[int, Packet]] = []
        self._buffered_seqs: Set[int] = set()
        
        # Telemetry metrics
        self.total_received = 0
        self.in_order_count = 0
        self.out_of_order_count = 0
        self.duplicate_count = 0
        self.max_buffer_depth = 0
        self.delivered_packets: List[Packet] = []

    def push(self, packet: Packet) -> List[Packet]:
        """
        Processes an incoming packet.
        Returns a list of ordered packets that are ready for immediate delivery.
        """
        self.total_received += 1
        seq = packet.seq_num
        
        # 1. Duplicate or old packet
        if seq < self.expected_seq or seq in self._buffered_seqs:
            self.duplicate_count += 1
            return []
            
        # 2. In-order packet arrived
        if seq == self.expected_seq:
            self.in_order_count += 1
            deliverable = [packet]
            self.expected_seq += 1
            
            # Drain any contiguous buffered packets
            while self._heap and self._heap[0][0] == self.expected_seq:
                next_seq, next_pkt = heapq.heappop(self._heap)
                self._buffered_seqs.remove(next_seq)
                deliverable.append(next_pkt)
                self.expected_seq += 1
                
            self.delivered_packets.extend(deliverable)
            return deliverable

        # 3. Out-of-order packet (future packet with gap)
        self.out_of_order_count += 1
        heapq.heappush(self._heap, (seq, packet))
        self._buffered_seqs.add(seq)
        
        if len(self._heap) > self.max_buffer_depth:
            self.max_buffer_depth = len(self._heap)
            
        return []

    def get_missing_sequences(self, max_gaps: int = 20) -> List[int]:
        """
        Returns the list of missing sequence numbers between expected_seq
        and the highest buffered sequence number. Useful for selective NACKs.
        """
        if not self._buffered_seqs:
            return []
            
        max_buffered = max(self._buffered_seqs)
        missing = []
        for seq in range(self.expected_seq, max_buffered):
            if seq not in self._buffered_seqs:
                missing.append(seq)
                if len(missing) >= max_gaps:
                    break
        return missing

    def current_buffer_size(self) -> int:
        return len(self._heap)

    def reset(self, initial_seq: int = 0):
        self.expected_seq = initial_seq
        self._heap.clear()
        self._buffered_seqs.clear()
        self.total_received = 0
        self.in_order_count = 0
        self.out_of_order_count = 0
        self.duplicate_count = 0
        self.max_buffer_depth = 0
        self.delivered_packets.clear()
