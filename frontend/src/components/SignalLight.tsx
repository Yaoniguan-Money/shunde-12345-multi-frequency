import type { JSX } from "react";
import type { SignalTone } from "./signalState";

interface SignalLightProps {
  tone: SignalTone;
  label: string;
  value?: string | number;
  detail?: string;
  compact?: boolean;
}

export function SignalLight({
  tone,
  label,
  value,
  detail,
  compact = false,
}: SignalLightProps): JSX.Element {
  return (
    <div className={`signal-light signal-light--${tone}${compact ? " signal-light--compact" : ""}`}>
      <span className="signal-light__bulb" aria-hidden="true" />
      <span className="signal-light__copy">
        <span className="signal-light__label">{label}</span>
        {value !== undefined ? <strong className="signal-light__value">{value}</strong> : null}
        {detail ? <span className="signal-light__detail">{detail}</span> : null}
      </span>
    </div>
  );
}
