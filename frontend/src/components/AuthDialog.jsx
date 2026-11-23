import { useEffect, useId, useRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { loginAccount, registerAccount } from "../api.js";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const inputClass =
  "block min-h-11 w-full rounded-control border border-border bg-surface px-3 text-body text-text transition-colors duration-(--duration-press) ease-standard hover:border-text focus:border-primary";

function focusableItems(node) {
  if (!node) return [];
  return [...node.querySelectorAll("button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])")];
}

export function publicAuthError(result, email) {
  if (result?.status === 429) return "Too many attempts. Try again later.";
  if (result?.status === 401) return "Incorrect email or password.";
  if (result?.status === 409) return "Unable to register with those details.";
  if (result?.status === 422) return "Check the email and password and try again.";
  return "Could not sign in or create an account. Please try again.";
}

export default function AuthDialog({ open, notice = "", onClose, onAuthenticated }) {
  const titleId = useId();
  const errorId = useId();
  const hintId = useId();
  const dialogRef = useRef(null);
  const emailRef = useRef(null);
  const attempt = useRef(0);
  const [mode, setMode] = useState("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    setPassword("");
    setError("");
    setShowPassword(false);
    setSubmitting(false);
    emailRef.current?.focus();
    return () => {
      attempt.current += 1;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, [open]);

  if (!open) return null;

  function onKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusableItems(dialogRef.current);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function switchMode(next) {
    attempt.current += 1;
    setSubmitting(false);
    setMode(next);
    setError("");
    setShowPassword(false);
  }

  async function onSubmit(event) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 10) {
      setError("Use 10 or more characters.");
      return;
    }
    if (submitting) return;
    const currentAttempt = ++attempt.current;
    setSubmitting(true);
    setError("");
    const result = mode === "create" ? await registerAccount(trimmed, password) : await loginAccount(trimmed, password);
    if (currentAttempt !== attempt.current) return;
    setSubmitting(false);
    if (!result?.ok || !result.data?.token || !result.data?.user?.email) {
      setError(publicAuthError(result, trimmed));
      return;
    }
    setPassword("");
    onAuthenticated(result.data);
  }

  const title = mode === "create" ? "Create account" : "Sign in";
  const describedBy = [hintId, error ? errorId : ""].filter(Boolean).join(" ");

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-text/40 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        className="max-h-[90dvh] w-full max-w-[440px] overflow-y-auto rounded-card bg-surface p-4 shadow-3 sm:p-6"
      >
        <h2 id={titleId} className="text-h3 text-text">{title}</h2>
        {notice && <p role="alert" className="mt-3 text-small text-danger">{notice}</p>}
        <form className="mt-4 space-y-4" onSubmit={onSubmit} noValidate>
          <div>
            <label htmlFor="account-email" className="text-small font-semibold text-text">Email</label>
            <input
              ref={emailRef}
              id="account-email"
              name="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label htmlFor="account-password" className="text-small font-semibold text-text">Password</label>
            <div className="mt-1 flex gap-2">
              <input
                id="account-password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "create" ? "new-password" : "current-password"}
                value={password}
                aria-describedby={describedBy}
                onChange={(event) => setPassword(event.target.value)}
                className={inputClass}
              />
              <button
                type="button"
                aria-pressed={showPassword}
                onClick={() => setShowPassword((current) => !current)}
                className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-control border border-border-strong bg-surface px-3 text-small font-semibold text-text hover:bg-surface-muted"
              >
                {showPassword ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
                {showPassword ? "Hide password" : "Show password"}
              </button>
            </div>
            <p id={hintId} className="mt-2 text-small text-text-muted">10 or more characters</p>
          </div>
          {error && <p id={errorId} role="alert" className="text-small text-danger">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-control bg-primary px-4 text-small font-semibold text-on-primary hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted"
          >
            {submitting ? (mode === "create" ? "Creating account..." : "Signing in...") : title}
          </button>
        </form>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {mode === "create" ? (
            <button type="button" onClick={() => switchMode("sign-in")} className="min-h-11 rounded-control px-2 text-small font-semibold text-primary underline underline-offset-2">
              Sign in
            </button>
          ) : (
            <button type="button" onClick={() => switchMode("create")} className="min-h-11 rounded-control px-2 text-small font-semibold text-primary underline underline-offset-2">
              Create an account
            </button>
          )}
          <button type="button" onClick={onClose} className="ml-auto min-h-11 rounded-control px-2 text-small font-semibold text-text">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
