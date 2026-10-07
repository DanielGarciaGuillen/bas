import type { HistorySample } from '@/lib/api';

interface LineChartProps {
    samples: HistorySample[];
    units: string | null;
}

const WIDTH = 760;
const HEIGHT = 220;
const PAD_X = 50;
const PAD_Y = 20;

export default function LineChart({ samples, units }: LineChartProps) {
    if (samples.length < 2) {
        return (
            <div className="trend-empty">
                Not enough samples yet — leave this tab open for a few supervisor ticks.
            </div>
        );
    }

    const values = samples.map((s) => s.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const times = samples.map((s) => new Date(s.timestamp).getTime());
    const t0 = times[0];
    const t1 = times[times.length - 1];
    const tRange = t1 - t0 || 1;

    const points = samples.map((s, i) => {
        const x = PAD_X + ((times[i] - t0) / tRange) * (WIDTH - PAD_X * 2);
        const y = PAD_Y + (1 - (s.value - min) / range) * (HEIGHT - PAD_Y * 2);
        return [x, y] as const;
    });

    const linePath = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ');
    const areaPath = `${linePath} L${points[points.length - 1][0]},${HEIGHT - PAD_Y} L${points[0][0]},${HEIGHT - PAD_Y} Z`;
    const last = samples[samples.length - 1];

    return (
        <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Trend chart"
            className="trend-chart"
        >
            <line
                x1={PAD_X}
                y1={HEIGHT - PAD_Y}
                x2={WIDTH - PAD_X}
                y2={HEIGHT - PAD_Y}
                className="trend-axis"
            />
            <text x={PAD_X} y={PAD_Y - 4} className="trend-label">
                {max.toFixed(1)} {units ?? ''}
            </text>
            <text x={PAD_X} y={HEIGHT - PAD_Y + 16} className="trend-label">
                {min.toFixed(1)} {units ?? ''}
            </text>
            <path d={areaPath} className="trend-area" />
            <path d={linePath} className="trend-line" />
            <circle
                cx={points[points.length - 1][0]}
                cy={points[points.length - 1][1]}
                r="4"
                className="trend-dot"
            />
            <text
                x={points[points.length - 1][0]}
                y={points[points.length - 1][1] - 10}
                textAnchor="end"
                className="trend-value"
            >
                {last.value.toFixed(1)} {units ?? ''}
            </text>
        </svg>
    );
}
