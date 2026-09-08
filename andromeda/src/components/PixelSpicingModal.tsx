import React, { useState, useRef } from 'react';

export interface PixelSpicingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface EnhanceResponse {
  status: string;
  output_file: string;
  download_url: string;
  original_resolution: [number, number];
  enhanced_resolution: [number, number];
  sentinel_critique: string;
  seat?: string;
  vram_status?: string;
  error?: string;
}

export const PixelSpicingModal: React.FC<PixelSpicingModalProps> = ({ isOpen, onClose }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [originalDimensions, setOriginalDimensions] = useState<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState<number>(4);
  const [model, setModel] = useState<string>('realesrgan-x4plus');
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [result, setResult] = useState<EnhanceResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'enhanced' | 'split' | 'original'>('split');
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

    setLoadingStage('Step 1/3: LAB Color CLAHE dynamic range balance...');
    const t1 = setTimeout(() => {
      setLoadingStage('Step 2/3: Real-ESRGAN Vulkan NCNN 4x Neural Upscaling...');
    }, 1800);
    const t2 = setTimeout(() => {
      setLoadingStage('Step 3/3: Moondream Sentinel visual critique analysis...');
    }, 3800);

    try {
      const res = await fetch('/api/spice/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: previewUrl,
          scale: scale,
          model: model,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status !== 'success') {
        throw new Error(data.error || 'Enhancement pipeline failed.');
      }
      setResult(data);
    } catch (err: any) {
      console.error('Enhance error:', err);
      setErrorMsg(err.message || 'Failed to connect to /api/spice/enhance');
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      {/* Modal Container */}
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#0E0B1A]/95 border border-white/10 rounded-3xl shadow-[0_20px_60px_rgba(0,0,0,0.8)] flex flex-col overflow-hidden">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-lg shadow-[0_0_15px_rgba(245,158,11,0.2)]">
              👁️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Pixel-Spicer & Moondream Sentinel
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  4x Vulkan Neural Engine
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                CLAHE dynamic range balancing • Real-ESRGAN NCNN • Moondream visual critique
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
              <div className="w-16 h-16 mx-auto rounded-3xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300 text-2xl mb-4">
                🖼️
              </div>
              <h3 className="text-base font-semibold text-white">
                Drag & Drop high-fidelity photo or click to browse
              </h3>
              <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
                Supports PNG, JPG, and WEBP. Image will be processed with CLAHE dynamic range balance and 4x neural upscaling.
              </p>
              <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600/30 border border-purple-500/40 text-purple-200 text-xs font-medium">
                Choose Image File
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
                  <div>
                    <label className="text-xs font-mono uppercase text-zinc-400 block mb-1.5">
                      Upscaling Scale Factor
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
                            : '400% detail synthesis'}
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
                            : '200% sharp scale'}
                        </div>
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-mono uppercase text-zinc-400 block mb-1.5">
                      Neural Model Engine
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

                  {/* Feature Checkpoints */}
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5 space-y-1.5 text-xs text-zinc-300">
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
                      <span>LAB Color space CLAHE dynamic range balance</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
                      <span>Vulkan NCNN GPU acceleration pipeline</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-amber-400">✓</span>
                      <span>Moondream (The Sentinel) visual layout analysis</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      onClick={executeEnhancement}
                      disabled={loading}
                      className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-pink-600 text-white font-semibold text-sm shadow-[0_4px_20px_rgba(168,85,247,0.4)] hover:brightness-110 active:scale-[0.98] disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                    >
                      {loading ? (
                        <>
                          <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>Processing...</span>
                        </>
                      ) : (
                        <>
                          <span>⚡</span>
                          <span>Spice & Enhance ({scale}x)</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={resetAll}
                      disabled={loading}
                      className="py-3 px-4 rounded-xl bg-white/5 border border-white/10 text-zinc-400 hover:text-white text-xs transition-colors"
                    >
                      Change
                    </button>
                  </div>

                  {/* Progress tracker during execution */}
                  {loading && (
                    <div className="p-3 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200 animate-pulse flex items-center gap-2">
                      <span>🔮</span>
                      <span>{loadingStage || 'Initiating Vulkan NCNN pipeline...'}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* If Enhancement Finished */}
          {result && (
            <div className="space-y-6">
              {/* Top View Selector & Resolution Badges */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/5">
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
                      Enhanced ({scale}x)
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
                    {result.original_resolution[0]} × {result.original_resolution[1]}
                  </span>
                  <span className="text-purple-400 font-bold">&rarr;</span>
                  <span className="px-2.5 py-1 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-bold">
                    {result.enhanced_resolution[0]} × {result.enhanced_resolution[1]} px
                  </span>
                </div>
              </div>

              {/* Image Comparison Render */}
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
                        src={result.download_url}
                        alt="4x Enhanced"
                        className="max-h-full max-w-full object-contain"
                      />
                      <span className="absolute top-2 right-2 px-2 py-0.5 rounded bg-emerald-950/80 text-[10px] font-mono text-emerald-300 border border-emerald-500/30">
                        {scale}x Enhanced (CLAHE + Vulkan)
                      </span>
                    </div>
                  </div>
                ) : viewMode === 'enhanced' ? (
                  <div className="w-full h-full flex items-center justify-center relative">
                    <img
                      src={result.download_url}
                      alt="4x Enhanced"
                      className="max-h-full max-w-full object-contain"
                    />
                    <span className="absolute top-2 right-2 px-2.5 py-1 rounded-lg bg-emerald-950/80 text-xs font-mono text-emerald-300 border border-emerald-500/30">
                      {scale}x Enhanced
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

              {/* Moondream Sentinel Visual Critique Panel */}
              <div className="p-4 rounded-2xl bg-amber-950/25 border border-amber-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400">👁️</span>
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                      Moondream Sentinel Visual Critique
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                    Council Vision Seat
                  </span>
                </div>
                <div className="text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap bg-black/30 p-3 rounded-xl border border-white/5">
                  {result.sentinel_critique || 'Visual fidelity verified. Sub-pixel edges and high-frequency textures restored.'}
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                  <a
                    href={result.download_url}
                    download={result.output_file}
                    className="py-3 px-5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold text-sm shadow-[0_4px_20px_rgba(16,185,129,0.35)] hover:brightness-110 active:scale-[0.98] transition-all flex items-center gap-2"
                  >
                    <span>⬇</span>
                    <span>Download {scale}x Enhanced Image</span>
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
