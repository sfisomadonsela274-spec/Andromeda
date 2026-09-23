/**
 * =============================================================================
 *             🌌 ANDROMEDA CLIENT RAM CALCULATOR & HARDWARE PROFILER
 * =============================================================================
 * Inspects the viewer's machine (RAM, CPU cores, WebGPU limits, window.ai) to
 * compute a safe in-browser AI memory budget and dynamically gates Andromeda's
 * Council of AIs seats (The Scribe, The Sentinel, The Logician, The Architect).
 * =============================================================================
 */

export interface ModelTier {
  id: string;
  name: string;
  seat: 'The Scribe' | 'The Architect' | 'The Logician' | 'The Sentinel';
  mlcModelId: string;
  stage: 1 | 2; // 1 = Fast Scout (<250MB, sub-8s), 2 = Full Council Seat
  weightsDownloadMB: number;
  requiredRamGB: number;      // Minimum physical device RAM
  runtimeVramGB: number;      // Active memory footprint during execution
  recommended: boolean;
  accessible: boolean;
  badge: 'Recommended' | 'Unlocked' | 'Tight' | 'Locked';
  description: string;
  estimatedDownloadSec: {
    fastFiber: number; // 300+ Mbps
    standardWifi: number; // 100 Mbps
    mobile4G: number; // 30 Mbps
  };
}

export interface ClientHardwareProfile {
  detectedRamGB: number;
  isOverridden: boolean;
  cpuCores: number;
  hasWebGpu: boolean;
  hasNativeWindowAi: boolean;
  gpuVendor: string;
  gpuArchitecture: string;
  maxStorageBufferMB: number;
  maxBufferSizeMB: number;
  safeMemoryBudgetGB: number;
  recommendedModelId: string;
  activeEngineMode: 'client_webgpu' | 'native_window_ai' | 'host_server';
  isMobile: boolean;
  isIOS: boolean;
  isAndroid: boolean;
  webGpuGuide: string | null;
  models: ModelTier[];
}

const RAM_OVERRIDE_KEY = 'andromeda_ram_override_gb';
const ENGINE_MODE_KEY = 'andromeda_engine_mode';

/**
 * Andromeda Council Models Catalog
 * Precise weights & runtime VRAM footprints (4-bit / 3-bit quantized)
 */
export const ANDROMEDA_MODEL_CATALOG: Omit<ModelTier, 'accessible' | 'recommended' | 'badge'>[] = [
  {
    id: 'qwen-0.5b-scout',
    name: 'Qwen 2.5 0.5B (Scout)',
    seat: 'The Scribe',
    mlcModelId: 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC',
    stage: 1,
    weightsDownloadMB: 280,
    requiredRamGB: 3,
    runtimeVramGB: 0.65,
    description: 'Stage 1 Ultra-light Scout. Sub-8 second download. Instant intent extraction & conversational triage.',
    estimatedDownloadSec: { fastFiber: 3, standardWifi: 10, mobile4G: 28 }
  },
  {
    id: 'smollm2-360m-scout',
    name: 'SmolLM2 360M (Pocket Scout)',
    seat: 'The Scribe',
    mlcModelId: 'SmolLM2-360M-Instruct-q4f16_1-MLC',
    stage: 1,
    weightsDownloadMB: 190,
    requiredRamGB: 2,
    runtimeVramGB: 0.45,
    description: 'Ultra-lean pocket agent. 5-second startup. Perfect for mobile or constrained battery life.',
    estimatedDownloadSec: { fastFiber: 2, standardWifi: 7, mobile4G: 18 }
  },
  {
    id: 'llama-3.2-1b',
    name: 'Llama 3.2 1B (The Scribe Lite)',
    seat: 'The Scribe',
    mlcModelId: 'Llama-3.2-1B-Instruct-q4f16_1-MLC',
    stage: 2,
    weightsDownloadMB: 750,
    requiredRamGB: 4,
    runtimeVramGB: 1.25,
    description: 'High-speed intent extraction, structured JSON tools, and fluid conversational intelligence.',
    estimatedDownloadSec: { fastFiber: 12, standardWifi: 45, mobile4G: 120 }
  },
  {
    id: 'qwen-1.5b-coder',
    name: 'Qwen 2.5 Coder 1.5B (The Scribe Standard)',
    seat: 'The Scribe',
    mlcModelId: 'Qwen2.5-Coder-1.5B-Instruct-q4f16_1-MLC',
    stage: 2,
    weightsDownloadMB: 980,
    requiredRamGB: 6,
    runtimeVramGB: 1.70,
    description: 'Andromeda flagship Scribe seat: exceptional coding, logic, and tool adjudication.',
    estimatedDownloadSec: { fastFiber: 18, standardWifi: 65, mobile4G: 180 }
  },
  {
    id: 'moondream2-vision',
    name: 'Moondream 2 (The Sentinel Vision)',
    seat: 'The Sentinel',
    mlcModelId: 'Moondream2-q4f16_1-MLC',
    stage: 2,
    weightsDownloadMB: 950,
    requiredRamGB: 6,
    runtimeVramGB: 1.40,
    description: 'Powers Pixel-Spicer layout evaluation, UI color critiques, OCR, and screen perception.',
    estimatedDownloadSec: { fastFiber: 16, standardWifi: 60, mobile4G: 170 }
  },
  {
    id: 'llama-3.2-3b',
    name: 'Llama 3.2 3B (The Logician)',
    seat: 'The Logician',
    mlcModelId: 'Llama-3.2-3B-Instruct-q4f16_1-MLC',
    stage: 2,
    weightsDownloadMB: 1850,
    requiredRamGB: 8,
    runtimeVramGB: 2.90,
    description: 'Deep reasoning, multi-turn inquiry, trade-off analysis, and Socrates critique loops.',
    estimatedDownloadSec: { fastFiber: 35, standardWifi: 130, mobile4G: 340 }
  },
  {
    id: 'qwen-7b-coder',
    name: 'Qwen 2.5 Coder 7B (The Architect)',
    seat: 'The Architect',
    mlcModelId: 'Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC',
    stage: 2,
    weightsDownloadMB: 4200,
    requiredRamGB: 14,
    runtimeVramGB: 5.70,
    description: 'Dense architectural logic, full multi-file refactoring, algorithms, and deep syntax generation.',
    estimatedDownloadSec: { fastFiber: 85, standardWifi: 320, mobile4G: 900 }
  }
];

