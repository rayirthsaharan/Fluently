import React, { createContext, useContext, useState, useCallback } from 'react';

const GeminiContext = createContext(null);

export function GeminiProvider({ children }) {
  const [userProfile, setUserProfile] = useState({
    ageGroup: null,
    focus: null,
    dailyGoal: null,
    onboardingComplete: false,
  });

  const [currentLesson, setCurrentLesson] = useState(null);
  const [isLiveSession, setIsLiveSession] = useState(false);
  const [confidenceScore, setConfidenceScore] = useState(50);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [lessonPhase, setLessonPhase] = useState('INTRO');

  const updateProfile = useCallback((key, value) => {
    setUserProfile(prev => ({ ...prev, [key]: value }));
  }, []);

  const completeOnboarding = useCallback(() => {
    setUserProfile(prev => ({ ...prev, onboardingComplete: true }));
  }, []);

  const completeLesson = useCallback((lessonId) => {
    setCompletedLessons(prev => [...new Set([...prev, lessonId])]);
  }, []);

  const getSystemInstructions = useCallback(() => {
    const ageLabels = { kid: '8-year-old child', teen: 'teenager', adult: 'adult', senior: 'senior citizen' };
    const focusLabels = {
      accent: 'Accent Reduction',
      'public-speaking': 'Public Speaking',
      pronunciation: 'Pronunciation Clarity',
      interview: 'Interview Preparation',
    };

    const age = ageLabels[userProfile.ageGroup] || 'user';
    const focus = focusLabels[userProfile.focus] || 'general speech';
    const lesson = currentLesson ? ` The lesson topic is: "${currentLesson.title}". ${currentLesson.desc}` : '';

    return `CONTEXT: Coaching a ${age} on ${focus}.${lesson}
Daily goal: ${userProfile.dailyGoal || 10} minutes.
For a ${age}, use age-appropriate language and humor.`;
  }, [userProfile, currentLesson]);

  const value = {
    userProfile, updateProfile, completeOnboarding,
    currentLesson, setCurrentLesson,
    isLiveSession, setIsLiveSession,
    confidenceScore, setConfidenceScore,
    completedLessons, completeLesson,
    lessonPhase, setLessonPhase,
    getSystemInstructions,
  };

  return <GeminiContext.Provider value={value}>{children}</GeminiContext.Provider>;
}

export function useGemini() {
  const ctx = useContext(GeminiContext);
  if (!ctx) throw new Error('useGemini must be used within GeminiProvider');
  return ctx;
}
