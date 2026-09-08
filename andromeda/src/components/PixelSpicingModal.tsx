import React, { useState, useRef, useEffect } from 'react';

export interface PixelSpicingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CameraMetadata {
  make?: string | null;
  model?: string | null;
  device_category?: string;
  device_display_name?: string;
  lens_model?: string | null;
  iso?: number | null;
  f_number?: number | null;
  exposure_time?: string | null;
  focal_length?: number | null;
  color_space?: string;
  has_exif?: boolean;
}

interface AdaptiveTuning {
  apply_denoise?: boolean;
  clip_limit?: number;
  optimal_scale?: number;
  reasons?: string[];
  target_screen_match?: {
    viewport?: [number, number];
    dpr?: number;
    target_effective_res?: [number, number];
    fit_scale_factor?: number;
  };
}

interface EnhanceResponse {
  status: string;
  output_file?: string;
  filename?: string;
  download_url: string;
  image_base64?: string;
  original_resolution?: string | [number, number];
  enhanced_resolution?: string | [number, number];
  sentinel_critique?: string;
  critique?: string;
  scale?: number;
  model?: string;
  camera_metadata?: CameraMetadata;
  adaptive_tuning?: AdaptiveTuning;
  denoise?: { applied?: boolean; type?: string; duration_ms?: number };
  duration_ms?: number;
  error?: string;
}

