import { useState } from 'react';

import AccessControlPanel from '@/components/AccessControlPanel';
import AhuPanel from '@/components/AhuPanel';
import AlarmsPanel from '@/components/AlarmsPanel';
import FirePanelAnnunciator from '@/components/FirePanelAnnunciator';
import Learn from '@/components/Learn';
import Points from '@/components/Points';
import Overview from '@/components/Overview';
import TrendsPanel from '@/components/TrendsPanel';
import WorkOrdersPanel from '@/components/WorkOrdersPanel';

type Tab = 'overview' | 'ahu' | 'fire' | 'access' | 'alarms' | 'trends' | 'points' | 'learn';

const TAB_LABEL: Record<Tab, string> = {
    overview: 'Overview',
    ahu: 'AHU-1',
    fire: 'Fire Panel',
    access: 'Access',
    alarms: 'Alarms',
    trends: 'Trends',
    points: 'Points',
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
            {tab === 'fire' && <FirePanelAnnunciator />}
            {tab === 'access' && <AccessControlPanel />}
            {tab === 'alarms' && (
                <>
                    <AlarmsPanel />
                    <WorkOrdersPanel />
                </>
            )}
            {tab === 'trends' && <TrendsPanel />}
            {tab === 'points' && <Points />}
            {tab === 'learn' && <Learn />}
        </div>
    );
}
