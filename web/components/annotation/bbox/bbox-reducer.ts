import type { Bbox } from "./bbox-geometry";

export type BboxState = {
  boxes: Bbox[];
  selectedId: string | null;
  activeLabel: string;
  past: Bbox[][];
  future: Bbox[][];
};

export type BboxAction =
  | { type: "select"; id: string | null }
  | { type: "set-active-label"; label: string }
  | { type: "set-selected-label"; label: string }
  | { type: "add"; box: Bbox }
  | { type: "update"; box: Bbox }
  | { type: "delete-selected" }
  | { type: "replace-external"; boxes: Bbox[] }
  | { type: "undo" }
  | { type: "redo" };

const copy = (boxes: Bbox[]) => boxes.map((box) => ({ ...box }));

export function createBboxState(boxes: Bbox[], activeLabel: string): BboxState {
  return { boxes: copy(boxes), selectedId: null, activeLabel, past: [], future: [] };
}

function commit(state: BboxState, boxes: Bbox[], selectedId = state.selectedId): BboxState {
  return {
    ...state,
    boxes: copy(boxes),
    selectedId,
    past: [...state.past.slice(-39), copy(state.boxes)],
    future: [],
  };
}

export function reduceBboxState(state: BboxState, action: BboxAction): BboxState {
  switch (action.type) {
    case "select":
      return { ...state, selectedId: action.id };
    case "set-active-label":
      return { ...state, activeLabel: action.label };
    case "set-selected-label":
      return state.selectedId
        ? commit(state, state.boxes.map((box) => box.id === state.selectedId ? { ...box, label: action.label } : box))
        : state;
    case "add":
      return commit(state, [...state.boxes, action.box], action.box.id);
    case "update":
      return commit(state, state.boxes.map((box) => box.id === action.box.id ? action.box : box), action.box.id);
    case "delete-selected":
      return state.selectedId
        ? commit(state, state.boxes.filter((box) => box.id !== state.selectedId), null)
        : state;
    case "replace-external":
      return { ...state, boxes: copy(action.boxes), selectedId: null, past: [], future: [] };
    case "undo": {
      const previous = state.past.at(-1);
      if (!previous) return state;
      return { ...state, boxes: copy(previous), selectedId: null, past: state.past.slice(0, -1), future: [copy(state.boxes), ...state.future].slice(0, 40) };
    }
    case "redo": {
      const next = state.future[0];
      if (!next) return state;
      return { ...state, boxes: copy(next), selectedId: null, past: [...state.past.slice(-39), copy(state.boxes)], future: state.future.slice(1) };
    }
  }
}
