import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './style.css';

// Ensure root element exists
let rootElement = document.getElementById('root');
if (!rootElement) {
  rootElement = document.createElement('div');
  rootElement.id = 'root';
  document.body.appendChild(rootElement);
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Navigation bridge between classic workspace view and React Cosmic Workspace
export function showReactCosmicDeck() {
  const landingView = document.getElementById('app-landing-view');
  const workspaceView = document.getElementById('app-workspace-view');
  const rootEl = document.getElementById('root');
  if (landingView) landingView.classList.add('hidden');
  if (workspaceView) workspaceView.classList.add('hidden');
  if (rootEl) {
    rootEl.classList.remove('hidden');
    rootEl.style.display = 'block';
  }
  window.location.hash = '#/cosmic-deck';
}

export function hideReactCosmicDeck() {
  const rootEl = document.getElementById('root');
  if (rootEl) {
    rootEl.classList.add('hidden');
    rootEl.style.display = 'none';
  }
}

(window as any).showReactCosmicDeck = showReactCosmicDeck;
(window as any).hideReactCosmicDeck = hideReactCosmicDeck;

if (window.location.hash === '#/cosmic-deck' || window.location.hash === '#/react') {
  showReactCosmicDeck();
}

console.log('Andromeda React Cosmic Core mounted.');
