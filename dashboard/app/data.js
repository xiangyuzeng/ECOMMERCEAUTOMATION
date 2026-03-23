'use client';

import { useState, useEffect, useCallback } from 'react';

const EMPTY = {
  competitors: [],
  keywords: [],
  ads: { search_term_summary: [], campaign_summary: [] },
  pricing: { scenarios: [], variants: [] },
  traffic: [],
  gapAnalysis: [],
};

export function useData() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fetched, setFetched] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/data', { cache: 'no-store' });
      const json = await res.json();
      if (json.exists === false) {
        setData(EMPTY);
      } else {
        setData({
          competitors: json.competitors || EMPTY.competitors,
          keywords: json.keywords || EMPTY.keywords,
          ads: json.ads || EMPTY.ads,
          pricing: json.pricing || EMPTY.pricing,
          traffic: json.traffic || EMPTY.traffic,
          gapAnalysis: json.gapAnalysis || EMPTY.gapAnalysis,
        });
      }
    } catch (err) {
      setError(err.message);
      setData(EMPTY);
    } finally {
      setLoading(false);
      setFetched(true);
    }
  }, []);

  useEffect(() => {
    if (!fetched) { fetchData(); }
  }, [fetched, fetchData]);

  return { ...data, loading, error, refresh: fetchData };
}
