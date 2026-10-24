"""
Intermediate Router Node with configurable network impairments.
Author: Sarang Raj & Dev Raj
"""

import socket
import threading
import time
import random
from typing import Tuple, Optional
from .packet import Packet

class RouterNode:
    def __init__(
        self,
        router_id: str,
        listen_host: str,
        listen_port: int,
        target_host: str,
        target_port: int,
        latency_ms: float = 20.0,
        jitter_ms: float = 5.0,
        loss_rate: float = 0.0,
        is_active: bool = True
    ):
        self.router_id = router_id
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_addr = (target_host, target_port)
        
        # Link condition parameters
        self.latency_ms = latency_ms
        self.jitter_ms = jitter_ms
        self.loss_rate = loss_rate
        self.is_active = is_active
        
        # Statistics
        self.packets_forwarded = 0
        self.packets_dropped_loss = 0
        self.packets_dropped_offline = 0
        self.total_bytes = 0
        
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the router listening thread."""
        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.listen_host, self.listen_port))
        self._socket.settimeout(0.5)
        
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name=f"Router-{self.router_id}")
        self._thread.start()

    def stop(self):
        """Stops the router node."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._socket:
            self._socket.close()

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65535)
                self.total_bytes += len(data)
                
                # Check link operational status
                if not self.is_active:
                    self.packets_dropped_offline += 1
                    continue
                    
                # Check simulated packet loss
                if random.random() < self.loss_rate:
                    self.packets_dropped_loss += 1
                    continue
                    
                # Calculate simulated latency with jitter
                delay_sec = max(0.001, (self.latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms)) / 1000.0)
                
                # Forward after simulated delay in a light thread to avoid blocking socket buffer
                forward_thread = threading.Thread(
                    target=self._delayed_forward,
                    args=(data, delay_sec),
                    daemon=True
                )
                forward_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    pass

    def _delayed_forward(self, data: bytes, delay_sec: float):
        time.sleep(delay_sec)
        try:
            # Tag the packet with this router's path_id before forwarding
            pkt = Packet.deserialize(data)
            pkt.path_id = self.router_id
            re_encoded = pkt.serialize()
            
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as send_sock:
                send_sock.sendto(re_encoded, self.target_addr)
            self.packets_forwarded += 1
        except Exception:
            pass

    def update_impairments(self, latency_ms: Optional[float] = None, jitter_ms: Optional[float] = None,
                           loss_rate: Optional[float] = None, is_active: Optional[bool] = None):
        """Allows dynamic runtime updates to simulated network link conditions."""
        if latency_ms is not None:
            self.latency_ms = max(1.0, latency_ms)
        if jitter_ms is not None:
            self.jitter_ms = max(0.0, jitter_ms)
        if loss_rate is not None:
            self.loss_rate = min(1.0, max(0.0, loss_rate))
        if is_active is not None:
            self.is_active = is_active
