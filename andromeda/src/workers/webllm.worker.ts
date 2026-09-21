/**
 * =============================================================================
 *            🌌 ANDROMEDA WEBGPU WORKER: OFF-MAIN-THREAD WEBLLM
 * =============================================================================
 * Runs WebLLM model execution in a background worker to ensure 60fps UI,
 * smooth Canvas 2D avatar animations, and uninterrupted media playback.
 * =============================================================================
 */

import { WebWorkerMLCEngineHandler } from '@mlc-ai/web-llm';

const handler = new WebWorkerMLCEngineHandler();

self.onmessage = (msg: MessageEvent) => {
  handler.onmessage(msg);
};
