import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

const ToastCtx = createContext(() => {});

const STYLE = {
  success: { icon: CheckCircle2, color: "text-emerald-500" },
  error: { icon: XCircle, color: "text-rose-500" },
  info: { icon: Info, color: "text-accent" },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const dismiss = (id) => setToasts((t) => t.filter((x) => x.id !== id));
  const toast = useCallback((text, kind = "success") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-3), { id, text, kind }]);
    setTimeout(() => dismiss(id), kind === "error" ? 8000 : 4500);
  }, []);
  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => {
          const S = STYLE[t.kind] || STYLE.info;
          return (
            <div key={t.id} className="card anim-pop pointer-events-auto flex items-start gap-3 p-3.5 shadow-lg">
              <S.icon className={`mt-0.5 h-4.5 w-4.5 shrink-0 ${S.color}`} />
              <p className="flex-1 text-[13px] leading-5 text-ink">{t.text}</p>
              <button onClick={() => dismiss(t.id)} className="text-ink-3 hover:text-ink" aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
