import { useState } from 'react';

import { MilestoneChip } from '@/components/learn/components';
import { MODULES } from '@/components/learn/content';

export default function Learn() {
    const [activeId, setActiveId] = useState(MODULES[0].id);
    const active = MODULES.find((m) => m.id === activeId) ?? MODULES[0];

    return (
        <div className="learn-layout">
            <nav className="learn-rail" aria-label="Course modules">
                {MODULES.map((m) => (
                    <button
                        key={m.id}
                        type="button"
                        className={m.id === activeId ? 'active' : ''}
                        onClick={() => setActiveId(m.id)}
                    >
                        <span>{m.navLabel}</span>
                        <MilestoneChip status={m.status} />
                    </button>
                ))}
            </nav>
            <div className="learn-pane">
                <div className="learn-head">
                    <h2>{active.heading}</h2>
                    <span className="learn-tag">{active.tag}</span>
                </div>
                {active.body}
            </div>
        </div>
    );
}