export const PixelSpicingModal: React.FC<PixelSpicingModalProps> = ({ isOpen, onClose }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [originalDimensions, setOriginalDimensions] = useState<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState<number>(4);
  const [model, setModel] = useState<string>('realesrgan-x4plus');
  const [autoAdaptive, setAutoAdaptive] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [result, setResult] = useState<EnhanceResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'enhanced' | 'split' | 'original'>('split');
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Screen metrics
  const [screenWidth, setScreenWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1920);
  const [screenHeight, setScreenHeight] = useState<number>(typeof window !== 'undefined' ? window.innerHeight : 1080);
  const [dpr, setDpr] = useState<number>(typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setScreenWidth(window.innerWidth);
      setScreenHeight(window.innerHeight);
      setDpr(window.devicePixelRatio || 1);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileSelect = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setErrorMsg('Please select a valid image file (PNG, JPG, WEBP).');
      return;
    }
    setErrorMsg(null);
    setResult(null);
    setSelectedFile(file);

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setPreviewUrl(dataUrl);

      // Extract image natural dimensions
      const img = new Image();
      img.onload = () => {
        setOriginalDimensions({ w: img.naturalWidth, h: img.naturalHeight });
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const executeEnhancement = async () => {
    if (!previewUrl) return;

    setLoading(true);
    setErrorMsg(null);
    setResult(null);

    setLoadingStage('Step 1/4: Reading Phone/Camera EXIF metadata & display viewport...');
    const t1 = setTimeout(() => {
      setLoadingStage('Step 2/4: Bilateral sensor noise filtering & LAB CLAHE dynamic range balance...');
    }, 1500);
    const t2 = setTimeout(() => {
      setLoadingStage('Step 3/4: Real-ESRGAN Vulkan NCNN Neural Super-Resolution on host GPU...');
    }, 3200);
    const t3 = setTimeout(() => {
      setLoadingStage('Step 4/4: Moondream Sentinel evaluating optical clarity against camera limits...');
    }, 5200);

    try {
      const res = await fetch('/api/spice/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: previewUrl,
          scale: scale,
          model: model,
          target_screen_width: screenWidth,
          target_screen_height: screenHeight,
          device_pixel_ratio: dpr,
          auto_adaptive: autoAdaptive,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.error || data.detail || 'Enhancement pipeline failed.');
      }
      setResult(data);
    } catch (err: any) {
      console.error('Enhance error:', err);
      setErrorMsg(err.message || 'Failed to connect to /api/spice/enhance');
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setLoading(false);
      setLoadingStage('');
    }
  };

  const resetAll = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setOriginalDimensions(null);
    setResult(null);
    setErrorMsg(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn">
      {/* Modal Container */}
      <div className="relative w-full max-w-4xl max-h-[92vh] bg-[#0E0B1A]/95 border border-white/10 rounded-3xl shadow-[0_24px_70px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-lg shadow-[0_0_15px_rgba(245,158,11,0.25)]">
              👁️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Pixel-Spicer & Moondream Sentinel
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  Camera EXIF & Screen Maximizer
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Origin phone profile • Sensor-aware noise suppression • 4x Vulkan NCNN super-resolution
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {errorMsg && (
            <div className="p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2">
              <span>⚠️</span>
              <span>{errorMsg}</span>
            </div>
          )}

          {/* If No Image Uploaded Yet */}
          {!previewUrl && (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-3xl p-12 text-center cursor-pointer transition-all ${
                isDragging
                  ? 'border-purple-500 bg-purple-950/30'
                  : 'border-white/15 bg-white/[0.02] hover:border-purple-500/50 hover:bg-purple-950/10'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelect(e.target.files[0]);
                  }
                }}
              />
              <div className="w-16 h-16 mx-auto rounded-3xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300 text-2xl mb-4 shadow-[0_0_20px_rgba(168,85,247,0.2)]">
                🖼️
              </div>
              <h3 className="text-base font-semibold text-white">
                Upload photo or drag and drop here
              </h3>
              <p className="text-xs text-zinc-400 mt-1.5 max-w-md mx-auto">
                Andromeda automatically reads origin phone/camera EXIF (ISO, lens, aperture) and maximizes resolution for your target screen ({screenWidth}×{screenHeight} @ {dpr}x DPR).
              </p>
              <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600/30 border border-purple-500/40 text-purple-200 text-xs font-medium shadow-md">
                Browse Files
              </div>
            </div>
          )}

          {/* If Image Selected but not enhanced yet */}
          {previewUrl && !result && (
            <div className="space-y-6">
              <div className="flex flex-col md:flex-row gap-6 items-start">
                
                {/* Image Preview Box */}
                <div className="w-full md:w-1/2 aspect-video bg-black/60 rounded-2xl border border-white/10 overflow-hidden flex items-center justify-center relative">
                  <img
                    src={previewUrl}
                    alt="Original Preview"
                    className="max-h-full max-w-full object-contain"
                  />
                  {originalDimensions && (
                    <div className="absolute bottom-2 left-2 px-2.5 py-1 rounded-lg bg-black/75 border border-white/10 text-[10px] font-mono text-zinc-300 backdrop-blur-md">
                      Original: {originalDimensions.w} × {originalDimensions.h} px
                    </div>
                  )}
                </div>

                {/* Settings & Execution Panel */}
                <div className="w-full md:w-1/2 space-y-4">
                  
                  {/* Target Screen Maximizer Banner */}
                  <div className="p-3 rounded-2xl bg-purple-950/30 border border-purple-500/30 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-purple-400">🖥️</span>
                      <div>
                        <div className="font-semibold text-white text-[11px]">Display Maximizer</div>
                        <div className="text-[10px] text-zinc-400 font-mono">
                          Target Viewport: {screenWidth}×{screenHeight} ({dpr}x DPR)
                        </div>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-600/40 text-purple-200">
                      Auto Maximized
                    </span>
                  </div>

                  {/* Adaptive Hardware Tuning Toggle */}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/5">
                    <div>
                      <div className="text-xs font-medium text-white">Camera Hardware Optimization</div>
                      <div className="text-[10px] text-zinc-400">
                        Adjusts denoising & CLAHE according to origin phone/camera sensor
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoAdaptive}
                      onChange={(e) => setAutoAdaptive(e.target.checked)}
                      className="w-4 h-4 accent-purple-500 cursor-pointer"
                    />
                  </div>

                  {/* Scale Selector */}
                  <div>
                    <label className="text-xs font-mono uppercase text-zinc-400 block mb-1.5">
                      Neural Super-Resolution Scale
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => setScale(4)}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          scale === 4
                            ? 'bg-purple-900/40 border-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.25)]'
                            : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
                        }`}
                      >
                        <div className="text-sm font-bold">4x Ultra HD</div>
                        <div className="text-[10px] text-zinc-400 mt-0.5">
                          {originalDimensions
                            ? `${originalDimensions.w * 4} × ${originalDimensions.h * 4} px`
                            : '400% Super-Sample'}
                        </div>
                      </button>
                      <button
                        onClick={() => setScale(2)}
                        className={`p-3 rounded-xl border text-left transition-all ${
                          scale === 2
                            ? 'bg-purple-900/40 border-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.25)]'
                            : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
                        }`}
                      >
                        <div className="text-sm font-bold">2x Fast HD</div>
                        <div className="text-[10px] text-zinc-400 mt-0.5">
                          {originalDimensions
                            ? `${originalDimensions.w * 2} × ${originalDimensions.h * 2} px`
                            : '200% Scale'}
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Model Engine */}
                  <div>
                    <label className="text-xs font-mono uppercase text-zinc-400 block mb-1.5">
                      Vulkan Neural Model
                    </label>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full bg-black/50 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-zinc-200 focus:outline-none focus:border-purple-500/50"
                    >
                      <option value="realesrgan-x4plus">RealESRGAN-x4plus (Photographic & Real World)</option>
                      <option value="realesrgan-x4plus-anime">RealESRGAN-x4plus-anime (Illustrations & UI)</option>
                    </select>
                  </div>

                  {/* Execute Button */}
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      onClick={executeEnhancement}
                      disabled={loading}
                      className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-pink-600 text-white font-semibold text-sm shadow-[0_4px_20px_rgba(168,85,247,0.4)] hover:brightness-110 active:scale-[0.98] disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>Enhancing with Hardware Tuning...</span>
                        </>
                      ) : (
                        <>
                          <span>⚡</span>
                          <span>Spice & Maximize ({scale}x)</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={resetAll}
                      disabled={loading}
                      className="py-3 px-4 rounded-xl bg-white/5 border border-white/10 text-zinc-400 hover:text-white text-xs transition-colors"
                    >
                      Reset
                    </button>
                  </div>

                  {/* Progress tracker */}
                  {loading && (
                    <div className="p-3 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200 animate-pulse flex items-center gap-2">
                      <span>🔮</span>
                      <span>{loadingStage || 'Reading camera EXIF and initiating Vulkan NCNN...'}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* If Enhancement Finished */}
          {result && (
            <div className="space-y-6">
              
              {/* Origin Device & Camera Hardware Profile Card */}
              {result.camera_metadata && (
                <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/10 flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-xl">
                      {result.camera_metadata.device_category === 'smartphone'
                        ? '📱'
                        : result.camera_metadata.device_category === 'pro_camera'
                        ? '📷'
                        : result.camera_metadata.device_category === 'drone_action'
                        ? '🚁'
                        : '🖼️'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white tracking-wide">
                          {result.camera_metadata.device_display_name || 'Camera Device'}
                        </span>
                        <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-white/5">
                          {result.camera_metadata.device_category || 'origin'}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-zinc-400 mt-1">
                        {result.camera_metadata.iso && (
                          <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5">
                            ISO {result.camera_metadata.iso}
                          </span>
                        )}
                        {result.camera_metadata.f_number && (
                          <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5">
                            f/{result.camera_metadata.f_number}
                          </span>
                        )}
                        {result.camera_metadata.focal_length && (
                          <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5">
                            {result.camera_metadata.focal_length}mm
                          </span>
                        )}
                        {result.camera_metadata.exposure_time && (
                          <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5">
                            {result.camera_metadata.exposure_time}
                          </span>
                        )}
                        {result.camera_metadata.color_space && (
                          <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5 text-purple-300">
                            {result.camera_metadata.color_space}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Target Screen Maximization Match */}
                  {result.adaptive_tuning?.target_screen_match && (
                    <div className="text-right">
                      <div className="text-[10px] font-mono text-zinc-400">Target Screen Maximized</div>
                      <div className="text-xs font-bold text-emerald-400 font-mono">
                        {result.adaptive_tuning.target_screen_match.target_effective_res?.[0]} ×{' '}
                        {result.adaptive_tuning.target_screen_match.target_effective_res?.[1]} px
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Adaptive Tuning Explanations */}
              {result.adaptive_tuning?.reasons && result.adaptive_tuning.reasons.length > 0 && (
                <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-500/20 text-xs text-purple-200 space-y-1">
                  <div className="font-semibold text-[11px] flex items-center gap-1.5 text-purple-300">
                    <span>🎛️</span>
                    <span>Adaptive Hardware Optimizations Applied:</span>
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-[10px] text-zinc-300">
                    {result.adaptive_tuning.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* View Selector & Resolution Details */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-zinc-400">View:</span>
                  <div className="flex rounded-xl bg-white/5 p-1 border border-white/10 text-xs">
                    <button
                      onClick={() => setViewMode('split')}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        viewMode === 'split' ? 'bg-purple-600 text-white' : 'text-zinc-400 hover:text-white'
                      }`}
                    >
                      Split Comparison
                    </button>
                    <button
                      onClick={() => setViewMode('enhanced')}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        viewMode === 'enhanced' ? 'bg-purple-600 text-white' : 'text-zinc-400 hover:text-white'
                      }`}
                    >
                      Enhanced ({result.scale || scale}x)
                    </button>
                    <button
                      onClick={() => setViewMode('original')}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        viewMode === 'original' ? 'bg-purple-600 text-white' : 'text-zinc-400 hover:text-white'
                      }`}
                    >
                      Original
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="px-2.5 py-1 rounded-lg bg-zinc-800 text-zinc-300">
                    {Array.isArray(result.original_resolution)
                      ? `${result.original_resolution[0]} × ${result.original_resolution[1]}`
                      : result.original_resolution || 'Original'}
                  </span>
                  <span className="text-purple-400 font-bold">&rarr;</span>
                  <span className="px-2.5 py-1 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-bold">
                    {Array.isArray(result.enhanced_resolution)
                      ? `${result.enhanced_resolution[0]} × ${result.enhanced_resolution[1]}`
                      : result.enhanced_resolution || 'Enhanced'}
                  </span>
                </div>
              </div>

              {/* Image Comparison Box */}
              <div className="relative rounded-2xl border border-white/10 bg-black overflow-hidden aspect-video flex items-center justify-center">
                {viewMode === 'split' ? (
                  <div className="w-full h-full flex">
                    <div className="w-1/2 h-full border-r border-purple-500/50 relative overflow-hidden flex items-center justify-center bg-black/60">
                      <img
                        src={previewUrl || ''}
                        alt="Original"
                        className="max-h-full max-w-full object-contain"
                      />
                      <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono text-zinc-400 border border-white/10">
                        Original (1x)
                      </span>
                    </div>
                    <div className="w-1/2 h-full relative overflow-hidden flex items-center justify-center bg-black/60">
                      <img
                        src={result.image_base64 || result.download_url}
                        alt="Enhanced"
                        className="max-h-full max-w-full object-contain"
                      />
                      <span className="absolute top-2 right-2 px-2 py-0.5 rounded bg-emerald-950/80 text-[10px] font-mono text-emerald-300 border border-emerald-500/30">
                        {result.scale || scale}x Enhanced (Vulkan NCNN)
                      </span>
                    </div>
                  </div>
                ) : viewMode === 'enhanced' ? (
                  <div className="w-full h-full flex items-center justify-center relative">
                    <img
                      src={result.image_base64 || result.download_url}
                      alt="Enhanced"
                      className="max-h-full max-w-full object-contain"
                    />
                    <span className="absolute top-2 right-2 px-2.5 py-1 rounded-lg bg-emerald-950/80 text-xs font-mono text-emerald-300 border border-emerald-500/30">
                      {result.scale || scale}x Maximize
                    </span>
                  </div>
                ) : (
                  <div className="w-full h-full flex items-center justify-center relative">
                    <img
                      src={previewUrl || ''}
                      alt="Original"
                      className="max-h-full max-w-full object-contain"
                    />
                    <span className="absolute top-2 left-2 px-2.5 py-1 rounded-lg bg-black/80 text-xs font-mono text-zinc-400 border border-white/10">
                      Original
                    </span>
                  </div>
                )}
              </div>

              {/* Moondream Sentinel Hardware-Calibrated Visual Critique */}
              <div className="p-4 rounded-2xl bg-amber-950/25 border border-amber-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400">👁️</span>
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                      Moondream Sentinel Hardware Critique
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                    Camera Calibrated
                  </span>
                </div>
                <div className="text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap bg-black/30 p-3 rounded-xl border border-white/5">
                  {result.critique || result.sentinel_critique || 'Visual fidelity verified against camera sensor parameters.'}
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                  <a
                    href={result.image_base64 || result.download_url}
                    download={result.filename || 'spiced_enhanced.png'}
                    className="py-3 px-5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold text-sm shadow-[0_4px_20px_rgba(16,185,129,0.35)] hover:brightness-110 active:scale-[0.98] transition-all flex items-center gap-2"
                  >
                    <span>⬇</span>
                    <span>Download {result.scale || scale}x Enhanced Image</span>
                  </a>
                  <button
                    onClick={resetAll}
                    className="py-3 px-4 rounded-xl bg-white/5 border border-white/10 text-zinc-300 hover:text-white text-xs font-medium transition-colors"
                  >
                    Spice Another
                  </button>
                </div>

                <button
                  onClick={onClose}
                  className="py-3 px-4 rounded-xl text-zinc-400 hover:text-white text-xs transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PixelSpicingModal;
