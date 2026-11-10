# Adaptive Multipath Network Communication System with Intelligent Path Selection

**Course**: BCSE308L / BCSE308P – Computer Networks  
**Faculty Guide**: Dr. Tamizharasi T  
**Team Members**:
- **Sarang Raj** (Path discovery, topology orchestration, packet structure & CRC32 integrity)
-   (Packet spraying engine, sliding-window reordering buffer, reliability layer)
-  (Real-time path telemetry, EWMA RTT / RFC 3550 jitter / loss monitoring, failure detection)
-  (Adaptive weighted path scoring, traffic distribution, Streamlit web dashboard & benchmarking)

---

## 📌 Project Overview
Conventional routing mechanisms (e.g. OSPF, BGP) bind network flows to a single static path. When this path becomes congested, experiences packet loss, or suffers link failure, performance degrades until slow reconvergence occurs.

This project implements an **Adaptive Multipath Communication System** over UDP that treats multiple network paths ($R_1, R_2, R_3 \to R_5$) as an active pool of resources:
1. **Packet Spraying**: Individual packets of a flow are sprayed across paths simultaneously.
2. **Receiver Reordering**: A sliding-window priority buffer reorders out-of-order packets before delivery.
3. **Continuous Path Telemetry**: Measures EWMA RTT, jitter, and loss rates in real time.
4. **Adaptive Scoring Formula**:
   $$\text{Score}_i = w_1 \cdot \text{RTT}_i + w_2 \cdot \text{LossRate}_i + w_3 \cdot \text{Jitter}_i + w_4 \cdot \text{HopCount}_i$$
   Lower score indicates superior quality. Traffic allocation is dynamically computed via inverse score weighting:
   $$P_i = \frac{1 / \text{Score}_i^\alpha}{\sum_k (1 / \text{Score}_k^\alpha)}$$
5. **Instant Failure Detection & Self-Healing**: Failed paths are detected via ACK timeouts / probe loss ($P_i \to 0$), immediately rerouting in-flight and pending traffic to healthy paths.
6. **QoS Support**: High-priority flows (e.g. video/voice) are prioritized over the lowest-latency path, while bulk traffic is distributed across all active capacity.

---

## 🗂️ Project Structure

```text
adaptive-multipath-routing/
├── core/
│   ├── packet.py             # Custom binary/JSON packet with sequence numbers & CRC32
│   ├── router.py             # Intermediate router nodes with configurable impairments
│   ├── receiver.py           # Receiver (R5) with reordering buffer & ACK engine
│   ├── sender.py             # Multipath spraying engine, QoS scheduler & RTO retransmission
│   ├── monitor.py            # EWMA RTT, RFC 3550 jitter, and loss rate tracker
│   ├── scorer.py             # Multi-metric cost function & traffic distribution calculator
│   └── reordering_buffer.py  # Min-heap sliding window reordering buffer
├── simulation/
│   ├── topology.py           # Multi-process network topology (Sender -> R1/R2/R3 -> R5)
│   └── benchmark.py          # Automated benchmark: Adaptive vs Round-Robin vs Shortest-Path
├── dashboard/
│   └── app.py                # Interactive Streamlit UI with live topology & fault injection
├── tests/
│   ├── test_packet.py        # Packet serialization & integrity tests
│   ├── test_reordering.py    # Out-of-order & duplicate handling tests
│   └── test_scoring_and_failover.py # Scoring & failover tests
├── results/                  # Generated benchmark plots, CSVs, and JSON summaries
├── run_tests.py              # Automated test runner
└── requirements.txt          # Python dependencies
```

---

## 🚀 How to Run the Project

### 1. Run Unit & Integration Tests
Verify all core components (packet integrity, reordering buffer, scoring & failover):
```bash
python run_tests.py
```

### 2. Launch the Interactive Web Dashboard
Run the Streamlit live control panel:
```bash
streamlit run dashboard/app.py
```
Open `http://localhost:8501` in your browser. From the dashboard you can:
- View live network topology and path metrics.
- Spray packets across paths in real-time.
- Dynamically inject network impairments (latency spikes, packet loss %, or kill a link completely).
- Watch the adaptive engine dynamically re-score paths and divert traffic in real-time!

### 3. Run Automated Comparative Benchmark
Run the head-to-head evaluation comparing **Adaptive Multipath**, **Round-Robin**, and **Shortest-Path**:
```bash
python simulation/benchmark.py
```
This generates:
- `results/benchmark_summary.json`
- `results/benchmark_summary.csv`
- `results/benchmark_comparison.png` (Publication/report-ready comparison chart)

---


