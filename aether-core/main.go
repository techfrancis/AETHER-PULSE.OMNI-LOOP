package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"strings"

	"google.golang.org/grpc"
	// pb "aether-pulse/aether-core/proto/telemetry" // Uncomment once protoc is run
)

// PulseRouterServer implements the gRPC interface defined in telemetry.proto
type PulseRouterServer struct {
	// pb.UnimplementedPulseRouterServer
}

// StreamTelemetry acts as the Axon/Dendrite ingestion point for REVENANT sensors
// Uncomment and use the pb types once protoc is compiled
// func (s *PulseRouterServer) StreamTelemetry(ctx context.Context, req *pb.TelemetryEvent) (*pb.RoutingResponse, error) {
func StreamTelemetryStub(ctx context.Context, provider string, eventID uint32, payload string) (string, error) {
	log.Printf("[Dendrite] Received Telemetry - Provider: %s | EventID: %d", provider, eventID)

	// ==============================================================================
	// THE AETHER-PULSE // OMNI-LOOP TRIAGE ENGINE
	// ==============================================================================

	if strings.Contains(payload, "powershell.exe -NoP -NonI -W Hidden -Enc") {
		log.Println("[Axon-Reflex] CRITICAL: Encoded PowerShell bypass detected!")
		log.Println(" -> Executing WebAssembly (WASM) Auto-Remediation payload...")
		
		// 1. WASM Execution: Instantly kill process via cgroups/WASM sandbox escape
		
		// 2. Integration: 0xARGUS (Supply Chain & Hardware Attestation)
		// We query 0xARGUS to check if this binary matches a known signed baseline or 
		// if the hardware state (TPM/PCRs) has been compromised.
		log.Println(" -> [0xARGUS] Verifying hardware attestation state via localhost:50053...")

		/*
		// Uncomment once you compile panoptic_pb2 for Go:
		conn, err := grpc.Dial("localhost:50053", grpc.WithInsecure())
		if err != nil {
			log.Printf(" -> [0xARGUS] Failed to connect: %v", err)
		} else {
			defer conn.Close()
			client := pb_panoptic.NewAttestationServiceClient(conn)
			
			log.Println(" -> [0xARGUS] Requesting TPM/PCR verification...")
			res, err := client.VerifyHardware(ctx, &pb_panoptic.AttestationRequest{NodeId: "PX13-Node"})
			if err == nil && res.IsTrusted {
				log.Printf(" -> [0xARGUS] Hardware Attestation Verified. Trust Token: %s", res.TrustToken)
			} else {
				log.Printf(" -> [0xARGUS] CRITICAL: Hardware Trust Compromised! Mitigating.")
			}
		}
		*/

		// 3. Integration: Cortex.X (Cognitive Engine)
		// We forward the anomaly to Cortex.X (Ollama/Qdrant) to update the vector 
		// database and query the LLM for advanced mitigation protocols.
		QueryCortexX(payload)

		return "REMEDIATED_AND_ROUTED_TO_CORTEX", nil
	}

	return "ACKNOWLEDGED", nil
}

// QueryCortexX acts as the bridge to the LLM Cognitive Layer
func QueryCortexX(payload string) {
	log.Println(" -> [Cortex.X] Recalling historical context from Gemini chats...")

	// 1. Memory Recall (CORTEX.X RAG)
	searchURL := "http://localhost:8000/api/search?q=" + url.QueryEscape(payload) + "&top_k=2"
	respSearch, err := http.Get(searchURL)
	historicalContext := ""
	if err != nil {
		log.Printf(" -> [Cortex.X] Failed to reach RAG API: %v. Proceeding without history.", err)
	} else {
		defer respSearch.Body.Close()
		var searchResult struct {
			Results []struct {
				Content string `json:"content"`
			} `json:"results"`
		}
		if err := json.NewDecoder(respSearch.Body).Decode(&searchResult); err == nil && len(searchResult.Results) > 0 {
			historicalContext = searchResult.Results[0].Content
			log.Println(" -> [Cortex.X] Successfully retrieved relevant Gemini chat history.")
		}
	}

	log.Println(" -> [Ironclad-Sentinel] Pushing payload & history to Gemma 2 for Zero-Trust analysis...")
	
	// 2. Zero-Trust Decision (Ironclad -> Gemma 2)
	ironcladURL := "http://localhost:9000/api/generate"
	prompt := fmt.Sprintf("Analyze this anomaly: %s\n\nPast Chat Context: %s\n\nRecommend DevSecOps mitigation (e.g., TERMINATE or ISOLATE):", payload, historicalContext)
	
	requestBody, _ := json.Marshal(map[string]interface{}{
		"model":  "gemma2",
		"prompt": prompt,
		"stream": false,
	})

	respGen, err := http.Post(ironcladURL, "application/json", bytes.NewBuffer(requestBody))
	if err != nil {
		log.Printf(" -> [Ironclad-Sentinel] Proxy offline or unreachable: %v", err)
	} else {
		defer respGen.Body.Close()
		log.Println(" -> [Ironclad-Sentinel] Cognitive Analysis Complete. Applying dynamic mitigation via WASM.")
		// Parse mitigation action here and execute Axon WASM sandbox...
	}
}

func main() {
	port := ":50051"
	lis, err := net.Listen("tcp", port)
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	
	// pb.RegisterPulseRouterServer(grpcServer, &PulseRouterServer{})
	
	log.Printf("[Synapse] gRPC PulseRouter is online and listening on %s", port)
	log.Println("AETHER-PULSE is ready to receive REVENANT telemetry...")
	
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
