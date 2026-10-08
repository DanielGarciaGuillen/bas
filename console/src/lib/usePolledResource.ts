import { useEffect, useRef, useState } from 'react';

export interface UsePolledResourceOptions {
    intervalMs: number;
    /** Shown via the returned `error` field when the fetcher throws. Omit to swallow
     * failures silently — several tabs rely on a summary elsewhere in the page and never
     * render their own error banner. */
    errorMessage?: string;
    /** Extra values that restart polling when they change (e.g. a selected point id and
     * time range) — same role as a useEffect dependency array. */
    deps?: readonly unknown[];
    /** Skip polling entirely while false, without unmounting the component. */
    enabled?: boolean;
}

export interface PolledResource<T> {
    data: T;
    error: string | null;
    updatedAt: Date | null;
    refresh: () => Promise<void>;
}

/**
 * Fetch-on-mount + setInterval polling with cleanup on unmount — the shape every console
 * tab used to hand-roll itself (8 near-identical copies as of M8). Extracted after the
 * pattern had already drifted twice on its own: two copies lost their own named interval
 * constant to a bare literal, and error handling diverged three ways (banner / silent
 * swallow / stale render) with nothing keeping them in sync. See docs/engineering-notes.md.
 */
export function usePolledResource<T>(
    fetcher: () => Promise<T>,
    initialData: T,
    { intervalMs, errorMessage, deps = [], enabled = true }: UsePolledResourceOptions
): PolledResource<T> {
    const [data, setData] = useState<T>(initialData);
    const [error, setError] = useState<string | null>(null);
    const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

    // Always the latest fetcher without making it a dependency itself — most callers
    // pass a fresh closure every render, and re-running the poll effect on every render
    // would defeat the interval entirely.
    const fetcherRef = useRef(fetcher);
    fetcherRef.current = fetcher;
    const errorMessageRef = useRef(errorMessage);
    errorMessageRef.current = errorMessage;

    async function poll(): Promise<void> {
        try {
            const next = await fetcherRef.current();
            setData(next);
            setError(null);
            setUpdatedAt(new Date());
        } catch {
            if (errorMessageRef.current) setError(errorMessageRef.current);
        }
    }

    useEffect(() => {
        if (!enabled) return;
        let cancelled = false;
        async function tick() {
            try {
                const next = await fetcherRef.current();
                if (cancelled) return;
                setData(next);
                setError(null);
                setUpdatedAt(new Date());
            } catch {
                if (!cancelled && errorMessageRef.current) setError(errorMessageRef.current);
            }
        }
        tick();
        const id = setInterval(tick, intervalMs);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [intervalMs, enabled, ...deps]);

    return { data, error, updatedAt, refresh: poll };
}
