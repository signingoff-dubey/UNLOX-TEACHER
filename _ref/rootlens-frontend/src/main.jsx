import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import { applyAppearance, readAppearance } from './lib/appearance';

// Before the first render, so the saved theme and accent never flash in after the default ones.
applyAppearance(readAppearance());

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
