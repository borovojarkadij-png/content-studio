import { useEffect, useRef, type ReactNode } from "react";
import type { Tone } from "./studio";

const paths: Record<string, ReactNode> = {
  overview: (
    <>
      <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-8H9v8H4a1 1 0 0 1-1-1Z" />
    </>
  ),
  inbox: (
    <>
      <path d="M5 4h14l3 11v5H2v-5Z" />
      <path d="M2 15h6l2 3h4l2-3h6M8 8h8M9 11h6" />
    </>
  ),
  donors: (
    <>
      <path d="M4 15c-2-7 2-10 8-6 6-4 10-1 8 6l-8 4Z" />
      <path d="M6 18H3v4h18v-4h-3" />
    </>
  ),
  channels: (
    <>
      <path d="m22 2-7 20-4-9-9-4Z M22 2 11 13" />
    </>
  ),
  connections: (
    <>
      <path d="m10 14 4-4m-5 7-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m0-1 2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" />
    </>
  ),
  planner: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M7 2v6m10-6v6M3 11h18M7 15h2m4 0h3" />
    </>
  ),
  accounts: (
    <>
      <circle cx="10" cy="7" r="4" />
      <path d="M2 21v-3c0-5 16-5 16 0v3Zm15-18a4 4 0 0 1 0 8m3 3c3 1 3 3 3 7" />
    </>
  ),
  settings: (
    <>
      <path d="m9 3 1-2h4l1 2 3 1 2 3-1 2v4l1 2-2 3-3 1-1 2h-4l-1-2-3-1-2-3 1-2V9L4 7l2-3Z" />
      <circle cx="12" cy="11" r="3" />
    </>
  ),
  search: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="m15 15 6 6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m7 12 3 3 7-7" />
    </>
  ),
  download: (
    <>
      <path d="M12 2v13m-5-5 5 5 5-5M3 15v6h18v-6" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V3m-5 5 5-5 5 5M3 15v6h18v-6" />
    </>
  ),
  plus: (
    <>
      <path d="M12 4v16M4 12h16" />
    </>
  ),
  close: (
    <>
      <path d="m5 5 14 14M19 5 5 19" />
    </>
  ),
  bell: (
    <>
      <path d="M4 18h16l-3-4V9a5 5 0 0 0-10 0v5Zm5 3h6M12 2v2" />
    </>
  ),
  shield: (
    <>
      <path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  spark: (
    <>
      <path d="m12 3 3 6 6 3-6 3-3 6-3-6-6-3 6-3ZM21 1v5m-2-3h5" />
    </>
  ),
  chart: (
    <>
      <path d="M4 21V11m8 10V3m8 18V7" />
    </>
  ),
  more: (
    <>
      <circle cx="12" cy="4" r="1" />
      <circle cx="12" cy="12" r="1" />
      <circle cx="12" cy="20" r="1" />
    </>
  ),
  moon: (
    <>
      <path d="M20 15A9 9 0 0 1 9 3a9 9 0 1 0 11 12Z" />
    </>
  ),
  arrow: (
    <>
      <path d="M3 12h18m-6-6 6 6-6 6" />
    </>
  ),
  edit: (
    <>
      <path d="m4 16 12-12 4 4L8 20l-5 1Zm10-10 4 4" />
    </>
  ),
  pause: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9 8v8m6-8v8" />
    </>
  ),
};
export function Icon({ name, size = 22 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] ?? paths.channels}
    </svg>
  );
}

