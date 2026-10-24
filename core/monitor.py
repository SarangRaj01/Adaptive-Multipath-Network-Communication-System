"""
Real-time Path Monitoring, Telemetry, and Failure Detection.
Author: Antony Roy (Monitoring & Failure Detection Lead)
"""

import time
from typing import Dict, List, Optional, Any
from collections import deque

class PathStats:
    def __init__(self, path_id: str, window_size: int = 50):
        self.path_id = path_id
        self.window_size = window_size
        
        # Telemetry metrics
        self.srtt_ms: float = 30.0          # Smoothed RTT (EWMA)
        self.latest_rtt_ms: float = 30.0
        self.jitter_ms: float = 2.0         # RFC 3550 jitter
        self.loss_rate: float = 0.0         # 0.0 to 1.0
        self.is_alive: bool = True
        
        # Internal tracking
        self.last_seen_time: float = time.time()
        self.sent_history: deque = deque(maxlen=window_size)     # (seq, timestamp)
        self.acked_seqs: set = set()
        self.total_sent: int = 0
        self.total_acked: int = 0

    def record_sent(self, seq_num: int):
        now = time.time()
        self.total_sent += 1
        self.sent_history.append((seq_num, now))

    def record_ack(self, seq_num: int, original_timestamp: float):
        now = time.time()
        self.last_seen_time = now
        self.is_alive = True
        self.total_acked += 1
        self.acked_seqs.add(seq_num)
        
        sample_rtt = max(0.5, (now - original_timestamp) * 1000.0)
        self.latest_rtt_ms = sample_rtt
        
        # EWMA for RTT (alpha = 0.125)
        self.srtt_ms = 0.875 * self.srtt_ms + 0.125 * sample_rtt
        
        # RFC 3550 Interarrival Jitter
        d = abs(sample_rtt - self.latest_rtt_ms)
        self.jitter_ms = self.jitter_ms + (d - self.jitter_ms) / 16.0
        
        self._update_loss_rate()

    def _update_loss_rate(self):
        if not self.sent_history:
            self.loss_rate = 0.0
            return
            
        now = time.time()
        # Packets in window older than 1.5 * srtt that haven't been acked are considered lost
        loss_cutoff = max(0.4, (self.srtt_ms * 2.5) / 1000.0)
        evaluated = 0
        lost = 0
        
        for seq, sent_time in self.sent_history:
            if (now - sent_time) > loss_cutoff:
                evaluated += 1
                if seq not in self.acked_seqs:
                    lost += 1
                    
        if evaluated >= 5:
            self.loss_rate = min(1.0, lost / evaluated)
        else:
            self.loss_rate = 0.0

    def check_health(self, timeout_sec: float = 2.0) -> bool:
        """Evaluates if the path has timed out or suffered catastrophic loss."""
        now = time.time()
        self._update_loss_rate()
        
        # If no ACK received for over timeout_sec while packets were transmitted
        if (now - self.last_seen_time) > timeout_sec and self.total_sent > self.total_acked:
            self.is_alive = False
        elif self.loss_rate > 0.90:
            self.is_alive = False
        else:
            self.is_alive = True
            
        return self.is_alive

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "rtt_ms": round(self.srtt_ms, 2),
            "latest_rtt_ms": round(self.latest_rtt_ms, 2),
            "jitter_ms": round(self.jitter_ms, 2),
            "loss_rate": round(self.loss_rate, 3),
            "is_alive": self.is_alive,
            "total_sent": self.total_sent,
            "total_acked": self.total_acked
        }


class PathMonitor:
    def __init__(self, path_ids: List[str]):
        self.stats: Dict[str, PathStats] = {pid: PathStats(pid) for pid in path_ids}

    def record_packet_sent(self, path_id: str, seq_num: int):
        if path_id in self.stats:
            self.stats[path_id].record_sent(seq_num)

    def record_ack_received(self, path_id: str, seq_num: int, timestamp: float):
        if path_id in self.stats:
            self.stats[path_id].record_ack(seq_num, timestamp)

    def evaluate_all_paths(self, timeout_sec: float = 2.0) -> Dict[str, Dict[str, Any]]:
        snapshot = {}
        for pid, stat in self.stats.items():
            stat.check_health(timeout_sec)
            snapshot[pid] = stat.to_dict()
        return snapshot

    def reset(self):
        for stat in self.stats.values():
            stat.__init__(stat.path_id)
