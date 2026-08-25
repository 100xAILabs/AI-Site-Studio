import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * Voice settings store – persisted in localStorage.
 * Stores the user's preferred voice name, rate, pitch, and volume.
 */
export const useVoiceStore = create(
  persist(
    (set) => ({
      voiceName: '',        // empty = auto-detect calm voice
      rate: 0.85,
      pitch: 0.9,
      volume: 0.8,
      lang: '',             // empty = any language
      setVoiceName: (name) => set({ voiceName: name }),
      setRate: (rate) => set({ rate }),
      setPitch: (pitch) => set({ pitch }),
      setVolume: (volume) => set({ volume }),
      setLang: (lang) => set({ lang }),
    }),
    { name: 'voice-settings' }
  )
);
