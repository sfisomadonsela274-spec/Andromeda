import React, { useState, useEffect } from 'react';
import {
  ModelTier,
  ClientHardwareProfile,
  profileClientHardware,
  setStoredRamOverride,
  getStoredRamOverride,
  setStoredEngineMode
} from '../utils/ramCalculator';
import { clientInference, InferenceProgressEvent } from '../services/clientInference';

export interface ClientHardwareModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectModel: (model: ModelTier) => void;
  activeModelId?: string;
}

export const ClientHardwareModal: React.FC<ClientHardwareModalProps> = ({
  isOpen,
  onClose,
  onSelectModel,
  activeModelId
}) => {
  const [profile, setProfile] = useState<ClientHardwareProfile | null>(null);
  const [ramSliderValue, setRamSliderValue] = useState<number>(8);
  const [isWarming, setIsWarming] = useState<boolean>(false);
  const [warmProgress, setWarmProgress] = useState<InferenceProgressEvent | null>(null);
  const [cacheClearedMsg, setCacheClearedMsg] = useState<string | null>(null);
  const [oomError, setOomError] = useState<string | null>(null);

  // Load hardware profile on mount or modal open
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    profileClientHardware().then((prof) => {
      if (isMounted) {
        setProfile(prof);
        setRamSliderValue(prof.detectedRamGB);
      }
    });

    const unsubscribe = clientInference.subscribe((evt) => {
      setWarmProgress(evt);
      if (evt.phase === 'ready' || evt.phase === 'error') {
        setIsWarming(false);
      }
      if (evt.oomWarning) {
        setOomError(evt.oomWarning);
      }
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, [isOpen]);

  if (!isOpen || !profile) return null;

  const handleSliderChange = async (newVal: number) => {
    setRamSliderValue(newVal);
    setStoredRamOverride(newVal);
    const updated = await profileClientHardware(newVal);
    setProfile(updated);
    setOomError(null);
  };

  const handleResetToAuto = async () => {
    setStoredRamOverride(null);
    const updated = await profileClientHardware(null);
    setProfile(updated);
    setRamSliderValue(updated.detectedRamGB);
    setOomError(null);
  };

  const handleEngineModeToggle = (mode: 'client_webgpu' | 'native_window_ai' | 'host_server') => {
    setStoredEngineMode(mode);
    setProfile((prev) => (prev ? { ...prev, activeEngineMode: mode } : null));
    // EDG-01: Abort any running inference if mode switches
    clientInference.abortGeneration();
  };

  const handleModelSelect = async (model: ModelTier) => {
    if (!model.accessible) return;

    // EDG-02: Validate memory boundary
    const boundary = clientInference.validateMemoryBoundary(model, profile.detectedRamGB);
    if (!boundary.safe) {
      setOomError(boundary.warning || 'Memory boundary violation');
      return;
    }

    setOomError(null);
    setIsWarming(true);
    onSelectModel(model);
    await clientInference.warmModel(model, profile.detectedRamGB);
    setIsWarming(false);
  };

  const handleClearCache = async () => {
    const cleared = await clientInference.purgeCache();
    if (cleared) {
      setCacheClearedMsg('✓ Browser CacheStorage emptied (andromeda-model-weights-v1 purged).');
    } else {
      setCacheClearedMsg('Notice: No active cache found.');
    }
    setTimeout(() => setCacheClearedMsg(null), 3500);
  };

  const activeModel = profile.models.find((m) => m.id === (activeModelId || profile.recommendedModelId));

  return (
    <div id="modal-hardware" className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-3xl bg-[#0B0914] border border-white/10 shadow-[0_24px_80px_rgba(0,0,0,0.8)] text-zinc-100 overflow-hidden">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center text-white text-base shadow-[0_0_20px_rgba(147,51,234,0.4)]">
              ⚡
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-bold tracking-tight text-white">
                  Client Hardware Sync & In-Browser AI Allocation
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-emerald-300">
                  Zero Host Resources
                </span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Inference runs locally in your browser’s WebGPU RAM. Weights are cached on your disk for instant restarts.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition-colors text-sm"
          >
            ✕
          </button>
        </div>

        {/* Real-time Hardware Telemetry Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 px-6 py-3 bg-black/40 border-b border-white/5 text-[11px] font-mono">
          <div className="p-2 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="text-zinc-500 text-[9px] uppercase tracking-wider">System RAM</div>
            <div className="text-zinc-200 font-semibold flex items-center gap-1.5 mt-0.5">
              <span>{profile.detectedRamGB} GB</span>
              {profile.isOverridden && (
                <span className="text-[9px] text-purple-400 bg-purple-950/50 px-1 rounded border border-purple-500/30">Manual</span>
              )}
            </div>
          </div>

          <div className="p-2 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="text-zinc-500 text-[9px] uppercase tracking-wider">CPU Threads</div>
            <div className="text-zinc-200 font-semibold mt-0.5">{profile.cpuCores} Cores</div>
          </div>

          <div className="p-2 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="text-zinc-500 text-[9px] uppercase tracking-wider">WebGPU State</div>
            <div className="mt-0.5 flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${profile.hasWebGpu ? 'bg-emerald-400' : 'bg-rose-500'}`} />
              <span className={profile.hasWebGpu ? 'text-emerald-300' : 'text-rose-400'}>
                {profile.hasWebGpu ? 'Accelerated' : 'Disabled'}
              </span>
            </div>
          </div>

          <div className="p-2 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="text-zinc-500 text-[9px] uppercase tracking-wider">GPU / VRAM</div>
            <div className="text-zinc-200 truncate mt-0.5" title={profile.gpuVendor}>
              {profile.gpuVendor}
            </div>
          </div>
        </div>

        {/* EDG-03: Multi-Tab Concurrency Notice */}
        {warmProgress?.isMultiTabLocked && (
          <div className="mx-6 mt-3 p-3 rounded-2xl bg-amber-950/70 border border-amber-500/40 text-amber-200 text-xs flex items-center gap-2">
            <span>⚠️</span>
            <span>WebGPU is currently active in another browser tab. Concurrent multi-tab VRAM allocation is throttled to prevent browser crash.</span>
          </div>
        )}

        {/* EDG-02: OOM / VRAM Boundary Alert */}
        {oomError && (
          <div className="mx-6 mt-3 p-3 rounded-2xl bg-rose-950/80 border border-rose-500/50 text-rose-200 text-xs flex items-center justify-between animate-fadeIn">
            <div className="flex items-center gap-2">
              <span>🛑</span>
              <span>{oomError}</span>
            </div>
            <button
              onClick={handleResetToAuto}
              className="px-2 py-1 rounded bg-rose-900/60 hover:bg-rose-800 text-[10px] font-mono text-white underline"
            >
              Reset to Safe RAM
            </button>
          </div>
        )}

        {/* Engine Mode Selector Tabs */}
        <div className="px-6 pt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              id="btn-engine-webgpu"
              onClick={() => handleEngineModeToggle('client_webgpu')}
              disabled={!profile.hasWebGpu}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all flex items-center gap-1.5 ${
                profile.activeEngineMode === 'client_webgpu'
                  ? 'bg-purple-600/30 border-purple-500/60 text-purple-200 shadow-[0_0_12px_rgba(168,85,247,0.3)]'
                  : profile.hasWebGpu
                  ? 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-600 cursor-not-allowed'
              }`}
            >
              <span>⚡</span>
              <span>Client WebGPU (Zero Host Load)</span>
            </button>

            {profile.hasNativeWindowAi && (
              <button
                id="btn-engine-windowai"
                onClick={() => handleEngineModeToggle('native_window_ai')}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all flex items-center gap-1.5 ${
                  profile.activeEngineMode === 'native_window_ai'
                    ? 'bg-emerald-600/30 border-emerald-500/60 text-emerald-200 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                    : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
                }`}
              >
                <span>🚀</span>
                <span>Chrome Native AI (0s Setup)</span>
              </button>
            )}

            <button
              id="btn-engine-host"
              onClick={() => handleEngineModeToggle('host_server')}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all flex items-center gap-1.5 ${
                profile.activeEngineMode === 'host_server'
                  ? 'bg-amber-600/30 border-amber-500/60 text-amber-200'
                  : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
              }`}
            >
              <span>🖥️</span>
              <span>Host Ollama Container</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              id="btn-purge-cache"
              onClick={handleClearCache}
              className="text-[10px] font-mono text-zinc-500 hover:text-rose-400 transition-colors"
              title="Purge cached model shards from browser CacheStorage"
            >
              Purge Weight Cache
            </button>
          </div>
        </div>

        {cacheClearedMsg && (
          <div className="mx-6 mt-2 px-3 py-1.5 rounded-xl bg-purple-950/40 border border-purple-500/30 text-purple-300 text-xs animate-fadeIn">
            {cacheClearedMsg}
          </div>
        )}

        {/* Live Warming / Download Progress Bar */}
        {warmProgress && warmProgress.phase !== 'idle' && (
          <div className="mx-6 mt-3 p-3 rounded-2xl bg-white/[0.02] border border-purple-500/30 shadow-inner">
            <div className="flex items-center justify-between text-xs font-mono mb-1.5">
              <span className="text-purple-300 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
                <span>{warmProgress.text}</span>
              </span>
              <span className="text-purple-400 font-bold">
                {Math.round(warmProgress.progress * 100)}%
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-black/60 overflow-hidden p-0.5">
              <div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 via-indigo-400 to-emerald-400 transition-all duration-200"
                style={{ width: `${Math.round(warmProgress.progress * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Interactive RAM Override Slider */}
        <div className="mx-6 mt-4 p-4 rounded-2xl bg-gradient-to-b from-white/[0.04] to-transparent border border-white/10">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
            <div>
              <span className="text-xs font-semibold text-white">Device RAM Allocation Slider</span>
              <span className="text-[10px] text-zinc-400 ml-2">
                (Browsers cap detection at 8GB for privacy; adjust if your machine has 16GB, 32GB or 64GB)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono font-bold text-purple-400">
                {ramSliderValue} GB Total RAM
              </span>
              <span className="text-[10px] text-zinc-500">|</span>
              <span id="badge-safe-budget" className="text-[11px] font-mono text-emerald-400">
                ~{profile.safeMemoryBudgetGB} GB AI Budget
              </span>
              {profile.isOverridden && (
                <button
                  id="btn-reset-ram"
                  onClick={handleResetToAuto}
                  className="text-[10px] text-zinc-400 hover:text-white underline ml-1"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          <input
            id="ram-slider"
            type="range"
            min="2"
            max="32"
            step="2"
            value={ramSliderValue}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
          />

          <div className="flex justify-between text-[10px] font-mono text-zinc-500 mt-1">
            <span>2GB (Mobile)</span>
            <span>4GB</span>
            <span>8GB (Browser Default)</span>
            <span>16GB (Pro Laptop)</span>
            <span>24GB</span>
            <span>32GB (Workstation)</span>
          </div>
        </div>

        {/* Council Model Tier Selection Cards */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 flex items-center justify-between">
            <span>Andromeda Council Seats & Weights Catalog</span>
            <span>Local WebGPU 4-bit Quantization</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {profile.models.map((model) => {
              const isSelected = model.id === (activeModel?.id);

              let badgeStyle = 'bg-zinc-800 text-zinc-400 border-zinc-700';
              if (model.badge === 'Recommended') {
                badgeStyle = 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.3)]';
              } else if (model.badge === 'Unlocked') {
                badgeStyle = 'bg-cyan-950/80 text-cyan-300 border-cyan-500/40';
              } else if (model.badge === 'Tight') {
                badgeStyle = 'bg-amber-950/80 text-amber-300 border-amber-500/40';
              } else if (model.badge === 'Locked') {
                badgeStyle = 'bg-rose-950/60 text-rose-400 border-rose-500/30';
              }

              return (
                <div
                  id={`model-card-${model.id}`}
                  key={model.id}
                  className={`p-4 rounded-2xl border transition-all relative flex flex-col justify-between ${
                    isSelected
                      ? 'bg-purple-950/30 border-purple-500 shadow-[0_0_20px_rgba(147,51,234,0.25)]'
                      : model.accessible
                      ? 'bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]'
                      : 'bg-black/30 border-white/5 opacity-60'
                  }`}
                >
                  <div>
                    {/* Top Seat Title & Badge */}
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-sm text-white">{model.name}</span>
                          {model.stage === 1 && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-500/30">
                              ⚡ Fast-Start
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] font-mono text-purple-400">
                          Council Seat: {model.seat}
                        </div>
                      </div>

                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${badgeStyle}`}>
                        {model.badge}
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-400 mb-3 leading-relaxed">
                      {model.description}
                    </p>
                  </div>

                  {/* Telemetry Footprint & Selection Trigger */}
                  <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono">
                    <div className="space-y-0.5 text-zinc-400">
                      <div>Download: <span className="text-zinc-200">{model.weightsDownloadMB} MB</span></div>
                      <div>RAM Required: <span className="text-zinc-200">{model.requiredRamGB} GB</span> (VRAM ~{model.runtimeVramGB}GB)</div>
                      <div className="text-emerald-400/90">
                        Fiber: ~{model.estimatedDownloadSec.fastFiber}s | Wi-Fi: ~{model.estimatedDownloadSec.standardWifi}s
                      </div>
                    </div>

                    <button
                      id={`btn-select-model-${model.id}`}
                      onClick={() => handleModelSelect(model)}
                      disabled={!model.accessible || isWarming}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                        isSelected
                          ? 'bg-purple-600 text-white font-semibold'
                          : model.accessible
                          ? 'bg-white/10 hover:bg-purple-600/60 text-white active:scale-95'
                          : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                      }`}
                    >
                      {isSelected ? 'Active Seat ✓' : model.accessible ? 'Mount Model' : 'Locked'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-white/[0.01] flex items-center justify-between text-[11px] text-zinc-400">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>PWA & WebGPU local cache enabled. Subsequent visits load in ~1-2s.</span>
          </div>

          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-medium transition-colors"
          >
            Done
          </button>
        </div>

      </div>
    </div>
  );
};
