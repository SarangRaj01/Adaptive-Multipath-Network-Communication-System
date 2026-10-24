"""
Interactive Web Dashboard & Control Panel for Adaptive Multipath Routing.
Built with Streamlit & Plotly.
Author: Ayush (Dashboard & Visualization Lead)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import os

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulation.topology import NetworkTopology
from core.scorer import RoutingMode
from core.packet import QoSClass
from simulation.benchmark import run_scenario_trial

st.set_page_config(
    page_title="Adaptive Multipath Routing System",
    page_icon="🌐",
    layout="wide"
)

# Initialize persistent network topology in session state
if "topology" not in st.session_state:
    top = NetworkTopology(routing_mode=RoutingMode.ADAPTIVE)
    top.start()
    st.session_state.topology = top

topology: NetworkTopology = st.session_state.topology

# Custom CSS for modern styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e222d;
        border: 1px solid #363c4e;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .badge-up {
        background-color: #10b981;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-down {
        background-color: #ef4444;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌐 Adaptive Multipath Network Communication System")
st.caption("BCSE308P Computer Networks Project — Intelligent Real-Time Path Selection & Packet Spraying")

# Sidebar Controls
st.sidebar.header("🛠️ Network Controller")

mode_selected = st.sidebar.selectbox(
    "Routing Algorithm",
    [RoutingMode.ADAPTIVE, RoutingMode.ROUND_ROBIN, RoutingMode.SHORTEST_PATH],
    index=0
)
topology.set_routing_mode(mode_selected)

qos_selected = st.sidebar.selectbox(
    "QoS Traffic Class",
    [QoSClass.NORMAL, QoSClass.HIGH, QoSClass.LOW],
    index=0,
    help="HIGH prioritizes lowest latency; LOW allows bulk spraying."
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Fault & Impairment Injection")

# Router 1 Impairments
with st.sidebar.expander("Router 1 (R1 - Primary Path)", expanded=True):
    r1_active = st.toggle("R1 Link Active", value=topology.routers["R1"].is_active, key="r1_active")
    r1_lat = st.slider("R1 Base Latency (ms)", 5, 200, int(topology.routers["R1"].latency_ms), key="r1_lat")
    r1_loss = st.slider("R1 Packet Loss Rate (%)", 0, 50, int(topology.routers["R1"].loss_rate * 100), key="r1_loss")
    topology.configure_path("R1", latency_ms=float(r1_lat), loss_rate=float(r1_loss)/100.0, is_active=r1_active)

# Router 2 Impairments
with st.sidebar.expander("Router 2 (R2 - Alternate Path)", expanded=False):
    r2_active = st.toggle("R2 Link Active", value=topology.routers["R2"].is_active, key="r2_active")
    r2_lat = st.slider("R2 Base Latency (ms)", 5, 200, int(topology.routers["R2"].latency_ms), key="r2_lat")
    r2_loss = st.slider("R2 Packet Loss Rate (%)", 0, 50, int(topology.routers["R2"].loss_rate * 100), key="r2_loss")
    topology.configure_path("R2", latency_ms=float(r2_lat), loss_rate=float(r2_loss)/100.0, is_active=r2_active)

# Router 3 Impairments
with st.sidebar.expander("Router 3 (R3 - Long / Backup Path)", expanded=False):
    r3_active = st.toggle("R3 Link Active", value=topology.routers["R3"].is_active, key="r3_active")
    r3_lat = st.slider("R3 Base Latency (ms)", 5, 200, int(topology.routers["R3"].latency_ms), key="r3_lat")
    r3_loss = st.slider("R3 Packet Loss Rate (%)", 0, 50, int(topology.routers["R3"].loss_rate * 100), key="r3_loss")
    topology.configure_path("R3", latency_ms=float(r3_lat), loss_rate=float(r3_loss)/100.0, is_active=r3_active)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset Telemetry Statistics"):
    topology.reset_stats()
    st.sidebar.success("Statistics reset!")

# Main Tabs
tab_overview, tab_traffic, tab_reordering, tab_benchmark = st.tabs([
    "📊 System Overview & Topology",
    "🚀 Traffic Spraying & Testing",
    "📦 Sliding Window & Reordering",
    "📈 Comparative Evaluation"
])

full_status = topology.get_full_status()
sender_st = full_status["sender"]
receiver_st = full_status["receiver"]
routers_st = full_status["routers"]

with tab_overview:
    st.subheader("Active Topology & Path Quality Matrix")
    
    col1, col2, col3 = st.columns(3)
    cols = {"R1": col1, "R2": col2, "R3": col3}
    weights = sender_st["distribution_weights"]
    p_metrics = sender_st["path_metrics"]
    
    for r_id, col in cols.items():
        r_info = routers_st[r_id]
        m_info = p_metrics.get(r_id, {})
        weight_pct = round(weights.get(r_id, 0.0) * 100, 1)
        is_up = r_info["is_active"]
        
        with col:
            status_badge = '<span class="badge-up">ONLINE</span>' if is_up else '<span class="badge-down">OFFLINE</span>'
            st.markdown(f"### Path {r_id} {status_badge}", unsafe_allow_html=True)
            st.metric("Traffic Share", f"{weight_pct}%")
            st.metric("RTT (Smoothed)", f"{m_info.get('rtt_ms', r_info['latency_ms'])} ms")
            st.metric("Loss Rate", f"{round(m_info.get('loss_rate', 0.0)*100, 1)}%")
            st.metric("Packets Forwarded", f"{r_info['forwarded']}")

    st.markdown("---")
    st.subheader("Dynamic Traffic Distribution Split")
    
    dist_df = pd.DataFrame([
        {"Path": p, "Traffic Share (%)": weights.get(p, 0.0) * 100}
        for p in ["R1", "R2", "R3"]
    ])
    fig_bar = px.bar(
        dist_df, x="Path", y="Traffic Share (%)", color="Path",
        color_discrete_map={"R1": "#3b82f6", "R2": "#10b981", "R3": "#f59e0b"},
        range_y=[0, 100]
    )
    fig_bar.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

with tab_traffic:
    st.subheader("Packet Transmission Generator")
    
    c_send1, c_send2, c_send3 = st.columns([2, 1, 1])
    with c_send1:
        burst_size = st.slider("Burst Packet Count", 5, 100, 30)
    with c_send2:
        interval_ms = st.slider("Inter-packet Gap (ms)", 10, 100, 25)
    with c_send3:
        send_btn = st.button("🚀 Spray Packets", type="primary")

    if send_btn:
        progress_bar = st.progress(0)
        for i in range(burst_size):
            payload = f"Telemetry-Stream-Packet-{time.time():.4f}"
            topology.sender.send_packet(payload, qos_class=qos_selected)
            time.sleep(interval_ms / 1000.0)
            progress_bar.progress((i + 1) / burst_size)
        st.success(f"Successfully sprayed {burst_size} packets across active paths!")
        time.sleep(0.5)
        st.rerun()

    st.markdown("---")
    st.subheader("Live Transmission Metrics")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Packets Sent", sender_st["total_sent"])
    m2.metric("Total ACKs Received", sender_st["acks_received"])
    m3.metric("Retransmissions", sender_st["retransmissions"])
    m4.metric("In-Flight (Unacked)", sender_st["unacked_in_flight"])

    # Recent Packets Table
    st.markdown("#### Recent Receiver Arrival Log")
    recent = receiver_st.get("recent_packets", [])
    if recent:
        df_recent = pd.DataFrame(recent)
        st.dataframe(df_recent[["seq_num", "path_id", "qos_class", "latency_ms", "in_order", "buffer_size"]], use_container_width=True)
    else:
        st.info("No packets received yet. Click 'Spray Packets' above to transmit data.")

with tab_reordering:
    st.subheader("Receiver-Side Sliding Window & Reordering Engine")
    st.write(
        "Because packets traverse paths with heterogeneous latencies, they arrive out-of-order. "
        "The receiver reorders packets using sequence numbers before upper-layer delivery."
    )
    
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("In-Order Direct Delivery", receiver_st["in_order_count"])
    r_col2.metric("Out-of-Order Buffered", receiver_st["out_of_order_count"])
    r_col3.metric("Max Buffer Occupancy", receiver_st["max_buffer_depth"])
    r_col4.metric("Next Expected Seq #", receiver_st["expected_seq"])

    # Latency scatter plot
    recent_logs = receiver_st.get("recent_packets", [])
    if recent_logs:
        df_lat = pd.DataFrame(recent_logs)
        fig_scatter = px.scatter(
            df_lat, x="seq_num", y="latency_ms", color="path_id",
            symbol="in_order",
            title="Packet Arrival Latency by Sequence & Path",
            color_discrete_map={"R1": "#3b82f6", "R2": "#10b981", "R3": "#f59e0b"}
        )
        fig_scatter.update_layout(height=350)
        st.plotly_chart(fig_scatter, use_container_width=True)

with tab_benchmark:
    st.subheader("Algorithmic Comparison: Adaptive vs Round-Robin vs Shortest-Path")
    st.write("Demonstrates how the proposed system responds under normal load, high congestion, and complete path failure.")
    
    if st.button("🧪 Run Automated Evaluation Benchmark", type="secondary"):
        with st.spinner("Executing benchmark across all scenarios..."):
            modes = [RoutingMode.ADAPTIVE, RoutingMode.ROUND_ROBIN, RoutingMode.SHORTEST_PATH]
            scenarios = ["Normal", "Congested_R1", "Link_Failure_R1"]
            benchmark_data = []
            
            for scn in scenarios:
                for mode in modes:
                    res = run_scenario_trial(topology, mode, scn, num_packets=40)
                    benchmark_data.append(res)
                    
            st.session_state.benchmark_results = pd.DataFrame(benchmark_data)
        st.success("Benchmark completed!")

    if "benchmark_results" in st.session_state:
        b_df: pd.DataFrame = st.session_state.benchmark_results
        
        st.markdown("#### Performance Summary Table")
        st.dataframe(b_df[["scenario", "mode", "delivered", "delivery_rate_pct", "avg_latency_ms", "retransmissions", "throughput_pkts_per_sec"]], use_container_width=True)
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            fig_lat = px.bar(
                b_df, x="scenario", y="avg_latency_ms", color="mode", barmode="group",
                title="Average Delivery Latency (Lower is Better)",
                color_discrete_sequence=["#10b981", "#3b82f6", "#ef4444"]
            )
            st.plotly_chart(fig_lat, use_container_width=True)
            
        with b_col2:
            fig_retries = px.bar(
                b_df, x="scenario", y="retransmissions", color="mode", barmode="group",
                title="Retransmission Overhead (Lower is Better)",
                color_discrete_sequence=["#10b981", "#3b82f6", "#ef4444"]
            )
            st.plotly_chart(fig_retries, use_container_width=True)