/**
 * Get or set the manual RAM override from localStorage
 */
export function getStoredRamOverride(): number | null {
  try {
    const val = localStorage.getItem(RAM_OVERRIDE_KEY);
    return val ? Number(val) : null;
  } catch {
    return null;
  }
}

export function setStoredRamOverride(ramGB: number | null): void {
  try {
    if (ramGB === null) {
      localStorage.removeItem(RAM_OVERRIDE_KEY);
    } else {
      localStorage.setItem(RAM_OVERRIDE_KEY, String(ramGB));
    }
  } catch {
    // Ignore storage issues in sandboxed iframes
  }
}

export function getStoredEngineMode(): 'client_webgpu' | 'native_window_ai' | 'host_server' {
  try {
    const val = localStorage.getItem(ENGINE_MODE_KEY);
    if (val === 'host_server' || val === 'native_window_ai' || val === 'client_webgpu') {
      return val;
    }
  } catch {}
  return 'client_webgpu';
}

export function setStoredEngineMode(mode: 'client_webgpu' | 'native_window_ai' | 'host_server'): void {
  try {
    localStorage.setItem(ENGINE_MODE_KEY, mode);
  } catch {}
}

/**
 * Probe client hardware capabilities and compute eligible models
 */
export async function profileClientHardware(manualOverride?: number | null): Promise<ClientHardwareProfile> {
  const nav = typeof navigator !== 'undefined' ? (navigator as any) : {};
  const win = typeof window !== 'undefined' ? (window as any) : {};

  // Check stored override if none provided
  const savedOverride = manualOverride !== undefined ? manualOverride : getStoredRamOverride();
  const isOverridden = savedOverride !== null && savedOverride > 0;

  // 1. Base Device Memory (browsers cap at 8GB for privacy)
  let rawReportedRam = nav.deviceMemory ? Number(nav.deviceMemory) : 4;
  const cpuCores = nav.hardwareConcurrency || 4;

  let estimatedRam = isOverridden ? Number(savedOverride) : rawReportedRam;

  // 2. Hardware heuristic: if reported RAM is maxed at 8GB, but CPU cores >= 8,
  // there is high likelihood the machine actually has 16GB physical RAM.
  if (!isOverridden && rawReportedRam >= 8 && cpuCores >= 8) {
    estimatedRam = 12;
  }

  // 3. Native Chrome Built-in AI check (Gemini Nano)
  const hasNativeWindowAi = Boolean(win.ai?.languageModel || win.model?.languageModel);

  // 4. WebGPU Probing
  let hasWebGpu = false;
  let gpuVendor = 'Generic / Integrated';
  let gpuArchitecture = 'Unknown';
  let maxStorageBufferMB = 128;
  let maxBufferSizeMB = 128;

  if (nav.gpu) {
    try {
      const adapter = await nav.gpu.requestAdapter({ powerPreference: 'high-performance' });
      if (adapter) {
        hasWebGpu = true;
        const limits = adapter.limits;
        maxStorageBufferMB = Math.round((limits.maxStorageBufferBindingSize || 134217728) / (1024 * 1024));
        maxBufferSizeMB = Math.round((limits.maxBufferSize || 268435456) / (1024 * 1024));

        const info = (adapter as any).info || {};
        gpuVendor = info.vendor || info.architecture || 'WebGPU Hardware Accelerated';
        gpuArchitecture = info.architecture || info.device || '';

        // Dedicated GPUs (Apple Silicon M-series, Nvidia RTX, AMD Radeon) typically feature >= 2048MB storage buffers
        if (!isOverridden && maxStorageBufferMB >= 2048 && estimatedRam < 16) {
          estimatedRam = 16;
        }
      }
    } catch {
      hasWebGpu = false;
    }
  }

  // 5. Calculate Safe Memory Budget (~45% of system RAM dedicated to WebGPU buffers)
  // Prevents browser tab crashing or OS swapping
  const safeMemoryBudgetGB = hasWebGpu
    ? Number(Math.max(0.6, estimatedRam * 0.45).toFixed(2))
    : 0.5;

  // Platform Detection (Mobile & OS Diagnostics)
  const ua = nav.userAgent || '';
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (nav.platform === 'MacIntel' && nav.maxTouchPoints > 1);
  const isAndroid = /Android/.test(ua);
  const isMobile = isIOS || isAndroid || (typeof window !== 'undefined' && window.innerWidth < 768);

  let webGpuGuide: string | null = null;
  if (!hasWebGpu) {
    if (isIOS) {
      webGpuGuide = 'To enable WebGPU on iPhone/iPad: Open iOS Settings → Safari → Advanced → Feature Flags → Turn ON "WebGPU".';
    } else if (isAndroid) {
      webGpuGuide = 'To enable WebGPU on Android: Open Chrome → visit chrome://flags/#enable-unsafe-webgpu → Set to Enabled → Relaunch Chrome.';
    } else {
      webGpuGuide = 'WebGPU is inactive. Running In-Browser Fast Scout mode (Zero Host Load) with full Vector Memory.';
    }
  }

  // 6. Evaluate Model Tier Availability
  let recommendedModelId = 'smollm2-360m-scout';

  const models: ModelTier[] = ANDROMEDA_MODEL_CATALOG.map((m) => {
    const isFastScout = m.id === 'smollm2-360m-scout' || m.id === 'qwen-0.5b-scout';
    const accessible = (hasWebGpu || hasNativeWindowAi || isFastScout) && estimatedRam >= m.requiredRamGB;
    const isBudgetFit = m.runtimeVramGB <= safeMemoryBudgetGB || isFastScout;

    let badge: ModelTier['badge'] = 'Locked';
    if (!accessible) {
      badge = 'Locked';
    } else if (!hasWebGpu && isFastScout) {
      badge = 'Unlocked';
    } else if (isBudgetFit) {
      badge = 'Unlocked';
    } else {
      badge = 'Tight';
    }

    return {
      ...m,
      accessible,
      recommended: false,
      badge
    };
  });

  // Automatically determine the recommended model:
  // Default to SmolLM2 360M Pocket Scout for sub-5 second instant warm-up,
  // while keeping heavier models unlocked and ready for 1-click selection.
  const pocketScout = models.find((m) => m.id === 'smollm2-360m-scout' && m.accessible);
  if (pocketScout) {
    pocketScout.recommended = true;
    pocketScout.badge = 'Recommended';
    recommendedModelId = pocketScout.id;
  } else {
    const fallbackScout = models.find((m) => m.accessible) || models[0];
    fallbackScout.recommended = true;
    fallbackScout.badge = 'Recommended';
    recommendedModelId = fallbackScout.id;
  }

  // Determine active engine mode
  let activeEngineMode = getStoredEngineMode();
  if (activeEngineMode === 'native_window_ai' && !hasNativeWindowAi) {
    activeEngineMode = 'client_webgpu';
  }

  return {
    detectedRamGB: estimatedRam,
    isOverridden,
    cpuCores,
    hasWebGpu,
    hasNativeWindowAi,
    gpuVendor,
    gpuArchitecture,
    maxStorageBufferMB,
    maxBufferSizeMB,
    safeMemoryBudgetGB,
    recommendedModelId,
    activeEngineMode,
    isMobile,
    isIOS,
    isAndroid,
    webGpuGuide,
    models
  };
}
