import { useState } from 'react';

import AhuPanel from '@/components/AhuPanel';
import Learn from '@/components/Learn';
import Operations from '@/components/Operations';
import Overview from '@/components/Overview';

type Tab = 'overview' | 'ahu' | 'operations' | 'learn';

const TAB_LABEL: Record<Tab, string> = {
    overview: 'Overview',
    ahu: 'AHU-1',
    operations: 'Operations',
    learn: 'Build Notes'
};

export default function App() {
    const [tab, setTab] = useState<Tab>('overview');

    return (
        <div className="shell">
            <header className="top">
                <div>
                    <span className="eyebrow">BuildingOps Lab</span>
                    <h1>{TAB_LABEL[tab]}</h1>
                </div>
                <div className="tabs" role="tablist">
                    {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
                        <button
                            key={t}
                            role="tab"
                            aria-selected={tab === t}
                            className={tab === t ? 'active' : ''}
                            onClick={() => setTab(t)}
                        >
                            {t === 'learn' ? 'Notes' : TAB_LABEL[t]}
                        </button>
                    ))}
                </div>
            </header>

            {tab === 'overview' && <Overview />}
            {tab === 'ahu' && <AhuPanel />}
            {tab === 'operations' && <Operations />}
            {tab === 'learn' && <Learn />}
        </div>
    );
}
