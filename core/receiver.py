"""
Receiver Node (R5 / Egress) with Reordering Buffer and Telemetry.
Author: Dev Raj & Antony Roy
"""

import socket
import threading
import time
from typing import Optional, List, Dict, Any
from .packet import Packet, PacketType
from .reordering_buffer import ReorderingBuffer

class ReceiverNode:
    def __init__(self, listen_host: str, listen_port: int, sender_host: str, sender_port: int):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.sender_addr = (sender_host, sender_port)
        
        self.reorder_buffer = ReorderingBuffer()
        self.received_log: List[Dict[str, Any]] = []
        self.corrupted_count = 0
        
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.listen_host, self.listen_port))
        self._socket.settimeout(0.5)
        
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="ReceiverNode")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._socket:
            self._socket.close()

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                now = time.time()
                
                try:
                    pkt = Packet.deserialize(data)
                except Exception:
                    with self._lock:
                        self.corrupted_count += 1
                    continue
                    
                if not pkt.verify_checksum():
                    with self._lock:
                        self.corrupted_count += 1
                    continue

                if pkt.pkt_type == PacketType.PROBE:
                    # Echo back PROBE_ACK immediately to sender
                    probe_ack = Packet(
                        seq_num=pkt.seq_num,
                        pkt_type=PacketType.PROBE_ACK,
                        payload=pkt.payload,
                        path_id=pkt.path_id,
                        timestamp=pkt.timestamp  # Echo original sender timestamp
                    )
                    self._send_response(probe_ack)
                    
                elif pkt.pkt_type == PacketType.DATA:
                    # 1. Send ACK back to sender
                    ack_pkt = Packet(
                        seq_num=pkt.seq_num,
                        pkt_type=PacketType.ACK,
                        path_id=pkt.path_id,
                        timestamp=pkt.timestamp
                    )
                    self._send_response(ack_pkt)
                    
                    # 2. Push to reordering buffer
                    with self._lock:
                        deliverable = self.reorder_buffer.push(pkt)
                        one_way_latency_ms = max(0.1, (now - pkt.timestamp) * 1000.0)
                        
                        self.received_log.append({
                            "timestamp": now,
                            "seq_num": pkt.seq_num,
                            "path_id": pkt.path_id,
                            "qos_class": pkt.qos_class,
                            "latency_ms": one_way_latency_ms,
                            "in_order": len(deliverable) > 0 and deliverable[0].seq_num == pkt.seq_num,
                            "buffer_size": self.reorder_buffer.current_buffer_size(),
                            "expected_seq": self.reorder_buffer.expected_seq
                        })
                        if len(self.received_log) > 500:
                            self.received_log.pop(0)

            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    pass

    def _send_response(self, packet: Packet):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(packet.serialize(), self.sender_addr)
        except Exception:
            pass

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_received": self.reorder_buffer.total_received,
                "in_order_count": self.reorder_buffer.in_order_count,
                "out_of_order_count": self.reorder_buffer.out_of_order_count,
                "duplicate_count": self.reorder_buffer.duplicate_count,
                "corrupted_count": self.corrupted_count,
                "delivered_count": len(self.reorder_buffer.delivered_packets),
                "current_buffer_size": self.reorder_buffer.current_buffer_size(),
                "max_buffer_depth": self.reorder_buffer.max_buffer_depth,
                "expected_seq": self.reorder_buffer.expected_seq,
                "recent_packets": list(self.received_log[-20:])
            }

    def reset(self):
        with self._lock:
            self.reorder_buffer.reset()
            self.received_log.clear()
            self.corrupted_count = 0
