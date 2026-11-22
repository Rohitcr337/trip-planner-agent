import { useId, useState } from "react";
import { Check, Search } from "lucide-react";

function fold(text) {
  return text.trim().toLocaleLowerCase();
}

export default function DestinationCombobox({ id, names, value, onChange, invalid = false, describedBy, inputClassName = "" }) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const baseId = useId();
  const listboxId = `${baseId}-listbox`;
  const messageId = `${baseId}-no-match`;

  const typed = fold(query);
  const matches = typed && query !== value ? names.filter((name) => fold(name).includes(typed)) : names;
  const noMatch = matches.length === 0;
  const shown = noMatch ? names : matches;
  const activeId = open && active >= 0 && active < shown.length ? `${baseId}-option-${active}` : undefined;

  const choose = (name) => {
    setQuery(name);
    onChange(name);
    setOpen(false);
    setActive(-1);
  };

  const handleInput = (event) => {
    const text = event.target.value;
    setQuery(text);
    setOpen(true);
    setActive(-1);
    onChange(names.find((name) => fold(name) === fold(text)) ?? "");
  };

  const handleKeyDown = (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!shown.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      if (!open) {
        setOpen(true);
        setActive(step === 1 ? 0 : shown.length - 1);
        return;
      }
      setActive((current) => current < 0 ? (step === 1 ? 0 : shown.length - 1) : (current + step + shown.length) % shown.length);
    } else if (event.key === "Enter" && open && activeId) {
      event.preventDefault();
      choose(shown[active]);
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      setActive(-1);
    }
  };

  const status = !open ? "" : noMatch
    ? `That destination isn't available yet. ${names.length} available destinations listed.`
    : `${shown.length} ${shown.length === 1 ? "destination" : "destinations"} available.`;

  return (
    <div className="relative mt-2">
      <Search aria-hidden="true" className="pointer-events-none absolute top-3.5 left-3 size-4 text-text-muted" />
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        spellCheck={false}
        placeholder="Search a destination"
        value={query}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          setOpen(false);
          setActive(-1);
        }}
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-invalid={invalid}
        aria-describedby={[open && noMatch && messageId, describedBy].filter(Boolean).join(" ") || undefined}
        className={`${inputClassName} pl-9`}
      />
      <p aria-live="polite" aria-atomic="true" className="sr-only">{status}</p>
      {open && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 animate-enter overflow-hidden rounded-control border border-border-strong bg-surface shadow-2 motion-reduce:animate-fade">
          {noMatch && (
            <p id={messageId} className="border-b border-border px-3 py-2.5 text-small text-text-muted">
              That destination isn't available yet
            </p>
          )}
          <ul id={listboxId} role="listbox" aria-label="Destinations" className="max-h-64 overflow-y-auto py-1">
            {shown.map((name, index) => {
              const selected = name === value;
              return (
                <li
                  key={name}
                  id={`${baseId}-option-${index}`}
                  role="option"
                  aria-selected={selected}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(name)}
                  onMouseMove={() => setActive(index)}
                  className={`mx-1 flex min-h-11 cursor-pointer items-center justify-between gap-2 rounded-tag px-3 text-body text-text ${index === active ? "bg-primary-soft outline-2 -outline-offset-2 outline-primary" : ""}`}
                >
                  <span className={selected ? "font-semibold" : undefined}>{name}</span>
                  {selected && <Check aria-hidden="true" className="size-4 shrink-0 text-primary" />}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
