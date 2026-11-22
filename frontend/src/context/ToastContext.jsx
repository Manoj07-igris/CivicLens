import React, { useState, useCallback } from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from "lucide-react";
import { ToastContext } from "./ToastContextInstance";

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(({ title, message, type = "info", duration = 4000 }) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9);
    const newToast = { id, title, message, type };

    setToasts((prev) => [...prev, newToast]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
    return id;
  }, [removeToast]);

  // Support both addToast({ title, message, type }) and addToast("message", "type")
  const addToast = useCallback((msgOrObj, type = "info", duration = 4000) => {
    if (typeof msgOrObj === "string") {
      return showToast({ message: msgOrObj, type, duration });
    }
    if (msgOrObj && typeof msgOrObj === "object") {
      const message = msgOrObj.message || msgOrObj.title || "";
      const title = msgOrObj.title && msgOrObj.message ? msgOrObj.title : undefined;
      const toastType = msgOrObj.type || type;
      const toastDuration = msgOrObj.duration || duration;
      return showToast({ title, message, type: toastType, duration: toastDuration });
    }
    return null;
  }, [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, addToast, removeToast }}>
      {children}
      {/* Toast container overlay */}
      <div 
        aria-live="polite" 
        className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      >
        {toasts.map((toast) => {
          let bg = "bg-white border-slate-200 text-slate-800";
          let Icon = Info;
          let iconColor = "text-blue-600";

          if (toast.type === "success") {
            bg = "bg-emerald-50 border-emerald-200 text-emerald-900";
            Icon = CheckCircle2;
            iconColor = "text-emerald-600";
          } else if (toast.type === "warning") {
            bg = "bg-amber-50 border-amber-200 text-amber-900";
            Icon = AlertTriangle;
            iconColor = "text-amber-600";
          } else if (toast.type === "error") {
            bg = "bg-rose-50 border-rose-200 text-rose-900";
            Icon = AlertCircle;
            iconColor = "text-rose-600";
          }

          return (
            <div
              key={toast.id}
              role="alert"
              className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-lg border shadow-lg transition-all transform duration-200 ${bg}`}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${iconColor}`} />
              <div className="flex-1 text-sm leading-relaxed">
                {toast.title && <div className="font-semibold mb-0.5">{toast.title}</div>}
                <div className="font-medium">{toast.message}</div>
              </div>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="text-slate-400 hover:text-slate-600 p-0.5 rounded cursor-pointer"
                aria-label="Close notification"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export default ToastProvider;
