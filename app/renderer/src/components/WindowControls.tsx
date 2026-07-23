import { useEffect, useState } from "react";

export function WindowControls() {
  const [maximized, setMaximized] = useState(false);
  useEffect(() => {
    let active = true;
    void window.newxau.window.isMaximized().then((value) => active && setMaximized(value));
    const unsubscribe = window.newxau.window.onMaximizedChange(setMaximized);
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);
  return (
    <div className="window-controls" onDoubleClick={(event) => event.stopPropagation()}>
      <button type="button" aria-label="Minimize window" onClick={() => void window.newxau.window.minimize()}>
        <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1 5.5h8" /></svg>
      </button>
      <button
        type="button"
        aria-label={maximized ? "Restore window" : "Maximize window"}
        onClick={() => void window.newxau.window.toggleMaximize()}
      >
        {maximized ? (
          <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M3 2V1h6v6H8M1 3h6v6H1z" /></svg>
        ) : (
          <svg viewBox="0 0 10 10" aria-hidden="true"><rect x="1" y="1" width="8" height="8" /></svg>
        )}
      </button>
      <button className="window-close" type="button" aria-label="Close window" onClick={() => void window.newxau.window.close()}>
        <svg viewBox="0 0 10 10" aria-hidden="true"><path d="m1.5 1.5 7 7m0-7-7 7" /></svg>
      </button>
    </div>
  );
}
