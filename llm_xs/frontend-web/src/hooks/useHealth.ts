import { useEffect, useState } from "react";
import { getHealth } from "../lib/api";
import type { Health } from "../lib/types";

/** 周期性探测后端健康状态。 */
export function useHealth(intervalMs = 15000) {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const h = await getHealth();
        if (alive) {
          setHealth(h);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [intervalMs]);

  return { health, error };
}
