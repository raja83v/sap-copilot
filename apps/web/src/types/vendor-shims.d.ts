declare module "zustand" {
  export type SetState<T> = (
    partial: T | Partial<T> | ((state: T) => T | Partial<T>),
    replace?: boolean,
  ) => void;

  export type GetState<T> = () => T;

  export type StateCreator<T> = (
    set: SetState<T>,
    get: GetState<T>,
    api: unknown,
  ) => T;

  export interface UseBoundStore<T> {
    (): T;
    <U>(selector: (state: T) => U): U;
    getState: GetState<T>;
  }

  export function create<T>(initializer: StateCreator<T>): UseBoundStore<T>;
}