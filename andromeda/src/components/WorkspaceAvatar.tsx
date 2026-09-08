import React, { useEffect, useRef } from 'react';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'alert';

interface WorkspaceAvatarProps {
  state: AvatarState;
  audioLevel?: number; // 0.0 to 1.0 (from Web Audio API)
  size?: number;
}

export const WorkspaceAvatar: React.FC<WorkspaceAvatarProps> = ({
  state = 'idle',
  audioLevel = 0,
  size = 180,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number>(0);
  const angleRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const center = size / 2;
    const particles = Array.from({ length: 24 }, (_, i) => ({
      angle: (i / 24) * Math.PI * 2,
      dist: 40 + (i % 3) * 12,
      speed: 0.015 + (i % 4) * 0.005,
      size: 1.5 + (i % 2) * 1.2,
    }));

    const render = () => {
      ctx.clearRect(0, 0, size, size);
      angleRef.current += 0.02;
      const t = angleRef.current;

      // Color scheme selector based on agent state
      let coreColor = 'rgba(139, 44, 255, '; // Violet (Default / Idle)
      let glowColor = 'rgba(255, 42, 141, '; // Hot Pink / Magenta

      if (state === 'listening') {
        coreColor = 'rgba(0, 240, 255, '; // Electric Cyan
        glowColor = 'rgba(0, 255, 102, '; // Matrix Green
      } else if (state === 'thinking') {
        coreColor = 'rgba(168, 85, 247, '; // Cosmic Lavender
        glowColor = 'rgba(99, 102, 241, '; // Deep Indigo
      } else if (state === 'alert') {
        coreColor = 'rgba(245, 158, 11, '; // Amber Alert
        glowColor = 'rgba(239, 68, 68, '; // Crimson Flare
      }

      // 1. Outer Glow Aura
      const dynamicRadius =
        state === 'listening'
          ? 32 + audioLevel * 24
          : state === 'thinking'
          ? 28 + Math.sin(t * 4) * 4
          : 30 + Math.sin(t * 1.5) * 3;

      const radial = ctx.createRadialGradient(center, center, 4, center, center, dynamicRadius * 1.8);
      radial.addColorStop(0, `${coreColor}0.9)`);
      radial.addColorStop(0.5, `${glowColor}0.35)`);
      radial.addColorStop(1, 'rgba(10, 7, 20, 0)');
      ctx.fillStyle = radial;
      ctx.beginPath();
      ctx.arc(center, center, dynamicRadius * 1.8, 0, Math.PI * 2);
      ctx.fill();

      // 2. Swirling / Orbiting Micro-Particles
      particles.forEach((p, idx) => {
        p.angle += state === 'thinking' ? p.speed * 4 : p.speed;
        const currentDist =
          state === 'thinking'
            ? p.dist * (0.6 + 0.4 * Math.sin(t * 2 + idx)) // Inward swirl
            : state === 'listening'
            ? p.dist + audioLevel * 18
            : p.dist + Math.sin(t + idx) * 3;

        const x = center + Math.cos(p.angle) * currentDist;
        const y = center + Math.sin(p.angle) * currentDist;

        ctx.fillStyle = `${glowColor}0.85)`;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      // 3. Central Cosmic Core
      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(center, center, state === 'thinking' ? 7 + Math.sin(t * 6) * 2 : 8, 0, Math.PI * 2);
      ctx.shadowColor = `${coreColor}1.0)`;
      ctx.shadowBlur = 15;
      ctx.fill();
      ctx.shadowBlur = 0; // reset

      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animFrameRef.current);
  }, [state, audioLevel, size]);

  return (
    <div className="relative flex items-center justify-center">
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        className="pointer-events-none drop-shadow-[0_0_20px_rgba(139,44,255,0.4)]"
      />
      <div className="absolute bottom-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono tracking-widest uppercase bg-black/60 border border-white/10 text-zinc-300 backdrop-blur-md">
        {state}
      </div>
    </div>
  );
};
