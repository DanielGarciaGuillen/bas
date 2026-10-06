import { describe, expect, it } from 'vitest';

import { formatValue, protocolFor } from './points';

describe('protocolFor', () => {
    it('maps known devices to the protocol that explains them', () => {
        expect(protocolFor('meter-1')).toBe('Modbus TCP');
        expect(protocolFor('ahu-1')).toBe('BACnet/IP');
    });

    it('falls back to an em dash for an unknown device', () => {
        expect(protocolFor('vav-101')).toBe('—');
    });
});

describe('formatValue', () => {
    it('renders null as an em dash', () => {
        expect(
            formatValue({
                id: 'x',
                device: 'x',
                name: 'x',
                value: null,
                units: null,
                status: 'fault'
            })
        ).toBe('—');
    });

    it('renders a number with locale separators', () => {
        expect(
            formatValue({
                id: 'x',
                device: 'x',
                name: 'x',
                value: 1234.5,
                units: 'kW',
                status: 'ok'
            })
        ).toBe((1234.5).toLocaleString());
    });

    it('passes a string value through unchanged', () => {
        expect(
            formatValue({
                id: 'x',
                device: 'x',
                name: 'x',
                value: 'active',
                units: null,
                status: 'ok'
            })
        ).toBe('active');
    });
});
