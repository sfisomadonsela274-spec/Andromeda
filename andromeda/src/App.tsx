import React, { useState, useEffect, useRef } from 'react';
import { WorkspaceAvatar, AvatarState, CouncilBadgeInfo } from './components/WorkspaceAvatar';
import { MediaDeck } from './components/MediaDeck';
import { PixelSpicingModal } from './components/PixelSpicingModal';
import { MacroRunnerModal } from './components/MacroRunnerModal';
import { AppLauncherModal } from './components/AppLauncherModal';

export const App: React.FC = () => {
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [councilSeat, setCouncilSeat] = useState<CouncilBadgeInfo>({
    seat: 'The Scribe',
    model: 'qwen2.5-coder:1.5b',
    vramProfile: 'FP8 (Always Warm)',
    reason: 'Standard fast intent & tool calling',
  });
  const [activeMediaEmbed, setActiveMediaEmbed] = useState<string | null>(null);
  const [isPixelSpicerOpen, setIsPixelSpicerOpen] = useState<boolean>(false);
  const [isMacroRunnerOpen, setIsMacroRunnerOpen] = useState<boolean>(false);
  const [isAppLauncherOpen, setIsAppLauncherOpen] = useState<boolean>(false);
  const [sweepNotice, setSweepNotice] = useState<string | null>(null);
  const [promptInput, setPromptInput] = useState<string>('');
  const [messages, setMessages] = useState<
    Array<{ role: 'user' | 'agent' | 'system'; text: string; seat?: string }>
  >([
    {
      role: 'system',
      text: '🌌 Andromeda Cosmic Workspace online. Council of AIs active across Ollama.',
    },
  ]);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [simulatedAudio, setSimulatedAudio] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);

  // WebSocket Connection to /ws/core
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsUrl = `${protocol}//${host}/ws/core`;
    let ws: WebSocket;
    let shouldReconnect = true;

    const connectWs = () => {
      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onclose = () => {
          setWsConnected(false);
          if (shouldReconnect) {
            setTimeout(connectWs, 3000);
          }
        };

        ws.onerror = () => {
          setWsConnected(false);
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);

            // 1. Real-time Council Status Packet
            if (payload.type === 'council_status') {
              setCouncilSeat({
                seat: payload.presiding_seat || 'The Scribe',
                model: payload.model || '',
                vramProfile: payload.vram_profile || '',
                reason: payload.reason || '',
              });
              setAvatarState('thinking');
              setMessages((prev) => [
                ...prev,
                {
                  role: 'system',
                  text: `⚖️ [Council of AIs]: ${payload.presiding_seat} presiding with ${payload.model} (${payload.vram_profile || 'Normal'})`,
                  seat: payload.presiding_seat,
                },
              ]);
            }

            // 2. Intermediate Status Stream
            else if (payload.type === 'status') {
              const msg = payload.message || '';
              if (
                msg.includes('Thinking') ||
                msg.includes('Synthesizing') ||
                msg.includes('deliberat')
              ) {
                setAvatarState('thinking');
              } else if (msg.includes('Listening') || msg.includes('Audio')) {
                setAvatarState('listening');
              }
            }

            // 3. Final Agent Response Packet
            else if (payload.type === 'response') {
              setAvatarState('idle');
              let content = '';

              let msgObj = null;
              try {
                msgObj =
                  typeof payload.message === 'string'
                    ? JSON.parse(payload.message)
                    : payload.message;
              } catch {
                content =
                  typeof payload.message === 'string'
                    ? payload.message
                    : JSON.stringify(payload.message);
              }

              // Detect Media Intent actions
              if (msgObj) {
                if (
                  (msgObj.action === 'app_control' && msgObj.category === 'music') ||
                  msgObj.action === 'youtube'
                ) {
                  if (msgObj.query) {
                    setActiveMediaEmbed(msgObj.query);
                    setAvatarState('alert');
                    setTimeout(() => setAvatarState('idle'), 2500);
                  }
                }
                content = msgObj.reply || msgObj.output || JSON.stringify(msgObj);
              }

              if (content) {
                setMessages((prev) => [
                  ...prev,
                  { role: 'agent', text: content, seat: councilSeat.seat },
                ]);
              }
            }

            // 4. Error packet
            else if (payload.type === 'error') {
              setAvatarState('alert');
              setMessages((prev) => [
                ...prev,
                { role: 'system', text: `⚠️ ${payload.message || 'System fault'}` },
              ]);
              setTimeout(() => setAvatarState('idle'), 2500);
            }
          } catch {
            if (typeof event.data === 'string' && event.data.trim()) {
              setMessages((prev) => [...prev, { role: 'agent', text: event.data }]);
              setAvatarState('idle');
            }
          }
        };
      } catch (err) {
        console.warn('WS Init failed:', err);
      }
    };

    connectWs();

    return () => {
      shouldReconnect = false;
      if (wsRef.current) wsRef.current.close();
    };
  }, [councilSeat.seat]);

  // Audio simulation oscillation when in listening state
  useEffect(() => {
    let animId: number;
    let t = 0;
    const updateAudio = () => {
      if (avatarState === 'listening') {
        t += 0.09;
        setSimulatedAudio(Math.abs(Math.sin(t) * 0.75 + Math.cos(t * 1.6) * 0.25));
      } else {
        setSimulatedAudio(0);
      }
      animId = requestAnimationFrame(updateAudio);
    };
    animId = requestAnimationFrame(updateAudio);
    return () => cancelAnimationFrame(animId);
  }, [avatarState]);

  const sendPrompt = (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = promptInput.trim();
    if (!prompt) return;

    setMessages((prev) => [...prev, { role: 'user', text: prompt }]);
    setPromptInput('');
    setAvatarState('thinking');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          prompt: prompt,
          session_id: 'cosmic_session',
        })
      );
    } else {
      setTimeout(() => {
        setAvatarState('idle');
        setMessages((prev) => [
          ...prev,
          {
            role: 'agent',
            text: `[Local Simulation]: Received intent: "${prompt}". Backend /ws/core active when containerized runtime is routed.`,
            seat: councilSeat.seat,
          },
        ]);
      }, 900);
    }
  };

  const executeVramSweep = async () => {
    try {
      const res = await fetch('/api/memory/sweep', { method: 'POST' });
      const data = await res.json();
      setSweepNotice(data.message || 'VRAM & heavy models swept');
      setTimeout(() => setSweepNotice(null), 3500);
    } catch {
      setSweepNotice('Memory sweep dispatched to Ollama engine');
      setTimeout(() => setSweepNotice(null), 2500);
    }
  };

  const switchToClassicWorkspace = () => {
    if (typeof (window as any).navigateToWorkspace === 'function') {
      (window as any).hideReactCosmicDeck?.();
      (window as any).navigateToWorkspace();
    } else {
      window.location.hash = '#/workspace';
    }
  };

  return (
    <div className="min-h-screen bg-[#07050E] text-zinc-100 flex flex-col items-center justify-between p-4 sm:p-6 selection:bg-purple-900 selection:text-white font-sans">
      
      {/* Top Navbar */}
      <header className="w-full max-w-6xl flex flex-wrap items-center justify-between gap-3 py-3 px-5 rounded-2xl bg-white/[0.02] border border-white/10 backdrop-blur-xl mb-6 shadow-[0_4px_24px_rgba(0,0,0,0.5)]">
        
        {/* Brand & Connection Badge */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-300 font-bold text-base shadow-[0_0_15px_rgba(168,85,247,0.35)]">
            🌌
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-white">Andromeda</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-950/60 border border-purple-500/30 text-purple-300">
                React Cosmic Deck
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-400">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  wsConnected ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-amber-400 animate-pulse'
                }`}
              />
              <span>{wsConnected ? 'WS Core Synced' : 'Connecting to /ws/core'}</span>
              <span className="text-zinc-600">•</span>
              <span className="text-purple-400">MPRIS Active</span>
            </div>
          </div>
        </div>

        {/* Action Controls & Modal Triggers */}
        <div className="flex flex-wrap items-center gap-2">
          
          {/* Pixel Spicer Trigger */}
          <button
            onClick={() => setIsPixelSpicerOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-600/30 via-orange-600/30 to-amber-500/20 border border-amber-500/40 text-amber-200 text-xs font-medium hover:brightness-110 active:scale-95 transition-all flex items-center gap-1.5 shadow-[0_0_15px_rgba(245,158,11,0.2)]"
            title="Open EXIF-aware Pixel Spicer modal"
          >
            <span>✨</span>
            <span>Pixel-Spicer (4x)</span>
          </button>

          {/* Workflow Macro Trigger */}
          <button
            onClick={() => setIsMacroRunnerOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-500/40 text-indigo-200 text-xs font-medium active:scale-95 transition-all flex items-center gap-1.5"
            title="Open Automation Macro Runner"
          >
            <span>⚙️</span>
            <span>Macros</span>
          </button>

          {/* Desktop Apps Trigger */}
          <button
            onClick={() => setIsAppLauncherOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-500/40 text-cyan-200 text-xs font-medium active:scale-95 transition-all flex items-center gap-1.5"
            title="Open Desktop Application Hub"
          >
            <span>🖥️</span>
            <span>Apps</span>
          </button>

          {/* VRAM Sweep Button */}
          <button
            onClick={executeVramSweep}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 hover:text-rose-300 text-xs transition-colors"
            title="Sweep VRAM & Evict Heavy Models"
          >
            🧹
          </button>

          {/* Switch View Trigger */}
          <button
            onClick={switchToClassicWorkspace}
            className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 hover:text-white text-xs font-medium transition-colors flex items-center gap-1.5"
            title="Switch to Neumorphic Soft UI Workspace"
          >
            <span>📐</span>
            <span className="hidden sm:inline">Neumorphic</span>
          </button>
        </div>
      </header>

      {/* Sweep Notification Toast */}
      {sweepNotice && (
        <div className="w-full max-w-md p-3 rounded-2xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-200 text-xs flex items-center justify-between mb-4 shadow-lg animate-fadeIn">
          <div className="flex items-center gap-2">
            <span>🧹</span>
            <span>{sweepNotice}</span>
          </div>
          <button onClick={() => setSweepNotice(null)} className="text-emerald-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Main Grid: Avatar Stage & MediaDeck */}
      <main className="w-full max-w-6xl flex-1 flex flex-col items-center justify-start space-y-6">
        
        <div className="w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
          
          {/* Avatar Cosmic Core Box */}
          <div className="flex flex-col items-center justify-between p-6 rounded-3xl bg-[#0A0816]/75 border border-white/10 backdrop-blur-2xl shadow-[0_12px_40px_rgba(0,0,0,0.6)] min-h-[420px]">
            <div className="w-full flex items-center justify-between pb-2 border-b border-white/5">
              <div className="text-[11px] font-mono tracking-wider text-zinc-400 uppercase flex items-center gap-1.5">
                <span>Cosmic Core Singularity</span>
              </div>
              <span className="text-[10px] font-mono text-purple-400 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-500/20">
                HTML5 Canvas 2D
              </span>
            </div>

            {/* Canvas Avatar Component with Wired Council Badge */}
            <div className="my-auto py-3">
              <WorkspaceAvatar
                state={avatarState}
                councilSeat={councilSeat}
                audioLevel={simulatedAudio}
                size={190}
              />
            </div>

            {/* Quick State Simulation Switchers */}
            <div className="pt-3 border-t border-white/5 w-full flex flex-col items-center space-y-2">
              <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                Avatar State Engine
              </div>
              <div className="flex flex-wrap gap-1.5 justify-center">
                {(['idle', 'listening', 'thinking', 'alert'] as AvatarState[]).map((st) => (
                  <button
                    key={st}
                    onClick={() => setAvatarState(st)}
                    className={`px-3 py-1 rounded-lg text-[10px] font-mono uppercase tracking-wider transition-all ${
                      avatarState === st
                        ? 'bg-purple-600 text-white shadow-[0_0_12px_rgba(168,85,247,0.5)] font-semibold'
                        : 'bg-white/5 border border-white/5 text-zinc-400 hover:text-white'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>

              {/* Council Seat Switcher */}
              <div className="flex flex-wrap gap-1.5 justify-center pt-1">
                {[
                  { name: 'The Scribe', model: 'qwen2.5-coder:1.5b' },
                  { name: 'The Architect', model: 'qwen2.5-coder:7b' },
                  { name: 'The Logician', model: 'llama3.2' },
                  { name: 'The Sentinel', model: 'moondream' },
                ].map((s) => (
                  <button
                    key={s.name}
                    onClick={() =>
                      setCouncilSeat({
                        seat: s.name,
                        model: s.model,
                        vramProfile: 'Presiding Seat',
                        reason: 'Manual council delegate',
                      })
                    }
                    className={`px-2 py-0.5 rounded-md text-[9px] font-mono transition-all ${
                      councilSeat.seat === s.name
                        ? 'bg-zinc-200 text-black font-semibold'
                        : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Media Deck Hardware Card */}
          <div className="flex flex-col items-center justify-center">
            <MediaDeck embeddedYoutubeQuery={activeMediaEmbed} />
          </div>
        </div>

        {/* Live Council Deliberation Feed */}
        <div className="w-full max-w-4xl rounded-3xl bg-[#090714]/80 border border-white/10 p-5 shadow-2xl flex flex-col space-y-3 backdrop-blur-xl">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-zinc-200">
                Council Deliberation Stream
              </span>
              <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-purple-950/60 text-purple-300 border border-purple-500/30">
                {councilSeat.seat} ({councilSeat.model || 'Auto'})
              </span>
            </div>
            <button
              onClick={() => setMessages([])}
              className="text-[10px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear Feed
            </button>
          </div>

          {/* Message Stream */}
          <div className="h-44 overflow-y-auto space-y-2 pr-1 text-xs">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`p-3 rounded-2xl transition-all ${
                  m.role === 'user'
                    ? 'bg-purple-900/30 border border-purple-500/30 text-purple-100 ml-auto max-w-[85%]'
                    : m.role === 'system'
                    ? 'bg-black/40 border border-white/5 text-zinc-400 font-mono text-[11px]'
                    : 'bg-white/5 border border-white/10 text-zinc-200 mr-auto max-w-[90%]'
                }`}
              >
                {m.seat && (
                  <div className="text-[9px] font-mono uppercase tracking-widest text-purple-400 font-semibold mb-1">
                    {m.seat}
                  </div>
                )}
                <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
              </div>
            ))}
          </div>

          {/* Prompt Dispatch Bar */}
          <form onSubmit={sendPrompt} className="flex gap-2 pt-2 border-t border-white/5">
            <input
              type="text"
              placeholder="Ask the Council or enter action (e.g. '/music lofi chill', '/install vscode', '/macro deep_work')..."
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              className="flex-1 bg-black/50 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500/50"
            />
            <button
              type="submit"
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/30 active:scale-95 transition-all"
            >
              Dispatch
            </button>
          </form>
        </div>
      </main>

      {/* Modals */}
      <PixelSpicingModal
        isOpen={isPixelSpicerOpen}
        onClose={() => setIsPixelSpicerOpen(false)}
      />

      <MacroRunnerModal
        isOpen={isMacroRunnerOpen}
        onClose={() => setIsMacroRunnerOpen(false)}
      />

      <AppLauncherModal
        isOpen={isAppLauncherOpen}
        onClose={() => setIsAppLauncherOpen(false)}
      />
    </div>
  );
};

export default App;
