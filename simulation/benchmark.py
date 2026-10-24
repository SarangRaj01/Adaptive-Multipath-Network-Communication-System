"""
Automated Benchmarking Suite:
Compares Adaptive vs. Round-Robin vs. Shortest-Path under Normal, Congested, and Failure scenarios.
Author: Ayush & Dev Raj
"""

import time
import json
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, Any, List
from simulation.topology import NetworkTopology
from core.scorer import RoutingMode

def run_scenario_trial(
    topology: NetworkTopology,
    routing_mode: str,
    scenario_name: str,
    num_packets: int = 60,
    packet_interval_sec: float = 0.03
) -> Dict[str, Any]:
    """
    Executes a single test run for a specific mode and scenario.
    """
    topology.reset_stats()
    topology.set_routing_mode(routing_mode)
    
    # Configure scenario conditions
    if scenario_name == "Normal":
        topology.configure_path("R1", latency_ms=15.0, jitter_ms=3.0, loss_rate=0.0, is_active=True)
        topology.configure_path("R2", latency_ms=35.0, jitter_ms=6.0, loss_rate=0.0, is_active=True)
        topology.configure_path("R3", latency_ms=70.0, jitter_ms=12.0, loss_rate=0.0, is_active=True)
        
    elif scenario_name == "Congested_R1":
        # R1 experiences heavy congestion & jitter & packet drop
        topology.configure_path("R1", latency_ms=150.0, jitter_ms=35.0, loss_rate=0.15, is_active=True)
        topology.configure_path("R2", latency_ms=35.0, jitter_ms=6.0, loss_rate=0.0, is_active=True)
        topology.configure_path("R3", latency_ms=70.0, jitter_ms=10.0, loss_rate=0.0, is_active=True)
        
    elif scenario_name == "Link_Failure_R1":
        # R1 link severed mid-traffic
        topology.configure_path("R1", latency_ms=15.0, jitter_ms=3.0, loss_rate=0.0, is_active=True)
        topology.configure_path("R2", latency_ms=35.0, jitter_ms=6.0, loss_rate=0.0, is_active=True)
        topology.configure_path("R3", latency_ms=70.0, jitter_ms=10.0, loss_rate=0.0, is_active=True)

    # Warm-up path probe
    time.sleep(0.15)
    
    start_time = time.time()
    
    for i in range(num_packets):
        # Trigger mid-flight link failure at packet 15 for failure scenario
        if scenario_name == "Link_Failure_R1" and i == 15:
            topology.configure_path("R1", is_active=False)
            
        payload = f"Payload-Data-Block-{i:04d}"
        topology.sender.send_packet(payload)
        time.sleep(packet_interval_sec)
        
    # Wait for in-flight packets and retransmissions to settle
    time.sleep(2.0)
    end_time = time.time()
    
    status = topology.get_full_status()
    sender_st = status["sender"]
    receiver_st = status["receiver"]
    
    total_time = end_time - start_time
    total_sent = sender_st["total_sent"]
    delivered = receiver_st["delivered_count"]
    retransmissions = sender_st["retransmissions"]
    out_of_order = receiver_st["out_of_order_count"]
    
    # Calculate average one-way latency from received log
    recent_logs = receiver_st.get("recent_packets", [])
    if recent_logs:
        avg_latency = sum(p["latency_ms"] for p in recent_logs) / len(recent_logs)
    else:
        avg_latency = 0.0
        
    delivery_rate = (delivered / total_sent * 100.0) if total_sent > 0 else 0.0
    throughput = delivered / total_time if total_time > 0 else 0.0
    
    return {
        "mode": routing_mode,
        "scenario": scenario_name,
        "total_sent": total_sent,
        "delivered": delivered,
        "delivery_rate_pct": round(delivery_rate, 2),
        "retransmissions": retransmissions,
        "out_of_order_packets": out_of_order,
        "avg_latency_ms": round(avg_latency, 2),
        "throughput_pkts_per_sec": round(throughput, 2),
        "duration_sec": round(total_time, 2),
        "distribution_weights": sender_st["distribution_weights"]
    }

def run_full_benchmark(output_dir: str = None) -> pd.DataFrame:
    """
    Runs the entire suite of comparative tests and exports plots & JSON summary.
    """
    if output_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, "results")
        
    os.makedirs(output_dir, exist_ok=True)
    topology = NetworkTopology()
    topology.start()
    
    modes = [RoutingMode.ADAPTIVE, RoutingMode.ROUND_ROBIN, RoutingMode.SHORTEST_PATH]
    scenarios = ["Normal", "Congested_R1", "Link_Failure_R1"]
    
    results: List[Dict[str, Any]] = []
    
    print("\n================ STARTING MULTIPATH BENCHMARK SUITE ================")
    for scn in scenarios:
        print(f"\n---> Testing Scenario: {scn}")
        for mode in modes:
            print(f"     Running Mode: {mode}...")
            res = run_scenario_trial(topology, mode, scn, num_packets=50)
            results.append(res)
            print(f"       Delivered: {res['delivered']}/{res['total_sent']} ({res['delivery_rate_pct']}%), "
                  f"Avg Latency: {res['avg_latency_ms']} ms, Retries: {res['retransmissions']}")
            time.sleep(0.3)
            
    topology.stop()
    
    df = pd.DataFrame(results)
    json_path = os.path.join(output_dir, "benchmark_summary.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=4)
        
    csv_path = os.path.join(output_dir, "benchmark_summary.csv")
    df.to_csv(csv_path, index=False)
    
    # Generate Comparison Plot
    _generate_plots(df, output_dir)
    print(f"\n[+] Benchmark completed. Results saved to {output_dir}/")
    return df

def _generate_plots(df: pd.DataFrame, output_dir: str):
    """Generates comparative charts."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # 1. Delivery Rate by Scenario and Mode
    pivot_delivery = df.pivot(index="scenario", columns="mode", values="delivery_rate_pct")
    pivot_delivery.plot(kind="bar", ax=axes[0], colormap="viridis")
    axes[0].set_title("Packet Delivery Rate (%)", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Delivery %")
    axes[0].set_ylim(0, 105)
    axes[0].tick_params(axis='x', rotation=15)
    
    # 2. Average Latency (ms)
    pivot_latency = df.pivot(index="scenario", columns="mode", values="avg_latency_ms")
    pivot_latency.plot(kind="bar", ax=axes[1], colormap="plasma")
    axes[1].set_title("Average Delivery Latency (ms)", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Latency (ms)")
    axes[1].tick_params(axis='x', rotation=15)
    
    # 3. Retransmission Overhead
    pivot_retries = df.pivot(index="scenario", columns="mode", values="retransmissions")
    pivot_retries.plot(kind="bar", ax=axes[2], colormap="magma")
    axes[2].set_title("Retransmissions (Overhead)", fontsize=12, fontweight="bold")
    axes[2].set_ylabel("Retry Count")
    axes[2].tick_params(axis='x', rotation=15)
    
    plt.tight_layout()
    chart_path = os.path.join(output_dir, "benchmark_comparison.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()

if __name__ == "__main__":
    run_full_benchmark()
