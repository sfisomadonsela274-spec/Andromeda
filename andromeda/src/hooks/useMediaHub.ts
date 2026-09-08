import { useState, useEffect, useCallback } from 'react';

export interface MediaStatus {
  active: boolean;
  playback_status: 'Playing' | 'Paused' | 'Stopped' | 'Unknown';
  player?: string;
  title?: string;
  artist?: string;
  album?: string;
  volume?: number;
  available_players?: string[];
  message?: string;
}

export const useMediaHub = (pollIntervalMs: number = 3000) => {
  const [status, setStatus] = useState<MediaStatus>({
    active: false,
    playback_status: 'Stopped',
  });
  const [loading, setLoading] = useState<boolean>(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/media/status');
      if (res.ok) {
        const data: MediaStatus = await res.json();
        setStatus(data);
      }
    } catch {
      // Backend unreachable or host offline
    }
  }, []);

  const sendAction = async (action: string, value?: number, player?: string) => {
    setLoading(true);
    // Optimistic UI updates
    if (action === 'play_pause') {
      setStatus((prev) => ({
        ...prev,
        playback_status: prev.playback_status === 'Playing' ? 'Paused' : 'Playing',
      }));
    } else if (action === 'set_volume' && value !== undefined) {
      setStatus((prev) => ({ ...prev, volume: value }));
    }

    try {
      await fetch('/api/media/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, value, player }),
      });
      await fetchStatus();
    } catch (err) {
      console.error('Failed to dispatch media command:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchStatus, pollIntervalMs]);

  return {
    status,
    loading,
    refresh: fetchStatus,
    togglePlay: () => sendAction('play_pause'),
    nextTrack: () => sendAction('next'),
    prevTrack: () => sendAction('previous'),
    setVolume: (val: number) => sendAction('set_volume', val),
  };
};
