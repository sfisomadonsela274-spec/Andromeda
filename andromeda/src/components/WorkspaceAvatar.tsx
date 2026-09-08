import React, { useEffect, useRef } from 'react';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'alert';

export interface CouncilBadgeInfo {
  seat: 'The Scribe' | 'The Architect' | 'The Logician' | 'The Sentinel' | string;
  model?: string;
  vramProfile?: string;
  reason?: string;
}

export interface WorkspaceAvatarProps {
  state: AvatarState;
  councilSeat?: CouncilBadgeInfo | string | null;
  audioLevel?: number; // 0.0 to 1.0 (from Web Audio API)
  size?: number;
  className?: string;
  onClick?: () => void;
}

// Seat styling configurations
const SEAT_CONFIG: Record<
  string,
  { name: string; title: string; color: string; border: string; bg: string; dot: string; icon: string }
> = {
  'The Scribe': {
    name: 'The Scribe',
    title: 'Fast Intent & Code Tooling (Qwen 1.5B)',
    color: 'text-emerald-400',
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-950/40',
    dot: 'bg-emerald-400',
    icon: '✍️',
  },
  'The Architect': {
    name: 'The Architect',
    title: 'Deep Multi-File Coder (Qwen 7B)',
    color: 'text-blue-400',
    border: 'border-blue-500/30',
    bg: 'bg-blue-950/40',
    dot: 'bg-blue-400',
    icon: '🏛️',
  },
  'The Logician': {
    name: 'The Logician',
    title: 'Deep Research & Socrates (Llama 3.2)',
    color: 'text-purple-400',
    border: 'border-purple-500/30',
    bg: 'bg-purple-950/40',
    dot: 'bg-purple-400',
    icon: '🧠',
  },
  'The Sentinel': {
    name: 'The Sentinel',
    title: 'Vision & Moondream Visual Critique',
    color: 'text-amber-400',
    border: 'border-amber-500/30',
    bg: 'bg-amber-950/40',
    dot: 'bg-amber-400',
    icon: '👁️',
  },
};

