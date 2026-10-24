"""
Network Topology Orchestrator for Multi-Path Simulation.
Author: Sarang Raj (Topology & Orchestration Lead)
"""

import time
from typing import Dict, Any, Optional
from core.router import RouterNode
from core.receiver import ReceiverNode
from core.sender import SenderNode
from core.scorer import RoutingMode

# Standard simulated port allocations
SENDER_PORT = 9000
R1_PORT = 9001
R2_PORT = 9002
R3_PORT = 9003
RECEIVER_PORT = 9005
HOST = "127.0.0.1"

class NetworkTopology:
    def __init__(self, routing_mode: str = RoutingMode.ADAPTIVE):
        self.host = HOST
        self.routing_mode = routing_mode
        
        # 1. Receiver Node (R5 / Egress)
        self.receiver = ReceiverNode(
            listen_host=self.host,
            listen_port=RECEIVER_PORT,
            sender_host=self.host,
            sender_port=SENDER_PORT
        )
        
        # 2. Intermediate Router Nodes (R1, R2, R3)
        self.routers: Dict[str, RouterNode] = {
            "R1": RouterNode(
                router_id="R1",
                listen_host=self.host,
                listen_port=R1_PORT,
                target_host=self.host,
                target_port=RECEIVER_PORT,
                latency_ms=15.0,
                jitter_ms=3.0,
                loss_rate=0.0,
                is_active=True
            ),
            "R2": RouterNode(
                router_id="R2",
                listen_host=self.host,
                listen_port=R2_PORT,
                target_host=self.host,
                target_port=RECEIVER_PORT,
                latency_ms=35.0,
                jitter_ms=6.0,
                loss_rate=0.0,
                is_active=True
            ),
            "R3": RouterNode(
                router_id="R3",
                listen_host=self.host,
                listen_port=R3_PORT,
                target_host=self.host,
                target_port=RECEIVER_PORT,
                latency_ms=70.0,
                jitter_ms=12.0,
                loss_rate=0.0,
                is_active=True
            )
        }
        
        # 3. Sender / Controller Node
        path_targets = {
            "R1": (self.host, R1_PORT),
            "R2": (self.host, R2_PORT),
            "R3": (self.host, R3_PORT)
        }
        self.sender = SenderNode(
            listen_host=self.host,
            listen_port=SENDER_PORT,
            paths=path_targets,
            routing_mode=self.routing_mode
        )

    def start(self):
        """Starts all network nodes in the topology."""
        self.receiver.start()
        for router in self.routers.values():
            router.start()
        self.sender.start()
        time.sleep(0.1)

    def stop(self):
        """Gracefully shuts down all nodes."""
        self.sender.stop()
        for router in self.routers.values():
            router.stop()
        self.receiver.stop()

    def set_routing_mode(self, mode: str):
        self.routing_mode = mode
        self.sender.routing_mode = mode

    def configure_path(
        self,
        router_id: str,
        latency_ms: Optional[float] = None,
        jitter_ms: Optional[float] = None,
        loss_rate: Optional[float] = None,
        is_active: Optional[bool] = None
    ):
        if router_id in self.routers:
            self.routers[router_id].update_impairments(
                latency_ms=latency_ms,
                jitter_ms=jitter_ms,
                loss_rate=loss_rate,
                is_active=is_active
            )

    def get_full_status(self) -> Dict[str, Any]:
        sender_status = self.sender.get_status()
        receiver_status = self.receiver.get_metrics()
        
        router_status = {}
        for r_id, r in self.routers.items():
            router_status[r_id] = {
                "is_active": r.is_active,
                "latency_ms": r.latency_ms,
                "jitter_ms": r.jitter_ms,
                "loss_rate": r.loss_rate,
                "forwarded": r.packets_forwarded,
                "dropped_loss": r.packets_dropped_loss,
                "dropped_offline": r.packets_dropped_offline
            }
            
        return {
            "sender": sender_status,
            "routers": router_status,
            "receiver": receiver_status
        }

    def reset_stats(self):
        self.sender.reset()
        self.receiver.reset()
        for r in self.routers.values():
            r.packets_forwarded = 0
            r.packets_dropped_loss = 0
            r.packets_dropped_offline = 0
            r.total_bytes = 0
