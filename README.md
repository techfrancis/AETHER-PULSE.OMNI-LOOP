# AETHER-PULSE // OMNI-LOOP
**High-Assurance Autonomic DevSecOps Engine**

AETHER-PULSE is a localized, high-speed, edge-deployed cyber-defense platform. Designed to run completely air-gapped on edge hardware (such as the ASUS ProArt PX13), it seamlessly unifies real-time kernel telemetry, hardware attestation, and localized Large Language Model (Gemma 2) reasoning to identify and neutralize advanced threats automatically.

---

## 🏗️ Architecture Diagram

```mermaid
graph TD
    subgraph "The Ether (Sensors)"
        RWIN[REVENANT.WIN<br/>Windows ETW Sensor]
        RLSM[REVENANT.LSM<br/>Linux eBPF Sensor]
    end

    subgraph "The Pulse (Reflex Engine)"
        SYN[Synapse Router<br/>Go / gRPC]
        WASM[Axon Module<br/>WebAssembly Mitigations]
    end

    subgraph "The Omni-Loop (Cognitive Engine)"
        CORTEX[Cortex.X<br/>Ollama: Gemma 2 & Qdrant]
        ARGUS[0xARGUS<br/>Hardware Attestation & SCRM]
    end

    RWIN -- "gRPC Telemetry" --> SYN
    RLSM -- "gRPC Telemetry" --> SYN
    
    SYN -- "Query Trust" --> ARGUS
    SYN -- "Behavioral Analysis" --> CORTEX
    
    CORTEX -. "Logic/Mitigation" .-> SYN
    ARGUS -. "Trust State" .-> SYN
    
    SYN -- "Trigger Reflex" --> WASM
    WASM -- "Remediate" --> RWIN
```

## 🔄 Process Flow Diagram

```mermaid
sequenceDiagram
    participant OS as Host OS (Win/Linux)
    participant Rev as REVENANT (Sensor)
    participant Syn as Synapse (Router)
    participant Arg as 0xARGUS (Trust)
    participant Cor as Cortex.X (Gemma 2)
    participant Wasm as Axon (WASM)

    OS->>Rev: Kernel Event (e.g., Process Creation)
    Rev->>Syn: Stream Telemetry (gRPC)
    activate Syn
    Syn->>Arg: Verify Hardware/Process Trust
    Arg-->>Syn: Trust Level = Low
    Syn->>Cor: Send Payload for Behavioral Analysis
    activate Cor
    Cor-->>Syn: Analysis complete. Recommended Action: TERMINATE
    deactivate Cor
    Syn->>Wasm: Load & Execute WASM Remediation Payload
    Wasm->>OS: Execute Kernel Hook (Kill Process)
    Syn-->>Rev: Return Mitigation Status
    deactivate Syn
```

## 🚀 Getting Started

1. **Start the Cognitive Cluster**
   ```bash
   docker compose up -d
   ```
   *This brings up Ollama, Qdrant, and the dual 0xARGUS engines.*

2. **Start the Synapse Router**
   ```bash
   cd synapse-core
   go run main.go
   ```

3. **Start the Kernel Sensors**
   ```bash
   cd ../REVENANT.WIN
   cargo run
   ```

4. **Monitor the Loop**
   Right-click the `AetherTray.ps1` orb in your Windows taskbar to see live threat status!

## 📚 Documentation
Full documentation is built with MkDocs.

## 🛡️ Ecosystem Alignment
AETHER-PULSE is designed to seamlessly integrate with the broader high-assurance ecosystem:
*   **Railhead:** Acts as the secure, zero-trust deployment and orchestration layer for rolling out AETHER-PULSE sensors and updates across edge networks.
*   **Keystone:** Provides the foundational secure enclaves, identity, and cryptographic key management that deeply anchor the `0xARGUS` hardware attestation chains.
```
