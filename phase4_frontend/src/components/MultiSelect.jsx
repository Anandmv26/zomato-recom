import { useState, useRef, useEffect } from 'react';

/**
 * MultiSelect — A custom multi-select dropdown with tag pills and search.
 *
 * Props:
 *   id          — id for the toggle button (for labels / testing)
 *   options     — string[]
 *   selected    — string[]
 *   onChange    — (newSelected: string[]) => void
 *   placeholder — string shown when nothing is selected
 *   label       — label text shown above
 */
export default function MultiSelect({ id, options = [], selected = [], onChange, placeholder = 'Select…', label }) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const wrapperRef = useRef(null);

    // Close on outside click
    useEffect(() => {
        function onOutside(e) {
            if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
                setOpen(false);
                setSearch('');
            }
        }
        document.addEventListener('mousedown', onOutside);
        return () => document.removeEventListener('mousedown', onOutside);
    }, []);

    function toggle(option) {
        onChange(selected.includes(option)
            ? selected.filter(s => s !== option)
            : [...selected, option]
        );
    }

    function removeTag(option, e) {
        e.stopPropagation();
        onChange(selected.filter(s => s !== option));
    }

    function clearAll(e) {
        e.stopPropagation();
        onChange([]);
    }

    const filtered = options.filter(o =>
        o.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="ms-wrapper" ref={wrapperRef}>
            {label && (
                <span className="group-label">{label}</span>
            )}

            {/* Trigger */}
            <div
                id={id}
                className={`ms-trigger ${open ? 'ms-open' : ''}`}
                onClick={() => setOpen(o => !o)}
                role="combobox"
                aria-expanded={open}
                aria-haspopup="listbox"
                tabIndex={0}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setOpen(o => !o); }}
            >
                {selected.length === 0 ? (
                    <span className="ms-placeholder">{placeholder}</span>
                ) : (
                    <div className="ms-tags">
                        {selected.slice(0, 3).map(s => (
                            <span key={s} className="ms-tag">
                                {s}
                                <button
                                    type="button"
                                    className="ms-tag-remove"
                                    onClick={e => removeTag(s, e)}
                                    aria-label={`Remove ${s}`}
                                >×</button>
                            </span>
                        ))}
                        {selected.length > 3 && (
                            <span className="ms-tag ms-tag-count">+{selected.length - 3}</span>
                        )}
                    </div>
                )}
                <div className="ms-controls">
                    {selected.length > 0 && (
                        <button type="button" className="ms-clear" onClick={clearAll} aria-label="Clear all">✕</button>
                    )}
                    <span className={`ms-chevron ${open ? 'up' : ''}`}>▾</span>
                </div>
            </div>

            {/* Dropdown */}
            {open && (
                <div className="ms-dropdown" role="listbox" aria-multiselectable="true">
                    <div className="ms-search-wrap">
                        <input
                            className="ms-search"
                            type="text"
                            placeholder="Search…"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            onClick={e => e.stopPropagation()}
                            autoFocus
                        />
                    </div>
                    <ul className="ms-list">
                        {filtered.length === 0 && (
                            <li className="ms-no-results">No results for "{search}"</li>
                        )}
                        {filtered.map(option => {
                            const checked = selected.includes(option);
                            return (
                                <li
                                    key={option}
                                    className={`ms-option ${checked ? 'selected' : ''}`}
                                    role="option"
                                    aria-selected={checked}
                                    onClick={() => toggle(option)}
                                >
                                    <span className="ms-checkbox">{checked ? '✓' : ''}</span>
                                    {option}
                                </li>
                            );
                        })}
                    </ul>
                    {selected.length > 0 && (
                        <div className="ms-footer">
                            <span>{selected.length} selected</span>
                            <button type="button" onClick={clearAll}>Clear all</button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
