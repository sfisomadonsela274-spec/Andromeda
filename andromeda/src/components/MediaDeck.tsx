import React, { useState } from 'react';
import { useMediaHub } from '../hooks/useMediaHub';

export interface MediaDeckProps {
  embeddedYoutubeQuery?: string | null;
  className?: string;
}

const PRESET_STREAMS = [
  { label: 'Lofi Beats', query: 'lofi hip hop radio beats to relax study to' },
  { label: 'Synthwave', query: 'synthwave chillwave 2026 mix' },
  { label: 'Deep Focus', query: 'deep focus ambient binaural beats' },
  { label: 'Cyberpunk', query: 'cyberpunk dark ambient electronic music' },
];

export const MediaDeck: React.FC<MediaDeckProps> = ({
  embeddedYoutubeQuery = null,
  className = '',
}) => {
  const { status, togglePlay, nextTrack, prevTrack, setVolume } = useMediaHub();
  const [localVol, setLocalVol] = useState<number>(status.volume ?? 0.75);
  const [showEmbed, setShowEmbed] = useState<boolean>(Boolean(embeddedYoutubeQuery));
  const [customQuery, setCustomQuery] = useState<string>('');
  const [activeQuery, setActiveQuery] = useState<string | null>(embeddedYoutubeQuery);

  // Sync if prop changes
  React.useEffect(() => {
    if (embeddedYoutubeQuery) {
      setActiveQuery(embeddedYoutubeQuery);
      setShowEmbed(true);
    }
  }, [embeddedYoutubeQuery]);

  const isPlaying = status.playback_status === 'Playing';
  const isMprisActive = status.active;

  const displayTitle = isMprisActive
    ? status.title || 'Unknown Track'
    : activeQuery
    ? `YouTube: ${activeQuery}`
    : 'No Track Active';

  const displayArtist = isMprisActive
    ? status.artist || (status.player ? `${status.player} Audio` : 'Desktop Player')
    : activeQuery
    ? 'In-Stream Streamer'
    : 'MPRIS Desktop Idle';

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setLocalVol(val);
    setVolume(val);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customQuery.trim()) return;
    setActiveQuery(customQuery.trim());
    setShowEmbed(true);
  };

  return (
    <div
      className={`w-full max-w-md bg-[#0A0714]/85 border border-white/10 rounded-3xl p-5 shadow-[0_12px_40px_rgba(0,0,0,0.65)] backdrop-blur-2xl transition-all duration-300 hover:border-purple-500/30 ${className}`}
    >
      {/* Hardware Deck Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isMprisActive
                ? 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse'
                : activeQuery
                ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24] animate-pulse'
                : 'bg-zinc-600'
            }`}
          />
          <div className="flex flex-col">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-300 font-semibold">
              {isMprisActive
                ? `${status.player || 'MPRIS'} (Host D-Bus)`
                : activeQuery
                ? 'YouTube In-Stream Deck'
                : 'Media Controller (Idle)'}
            </span>
            <span className="text-[9px] font-mono text-zinc-500">
              {isMprisActive ? 'LINUX DESKTOP BRIDGE' : 'FALLBACK AUDIO GRID'}
            </span>
          </div>
        </div>

        {/* In-Stream YouTube Toggle */}
        <button
          onClick={() => setShowEmbed(!showEmbed)}
          className={`text-[10px] font-mono px-2.5 py-1 rounded-lg border transition-all ${
            showEmbed
              ? 'bg-purple-900/60 border-purple-500/50 text-purple-200 shadow-[0_0_10px_rgba(168,85,247,0.3)]'
              : 'bg-white/5 border-white/10 text-zinc-400 hover:text-zinc-200'
          }`}
          title="Toggle YouTube In-Stream Player"
        >
          {showEmbed ? '▼ Hide Stream' : '▲ YouTube In-Stream'}
        </button>
      </div>

      {/* Fallback YouTube In-Stream Section */}
      {showEmbed && (
        <div className="mt-3.5 space-y-2.5">
          {/* Preset Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {PRESET_STREAMS.map((p) => (
              <button
                key={p.label}
                onClick={() => {
                  setActiveQuery(p.query);
                  setShowEmbed(true);
                }}
                className={`text-[9px] font-mono px-2 py-0.5 rounded-md border whitespace-nowrap transition-colors ${
                  activeQuery === p.query
                    ? 'bg-purple-600/40 border-purple-400/60 text-purple-200'
                    : 'bg-white/5 border-white/5 text-zinc-400 hover:text-white'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Search Bar for YouTube */}
          <form onSubmit={handleSearchSubmit} className="flex gap-1.5">
            <input
              type="text"
              placeholder="Search YouTube in-stream..."
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-purple-500/50"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-xl bg-purple-600/40 border border-purple-500/30 text-purple-300 text-xs hover:bg-purple-600/60 font-medium transition-colors"
            >
              Stream
            </button>
          </form>

          {/* Embedded Player Iframe */}
          {activeQuery && (
            <div className="overflow-hidden rounded-2xl aspect-video border border-white/10 shadow-inner bg-black">
              <iframe
                className="w-full h-full"
                src={`https://www.youtube-nocookie.com/embed?listType=search&list=${encodeURIComponent(
                  activeQuery
                )}&autoplay=1`}
                title="Andromeda Stream Player"
                allow="autoplay; encrypted-media"
                allowFullScreen
              />
            </div>
          )}
        </div>
      )}

      {/* Track Details & Visualizer Bars */}
      <div className="py-3 flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-white truncate tracking-wide">
            {displayTitle}
          </div>
          <div className="text-xs text-zinc-400 truncate mt-0.5">
            {displayArtist} {status.album ? `• ${status.album}` : ''}
          </div>
        </div>

        {/* Animated Equalizer Wave Bars */}
        {(isPlaying || (showEmbed && activeQuery)) && (
          <div className="flex items-end gap-1 h-5 px-2">
            <span className="w-1 bg-purple-500 rounded-full animate-[pulse_0.7s_infinite] h-3" />
            <span className="w-1 bg-pink-500 rounded-full animate-[pulse_0.4s_infinite] h-5" />
            <span className="w-1 bg-blue-500 rounded-full animate-[pulse_0.9s_infinite] h-2" />
            <span className="w-1 bg-cyan-400 rounded-full animate-[pulse_0.6s_infinite] h-4" />
          </div>
        )}
      </div>

      {/* Transport Controls & Volume Slider */}
      <div className="flex items-center justify-between pt-2 border-t border-white/5">
        {/* Playback Controls */}
        <div className="flex items-center gap-2">
          {/* Prev */}
          <button
            onClick={prevTrack}
            disabled={!isMprisActive}
            className="p-2 text-zinc-400 hover:text-white disabled:opacity-30 disabled:hover:text-zinc-400 transition-colors"
            title="Previous Track"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>

          {/* Play/Pause */}
          <button
            onClick={togglePlay}
            disabled={!isMprisActive && !activeQuery}
            className="p-2.5 rounded-full bg-gradient-to-tr from-purple-600 via-indigo-600 to-pink-500 text-white shadow-lg shadow-purple-500/25 active:scale-95 disabled:opacity-40 transition-transform"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          {/* Next */}
          <button
            onClick={nextTrack}
            disabled={!isMprisActive}
            className="p-2 text-zinc-400 hover:text-white disabled:opacity-30 disabled:hover:text-zinc-400 transition-colors"
            title="Next Track"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>
        </div>

        {/* Volume Slider with Level Percentage */}
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-zinc-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
          </svg>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={localVol}
            onChange={handleVolumeChange}
            disabled={!isMprisActive}
            className="w-20 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500 disabled:opacity-30"
          />
          <span className="text-[10px] font-mono text-zinc-400 w-7 text-right">
            {Math.round(localVol * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
};

export default MediaDeck;
