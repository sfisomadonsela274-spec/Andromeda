"""
=============================================================================
        🌌 ANDROMEDA ENGINE & WORKSPACE E2E INTEGRATION SUITE 🌌
=============================================================================
End-to-End behavioral and integration tests validating:
  - Docker Services Health & Ingress Routing (Caddy, FastAPI, Ollama, Phoenix)
  - Council of AIs Multi-Model Adjudication (Scribe, Architect, Logician, Sentinel)
  - WebSocket Streaming Contract & Packet Sequence (/ws/core)
  - Fast Gate & Negative Boundary Verification
  - MPRIS Host Media Routing & Execution
  - Pixel-Spicing REST Endpoint & Hardware Acceleration
=============================================================================
"""

import os
import sys
import json
import socket
import asyncio
import pytest
import pytest_asyncio
import httpx
import websockets

# Ensure current working dir and local modules are resolvable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in [os.path.join(PROJECT_ROOT, "andromeda", "backend"), os.path.join(PROJECT_ROOT, "jimmy"), PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from council_engine import adjudicate_seat, SEAT_SCRIBE, SEAT_ARCHITECT, SEAT_LOGICIAN, SEAT_SENTINEL


# =============================================================================
# 🛠️ FIXTURES & CONSTANTS
# =============================================================================

CADDY_INGRESS_URL = "http://localhost:80"
BACKEND_DIRECT_URL = "http://localhost:8000"
OLLAMA_API_URL = "http://localhost:11434"
PHOENIX_UI_URL = "http://localhost:6006"
PHOENIX_OTEL_PORT = 4317

WS_CADDY_URI = "ws://localhost:80/ws/core"
WS_DIRECT_URI = "ws://localhost:8000/ws/core"


# =============================================================================
# 0️⃣ PRE-FLIGHT & SERVICE HEALTH CHECKS
# =============================================================================

