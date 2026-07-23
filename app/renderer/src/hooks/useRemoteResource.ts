import { useCallback, useEffect, useState } from "react";
import { redactErrorMessage } from "../../../shared/redaction";

export function useRemoteResource<T>(loader: () => Promise<T>, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      setData(await loader());
      setError(null);
    } catch (reason) {
      setError(redactErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [enabled, loader]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, error, loading, refresh };
}
