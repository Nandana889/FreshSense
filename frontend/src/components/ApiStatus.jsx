import { useEffect, useState } from 'react';
import { fetchHealth } from '../services/api.js';

const CHECK_INTERVAL_MS = 30_000;

/** Shows whether the backend is reachable, using GET /health. */
export default function ApiStatus() {
  const [health, setHealth] = useState(undefined); // undefined = first check pending

  useEffect(() => {
    let isActive = true;

    async function check() {
      const payload = await fetchHealth();
      if (isActive) setHealth(payload);
    }

    check();
    const timer = setInterval(check, CHECK_INTERVAL_MS);
    return () => {
      isActive = false;
      clearInterval(timer);
    };
  }, []);

  if (health === undefined) {
    return <span className="api-status">Checking model server…</span>;
  }

  if (health === null) {
    return <span className="api-status api-status--offline">Model server offline</span>;
  }

  return <span className="api-status api-status--online">{health.model} online</span>;
}
