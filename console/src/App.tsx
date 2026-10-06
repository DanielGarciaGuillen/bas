import { useState } from 'react';

import Learn from '@/components/Learn';
import LivePoints from '@/components/LivePoints';

type Tab = 'live' | 'learn';

export default function App() {
    const [tab, setTab] = useState<Tab>('live');

    return (
        <div className="shell">
            <header className="top">
                <div>
                    <span className="eyebrow">BuildingOps Lab</span>
                    <h1>{tab === 'live' ? 'Live Points' : 'Field Course'}</h1>
                </div>
                <div className="tabs" role="tablist">
                    <button
                        role="tab"
                        aria-selected={tab === 'live'}
                        className={tab === 'live' ? 'active' : ''}
                        onClick={() => setTab('live')}
                    >
                        Live
                    </button>
                    <button
                        role="tab"
                        aria-selected={tab === 'learn'}
                        className={tab === 'learn' ? 'active' : ''}
                        onClick={() => setTab('learn')}
                    >
                        Learn
                    </button>
                </div>
            </header>

            {tab === 'live' ? <LivePoints /> : <Learn />}
        </div>
    );
}
