import { ApiError } from "./problem";

export type AutosaveStatus = "idle" | "pending" | "saving" | "saved" | "conflict" | "error";

type Options = {
  save: (text: string) => Promise<void>;
  delayMs: number;
  onStatus: (status: AutosaveStatus) => void;
};

/** Debounced autosave of the post body with one save loop at a time. The latest
 *  pushed text always wins. A 412 stops it for good (the owner reloads). Any
 *  other failure keeps the text and stops the loop without rescheduling: the
 *  next `push` or `flush` retries, so an expired session or a 413 is not
 *  hammered on a timer. The caller's `save` records the reason of a failure. */
export function createAutosave({ save, delayMs, onStatus }: Options) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let latest: string | undefined;
  let inFlight: Promise<void> | undefined;
  let conflicted = false;
  let errored = false;
  let stopped = false;

  function clearTimer() {
    if (timer !== undefined) {
      clearTimeout(timer);
      timer = undefined;
    }
  }

  function schedule() {
    clearTimer();
    timer = setTimeout(() => void pump(), delayMs);
  }

  function pump(): Promise<void> {
    clearTimer();
    if (inFlight === undefined) {
      inFlight = (async () => {
        while (latest !== undefined && !conflicted && !stopped) {
          const text = latest;
          latest = undefined;
          errored = false;
          onStatus("saving");
          try {
            await save(text);
          } catch (e) {
            if (e instanceof ApiError && e.status === 412) {
              conflicted = true;
              onStatus("conflict");
            } else {
              latest ??= text; // keep the text for the next push or flush
              errored = true;
              onStatus("error");
            }
            return;
          }
        }
        if (!conflicted && !stopped) onStatus("saved");
      })().finally(() => {
        inFlight = undefined;
        // An edit that arrived while the loop was winding down still gets saved.
        if (latest !== undefined && !conflicted && !errored && !stopped) schedule();
      });
    }
    return inFlight;
  }

  return {
    push(text: string) {
      if (stopped || conflicted) return;
      latest = text;
      errored = false;
      onStatus("pending");
      if (inFlight === undefined) schedule(); // a running loop picks `latest` up itself
    },
    /** Saves everything now. True only when nothing is pending and nothing failed. */
    async flush(): Promise<boolean> {
      if (latest !== undefined || inFlight !== undefined) await pump();
      return !conflicted && !errored && latest === undefined;
    },
    /** Flush, then stop: used when the editor goes away. */
    async close(): Promise<boolean> {
      const saved = await this.flush();
      this.stop();
      return saved;
    },
    stop() {
      stopped = true;
      clearTimer();
    },
  };
}