class TestPreflightAndServices:
    """Validates connectivity and readiness of all orchestrating containers."""

    @pytest.mark.asyncio
    async def test_caddy_ingress_health(self):
        """Verifies Caddy Ingress reverse proxy is healthy on port 80."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(CADDY_INGRESS_URL)
            assert resp.status_code == 200
            assert "server" in resp.headers or "caddy" in resp.headers.get("server", "").lower()

    @pytest.mark.asyncio
    async def test_fastapi_backend_health(self):
        """Verifies FastAPI core backend reports status online both directly and via ingress."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Direct backend access
            resp_direct = await client.get(f"{BACKEND_DIRECT_URL}/")
            assert resp_direct.status_code == 200
            assert resp_direct.json().get("status") == "Andromeda Core Online"

            # Ingress route access (/api/apps)
            resp_ingress = await client.get(f"{CADDY_INGRESS_URL}/api/apps")
            assert resp_ingress.status_code == 200
            assert resp_ingress.json().get("status") == "ok"

    @pytest.mark.asyncio
    async def test_ollama_service_and_models(self):
        """Verifies Ollama API is reachable and all required Council models are pulled."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_API_URL}/api/tags")
            assert resp.status_code == 200
            data = resp.json()
            model_names = [m.get("name") or m.get("model") for m in data.get("models", [])]

            assert any("qwen2.5-coder:1.5b" in m for m in model_names), "Scribe model missing in Ollama"
            assert any("qwen2.5-coder:7b" in m for m in model_names), "Architect model missing in Ollama"
            assert any("llama3.2" in m for m in model_names), "Logician model missing in Ollama"
            assert any("moondream" in m for m in model_names), "Sentinel model missing in Ollama"

    @pytest.mark.asyncio
    async def test_phoenix_observability_and_otel(self):
        """Verifies Arize Phoenix web UI is active on 6006 and OTel collector is listening on 4317."""
        # 1. Web UI Check
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(PHOENIX_UI_URL)
            assert resp.status_code == 200
            assert "Phoenix" in resp.text

        # 2. OTel Collector Port Check (4317)
        loop = asyncio.get_running_loop()
        def check_otel_socket():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex(("localhost", PHOENIX_OTEL_PORT))
            sock.close()
            return result == 0

        connected = await loop.run_in_executor(None, check_otel_socket)
        assert connected, f"Arize Phoenix OTel collector port {PHOENIX_OTEL_PORT} is not open"


# =============================================================================
# 🏛️ SUITE A: COUNCIL SEAT ADJUDICATION & ROUTING LOGIC
# =============================================================================

class TestSuiteACouncilAdjudication:
    """Verifies Council of AIs deterministic seat routing across queries."""

    def test_scribe_seat_assignment(self):
        """Standard conversational queries route to The Scribe (qwen2.5-coder:1.5b)."""
        prompt = "Hey, what time is it?"
        seat, adj = adjudicate_seat(prompt)
        assert seat.title == "The Scribe"
        assert seat.model == "qwen2.5-coder:1.5b"
        assert seat.id == "scribe"
        assert adj["has_image"] is False

    def test_architect_seat_assignment(self):
        """Code-dense, refactoring, and algorithm tasks route to The Architect (qwen2.5-coder:7b)."""
        prompt = "Refactor this database session pool to async Rust"
        seat, adj = adjudicate_seat(prompt)
        assert seat.title == "The Architect"
        assert seat.model == "qwen2.5-coder:7b"
        assert seat.id == "architect"
        assert adj["code_density"] >= 0.08 or "refactor" in adj.get("reason", "").lower()

    def test_logician_seat_assignment(self):
        """Deep philosophical, ethical, and systematic critique tasks route to The Logician (llama3.2)."""
        prompt = "Conduct a deep philosophical critique of our safety boundaries"
        seat, adj = adjudicate_seat(prompt)
        assert seat.title == "The Logician"
        assert seat.model == "llama3.2"
        assert seat.id == "logician"
        assert "socratic" in adj.get("rule", "") or "logic" in adj.get("rule", "")

    def test_sentinel_seat_assignment(self):
        """Pixel-spacing, layout critique, and image inspect tasks route to The Sentinel (moondream)."""
        prompt = "Run pixel spacing on this damaged photo"
        seat, adj = adjudicate_seat(prompt)
        assert seat.title == "The Sentinel"
        assert seat.model == "moondream"
        assert seat.id == "sentinel"
        assert "layout" in adj.get("rule", "") or "pixel" in adj.get("reason", "").lower()


# =============================================================================
# ⚡ SUITE B: WEBSOCKET PROTOCOL & STREAMING CONTRACT (/ws/core)
# =============================================================================

class TestSuiteBWebSocketProtocol:
    """Verifies duplex WebSocket connection, sequencing, and packet contracts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ws_url", [WS_CADDY_URI, WS_DIRECT_URI])
    async def test_websocket_packet_sequence_figma(self, ws_url):
        """
        Sends: {"prompt": "open figma and search mobile wireframes"}
        Asserts Packet Sequence:
          1. Status packet: contains 'council_seat' and status 'presiding...' or 'Thinking...'
          2. Response packet: parses valid JSON with action='app_control', app='figma', category='graphics'
        """
        async with websockets.connect(ws_url, ping_timeout=20, close_timeout=10) as ws:
            payload = {"prompt": "open figma and search mobile wireframes"}
            await ws.send(json.dumps(payload))

            received_packets = []
            status_packet_verified = False
            response_packet_verified = False

            # Collect streaming packets until final response
            for _ in range(15):
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=35.0)
                packet = json.loads(raw_msg)
                received_packets.append(packet)

                pkt_type = packet.get("type")

                # 1. Verify Status Packet
                if pkt_type in ("council_status", "status"):
                    # Check for council_seat presence
                    has_council_seat = ("council_seat" in packet) or ("presiding_seat" in packet)
                    status_text = (
                        str(packet.get("status", "")) + " " +
                        str(packet.get("message", ""))
                    ).lower()
                    has_expected_status = ("presiding" in status_text) or ("thinking" in status_text)

                    if has_council_seat and has_expected_status:
                        status_packet_verified = True

                # 2. Verify Final Response Packet
                if pkt_type == "response":
                    content_str = packet.get("message", "")
                    try:
                        resp_json = json.loads(content_str)
                    except json.JSONDecodeError:
                        pytest.fail(f"Response message was not valid JSON: {content_str}")

                    assert resp_json.get("action") == "app_control", f"Expected action 'app_control', got {resp_json.get('action')}"
                    assert resp_json.get("app") == "figma", f"Expected app 'figma', got {resp_json.get('app')}"
                    assert resp_json.get("category") == "graphics", f"Expected category 'graphics', got {resp_json.get('category')}"
                    response_packet_verified = True
                    break

            assert status_packet_verified, f"Status packet with council_seat & presiding/thinking not found. Packets: {received_packets}"
            assert response_packet_verified, f"Final response packet not received. Packets: {received_packets}"


