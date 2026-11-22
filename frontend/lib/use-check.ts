import { useMemo, useState } from "react";

import { useLatest } from "../effects/useLatest";
import { useRequest } from "../effects/useRequest";

import type { CheckState } from "./steps";
import type { StudioApi } from "./studio-api";

type Args = {
  api: StudioApi;
  id: string;
  ready: boolean;
  saves: number;
  current: () => { bodyEtag: string; metaEtag: string };
};

/** Answers whose ETags are not current are dropped, so the state can stay `running`. */
export function useCheck({ api, id, ready, saves, current }: Args): CheckState {
  const [answer, setAnswer] = useState<{ at: number; state: CheckState } | null>(null);
  const latest = useLatest(current);
  const key = useMemo(() => ({ api, id, saves }), [api, id, saves]);
  useRequest(() => api.checkPost(id), key, {
    enabled: ready,
    onResult: (result) => {
      const now = latest.current();
      if (result.bodyEtag !== now.bodyEtag || result.metaEtag !== now.metaEtag) return;
      setAnswer({ at: saves, state: { phase: "done", problems: result.problems } });
    },
    onError: () => setAnswer({ at: saves, state: { phase: "failed" } }),
  });

  return ready && answer?.at === saves ? answer.state : { phase: "running" };
}
