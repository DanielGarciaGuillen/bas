import type { Point } from '@/lib/api';
import { numericValue, pointById } from '@/lib/points';

interface AhuGraphicProps {
    points: Point[];
}

function fmt(value: number | null, digits = 1): string {
    return value === null ? '—' : value.toFixed(digits);
}

export default function AhuGraphic({ points }: AhuGraphicProps) {
    const oat = numericValue(points, 'ahu-1.oat');
    const rat = numericValue(points, 'ahu-1.rat');
    const sat = numericValue(points, 'ahu-1.sat');
    const satSetpoint = numericValue(points, 'ahu-1.sat_setpoint');
    const oaDamper = numericValue(points, 'ahu-1.oa_damper');
    const coolingValve = numericValue(points, 'ahu-1.cooling_valve');
    const heatingValve = numericValue(points, 'ahu-1.heating_valve');
    const fanSpeed = numericValue(points, 'ahu-1.fan_speed');
    const fanStatus = pointById(points, 'ahu-1.fan_status')?.value === 'active';
    const occupancyMode = pointById(points, 'ahu-1.occupancy_mode')?.value ?? '—';

    return (
        <div className="ahu-graphic">
            <svg viewBox="0 0 760 220" role="img" aria-label="AHU-1 schematic">
                <line x1="20" y1="110" x2="740" y2="110" className="ahu-duct" />

                {/* Outside air */}
                <text x="20" y="40" className="ahu-label">
                    Outside Air
                </text>
                <text x="20" y="58" className="ahu-value">
                    {fmt(oat)} °C
                </text>

                {/* OA damper */}
                <rect x="110" y="85" width="60" height="50" className="ahu-box" />
                <text x="140" y="155" className="ahu-label" textAnchor="middle">
                    OA Damper
                </text>
                <text x="140" y="113" className="ahu-value" textAnchor="middle">
                    {fmt(oaDamper, 0)}%
                </text>
                <rect
                    x="112"
                    y={135 - Math.max(0, Math.min(100, oaDamper ?? 0)) * 0.44}
                    width="56"
                    height={Math.max(0, Math.min(100, oaDamper ?? 0)) * 0.44}
                    className="ahu-damper-fill"
                />

                {/* Filter */}
                <rect x="220" y="85" width="30" height="50" className="ahu-filter" />
                <text x="235" y="155" className="ahu-label" textAnchor="middle">
                    Filter
                </text>

                {/* Cooling coil */}
                <rect x="300" y="85" width="40" height="50" className="ahu-coil ahu-coil-cool" />
                <text x="320" y="155" className="ahu-label" textAnchor="middle">
                    Cooling
                </text>
                <text x="320" y="113" className="ahu-value" textAnchor="middle">
                    {fmt(coolingValve, 0)}%
                </text>

                {/* Heating coil */}
                <rect x="380" y="85" width="40" height="50" className="ahu-coil ahu-coil-heat" />
                <text x="400" y="155" className="ahu-label" textAnchor="middle">
                    Heating
                </text>
                <text x="400" y="113" className="ahu-value" textAnchor="middle">
                    {fmt(heatingValve, 0)}%
                </text>

                {/* Fan */}
                <g transform="translate(480,110)">
                    <circle r="34" className="ahu-fan-housing" />
                    <g className={fanStatus ? 'ahu-fan-blades ahu-fan-spin' : 'ahu-fan-blades'}>
                        <rect x="-3" y="-28" width="6" height="56" />
                        <rect x="-28" y="-3" width="56" height="6" />
                        <rect x="-20" y="-20" width="6" height="40" transform="rotate(45)" />
                        <rect x="-20" y="-20" width="6" height="40" transform="rotate(-45)" />
                    </g>
                </g>
                <text x="480" y="160" className="ahu-label" textAnchor="middle">
                    Supply Fan
                </text>
                <text x="480" y="46" className="ahu-value" textAnchor="middle">
                    {fanStatus ? 'RUNNING' : 'OFF'} · {fmt(fanSpeed, 0)}%
                </text>

                {/* Supply duct / SAT */}
                <text x="560" y="40" className="ahu-label">
                    Supply Air
                </text>
                <text x="560" y="58" className="ahu-value">
                    {fmt(sat)} °C → sp {fmt(satSetpoint)} °C
                </text>
                <text x="560" y="150" className="ahu-label">
                    Return Air
                </text>
                <text x="560" y="168" className="ahu-value">
                    {fmt(rat)} °C
                </text>

                <text x="20" y="200" className="ahu-label">
                    Occupancy: <tspan className="ahu-value">{occupancyMode}</tspan>
                </text>
            </svg>
        </div>
    );
}
