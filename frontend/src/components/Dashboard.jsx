import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGemini } from '../context/GeminiContext';

const lessons = [
  { id: 1, title: 'The Soft "Th"', desc: 'Master the voiced and unvoiced "th" sounds.', unit: 'Foundations', color: 'duo-green' },
  { id: 2, title: 'Vowel Clarity', desc: 'Distinguish short and long vowels clearly.', unit: 'Foundations', color: 'duo-green' },
  { id: 3, title: '"L" vs "R"', desc: 'Tongue placement for both sounds.', unit: 'Foundations', color: 'duo-green' },
  { id: 4, title: 'Word Stress', desc: 'Where you stress changes meaning.', unit: 'Rhythm', color: 'duo-blue' },
  { id: 5, title: 'Intonation', desc: 'Vary your pitch naturally.', unit: 'Rhythm', color: 'duo-blue' },
  { id: 6, title: 'Connected Speech', desc: 'How words blend in conversation.', unit: 'Flow', color: 'duo-purple' },
  { id: 7, title: 'Full Practice', desc: 'A real scenario practice run.', unit: 'Flow', color: 'duo-purple' },
];

const colorMap = {
  'duo-green': { bg: '#58CC02', border: '#4CAD02', ring: '#E5F9D0' },
  'duo-blue': { bg: '#1CB0F6', border: '#1899D6', ring: '#D0ECFB' },
  'duo-purple': { bg: '#CE82FF', border: '#AD5CE0', ring: '#F0DBFF' },
};

export default function Dashboard() {
  const { userProfile, completedLessons, setCurrentLesson, setIsLiveSession } = useGemini();
  const [selectedLesson, setSelectedLesson] = useState(null);
  const navigate = useNavigate();

  const focusLabels = {
    accent: '🌍 Accent Reduction',
    'public-speaking': '🎤 Public Speaking',
    pronunciation: '👄 Pronunciation',
    interview: '💼 Interview Prep',
  };

  // Unlock logic: first 3 always unlocked, rest unlock as you complete
  const isUnlocked = (lesson) => {
    if (lesson.id <= 3) return true;
    return completedLessons.includes(lesson.id - 1);
  };

  const isCompleted = (id) => completedLessons.includes(id);

  const handleStart = () => {
    setCurrentLesson(selectedLesson);
    setIsLiveSession(true);
    navigate('/session');
  };

  const units = [...new Set(lessons.map(l => l.unit))];
  const progress = (completedLessons.length / lessons.length) * 100;

  // Zigzag offsets for Duolingo path
  const zigzag = [0, 60, 30, -30, -60, 0, 40];

  return (
    <div className="min-h-screen bg-bg-page">
      {/* Top bar */}
      <div className="sticky top-0 bg-white border-b-2 border-border z-30 px-4 py-3">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <span className="text-2xl">🗣️</span>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 font-bold text-duo-orange">
              🔥 <span>{completedLessons.length}</span>
            </div>
            <div className="flex items-center gap-1 font-bold text-duo-yellow">
              ⭐ <span>{completedLessons.length * 10}</span>
            </div>
            <div className="flex items-center gap-1 font-bold text-duo-red">
              ❤️ <span>5</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-6">
        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="font-extrabold text-text-dark">{focusLabels[userProfile.focus]}</span>
            <span className="font-bold text-duo-green text-sm">{Math.round(progress)}%</span>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>

        {/* Unit sections with circular nodes */}
        {units.map((unit) => {
          const unitLessons = lessons.filter(l => l.unit === unit);
          const colors = colorMap[unitLessons[0].color];

          return (
            <div key={unit} className="mb-10">
              {/* Unit header */}
              <div className="rounded-2xl p-4 mb-6 text-white font-extrabold text-lg flex items-center justify-between"
                   style={{ backgroundColor: colors.bg, boxShadow: `0 4px 0 ${colors.border}` }}>
                <span>{unit}</span>
                <span className="text-white/70 text-sm font-bold">{unitLessons.filter(l => isCompleted(l.id)).length}/{unitLessons.length}</span>
              </div>

              {/* Lesson nodes - zigzag path */}
              <div className="flex flex-col items-center gap-6 py-4">
                {unitLessons.map((lesson, i) => {
                  const unlocked = isUnlocked(lesson);
                  const completed = isCompleted(lesson.id);
                  const offset = zigzag[lessons.indexOf(lesson) % zigzag.length];

                  return (
                    <div key={lesson.id} className="flex flex-col items-center" style={{ transform: `translateX(${offset}px)` }}>
                      <button
                        onClick={() => unlocked && setSelectedLesson(lesson)}
                        disabled={!unlocked}
                        className={`level-node ${
                          completed ? 'level-node-complete' :
                          unlocked ? 'level-node-active' :
                          'level-node-locked'
                        }`}
                        style={unlocked && !completed ? { backgroundColor: colors.bg, boxShadow: `0 4px 0 ${colors.border}, 0 0 0 4px ${colors.ring}` } : {}}
                      >
                        {completed ? '✓' :
                         unlocked ? (lessons.indexOf(lesson) + 1) :
                         '🔒'}
                      </button>
                      {unlocked && (
                        <span className="text-xs font-bold text-text-muted mt-2 text-center max-w-20">{lesson.title}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Session Preview Modal */}
      {selectedLesson && (
        <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <div className="text-center mb-6">
              <div className="level-node level-node-active mx-auto mb-4 text-2xl"
                   style={{ backgroundColor: colorMap[selectedLesson.color].bg, boxShadow: `0 4px 0 ${colorMap[selectedLesson.color].border}` }}>
                {lessons.indexOf(selectedLesson) + 1}
              </div>
              <h2 className="text-2xl font-black text-text-dark">{selectedLesson.title}</h2>
              <p className="text-text-muted font-semibold mt-1">{selectedLesson.desc}</p>
            </div>

            <div className="bg-bg-page rounded-xl p-4 mb-6">
              <p className="text-sm font-semibold text-text-muted text-center">
                🎧 Aura will coach you through this lesson using <strong className="text-text-dark">voice only</strong> for the best experience.
              </p>
            </div>

            <button onClick={handleStart} className="btn-3d btn-3d-green w-full py-4 text-lg mb-3">
              START LESSON
            </button>
            <button onClick={() => setSelectedLesson(null)} className="btn-3d btn-3d-white w-full py-3 text-sm">
              MAYBE LATER
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
