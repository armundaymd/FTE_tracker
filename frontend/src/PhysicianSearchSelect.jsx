import { useEffect, useMemo, useRef, useState } from "react";

function formatPhysicianName(p) {
  if (!p) return "";
  const type = p.provider_type?.name ? ` (${p.provider_type.name})` : "";
  return `${p.last_name}, ${p.first_name}${type}`;
}

/**
 * Typeahead replacement for a plain <select> bound to a physician_id.
 * Reuses the app's existing .field input styling (it's a descendant
 * selector, so it applies regardless of this wrapper div) — only the
 * dropdown itself needs its own .psearch-* rules, added alongside the
 * rest of App.jsx's CSS.
 */
export default function PhysicianSearchSelect({
  physicians,
  value,
  onChange,
  placeholder = "Search providers…",
  disabled = false,
  style,
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);

  const selected = useMemo(
    () => physicians.find(p => p.id === value) || null,
    [physicians, value]
  );

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return physicians;
    return physicians.filter(p => `${p.first_name} ${p.last_name}`.toLowerCase().includes(q));
  }, [physicians, query]);

  useEffect(() => { setActiveIndex(0); }, [query, open]);

  const selectPhysician = (p) => {
    onChange(p.id);
    setQuery("");
    setOpen(false);
  };

  const handleFocus = () => {
    setQuery("");
    setOpen(true);
  };

  const handleBlur = () => {
    setOpen(false);
    setQuery("");
  };

  const handleKeyDown = (e) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[activeIndex]) selectPhysician(results[activeIndex]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setQuery("");
      inputRef.current?.blur();
    }
  };

  const displayValue = open ? query : formatPhysicianName(selected);

  return (
    <div className="psearch" style={style}>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        value={displayValue}
        placeholder={placeholder}
        disabled={disabled}
        onChange={e => setQuery(e.target.value)}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <div className="psearch-dropdown">
          {results.length === 0 ? (
            <div className="psearch-empty">No matching providers</div>
          ) : results.map((p, i) => (
            <div
              key={p.id}
              className={`psearch-option ${i === activeIndex ? "active" : ""} ${p.id === value ? "selected" : ""}`}
              onMouseDown={e => { e.preventDefault(); selectPhysician(p); }}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {formatPhysicianName(p)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
