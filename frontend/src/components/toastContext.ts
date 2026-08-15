import { createContext } from "react";

export interface ToastMessage {
  id: number;
  kind: "info" | "success" | "error";
  text: string;
}

export interface ToastContextValue {
  toasts: ToastMessage[];
  push: (text: string, kind?: ToastMessage["kind"]) => void;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);
