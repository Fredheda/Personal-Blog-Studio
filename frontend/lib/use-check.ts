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

/** What publish would refuse on for the saved post (spec 7.5). Asks when the
 *  post has loaded and again whenever `saves` changes (every successful save,
 *  a reload). Until the answer for the current `saves` arrives the state is
 *  `running`. An answer whose ETags are not the current ones is dropped; if
 *  no save follows (the post changed in another tab, then a details Save
 *  here), the state stays `running` until the next edit raises the conflict. */
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
