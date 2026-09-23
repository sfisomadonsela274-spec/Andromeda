/**
 * =============================================================================
 *                 🌌 ANDROMEDA CLIENT INFERENCE & MEMORY BRIDGE
 * =============================================================================
 * Bridges the existing Andromeda workspace UI (index.html) to the in-browser
 * WebLLM engine, IndexedDB vector memory vault, and hardware profiler.
 * 
 * When the host PC is online, communications route through the host backend.
 * When the host PC is offline (e.g. mobile away from host, or host powered off),
 * this bridge transparently handles prompts, streaming, and memory recall
 * directly on the client's local hardware with 0 bytes of host compute.
 * =============================================================================
 */

import { clientInference } from './services/clientInference';
import { clientVectorMemory } from './services/clientVectorMemory';
import { profileClientHardware, ClientHardwareProfile } from './utils/ramCalculator';

export interface AndromedaClientAPI {
  generateCompletion: (
    prompt: string,
    onToken: (token: string) => void,
    context?: string
  ) => Promise<string>;
  retrieveMemories: (query: string, topK?: number) => Promise<any[]>;
  formatMemoryContext: (memories: any[]) => string;
  memorize: (text: string, category?: string) => Promise<string>;
  profileHardware: () => Promise<ClientHardwareProfile>;
  isReady: boolean;
  activeModelName: string;
}

declare global {
  interface Window {
    AndromedaClientAI?: AndromedaClientAPI;
  }
}

let isInitialized = false;
let activeProfile: ClientHardwareProfile | null = null;
let activeModelName = 'SmolLM2 360M Pocket Scout';

async function initClientBridge() {
  try {
    activeProfile = await profileClientHardware();
    if (activeProfile && activeProfile.models) {
      const rec = activeProfile.models.find((m) => m.id === activeProfile?.recommendedModelId) || activeProfile.models[0];
      if (rec) {
        activeModelName = rec.name;
        // Warm up model in background (cached locally or lightweight fallback)
        clientInference.warmModel(rec, activeProfile.detectedRamGB).catch((err) => {
          console.warn('[Andromeda Client Bridge]: Model warm-up notice:', err);
        });
      }
    }
    isInitialized = true;
  } catch (err) {
    console.warn('[Andromeda Client Bridge]: Initialization deferred:', err);
  }
}

// Auto-initialize when loaded
if (typeof window !== 'undefined') {
  initClientBridge();

  window.AndromedaClientAI = {
    generateCompletion: async (prompt: string, onToken: (token: string) => void, context?: string) => {
      return clientInference.generateCompletion(prompt, onToken, context);
    },
    retrieveMemories: async (query: string, topK = 3) => {
      try {
        return await clientVectorMemory.retrieve(query, topK);
      } catch {
        return [];
      }
    },
    formatMemoryContext: (memories: any[]) => {
      try {
        return clientVectorMemory.formatRetrievedContext(memories);
      } catch {
        return '';
      }
    },
    memorize: async (text: string, category = 'conversation') => {
      try {
        return await clientVectorMemory.memorize(text, category);
      } catch {
        return '';
      }
    },
    profileHardware: async () => {
      if (!activeProfile) {
        activeProfile = await profileClientHardware();
      }
      return activeProfile;
    },
    get isReady() {
      return isInitialized;
    },
    get activeModelName() {
      return activeModelName;
    }
  };
}
