import React, { useState, useEffect } from 'react';

export interface AppLauncherModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface AppInfo {
  id: string;
  name: string;
  category: string;
  icon: string;
  package_id: string;
  flatpak: boolean;
}

export const AppLauncherModal: React.FC<AppLauncherModalProps> = ({ isOpen, onClose }) => {
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [loadingApp, setLoadingApp] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const fetchApps = async () => {
      try {
        const res = await fetch('/api/apps');
        if (res.ok) {
          const data = await res.json();
          setApps(data.apps || []);
        }
      } catch (err) {
        console.warn('Failed to fetch apps:', err);
      }
    };

    fetchApps();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAppAction = async (appId: string, action: 'launch' | 'install') => {
    setLoadingApp(appId);
    setStatusMsg(null);

    try {
      const res = await fetch('/api/apps/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          app: appId,
          action: action,
        }),
      });

      const data = await res.json();
      setStatusMsg(data.message || `Action ${action} dispatched for ${appId}`);
    } catch (err: any) {
      setStatusMsg(`Error: ${err.message}`);
    } finally {
      setLoadingApp(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-[#0E0B1A]/95 border border-white/10 rounded-3xl shadow-[0_24px_70px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 text-lg shadow-[0_0_15px_rgba(6,182,212,0.25)]">
              🖥️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Desktop Application Hub
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Flatpak & Native Desktop
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Launch installed host applications or stage Flathub installations
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

        {/* Status Notification */}
        {statusMsg && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200 flex items-center gap-2">
            <span>ℹ️</span>
            <span>{statusMsg}</span>
          </div>
        )}

        {/* Grid of Apps */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {apps.map((a) => (
            <div
              key={a.id}
              className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-white/15 transition-all flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white tracking-wide">{a.name}</span>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-black/40 text-zinc-400">
                    {a.category}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-zinc-500 truncate mt-0.5">
                  {a.package_id}
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => handleAppAction(a.id, 'launch')}
                  disabled={loadingApp === a.id}
                  className="px-2.5 py-1 rounded-lg bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/40 text-cyan-200 text-xs font-medium transition-colors"
                  title="Launch Desktop App"
                >
                  Launch
                </button>
                <button
                  onClick={() => handleAppAction(a.id, 'install')}
                  disabled={loadingApp === a.id}
                  className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-400 hover:text-white text-[10px] font-mono transition-colors"
                  title="Stage Flatpak Install"
                >
                  Install
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AppLauncherModal;
