import React, { useState } from 'react';
import { useMediaHub } from '../hooks/useMediaHub';

interface MediaDeckProps {
  embeddedYoutubeQuery?: string | null;
}

export const MediaDeck: React.FC<MediaDeckProps> = ({ embeddedYoutubeQuery }) => {
  const { status, togglePlay, nextTrack, prevTrack, setVolume } = useMediaHub();
  const [localVol, setLocalVol] = useState<number>(status.volume ?? 0.7);
  const [showEmbed, setShowEmbed] = useState<boolean>(Boolean(embeddedYoutubeQuery));

  const isPlaying = status.playback_status === 'Playing';
  const displayTitle = status.title || (embeddedYoutubeQuery ? `YouTube Stream: ${embeddedYoutubeQuery}` : 'No Track Active');
  const displayArtist = status.artist || (embeddedYoutubeQuery ? 'Automated Stream' : 'Desktop Media Idle');

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setLocalVol(val);
    setVolume(val);
  };

  return (
    <div className="w-full max-w-md bg-[#0A0714]/85 border border-white/10 rounded-2xl p-4 shadow-[0_8px_32px_rgba(0,0,0,0.6)] backdrop-blur-xl transition-all duration-300 hover:border-purple-500/30">
      {/* Top Header: Active Player & Mode Switcher */}
      <div className="flex items-center justify-between pb-3 border-b border-white/5">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${status.active ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'}`} />
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
            {status.player ? `${status.player} (Host D-Bus)` : 'MPRIS Controller'}
          </span>
        </div>
        {embeddedYoutubeQuery && (
          <button
            onClick={() => setShowEmbed(!showEmbed)}
            className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/60 border border-purple-500/40 text-purple-300 hover:bg-purple-900/60 transition-colors"
          >
            {showEmbed ? 'Hide In-Stream' : 'Show In-Stream'}
          </button>
        )}
      </div>

      {/* Embedded In-Stream Player (if active) */}
      {showEmbed && embeddedYoutubeQuery && (
        <div className="mt-3 overflow-hidden rounded-xl aspect-video border border-white/10 shadow-inner">
          <iframe
            className="w-full h-full"
            src={`https://www.youtube-nocookie.com/embed?listType=search&list=${encodeURIComponent(
              embeddedYoutubeQuery
            )}&autoplay=1`}
            title="Andromeda Media Stream"
            allow="autoplay; encrypted-media"
            allowFullScreen
          />
        </div>
      )}

      {/* Track Details */}
      <div className="py-3">
        <div className="text-sm font-semibold text-white truncate tracking-wide">{displayTitle}</div>
        <div className="text-xs text-zinc-400 truncate mt-0.5">{displayArtist}</div>
      </div>

      {/* Playback Controls & Scrubber */}
      <div className="flex items-center justify-between mt-1 pt-2 border-t border-white/5">
        <div className="flex items-center gap-2">
          {/* Previous Track */}
          <button
            onClick={prevTrack}
            disabled={!status.active}
            className="p-2 text-zinc-400 hover:text-white disabled:opacity-30 transition-colors"
            title="Previous"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>

          {/* Play/Pause Toggle */}
          <button
            onClick={togglePlay}
            disabled={!status.active && !embeddedYoutubeQuery}
            className="p-2.5 rounded-full bg-gradient-to-tr from-purple-600 to-pink-500 text-white shadow-lg shadow-purple-500/20 active:scale-95 disabled:opacity-40 transition-transform"
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

          {/* Next Track */}
          <button
            onClick={nextTrack}
            disabled={!status.active}
            className="p-2 text-zinc-400 hover:text-white disabled:opacity-30 transition-colors"
            title="Next"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>
        </div>

        {/* Volume Slider Slider */}
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
            disabled={!status.active}
            className="w-20 h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-purple-500 disabled:opacity-30"
          />
        </div>
      </div>
    </div>
  );
};
