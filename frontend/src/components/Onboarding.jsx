import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGemini } from '../context/GeminiContext';

const ageOptions = [
  { id: 'kid', label: 'Kid', emoji: '🧒', desc: 'Ages 6–12' },
  { id: 'teen', label: 'Teen', emoji: '🧑', desc: 'Ages 13–17' },
  { id: 'adult', label: 'Adult', emoji: '🧑‍💼', desc: 'Ages 18–59' },
  { id: 'senior', label: 'Senior', emoji: '👴', desc: 'Ages 60+' },
];

const focusOptions = [
  { id: 'accent', label: 'Accent Reduction', emoji: '🌍', desc: 'Soften your accent' },
  { id: 'public-speaking', label: 'Public Speaking', emoji: '🎤', desc: 'Confidence on stage' },
  { id: 'pronunciation', label: 'Pronunciation', emoji: '👄', desc: 'Crystal clear words' },
  { id: 'interview', label: 'Interview Prep', emoji: '💼', desc: 'Nail your next interview' },
];

const goalOptions = [
  { id: 5, label: '5 min', emoji: '⚡', desc: 'Quick burst' },
  { id: 10, label: '10 min', emoji: '🔥', desc: 'Recommended' },
  { id: 20, label: '20 min', emoji: '🚀', desc: 'Power session' },
];

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const { userProfile, updateProfile, completeOnboarding } = useGemini();
  const navigate = useNavigate();

  const steps = [
    { title: 'How old are you?', subtitle: "We'll match Aura's style to you!", options: ageOptions, key: 'ageGroup' },
    { title: 'What\'s your focus?', subtitle: 'Pick your superpower to unlock', options: focusOptions, key: 'focus' },
    { title: 'Daily goal?', subtitle: 'Consistency is everything!', options: goalOptions, key: 'dailyGoal' },
  ];

  const current = steps[step];
  const selected = userProfile[current.key];

  const next = () => {
    if (step < steps.length - 1) setStep(step + 1);
    else { completeOnboarding(); navigate('/dashboard'); }
  };

  const back = () => { if (step > 0) setStep(step - 1); };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-8 bg-bg-page">
      {/* Progress bar */}
      <div className="w-full max-w-md mb-8">
        <div className="progress-bar-track">
          <div className="progress-bar-fill" style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
        </div>
      </div>

      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-black text-text-dark mb-2">{current.title}</h1>
        <p className="text-text-muted text-lg font-semibold">{current.subtitle}</p>
      </div>

      {/* Option cards */}
      <div className="w-full max-w-md grid grid-cols-2 gap-3 mb-8">
        {current.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => updateProfile(current.key, opt.id)}
            className={`btn-3d p-5 text-left transition-all
              ${selected === opt.id
                ? 'btn-3d-green !text-white'
                : 'btn-3d-white'}`}
          >
            <span className="text-3xl block mb-2">{opt.emoji}</span>
            <span className="font-extrabold text-base block">{opt.label}</span>
            <span className={`text-sm font-semibold ${selected === opt.id ? 'text-white/80' : 'text-text-muted'}`}>{opt.desc}</span>
          </button>
        ))}
      </div>

      {/* Navigation */}
      <div className="w-full max-w-md flex justify-between items-center">
        {step > 0 ? (
          <button onClick={back} className="btn-3d btn-3d-white px-6 py-3 text-sm">Back</button>
        ) : <div />}
        <button
          onClick={next}
          disabled={!selected}
          className={`btn-3d px-10 py-4 text-base
            ${selected ? 'btn-3d-green' : 'btn-3d-white opacity-50 cursor-not-allowed'}`}
        >
          {step === steps.length - 1 ? "LET'S GO!" : 'CONTINUE'}
        </button>
      </div>
    </div>
  );
}
