import { describe, expect, it } from 'vitest';
import { DEFAULT_CRITERIA, matchSociety, priceFor } from './filters.js';

// A Delhi building (rent only, from an open dataset) and a Gurugram society (buy and rent) can share one map.
const delhi = { id: 'a1', name: 'Test Apartments', developer: '', locality: 'Rohini', kind: 'apartment', open_data: true, no_sale: true,
  amenities: [], unit_types: [{ bhk: 2, label: '2 BHK', bedrooms: [] }], prices: { 2: { rent: { median: 25000, n: 5 } } } };
const gurugram = { id: 's1', name: 'Test Estate', developer: 'X', locality: 'Sector 50', kind: 'apartment', amenities: [],
  unit_types: [{ bhk: 2, label: '2 BHK', bedrooms: [] }], prices: { 2: { buy: { median: 9000000, n: 3 }, rent: { median: 40000, n: 4 } } } };

describe('mixed Delhi and Gurugram data', () => {
  it('Rent mode: both cities match a 2 BHK search', () => {
    const c = { ...DEFAULT_CRITERIA, mode: 'rent', bhk: [2] };
    expect(matchSociety(delhi, c)).toBe('match');
    expect(matchSociety(gurugram, c)).toBe('match');
  });
  it('Buy mode: a building with no sale prices is "unknown", never a match', () => {
    const c = { ...DEFAULT_CRITERIA, mode: 'buy', bhk: [2] };
    expect(matchSociety(delhi, c)).toBe('unknown');
    expect(matchSociety(gurugram, c)).toBe('match');
  });
  it('an open-data entry with no price is "unknown" under a rent budget, not a match', () => {
    const unpriced = { ...delhi, id: 'a2', unit_types: [], prices: {} };
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent', maxRent: 20000 })).toBe('unknown');
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent', minRent: 10000 })).toBe('unknown');
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent' })).toBe('match'); // no budget: still shown normally
  });
  it('Gurugram behaviour is unchanged: an unpriced non-open-data society still passes a budget', () => {
    const unpriced = { ...gurugram, id: 's2', unit_types: [], prices: {} };
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent', maxRent: 20000 })).toBe('match');
  });
  it('chat advisor: a city filter keeps only that city, and leaves unlabelled societies alone', () => {
    const d = { ...delhi, city_label: 'Delhi' }, g = { ...gurugram, city_label: 'Gurugram' };
    const c = { ...DEFAULT_CRITERIA, mode: 'rent', city: 'Gurugram' };
    expect(matchSociety(d, c)).toBe('no');
    expect(matchSociety(g, c)).toBe('match');
    expect(matchSociety(delhi, c)).toBe('match'); // no city_label (single-city data): the filter does not apply
  });
  it('chat advisor: commute keeps buildings within the straight-line distance of the workplace', () => {
    const near = { ...gurugram, lat: 28.45, lng: 77.1 };
    const work = { lat: 28.452, lng: 77.098 };
    expect(matchSociety(near, { ...DEFAULT_CRITERIA, mode: 'rent', commute: { ...work, km: 1 } })).toBe('match');
    expect(matchSociety({ ...near, lat: 28.55 }, { ...DEFAULT_CRITERIA, mode: 'rent', commute: { ...work, km: 1 } })).toBe('no');
  });
  it('chat advisor: strictPrice makes any unpriced society unknown under a budget', () => {
    const unpriced = { ...gurugram, id: 's3', unit_types: [], prices: {} };
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent', maxRent: 20000, strictPrice: true })).toBe('unknown');
    expect(matchSociety(unpriced, { ...DEFAULT_CRITERIA, mode: 'rent', maxRent: 20000 })).toBe('match'); // the panel's own behaviour is unchanged
  });
  it('rent budget applies to Delhi rents', () => {
    expect(matchSociety(delhi, { ...DEFAULT_CRITERIA, mode: 'rent', maxRent: 20000 })).toBe('no');
    expect(priceFor(delhi, 'rent', [2]).value).toBe(25000);
  });
});
