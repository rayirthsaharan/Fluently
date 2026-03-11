import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGemini } from '../context/GeminiContext';
import { useGeminiLive } from '../hooks/useGeminiLive';

const EXERCISE_LABELS = [
  '"THINK" — /θ/ voiceless TH',
  '"THE" — /ð/ voiced TH',
  '"THOUGHT" — /θ/ voiceless TH',
  '"The thin thing thought through the thicket"',
  '"BREATHE" — /ð/ voiced TH',
  '"They thought that three thin threads were free"',
];

export default function LiveSession() {
  const { 
    currentLesson, isLiveSession, setIsLiveSession, 
    confidenceScore, setConfidenceScore, 
    getSystemInstructions, completeLesson,
    lessonPhase, setLessonPhase,
  } = useGemini();
  const { 
    connect, disconnect, isConnected, sessionState, 
    sendAction, setEventHandlers, lessonState, transcription 
  } = useGeminiLive('ws://localhost:8000/ws');
  const navigate = useNavigate();
  
  const [elapsed, setElapsed] = useState(0);
  const [showSuccess, setShowSuccess] = useState(false);
  const [exerciseCount, setExerciseCount] = useState(0);
  const [currentExerciseLabel, setCurrentExerciseLabel] = useState('');

  // Connect on mount
  useEffect(() => {
    if (isLiveSession) {
      const instructions = getSystemInstructions();
      connect(instructions);
    }
    return () => disconnect();
  }, []);

  // Register event handlers for real-time UI sync
  useEffect(() => {
    setEventHandlers({
      onSuccess: () => {
        setShowSuccess(true);
        setExerciseCount(p => p + 1);
        setConfidenceScore(p => Math.min(100, p + 15));
        setTimeout(() => setShowSuccess(false), 1500);
      },
      onInterrupted: () => {
        // Barge-in handled — audio already flushed by hook
      },
      onTurnComplete: () => {
        // Aura finished speaking — session remains ACTIVE
      },
      onStateChange: (state) => {
        if (state) {
          setLessonPhase(state.phase);
          if (state.exercise_index < EXERCISE_LABELS.length) {
            setCurrentExerciseLabel(EXERCISE_LABELS[state.exercise_index]);
          }
          if (state.lesson_complete) {
            setShowSuccess(true);
            setTimeout(() => setShowSuccess(false), 3000);
          }
        }
      },
      onNudge: () => {
        // Nudge received — Aura is about to encourage the user
      },
      onTranscription: (t) => {
        // Could display real-time transcription in the future
      },
    });
  }, [setEventHandlers, setConfidenceScore, setLessonPhase]);

  // Sync lessonState from hook
  useEffect(() => {
    if (lessonState) {
      setLessonPhase(lessonState.phase);
      if (lessonState.exercise_index < EXERCISE_LABELS.length) {
        setCurrentExerciseLabel(EXERCISE_LABELS[lessonState.exercise_index]);
      }
    }
  }, [lessonState, setLessonPhase]);

  // Timer
  useEffect(() => {
    if (!isConnected) return;
    const t = setInterval(() => setElapsed(p => p + 1), 1000);
    return () => clearInterval(t);
  }, [isConnected]);

  // Confidence meter — gradual drift with bias upward over time
  useEffect(() => {
    if (!isConnected) return;
    const t = setInterval(() => {
      setConfidenceScore(prev => {
        const drift = (Math.random() - 0.3) * 6;
        return Math.max(15, Math.min(100, prev + drift));
      });
    }, 3000);
    return () => clearInterval(t);
  }, [isConnected, setConfidenceScore]);

  const handleEnd = () => {
    disconnect();
    if (currentLesson) completeLesson(currentLesson.id);
    setIsLiveSession(false);
    navigate('/dashboard');
  };

  const formatTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const isSpeaking = sessionState === 'AGENT_SPEAKING';
  const isActive = sessionState === 'ACTIVE';
  const isConnecting = sessionState === 'CONNECTING';
  const isPracticing = lessonPhase === 'PRACTICE';

  const confidenceColor = confidenceScore > 70 ? '#58CC02' : confidenceScore > 40 ? '#FFC700' : '#FF4B4B';

  // Session progress: exercises completed out of total
  const totalExercises = lessonState?.total_exercises || 6;
  const currentIdx = lessonState?.exercise_index || 0;
  const sessionProgress = Math.min(100, (currentIdx / totalExercises) * 100);

  // Phase labels for the badge
  const phaseLabel = isPracticing 
    ? `🎯 EXERCISE ${currentIdx + 1}/${totalExercises}` 
    : lessonPhase === 'NEXT' 
      ? '⏭️ NEXT UP' 
      : lessonPhase === 'INTRO' 
        ? '👋 INTRO' 
        : '🎤 ACTIVE';

  return (
    <div className="min-h-screen bg-bg-page flex flex-col relative">
      {/* Success Animation Overlay */}
      {showSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
          <div className="text-center animate-bounce">
            <div className="text-8xl mb-2">🎉</div>
            <div className="bg-duo-green text-white font-black text-2xl px-8 py-3 rounded-2xl" 
                 style={{ boxShadow: '0 4px 0 #4CAD02' }}>
              {lessonState?.lesson_complete ? 'LESSON COMPLETE!' : 'PERFECT!'}
            </div>
          </div>
        </div>
      )}

      {/* Top bar */}
      <div className="bg-white border-b-2 border-border px-4 py-3">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <button onClick={handleEnd} className="text-text-muted font-bold text-sm hover:text-duo-red transition cursor-pointer">
            ✕ QUIT
          </button>
          <div className="flex-1 mx-4">
            <div className="progress-bar-track">
              <div className="progress-bar-fill transition-all duration-500" style={{ width: `${sessionProgress}%` }} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-bold text-duo-green text-sm">{exerciseCount} ✓</span>
            <span className="font-bold text-text-muted text-sm">{formatTime(elapsed)}</span>
          </div>
        </div>
      </div>

      {/* Main coaching area */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-6">
        {/* Lesson title */}
        {currentLesson && (
          <div className="text-center mb-4">
            <span className="text-text-muted font-bold text-xs uppercase tracking-widest">Lesson</span>
            <h2 className="text-2xl font-black text-text-dark">{currentLesson.title}</h2>
          </div>
        )}

        {/* Current exercise label */}
        {isPracticing && currentExerciseLabel && (
          <div className="text-center mb-6 px-6 py-3 rounded-2xl" 
               style={{ backgroundColor: '#F0F4FF', border: '2px solid #D0DFFF' }}>
            <span className="text-xs font-bold text-duo-blue uppercase tracking-wide">Now practicing</span>
            <p className="text-lg font-black text-text-dark mt-1">{currentExerciseLabel}</p>
            {lessonState?.attempts > 0 && (
              <span className="text-xs font-bold text-text-muted mt-1 inline-block">
                Attempt {lessonState.attempts}/{lessonState?.max_attempts || 3}
              </span>
            )}
          </div>
        )}

        {/* Aura Avatar — large, central, reactive */}
        <div className="relative mb-8">
          {/* Pulse rings when speaking */}
          {isSpeaking && (
            <>
              <div className="absolute inset-0 rounded-full animate-ping opacity-20" 
                   style={{ backgroundColor: '#58CC02', animationDuration: '2s' }} />
              <div className="absolute -inset-3 rounded-full animate-ping opacity-10" 
                   style={{ backgroundColor: '#58CC02', animationDuration: '2.5s' }} />
            </>
          )}
          
          {/* Subtle breathing animation when active/listening */}
          {isActive && !isSpeaking && (
            <div className="absolute -inset-2 rounded-full opacity-15 animate-pulse" 
                 style={{ backgroundColor: '#1CB0F6', animationDuration: '3s' }} />
          )}
          
          <div className={`relative w-40 h-40 rounded-full flex items-center justify-center text-7xl select-none z-10
            ${isSpeaking ? 'aura-pulse' : ''}`}
            style={{
              backgroundColor: isSpeaking ? '#E5F9D0' : isActive ? '#D0ECFB' : isConnecting ? '#FFF4CC' : '#F7F7F7',
              border: `5px solid ${isSpeaking ? '#58CC02' : isActive ? '#1CB0F6' : isConnecting ? '#FFC700' : '#E5E5E5'}`,
              transition: 'all 0.3s ease',
              boxShadow: isSpeaking ? '0 0 30px rgba(88,204,2,0.3)' : isActive ? '0 0 20px rgba(28,176,246,0.2)' : 'none',
            }}
          >
            🦉
          </div>

          {/* Phase label */}
          <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 z-20">
            <span className={`px-4 py-1.5 rounded-full text-xs font-extrabold text-white whitespace-nowrap ${
              isSpeaking ? 'bg-duo-green' :
              isActive ? 'bg-duo-blue' :
              isConnecting ? 'bg-duo-yellow text-text-dark' :
              'bg-border-dark'
            }`} style={{ boxShadow: '0 2px 0 rgba(0,0,0,0.15)' }}>
              {isSpeaking ? '🗣️ AURA' :
               isActive ? phaseLabel :
               isConnecting ? '⏳ CONNECTING' :
               '⏸️ READY'}
            </span>
          </div>
        </div>

        {/* Live mic indicator — always on */}
        {isConnected && (
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 rounded-full bg-duo-red animate-pulse" />
            <span className="text-xs font-bold text-text-muted uppercase tracking-wider">Mic Live</span>
          </div>
        )}

        {/* Confidence Meter */}
        <div className="w-full max-w-xs mb-8">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-bold text-text-muted uppercase tracking-wide">Confidence</span>
            <span className="text-sm font-black" style={{ color: confidenceColor }}>{Math.round(confidenceScore)}%</span>
          </div>
          <div className="progress-bar-track">
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${confidenceScore}%`, backgroundColor: confidenceColor }} />
          </div>
        </div>

        {/* Hybrid Control Buttons */}
        <div className="w-full max-w-sm">
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={() => sendAction("I'm stuck")}
              className="btn-3d btn-3d-white py-4 text-xs flex flex-col items-center gap-1"
            >
              <span className="text-2xl">😰</span>
              <span>I'M STUCK</span>
            </button>
            <button
              onClick={() => sendAction("Repeat that")}
              className="btn-3d btn-3d-white py-4 text-xs flex flex-col items-center gap-1"
            >
              <span className="text-2xl">🔁</span>
              <span>REPEAT</span>
            </button>
            <button
              onClick={() => sendAction("Skip this word")}
              className="btn-3d btn-3d-white py-4 text-xs flex flex-col items-center gap-1"
            >
              <span className="text-2xl">⏭️</span>
              <span>SKIP</span>
            </button>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="bg-white border-t-2 border-border px-4 py-4">
        <div className="max-w-lg mx-auto">
          <button onClick={handleEnd} className="btn-3d btn-3d-red w-full py-4 text-base">
            END SESSION
          </button>
        </div>
      </div>
    </div>
  );
}
