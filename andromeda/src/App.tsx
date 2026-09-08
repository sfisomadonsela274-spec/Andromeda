import React, { useState, useEffect } from 'react';
import { WorkspaceAvatar, AvatarState } from './components/WorkspaceAvatar';
import { MediaDeck } from './components/MediaDeck';

export const App: React.FC = () => {
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [activeMediaEmbed, setActiveMediaEmbed] = useState<string | null>(null);

  useEffect(() => {
    // Connect to Andromeda Core WebSocket via Caddy port 80 or local port
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/core`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'status') {
          if (payload.message && (payload.message.includes('Thinking') || payload.message.includes('Synthesizing'))) {
            setAvatarState('thinking');
          }
        } else if (payload.type === 'response') {
          setAvatarState('idle');
          // Detect media actions triggered by chat intents
          let msgObj = null;
          try {
            msgObj = typeof payload.message === 'string' ? JSON.parse(payload.message) : payload.message;
          } catch {
            msgObj = payload;
          }
          if (msgObj && (msgObj.action === 'app_control' && msgObj.category === 'music' || msgObj.action === 'youtube')) {
            setActiveMediaEmbed(msgObj.query || null);
            setAvatarState('alert');
            setTimeout(() => setAvatarState('idle'), 2500);
          }
        }
      } catch {
        // Raw text frame
      }
    };

    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-[#06040A] text-zinc-100 flex flex-col items-center justify-between p-6">
      {/* Top Header: Avatar & Media Deck */}
      <header className="w-full max-w-4xl flex flex-col sm:flex-row items-center justify-between gap-6">
        <WorkspaceAvatar state={avatarState} />
        <MediaDeck embeddedYoutubeQuery={activeMediaEmbed} />
      </header>

      {/* Center Chat Viewport */}
      <main className="w-full max-w-2xl flex-1 flex flex-col justify-end my-6">
        {/* Messages stream rendered here */}
      </main>
    </div>
  );
};

export default App;
