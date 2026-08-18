import type { Bbox } from "./bbox-geometry";

export type BboxState = {
  boxes: Bbox[];
  selectedIds: string[];
  activeLabel: string;
  past: Bbox[][];
  future: Bbox[][];
};

export type BboxAction =
  | { type: "select"; ids: string[] }
  | { type: "select-toggle"; id: string }
  | { type: "clear-selection" }
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
  return { boxes: copy(boxes), selectedIds: [], activeLabel, past: [], future: [] };
}

function commit(state: BboxState, boxes: Bbox[], selectedIds: string[] = state.selectedIds): BboxState {
  return {
    ...state,
    boxes: copy(boxes),
    selectedIds,
    past: [...state.past.slice(-39), copy(state.boxes)],
    future: [],
  };
}

export function reduceBboxState(state: BboxState, action: BboxAction): BboxState {
  switch (action.type) {
    case "select":
      return { ...state, selectedIds: action.ids };
    case "select-toggle":
      return {
        ...state,
        selectedIds: state.selectedIds.includes(action.id)
          ? state.selectedIds.filter((id) => id !== action.id)
          : [...state.selectedIds, action.id],
      };
    case "clear-selection":
      return { ...state, selectedIds: [] };
    case "set-active-label":
      return { ...state, activeLabel: action.label };
    case "set-selected-label":
      return state.selectedIds.length
        ? commit(state, state.boxes.map((box) => state.selectedIds.includes(box.id) ? { ...box, label: action.label } : box))
        : state;
    case "add":
      return commit(state, [...state.boxes, action.box], [action.box.id]);
    case "update":
      return commit(
        state,
        state.boxes.map((box) => box.id === action.box.id ? action.box : box),
        state.selectedIds.includes(action.box.id) ? state.selectedIds : [action.box.id],
      );
    case "delete-selected": {
      if (!state.selectedIds.length) return state;
      const removed = new Set(state.selectedIds);
      return commit(state, state.boxes.filter((box) => !removed.has(box.id)), []);
    }
    case "replace-external":
      return { ...state, boxes: copy(action.boxes), selectedIds: [], past: [], future: [] };
    case "undo": {
      const previous = state.past.at(-1);
      if (!previous) return state;
      return { ...state, boxes: copy(previous), selectedIds: [], past: state.past.slice(0, -1), future: [copy(state.boxes), ...state.future].slice(0, 40) };
    }
    case "redo": {
      const next = state.future[0];
      if (!next) return state;
      return { ...state, boxes: copy(next), selectedIds: [], past: [...state.past.slice(-39), copy(state.boxes)], future: state.future.slice(1) };
    }
  }
}
