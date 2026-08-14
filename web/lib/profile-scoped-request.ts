export class ProfileScopedRequest {
  private generation = 0;
  private controller = new AbortController();

  switchProfile(): number {
    this.controller.abort();
    this.controller = new AbortController();
    this.generation += 1;
    return this.generation;
  }

  begin(): { signal: AbortSignal; generation: number } {
    return { signal: this.controller.signal, generation: this.generation };
  }

  accepts(generation: number): boolean {
    return generation === this.generation && !this.controller.signal.aborted;
  }
}
