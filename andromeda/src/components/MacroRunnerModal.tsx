import React, { useState, useEffect } from 'react';

export interface MacroRunnerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface MacroStep {
  name: string;
  type: string;
  command?: string;
  action?: string;
  app?: string;
  category?: string;
}

interface MacroItem {
  id: string;
  name: string;
  description: string;
  steps_count: number;
  steps: MacroStep[];
}

export const MacroRunnerModal: React.FC<MacroRunnerModalProps> = ({ isOpen, onClose }) => {
  const [macros, setMacros] = useState<MacroItem[]>([]);
  const [selectedMacro, setSelectedMacro] = useState<MacroItem | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const fetchMacros = async () => {
      try {
        const res = await fetch('/api/macros');
        if (res.ok) {
          const data = await res.json();
          setMacros(data.macros || []);
          if (data.macros && data.macros.length > 0 && !selectedMacro) {
            setSelectedMacro(data.macros[0]);
          }
        }
      } catch (err: any) {
        console.warn('Failed to fetch macros:', err);
      }
    };

    fetchMacros();
  }, [isOpen]);

  if (!isOpen) return null;

  const runSelectedMacro = async () => {
    if (!selectedMacro) return;
    setRunning(true);
    setExecutionResult(null);
    setErrorMsg(null);

    try {
      const res = await fetch('/api/macros/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          macro_name: selectedMacro.id,
          overrides: {},
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status === 'failed') {
        setErrorMsg(data.error || 'Macro step execution failed');
      }
      setExecutionResult(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Execution error');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-[#0E0B1A]/95 border border-white/10 rounded-3xl shadow-[0_24px_70px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-lg shadow-[0_0_15px_rgba(99,102,241,0.25)]">
              ⚙️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  Automation Macro Runner
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  YAML Multi-Step Orchestrator
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Chained step workflows with autonomous [MOMENTUM_TRIGGER] self-healing
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* Macro Selection Chips */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {macros.map((m) => (
              <div
                key={m.id}
                onClick={() => {
                  setSelectedMacro(m);
                  setExecutionResult(null);
                  setErrorMsg(null);
                }}
                className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
                  selectedMacro?.id === m.id
                    ? 'bg-indigo-950/40 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.3)]'
                    : 'bg-white/[0.02] border-white/5 hover:border-white/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white tracking-wide">{m.name}</span>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-black/40 text-zinc-400">
                    {m.steps_count} steps
                  </span>
                </div>
                <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                  {m.description}
                </p>
              </div>
            ))}
          </div>

          {/* Selected Macro Step Sequence */}
          {selectedMacro && (
            <div className="p-4 rounded-2xl bg-black/40 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-indigo-300 font-semibold">
                  Workflow Execution Pipeline
                </span>
                <span className="text-[10px] font-mono text-zinc-500">ID: {selectedMacro.id}</span>
              </div>

              {/* Steps Timeline */}
              <div className="space-y-2">
                {selectedMacro.steps.map((step, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-md bg-indigo-500/20 text-indigo-300 font-mono text-[10px] flex items-center justify-center font-bold">
                        {idx + 1}
                      </span>
                      <span className="font-semibold text-zinc-200">{step.name}</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                      {step.type}
                    </span>
                  </div>
                ))}
              </div>

              {/* Run Trigger */}
              <div className="pt-2">
                <button
                  onClick={runSelectedMacro}
                  disabled={running}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 active:scale-95 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                >
                  {running ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Executing Workflow Steps...</span>
                    </>
                  ) : (
                    <>
                      <span>🚀</span>
                      <span>Run Macro: {selectedMacro.name}</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Execution Output Stream */}
          {executionResult && (
            <div className="p-4 rounded-2xl bg-zinc-950/80 border border-white/10 space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-zinc-400 font-semibold">Execution Output</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    executionResult.status === 'success'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                      : 'bg-rose-950 text-rose-300 border border-rose-500/40'
                  }`}
                >
                  {executionResult.status === 'success' ? '✔ COMPLETED' : '✘ FAILED'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-black/60 border border-white/5 space-y-1.5 max-h-48 overflow-y-auto text-[11px] text-zinc-300">
                {executionResult.step_results?.map((step: any, i: number) => (
                  <div key={i} className="space-y-0.5">
                    <div className="text-indigo-400 font-bold">
                      [{i + 1}/{executionResult.step_results.length}] {step.step_name} ({step.type}):
                    </div>
                    <div className="text-zinc-400 pl-3">
                      {step.output || step.result || (step.status === 'success' ? 'Executed cleanly' : step.error)}
                    </div>
                  </div>
                ))}
                {executionResult.momentum_trigger && (
                  <div className="p-2 rounded bg-rose-950/40 border border-rose-500/40 text-rose-300 text-[10px] mt-2">
                    {executionResult.momentum_trigger}
                  </div>
                )}
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
              ⚠️ {errorMsg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MacroRunnerModal;
