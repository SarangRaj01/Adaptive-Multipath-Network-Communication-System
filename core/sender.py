"""
Sender Node: Multipath Packet Spraying, QoS Routing & Retransmissions.
Author: Sarang Raj, Dev Raj, Ayush & Antony Roy
"""

import socket
import threading
import time
import random
from typing import Dict, Tuple, List, Optional, Any
from .packet import Packet, PacketType, QoSClass
from .monitor import PathMonitor
from .scorer import PathScorer, RoutingMode

class SenderNode:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        paths: Dict[str, Tuple[str, int]],   # {"R1": ("127.0.0.1", 9001), ...}
        routing_mode: str = RoutingMode.ADAPTIVE,
        rto_sec: float = 0.35,
        max_retries: int = 4
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.paths = paths
        self.routing_mode = routing_mode
        self.rto_sec = rto_sec
        self.max_retries = max_retries
        
        self.monitor = PathMonitor(list(paths.keys()))
        self.scorer = PathScorer()
        
        self.next_seq_num = 0
        self.unacked_packets: Dict[int, Dict[str, Any]] = {}  # seq -> {pkt, sent_time, path_id, retries}
        self.distribution_weights: Dict[str, float] = {p: 1.0 / len(paths) for p in paths}
        
        # Stats
        self.total_data_sent = 0
        self.retransmissions_count = 0
        self.acks_received = 0
        self.transmission_log: List[Dict[str, Any]] = []
        
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rto_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.listen_host, self.listen_port))
        self._socket.settimeout(0.2)
        
        self._rx_thread = threading.Thread(target=self._ack_listener, daemon=True, name="SenderAckListener")
        self._rx_thread.start()
        
        self._rto_thread = threading.Thread(target=self._rto_monitor, daemon=True, name="SenderRtoMonitor")
        self._rto_thread.start()

    def stop(self):
        self._running = False
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        if self._rto_thread and self._rto_thread.is_alive():
            self._rto_thread.join(timeout=1.0)
        if self._socket:
            self._socket.close()

    def update_routing_distribution(self):
        """Polls monitor metrics and updates distribution shares."""
        metrics = self.monitor.evaluate_all_paths(timeout_sec=0.8)
        self.distribution_weights = self.scorer.calculate_traffic_distribution(metrics, mode=self.routing_mode)

    def select_path(self, qos_class: str = QoSClass.NORMAL) -> Optional[str]:
        """
        Intelligently selects a path based on QoS and current scoring weights.
        """
        self.update_routing_distribution()
        
        healthy_paths = [p for p, w in self.distribution_weights.items() if w > 0.0]
        if not healthy_paths:
            return None
            
        # QoS Optimization: HIGH priority goes to lowest RTT path
        if qos_class == QoSClass.HIGH:
            metrics = self.monitor.evaluate_all_paths()
            best_path = min(healthy_paths, key=lambda p: metrics[p].get("rtt_ms", 999.0))
            return best_path
            
        # Normal/Low QoS: Weighted probabilistic spraying
        path_list = list(self.distribution_weights.keys())
        weights = [self.distribution_weights[p] for p in path_list]
        total_w = sum(weights)
        if total_w <= 0:
            return None
        normalized_w = [w / total_w for w in weights]
        return random.choices(path_list, weights=normalized_w, k=1)[0]

    def send_packet(self, payload: str, qos_class: str = QoSClass.NORMAL) -> Optional[int]:
        """
        Sprays a single data packet across the selected path.
        Returns the assigned sequence number if transmitted.
        """
        with self._lock:
            chosen_path = self.select_path(qos_class)
            if not chosen_path:
                return None
                
            seq = self.next_seq_num
            self.next_seq_num += 1
            
            pkt = Packet(
                seq_num=seq,
                pkt_type=PacketType.DATA,
                payload=payload,
                path_id=chosen_path,
                qos_class=qos_class
            )
            
            now = time.time()
            self.unacked_packets[seq] = {
                "packet": pkt,
                "sent_time": now,
                "path_id": chosen_path,
                "retries": 0
            }
            
            self._transmit_to_path(pkt, chosen_path)
            self.monitor.record_packet_sent(chosen_path, seq)
            self.total_data_sent += 1
            
            self.transmission_log.append({
                "timestamp": now,
                "seq_num": seq,
                "path_id": chosen_path,
                "qos_class": qos_class,
                "status": "SENT"
            })
            if len(self.transmission_log) > 500:
                self.transmission_log.pop(0)
                
            return seq

    def _transmit_to_path(self, packet: Packet, path_id: str):
        if path_id in self.paths and self._socket:
            target_addr = self.paths[path_id]
            try:
                self._socket.sendto(packet.serialize(), target_addr)
            except Exception:
                pass

    def _ack_listener(self):
        """Listens for returning ACKs and PROBE_ACKs."""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                pkt = Packet.deserialize(data)
                
                if pkt.pkt_type in (PacketType.ACK, PacketType.PROBE_ACK):
                    seq = pkt.seq_num
                    path_id = pkt.path_id
                    
                    with self._lock:
                        if seq in self.unacked_packets:
                            original_sent = self.unacked_packets[seq]["sent_time"]
                            del self.unacked_packets[seq]
                            self.acks_received += 1
                            self.monitor.record_ack_received(path_id, seq, original_sent)
                            
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    pass

    def _rto_monitor(self):
        """Periodically scans unacknowledged packets and triggers retransmission."""
        while self._running:
            time.sleep(0.04)
            now = time.time()
            retransmit_list = []
            
            with self._lock:
                for seq, info in list(self.unacked_packets.items()):
                    curr_path = info["path_id"]
                    path_stat = self.monitor.stats.get(curr_path)
                    is_path_down = (path_stat is not None and not path_stat.is_alive)
                    
                    # Trigger retry if timeout exceeded OR if the path is confirmed DOWN (Fast Failover)
                    if (now - info["sent_time"]) > self.rto_sec or is_path_down:
                        if info["retries"] < self.max_retries:
                            retransmit_list.append(seq)
                        else:
                            # Drop after max retries
                            del self.unacked_packets[seq]
                            
            for seq in retransmit_list:
                with self._lock:
                    if seq not in self.unacked_packets:
                        continue
                    info = self.unacked_packets[seq]
                    # Select healthy alternative path for retransmission
                    alt_path = self.select_path(info["packet"].qos_class)
                    if not alt_path:
                        alt_path = info["path_id"]
                        
                    pkt = info["packet"]
                    pkt.path_id = alt_path
                    info["sent_time"] = now
                    info["retries"] += 1
                    info["path_id"] = alt_path
                    
                    self._transmit_to_path(pkt, alt_path)
                    self.retransmissions_count += 1
                    self.monitor.record_packet_sent(alt_path, seq)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            self.update_routing_distribution()
            metrics = self.monitor.evaluate_all_paths()
            return {
                "routing_mode": self.routing_mode,
                "total_sent": self.total_data_sent,
                "acks_received": self.acks_received,
                "retransmissions": self.retransmissions_count,
                "unacked_in_flight": len(self.unacked_packets),
                "distribution_weights": dict(self.distribution_weights),
                "path_metrics": metrics,
                "recent_transmissions": list(self.transmission_log[-20:])
            }

    def reset(self):
        with self._lock:
            self.next_seq_num = 0
            self.unacked_packets.clear()
            self.total_data_sent = 0
            self.retransmissions_count = 0
            self.acks_received = 0
            self.transmission_log.clear()
            self.monitor.reset()
