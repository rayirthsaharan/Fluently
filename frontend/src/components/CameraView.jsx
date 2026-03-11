import React from 'react';
import { Camera, Mic, Activity } from 'lucide-react';
import './CameraView.css';

export function CameraView({ videoRef, sessionState, isConnected }) {
  return (
    <div className="camera-container">
      <div className="camera-header">
        <div className="status-badge">
          <Activity size={16} className={isConnected ? "text-green" : "text-gray"} />
          <span>{isConnected ? sessionState.replace('_', ' ') : 'DISCONNECTED'}</span>
        </div>
        <div className="device-icons">
          <Mic size={18} />
          <Camera size={18} />
        </div>
      </div>
      
      <div className="video-wrapper">
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted 
          className="live-video"
        />
        {!isConnected && (
          <div className="offline-overlay">
            <p>Connect to start your session</p>
          </div>
        )}
        {sessionState === 'BARGE_IN' && (
          <div className="barge-in-overlay">
            <h2>Aura Interrupted</h2>
            <p>Let's correct that pronunciation!</p>
          </div>
        )}
      </div>
    </div>
  );
}