# =============================================================================
# 🛡️ SUITE C: FAST GATE & NEGATIVE BOUNDARY VERIFICATION
# =============================================================================

class TestSuiteCFastGateAndNegativeBoundary:
    """Verifies edge conditions, resilience to malformed input, and MPRIS dispatch."""

    @pytest.mark.asyncio
    async def test_negative_constraint_malformed_input(self):
        """
        Sends malformed payload over WebSocket.
        Asserts engine returns graceful rejection/clarification without closing socket.
        """
        async with websockets.connect(WS_CADDY_URI, open_timeout=10, close_timeout=10) as ws:
            # 1. Send invalid non-JSON string
            await ws.send("INVALID_RAW_NON_JSON_CORRUPT_BUFFER")
            msg_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            pkt = json.loads(msg_raw)
            assert pkt.get("type") == "error"
            assert "invalid json" in pkt.get("message", "").lower()

            # 2. Verify connection remains open by sending a clean follow-up prompt
            await ws.send(json.dumps({"prompt": "Hello Andromeda, are you operational?"}))
            followup_received = False
            for _ in range(10):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                pkt = json.loads(msg_raw)
                if pkt.get("type") == "response":
                    followup_received = True
                    # Verify no system prompt internals leaked
                    resp_msg = pkt.get("message", "")
                    assert "SYSTEM_PROMPT" not in resp_msg
                    assert "CRITICAL RULE FOR PROGRAMMING" not in resp_msg
                    assert "ActionResponse" not in resp_msg
                    break
            assert followup_received, "WebSocket was dropped or failed to respond after malformed input"

    @pytest.mark.asyncio
    async def test_host_mpris_route_execution(self):
        """
        Sends 'pause' to POST /api/media/execute.
        Asserts backend issues command to media_controller and returns HTTP 200 without 500 errors.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{CADDY_INGRESS_URL}/api/media/execute",
                json={"action": "pause"}
            )
            assert resp.status_code == 200, f"Expected 200 from media execute, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert "status" in data
            assert data.get("action") == "pause"
            assert "result" in data or "detail" in data

    @pytest.mark.asyncio
    async def test_host_mpris_route_via_websocket(self):
        """
        Sends 'pause music' over WebSocket stream.
        Asserts Fast Gate extracts media_control action without dropping connection.
        """
        async with websockets.connect(WS_CADDY_URI, open_timeout=10, close_timeout=10) as ws:
            await ws.send(json.dumps({"prompt": "pause music"}))

            mpris_handled = False
            for _ in range(10):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                pkt = json.loads(msg_raw)
                if pkt.get("type") == "response":
                    content = json.loads(pkt.get("message", "{}"))
                    assert content.get("action") == "media_control"
                    assert content.get("sub_action") in ("pause", "play_pause", "stop")
                    mpris_handled = True
                    break

            assert mpris_handled, "Media control prompt was not handled"


# =============================================================================
# 🎨 SUITE D: PIXEL-SPICING REST ENDPOINT
# =============================================================================

class TestSuiteDPixelSpicingEndpoint:
    """Verifies Pixel-Spicer REST status endpoint and hardware acceleration."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("base_url", [CADDY_INGRESS_URL, BACKEND_DIRECT_URL])
    async def test_spice_status_endpoint(self, base_url):
        """
        Queries GET /api/spice/status.
        Asserts HTTP status 200 and acceleration is reported as active.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/spice/status")
            assert resp.status_code == 200, f"Expected 200 from {base_url}/api/spice/status, got {resp.status_code}"
            data = resp.json()
            assert data.get("status") == "ok"
            assert data.get("acceleration") == "active"
            assert data.get("acceleration_active") is True
            assert data.get("vulkan_available") is True
            assert "Real-ESRGAN" in data.get("engine", "")


# =============================================================================
# ⚡ SUITE E: CONTENTION, STRESS & FALLBACK VERIFICATION
# =============================================================================

class TestSuiteEContentionStressAndFallback:
    """Verifies concurrency contention, rapid burst stress, and multi-tier fallback resilience."""

    @pytest.mark.asyncio
    async def test_model_resolution_fallback(self):
        """
        Tests fallback behavior when requesting an uninstalled or missing model.
        Asserts engine gracefully falls back to first available installed model.
        """
        from andromeda.backend.engine import SocratesScaffoldingAsync
        scaffolding = SocratesScaffoldingAsync()
        resolved_model = await scaffolding.get_working_model("nonexistent-uninstalled-slm:999b")
        assert resolved_model is not None
        assert resolved_model != "nonexistent-uninstalled-slm:999b"
        assert any(k in resolved_model for k in ["qwen", "llama", "moondream", "smollm"])

    def test_vector_gate_intent_fallback(self):
        """
        Tests VectorGate fallback when prompt matches no registered tool action.
        Asserts fallback classification returns 'chat' with is_tool=False.
        """
        from andromeda.backend.engine import VectorGateEngine
        gate = VectorGateEngine()
        intent, is_tool = gate.classify_intent("The clouds in the sky look particularly fluffy this afternoon.")
        assert intent == "chat"
        assert is_tool is False

    @pytest.mark.asyncio
    async def test_concurrent_websocket_client_contention(self):
        """
        Tests WebSocket server stability under concurrent client contention.
        Launches multiple parallel WebSocket sessions simultaneously over Caddy ingress.
        """
        async def run_client(idx: int):
            async with websockets.connect(WS_CADDY_URI, open_timeout=10, close_timeout=10) as ws:
                prompt = f"What is {idx} multiplied by 3?"
                await ws.send(json.dumps({"prompt": prompt}))

                received_response = False
                for _ in range(12):
                    raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                    pkt = json.loads(raw)
                    if pkt.get("type") == "response":
                        received_response = True
                        break
                return received_response

        # Concurrently execute 3 client sessions
        tasks = [run_client(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        assert all(results), f"One or more concurrent WebSocket clients failed under contention: {results}"

    @pytest.mark.asyncio
    async def test_websocket_rapid_burst_stress(self):
        """
        Tests socket stability and sequence ordering under rapid burst query stress.
        Sends a burst of sequential instructions over a single continuous stream.
        """
        async with websockets.connect(WS_CADDY_URI, open_timeout=10, close_timeout=10) as ws:
            burst_queries = [
                "Ping zero",
                "Ping one",
                "Ping two"
            ]

            for query in burst_queries:
                await ws.send(json.dumps({"prompt": query}))

                response_ok = False
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                    pkt = json.loads(raw)
                    if pkt.get("type") == "response":
                        response_ok = True
                        break

                assert response_ok, f"Failed to receive response for burst query '{query}'"

    def test_pixel_spicer_gpu_lock_contention(self):
        """
        Tests Real-ESRGAN GPU mutex lock contention safety.
        Ensures compute shader thread lock serializes access to avoid hardware collisions.
        """
        import threading
        import time
        from pixel_spicer import _ESRGAN_GPU_LOCK

        shared_state = []

        def worker(thread_id: int):
            with _ESRGAN_GPU_LOCK:
                shared_state.append(f"start_{thread_id}")
                time.sleep(0.05)
                shared_state.append(f"end_{thread_id}")

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Under proper mutex lock, operations must strictly serialize:
        # e.g. [start_1, end_1, start_2, end_2] or [start_2, end_2, start_1, end_1]
        assert len(shared_state) == 4
        assert (shared_state[0].replace("start_", "") == shared_state[1].replace("end_", ""))
        assert (shared_state[2].replace("start_", "") == shared_state[3].replace("end_", ""))

