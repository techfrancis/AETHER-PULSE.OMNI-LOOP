# Architecture

The AETHER-PULSE system is heavily segmented into three tiers to guarantee speed, modularity, and high-assurance trust:

## 1. The Ether (Sensors)
Kernel-level telemetry gatherers.
*   **REVENANT.WIN:** Hooks into Event Tracing for Windows (ETW) using Rust.
*   **REVENANT.LSM:** Hooks into Linux Security Modules (eBPF) using Rust Aya.

## 2. The Pulse (Reflex Engine)
The millisecond-latency mitigation router.
*   **Synapse:** A Go gRPC server that ingests telemetry, fetches hardware attestation states, and fires WebAssembly (WASM) payloads to neutralize threats.

## 3. The Omni-Loop (Cognitive Engine)
The heavy analytical and trust backend.
*   **Cortex.X:** Runs local inference using Ollama (Gemma 2) and Qdrant (Vector DB).
*   **0xARGUS:** Verifies hardware trust and performs Supply Chain Risk Management.
