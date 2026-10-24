"""
Adaptive Path-Scoring and Traffic Distribution Algorithm.
Author: Ayush (Scoring & Dashboard Lead)
"""

from typing import Dict, List, Optional
import numpy as np

class RoutingMode:
    ADAPTIVE = "ADAPTIVE"
    ROUND_ROBIN = "ROUND_ROBIN"
    SHORTEST_PATH = "SHORTEST_PATH"

class PathScorer:
    def __init__(
        self,
        w_latency: float = 1.0,
        w_loss: float = 3.0,
        w_jitter: float = 1.5,
        w_hop: float = 5.0,
        sensitivity_alpha: float = 1.8
    ):
        """
        Weights for the scoring formula:
        Score = w_latency * RTT + w_loss * (Loss_Percent) + w_jitter * Jitter + w_hop * HopCount
        """
        self.w_latency = w_latency
        self.w_loss = w_loss
        self.w_jitter = w_jitter
        self.w_hop = w_hop
        self.sensitivity_alpha = sensitivity_alpha
        
        # Static hop counts for simulated paths
        self.hop_counts: Dict[str, int] = {
            "R1": 2,
            "R2": 2,
            "R3": 3
        }

    def compute_path_score(
        self,
        rtt_ms: float,
        loss_rate: float,
        jitter_ms: float,
        path_id: str,
        is_alive: bool = True
    ) -> float:
        """
        Computes the health penalty score for a path.
        Lower score is better. Dead paths return infinity.
        """
        if not is_alive or loss_rate >= 0.95:
            return float('inf')
            
        hop_count = self.hop_counts.get(path_id, 2)
        loss_percent = loss_rate * 100.0  # Scale 0-1 to 0-100
        
        score = (
            self.w_latency * rtt_ms +
            self.w_loss * loss_percent +
            self.w_jitter * jitter_ms +
            self.w_hop * hop_count
        )
        return max(0.1, score)

    def calculate_traffic_distribution(
        self,
        path_metrics: Dict[str, Dict[str, float]],
        mode: str = RoutingMode.ADAPTIVE
    ) -> Dict[str, float]:
        """
        Given the latest metrics for each path, determines the traffic share (0.0 to 1.0).
        path_metrics schema:
        {
           "R1": {"rtt_ms": 22.0, "loss_rate": 0.02, "jitter_ms": 3.1, "is_alive": True},
           ...
        }
        """
        paths = list(path_metrics.keys())
        if not paths:
            return {}

        active_paths = [p for p in paths if path_metrics[p].get("is_alive", True) and path_metrics[p].get("loss_rate", 0.0) < 0.95]
        
        # If no paths are active, distribute 0
        if not active_paths:
            return {p: 0.0 for p in paths}

        if mode == RoutingMode.ROUND_ROBIN:
            share = 1.0 / len(active_paths)
            return {p: (share if p in active_paths else 0.0) for p in paths}

        elif mode == RoutingMode.SHORTEST_PATH:
            # Single path mode: pick primary path (R1) if active, else fallback
            primary = "R1"
            if primary in active_paths:
                chosen = primary
            else:
                chosen = active_paths[0]
            return {p: (1.0 if p == chosen else 0.0) for p in paths}

        # RoutingMode.ADAPTIVE:
        scores = {}
        for p in paths:
            m = path_metrics[p]
            scores[p] = self.compute_path_score(
                rtt_ms=m.get("rtt_ms", 50.0),
                loss_rate=m.get("loss_rate", 0.0),
                jitter_ms=m.get("jitter_ms", 2.0),
                path_id=p,
                is_alive=m.get("is_alive", True)
            )

        # Inverse score transformation for active paths
        inv_scores = {}
        for p in active_paths:
            inv_scores[p] = 1.0 / (scores[p] ** self.sensitivity_alpha)

        total_inv = sum(inv_scores.values())
        distribution = {}
        for p in paths:
            if p in active_paths and total_inv > 0:
                distribution[p] = round(inv_scores[p] / total_inv, 4)
            else:
                distribution[p] = 0.0

        # Normalize to ensure sum is exactly 1.0 due to rounding
        total_p = sum(distribution.values())
        if total_p > 0:
            for p in distribution:
                distribution[p] = distribution[p] / total_p
                
        return distribution
