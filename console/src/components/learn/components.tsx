import { type ReactNode, useState } from 'react';

export function MilestoneChip({ status }: { status: 'done' | 'next' | 'locked' }) {
    const label = status === 'done' ? 'done' : status === 'next' ? 'up next' : 'locked';
    return <span className={`m-chip m-chip-${status}`}>{label}</span>;
}

export function ConceptCard({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div className="concept-card">
            <h4>{title}</h4>
            <div>{children}</div>
        </div>
    );
}

export function FieldNote({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div className="field-note">
            <h4>Field note &middot; {title}</h4>
            <div>{children}</div>
        </div>
    );
}

export function FlashCard({ q, a }: { q: ReactNode; a: ReactNode }) {
    const [open, setOpen] = useState(false);
    return (
        <div
            className={`flashcard${open ? ' open' : ''}`}
            role="button"
            tabIndex={0}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setOpen((v) => !v);
                }
            }}
        >
            <div className="flashcard-q">{q}</div>
            {open && <div className="flashcard-a">{a}</div>}
            {!open && <div className="flashcard-hint">Click to reveal</div>}
        </div>
    );
}
