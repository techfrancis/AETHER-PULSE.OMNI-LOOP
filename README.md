# AETHER-PULSE // OMNI-LOOP

**The Neo-Techno DevSecOps Reflex & Cognitive Engine**

AETHER-PULSE is the unified orchestration layer connecting the localized autonomic defense systems on the ASUS ProArt PX13 edge workstation. It binds the millisecond-latency WASM execution of **Synapse** with the heavy-lifting cognitive analysis of **Cortex.X**, fed by real-time kernel telemetry from **REVENANT.LSM**.

## Architecture Overview

*   **The Ether (The Network/Kernel):** Monitored by `REVENANT.LSM` (eBPF/Rust) running within the WSL2 Linux subsystem.
*   **The Pulse (The Reflex Engine):** `Synapse` (Go/Wasm). A whisper-quiet daemon operating on the CPU efficiency cores to provide instantaneous auto-remediation.
*   **The Omni-Loop (The Cognitive Engine):** `Cortex.X` (Dockerized). Leverages local LLMs (Mistral-Nemo, Qwen2.5-Coder) via Ollama and a vector database (Qdrant) to analyze anomalies, query historical mitigation protocols, and instruct Synapse.

## Infrastructure

This repository contains the `docker-compose.yml` to spin up the local cognitive infrastructure.

### Services:
1.  **Ollama (`aether-pulse_ollama`)**: The local REST API for LLM inference (binds to port `11434`).
2.  **Qdrant (`aether-pulse_qdrant`)**: The ultra-fast vector database for embedding and retrieving SCRM / DevSecOps knowledge (binds to port `6333`).

### Getting Started

To initialize the cognitive engine infrastructure, run:

```powershell
docker-compose up -d
```
