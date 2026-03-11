import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { GeminiProvider, useGemini } from './context/GeminiContext';
import Onboarding from './components/Onboarding';
import Dashboard from './components/Dashboard';
import LiveSession from './components/LiveSession';
import './index.css';

function AppRoutes() {
  const { userProfile, isLiveSession } = useGemini();

  return (
    <Routes>
      <Route
        path="/"
        element={
          userProfile.onboardingComplete
            ? <Navigate to="/dashboard" replace />
            : <Navigate to="/onboarding" replace />
        }
      />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route
        path="/dashboard"
        element={
          userProfile.onboardingComplete
            ? <Dashboard />
            : <Navigate to="/onboarding" replace />
        }
      />
      <Route path="/session" element={<LiveSession />} />
    </Routes>
  );
}

function App() {
  return (
    <GeminiProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </GeminiProvider>
  );
}

export default App;
