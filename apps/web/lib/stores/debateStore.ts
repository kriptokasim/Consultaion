import { create } from 'zustand';
import { DebateEvent } from '../api/types';
import { SSEStatus } from '../sse';

export type ConnectionStatus = SSEStatus;

interface DebateState {
    activeDebateId: string | null;
    currentRound: number;
    connectionStatus: ConnectionStatus;
    events: DebateEvent[];

    // Replay state
    isPlaying: boolean;
    replayPosition: number; // index in events array

    // Actions
    setActiveDebate: (id: string | null) => void;
    setRound: (round: number) => void;
    setConnectionStatus: (status: ConnectionStatus) => void;
    addEvent: (event: DebateEvent) => void;
    setEvents: (events: DebateEvent[]) => void;

    // Replay actions
    setIsPlaying: (isPlaying: boolean) => void;
    setReplayPosition: (position: number) => void;
    reset: () => void;
}

export const useDebateStore = create<DebateState>((set) => ({
    activeDebateId: null,
    currentRound: 0,
    connectionStatus: 'idle',
    events: [],

    isPlaying: false,
    replayPosition: -1,

    setActiveDebate: (id) => set({ activeDebateId: id }),
    setRound: (round) => set({ currentRound: round }),
    setConnectionStatus: (status) => set({ connectionStatus: status }),
    addEvent: (event) => set((state) => ({ events: [...state.events, event] })),
    setEvents: (events) => set({ events }),

    setIsPlaying: (isPlaying) => set({ isPlaying }),
    setReplayPosition: (position) => set({ replayPosition: position }),
    reset: () => set({
        activeDebateId: null,
        currentRound: 0,
        connectionStatus: 'idle',
        events: [],
        isPlaying: false,
        replayPosition: -1
    }),
}));