export const WorkspaceAvatar: React.FC<WorkspaceAvatarProps> = ({
  state = 'idle',
  councilSeat = null,
  audioLevel = 0,
  size = 200,
  className = '',
  onClick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number>(0);
  const angleRef = useRef<number>(0);

  // Parse council seat information
  const currentSeatName =
    typeof councilSeat === 'string'
      ? councilSeat
      : councilSeat?.seat || 'The Scribe';
  const seatConfig = SEAT_CONFIG[currentSeatName] || {
    name: currentSeatName || 'Andromeda Core',
    title: 'Active Intelligence Core',
    color: 'text-purple-400',
    border: 'border-purple-500/30',
    bg: 'bg-purple-950/40',
    dot: 'bg-purple-400',
    icon: '✨',
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Retina High-DPI support
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const center = size / 2;

    // Micro-particles setup with diverse orbital radiuses and speeds
    const particles = Array.from({ length: 28 }, (_, i) => ({
      angle: (i / 28) * Math.PI * 2,
      dist: 36 + (i % 4) * 11,
      speed: 0.012 + (i % 5) * 0.004,
      size: 1.2 + (i % 3) * 0.9,
      z: (i % 5) / 5,
    }));

    const render = () => {
      ctx.clearRect(0, 0, size, size);
      angleRef.current += 0.02;
      const t = angleRef.current;

      // Color scheme selector based on agent state
      let coreR = 139,
        coreG = 44,
        coreB = 255; // Violet (Idle)
      let glowR = 255,
        glowG = 42,
        glowB = 141; // Hot Pink / Magenta

      if (state === 'listening') {
        coreR = 0;
        coreG = 240;
        coreB = 255; // Electric Cyan
        glowR = 0;
        glowG = 255;
        glowB = 102; // Matrix Green
      } else if (state === 'thinking') {
        // Adapt thinking color slightly to current council seat if active
        if (currentSeatName === 'The Architect') {
          coreR = 59;
          coreG = 130;
          coreB = 246; // Blue
          glowR = 99;
          glowG = 102;
          glowB = 241; // Indigo
        } else if (currentSeatName === 'The Sentinel') {
          coreR = 245;
          coreG = 158;
          coreB = 11; // Amber
          glowR = 239;
          glowG = 68;
          glowB = 68; // Crimson
        } else if (currentSeatName === 'The Scribe') {
          coreR = 16;
          coreG = 185;
          coreB = 129; // Emerald
          glowR = 6;
          glowG = 182;
          glowB = 212; // Cyan
        } else {
          coreR = 168;
          coreG = 85;
          coreB = 247; // Cosmic Lavender
          glowR = 99;
          glowG = 102;
          glowB = 241; // Deep Indigo
        }
      } else if (state === 'alert') {
        coreR = 245;
        coreG = 158;
        coreB = 11; // Amber Alert
        glowR = 239;
        glowG = 68;
        glowB = 68; // Crimson Flare
      }

      // 1. Outer Nebular Glow Aura
      const baseRadius =
        state === 'listening'
          ? 38 + audioLevel * 30
          : state === 'thinking'
          ? 34 + Math.sin(t * 3.5) * 6
          : state === 'alert'
          ? 44 + Math.sin(t * 6) * 8
          : 32 + Math.sin(t * 1.5) * 3;

      const radial = ctx.createRadialGradient(
        center,
        center,
        2,
        center,
        center,
        baseRadius * 1.9
      );
      radial.addColorStop(0, `rgba(${coreR}, ${coreG}, ${coreB}, 0.95)`);
      radial.addColorStop(0.4, `rgba(${glowR}, ${glowG}, ${glowB}, 0.4)`);
      radial.addColorStop(1, 'rgba(10, 7, 20, 0)');
      ctx.fillStyle = radial;
      ctx.beginPath();
      ctx.arc(center, center, baseRadius * 1.9, 0, Math.PI * 2);
      ctx.fill();

      // 2. Cosmic Orbital Resonator Rings
      ctx.save();
      ctx.translate(center, center);

      // Ring 1 (Tilted Ellipse)
      ctx.rotate(t * 0.4);
      ctx.beginPath();
      ctx.ellipse(0, 0, baseRadius * 1.15, baseRadius * 0.65, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${glowR}, ${glowG}, ${glowB}, ${
        state === 'thinking' ? 0.6 : 0.25
      })`;
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // Ring 2 (Counter-Tilted Ellipse)
      ctx.rotate(-t * 0.8);
      ctx.beginPath();
      ctx.ellipse(0, 0, baseRadius * 0.85, baseRadius * 1.25, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${coreR}, ${coreG}, ${coreB}, ${
        state === 'thinking' ? 0.5 : 0.2
      })`;
      ctx.lineWidth = 1.0;
      ctx.stroke();

      ctx.restore();

      // 3. Swirling Micro-Particles / Accretion Orbiters
      particles.forEach((p, idx) => {
        p.angle += state === 'thinking' ? p.speed * 3.5 : p.speed;
        let currentDist = p.dist;

        if (state === 'thinking') {
          // Inward accretion spiral effect
          currentDist = p.dist * (0.65 + 0.35 * Math.sin(t * 2 + idx));
        } else if (state === 'listening') {
          currentDist = p.dist + audioLevel * 22;
        } else if (state === 'alert') {
          currentDist = p.dist + Math.sin(t * 4 + idx) * 8;
        } else {
          currentDist = p.dist + Math.sin(t + idx) * 3;
        }

        const x = center + Math.cos(p.angle) * currentDist;
        const y = center + Math.sin(p.angle) * currentDist;

        ctx.fillStyle = `rgba(${glowR}, ${glowG}, ${glowB}, 0.85)`;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      // 4. Central Singularity / Star Core
      const coreSize =
        state === 'thinking'
          ? 8 + Math.sin(t * 7) * 2.5
          : state === 'listening'
          ? 9 + audioLevel * 4
          : state === 'alert'
          ? 10 + Math.sin(t * 5) * 3
          : 8.5 + Math.sin(t * 1.5) * 1;

      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(center, center, coreSize, 0, Math.PI * 2);
      ctx.shadowColor = `rgba(${coreR}, ${coreG}, ${coreB}, 1.0)`;
      ctx.shadowBlur = state === 'alert' ? 24 : 16;
      ctx.fill();
      ctx.shadowBlur = 0; // Reset shadow

      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animFrameRef.current);
  }, [state, audioLevel, size, currentSeatName]);

  return (
    <div
      onClick={onClick}
      className={`relative flex flex-col items-center justify-center select-none ${className}`}
    >
      {/* Canvas Cosmic Core */}
      <div className="relative flex items-center justify-center cursor-pointer group">
        <canvas
          ref={canvasRef}
          style={{ width: `${size}px`, height: `${size}px` }}
          className="drop-shadow-[0_0_24px_rgba(139,44,255,0.45)] transition-transform duration-300 group-hover:scale-105"
        />

        {/* State Floating Pill */}
        <div className="absolute bottom-2 px-3 py-0.5 rounded-full text-[10px] font-mono tracking-widest uppercase bg-black/75 border border-white/10 text-zinc-300 backdrop-blur-md shadow-lg flex items-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              state === 'listening'
                ? 'bg-cyan-400 animate-ping'
                : state === 'thinking'
                ? 'bg-purple-400 animate-pulse'
                : state === 'alert'
                ? 'bg-amber-400 animate-bounce'
                : 'bg-emerald-400'
            }`}
          />
          <span>{state}</span>
        </div>
      </div>

      {/* Council Seat Dynamic Badge (Wired to WebSocket) */}
      <div
        className={`mt-2 px-3 py-1 rounded-xl border ${seatConfig.border} ${seatConfig.bg} backdrop-blur-md shadow-[0_4px_16px_rgba(0,0,0,0.5)] flex items-center gap-2 transition-all duration-300 hover:scale-[1.02]`}
        title={seatConfig.title}
      >
        <span className="text-xs">{seatConfig.icon}</span>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className={`text-xs font-semibold tracking-wide ${seatConfig.color}`}>
              {seatConfig.name}
            </span>
            <span className={`w-1.5 h-1.5 rounded-full ${seatConfig.dot} animate-pulse`} />
          </div>
          {typeof councilSeat === 'object' && councilSeat?.model && (
            <span className="text-[9px] font-mono text-zinc-400">
              {councilSeat.model} {councilSeat.vramProfile ? `• ${councilSeat.vramProfile}` : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default WorkspaceAvatar;