export function Artwork({
  kind,
  large = false,
}: {
  kind: string;
  large?: boolean;
}) {
  return (
    <span
      className={`artwork art-${kind} ${large ? "large" : ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 120 90">
        {["mountain", "mars", "forest"].includes(kind) ? (
          <>
            <circle cx="95" cy="18" r="10" fill="var(--art-sun)" />
            <path
              d="m0 72 32-42 28 30 30-45 30 52v23H0Z"
              fill="var(--art-back)"
            />
            <path d="m0 88 45-48 22 33 15-19 38 36Z" fill="var(--art-front)" />
            {kind === "forest" &&
              [12, 30, 75, 96].map((x) => (
                <path
                  key={x}
                  d={`m${x} 15-15 48h30Zm0 55v15`}
                  fill="#238c70"
                  stroke="#124b45"
                />
              ))}
          </>
        ) : kind === "space" ? (
          <>
            <ellipse
              cx="60"
              cy="45"
              rx="47"
              ry="13"
              transform="rotate(-35 60 45)"
              stroke="#a584fb"
              strokeWidth="12"
              fill="none"
              opacity=".7"
            />
            <circle cx="60" cy="45" r="14" fill="#f3c8ff" />
            <circle cx="18" cy="15" r="2" fill="#fff" />
            <circle cx="104" cy="72" r="2" fill="#fff" />
          </>
        ) : kind === "cat" ? (
          <>
            <path
              d="m32 32-5-25 25 15 17 0L94 7l-5 25c21 35-4 51-30 51S13 67 32 32"
              fill="#c99a67"
            />
            <path
              d="m38 53 8-4 8 4m12 0 8-4 8 4"
              stroke="#233346"
              strokeWidth="4"
              fill="none"
            />
            <path d="m56 64 6 5 6-5" fill="#684646" />
          </>
        ) : kind === "sun" ? (
          <>
            <circle cx="60" cy="40" r="22" fill="#ffce63" />
            <path
              d="M50 62h20v14H50m10-58V5M28 38H12m96 0H92"
              stroke="#ffd57a"
              strokeWidth="5"
            />
          </>
        ) : kind === "atom" ? (
          <>
            <circle cx="60" cy="45" r="7" fill="#40e8f0" />
            {[0, 60, 120].map((angle) => (
              <ellipse
                key={angle}
                cx="60"
                cy="45"
                rx="39"
                ry="15"
                transform={`rotate(${angle} 60 45)`}
                stroke="#58d7ff"
                strokeWidth="3"
                fill="none"
              />
            ))}
          </>
        ) : (
          <>
            <rect
              x="24"
              y="12"
              width="72"
              height="65"
              rx="9"
              fill="#175b82"
              stroke="#50d4fb"
              strokeWidth="2"
            />
            <path
              d="m37 33 12 9-12 9m22 9h21"
              stroke="#98eaff"
              strokeWidth="4"
              fill="none"
            />
          </>
        )}
      </svg>
    </span>
  );
}
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`panel ${className}`}>{children}</section>;
}
export function Status({ value }: { value: string }) {
  const tone = ["Активен", "Готово"].includes(value)
    ? "green"
    : ["Ошибка", "Отклонён"].includes(value)
      ? "red"
      : ["Новый", "Требует 2FA"].includes(value)
        ? "violet"
        : ["На проверке", "Ожидает входа"].includes(value)
          ? "orange"
          : "muted";
  return (
    <span className={`status ${tone}`}>
      <i />
      {value}
    </span>
  );
}
export function PanelTitle({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: string;
  children?: ReactNode;
}) {
  return (
    <div className="panel-title">
      <h2>
        {icon && <Icon name={icon} />}
        {title}
      </h2>
      {children}
    </div>
  );
}
export function Search({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="search">
      <Icon name="search" size={19} />
      <input
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
export function Metric({
  title,
  value,
  icon,
  tone,
  detail,
}: {
  title: string;
  value: number;
  icon: string;
  tone: Tone;
  detail?: string;
}) {
  return (
    <Panel className="metric">
      <span className={`metric-icon ${tone}`}>
        <Icon name={icon} size={32} />
      </span>
      <div>
        <span>{title}</span>
        <b>{value}</b>
        <small>{detail ?? "DEMO · текущая очередь"}</small>
      </div>
    </Panel>
  );
}
export function Toggle({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="toggle-row">
      <span>{label}</span>
      <input
        role="switch"
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
      />
      <i />
    </label>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <p
      className={`notice ${error ? "error" : ""}`}
      role={error ? "alert" : "status"}
    >
      {children}
    </p>
  );
}
export function Unavailable({ title }: { title: string }) {
  return (
    <Panel>
      <div className="empty-state">
        <Icon name="connections" size={32} />
        <h2>{title}</h2>
        <p>
          Для этого раздела пока нет рабочего API. Включите DEMO в верхней
          панели, чтобы посмотреть интерфейс и проверить настройки.
        </p>
      </div>
    </Panel>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const prior = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("button, input, textarea")?.focus();
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]',
        ) ?? [],
      );
      const first = focusable[0],
        last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", listener);
    return () => {
      document.removeEventListener("keydown", listener);
      prior?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <PanelTitle title={title}>
          <button
            className="icon-button"
            aria-label="Закрыть"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        </PanelTitle>
        {children}
      </div>
    </div>
  );
}
