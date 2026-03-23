'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import { useData } from './data';
import { FILE_GUIDE, METRIC_DEFINITIONS, DATA_FLOW } from './guideContent';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';

const TABS = [
  { key: 'control', zh: '控制中心' },
  { key: 'competitors', zh: '竞品分析' },
  { key: 'products', zh: '产品清单' },
  { key: 'keywords', zh: '词库整理' },
  { key: 'ads', zh: '广告指标监测' },
  { key: 'pricing', zh: '定价策略' },
  { key: 'traffic', zh: '流量入口' },
  { key: 'gap', zh: '关键词差距分析' },
];

const COLORS = ['#0365C0', '#1A365D', '#00A5A5', '#f59e0b', '#ef4444', '#22c55e', '#8b5cf6'];

const styles = {
  container: { maxWidth: 1400, margin: '0 auto', padding: '24px 16px' },
  header: {
    background: '#1A365D', color: '#fff', padding: '20px 24px', borderRadius: 12,
    marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  headerTitle: { fontSize: 22, fontWeight: 700, fontFamily: "'Noto Sans SC', sans-serif" },
  headerSub: { fontSize: 13, opacity: 0.8, marginTop: 4 },
  tabBar: {
    display: 'flex', gap: 4, marginBottom: 24, overflowX: 'auto',
    WebkitOverflowScrolling: 'touch',
    background: '#fff', borderRadius: 10, padding: 4,
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
  },
  tab: (active) => ({
    padding: '10px 18px', borderRadius: 8, cursor: 'pointer', border: 'none',
    background: active ? '#0365C0' : 'transparent',
    color: active ? '#fff' : '#6b7280',
    fontWeight: active ? 600 : 400, fontSize: 14, whiteSpace: 'nowrap',
    flexShrink: 0,
    transition: 'all 0.2s', fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
  }),
  card: {
    background: '#fff', borderRadius: 10, padding: 24, marginBottom: 20,
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
  },
  cardTitle: {
    fontSize: 16, fontWeight: 600, color: '#1A365D', marginBottom: 16,
    fontFamily: "'Noto Sans SC', sans-serif",
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th: {
    background: '#1F4E79', color: '#fff', padding: '10px 12px', textAlign: 'left',
    fontWeight: 600, fontSize: 12, fontFamily: "'Noto Sans SC', sans-serif",
    position: 'sticky', top: 0,
  },
  td: (alt) => ({
    padding: '8px 12px', borderBottom: '1px solid #e5e7eb',
    background: alt ? '#f8f9fb' : '#fff', fontSize: 13,
  }),
  badge: (type) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
    background: type === 'MISSING' ? '#fee2e2' : type === 'CATCHUP' ? '#fef3c7' : '#d1fae5',
    color: type === 'MISSING' ? '#dc2626' : type === 'CATCHUP' ? '#d97706' : '#059669',
  }),
  stat: {
    textAlign: 'center', padding: 16, background: '#f8f9fb', borderRadius: 8, flex: 1,
  },
  statVal: { fontSize: 24, fontWeight: 700, color: '#0365C0', fontFamily: "'JetBrains Mono', monospace" },
  statLabel: { fontSize: 12, color: '#6b7280', marginTop: 4, fontFamily: "'Noto Sans SC', sans-serif" },
  searchInput: {
    padding: '8px 14px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14,
    width: 300, outline: 'none', marginBottom: 16,
  },
  helpToggle: {
    background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6,
    padding: '6px 12px', fontSize: 12, color: '#0365C0', cursor: 'pointer',
    fontFamily: "'Noto Sans SC', sans-serif", marginBottom: 16,
  },
  helpPanel: {
    background: '#eff6ff', borderLeft: '3px solid #0365C0', borderRadius: 8,
    padding: 16, marginBottom: 20, fontSize: 13,
  },
  accordionHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    cursor: 'pointer', padding: '12px 16px', background: '#fff',
    borderLeft: '3px solid #0365C0', borderRadius: 8,
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)', marginBottom: 12,
  },
  accordionTitle: {
    fontSize: 15, fontWeight: 600, color: '#1A365D',
    fontFamily: "'Noto Sans SC', sans-serif",
  },
  guideStep: {
    display: 'flex', gap: 8, padding: '6px 0', fontSize: 13, color: '#374151',
  },
  guideStepNum: {
    width: 20, height: 20, borderRadius: '50%', background: '#0365C0',
    color: '#fff', fontSize: 11, display: 'flex', alignItems: 'center',
    justifyContent: 'center', flexShrink: 0, fontWeight: 600,
  },
  guideNote: {
    background: '#eff6ff', borderLeft: '3px solid #0365C0', borderRadius: 4,
    padding: '8px 12px', fontSize: 12, color: '#1e40af', marginTop: 8,
  },
};

function fmt(n, dec = 0) {
  if (n == null || isNaN(n)) return 'N/A';
  return Number(n).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return 'N/A';
  return (Number(n) * 100).toFixed(1) + '%';
}

function fmtUSD(n) {
  if (n == null || isNaN(n)) return 'N/A';
  return '$' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function GuideAccordion({ title, subtitle, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={styles.accordionHeader} onClick={() => setOpen(!open)}>
        <div>
          <span style={styles.accordionTitle}>{title}</span>
          {subtitle && <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 8 }}>{subtitle}</span>}
        </div>
        <span style={{ fontSize: 14, color: '#0365C0', fontWeight: 600 }}>{open ? '▾' : '▸'}</span>
      </div>
      {open && <div style={{ padding: '4px 0 8px 0' }}>{children}</div>}
    </div>
  );
}

function TabMetricHelp({ tabKey }) {
  const [open, setOpen] = useState(false);
  const info = METRIC_DEFINITIONS[tabKey];
  if (!info) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <button style={styles.helpToggle} onClick={() => setOpen(!open)}>
        {open ? '隐藏指标说明' : '查看指标说明'} {open ? '▾' : 'i'}
      </button>
      {open && (
        <div style={styles.helpPanel}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8, color: '#1A365D', fontFamily: "'Noto Sans SC', sans-serif" }}>
            {info.title} — {info.description}
          </div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
            数据来源: {info.sourceFiles.join(', ')}
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {info.metrics.map((m, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 13 }}>
                <span style={{ fontWeight: 600, color: '#1A365D', minWidth: 120, fontFamily: "'Noto Sans SC', sans-serif" }}>
                  {m.name}
                </span>
                <span style={{ color: '#6b7280', fontSize: 11, minWidth: 60 }}>{m.en}</span>
                <span style={{ color: '#374151' }}>{m.definition}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FileGuideSection() {
  const fileTagStyle = (source) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
    background: source === 'SellerSprite' ? '#dbeafe' : '#d1fae5',
    color: source === 'SellerSprite' ? '#1e40af' : '#065f46',
  });

  return (
    <div>
      {[FILE_GUIDE.sellerSprite, FILE_GUIDE.sellerCentral].map((group) => (
        <div key={group.label} style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1A365D', marginBottom: 12, fontFamily: "'Noto Sans SC', sans-serif" }}>
            <span style={fileTagStyle(group.label)}>{group.labelEn}</span>
            <span style={{ marginLeft: 8 }}>{group.files.length} 个文件类型</span>
          </div>
          {group.files.map((f, fi) => (
            <div key={fi} style={{
              background: '#fff', borderRadius: 8, padding: 16, marginBottom: 12,
              border: '1px solid #e5e7eb',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <code style={{ fontSize: 13, color: '#0365C0', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                  {f.pattern}
                </code>
                <span style={{ fontSize: 12, color: '#6b7280' }}>— {f.tool || f.report}</span>
              </div>
              <div style={{ marginBottom: 8 }}>
                {f.steps.map((step, si) => (
                  <div key={si} style={styles.guideStep}>
                    <span style={styles.guideStepNum}>{si + 1}</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>
                <strong>运行次数:</strong> {f.runFor || f.dateRange}
              </div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
                {f.feedsTabs.map((tab, ti) => (
                  <span key={ti} style={{
                    display: 'inline-block', padding: '1px 6px', borderRadius: 3,
                    fontSize: 11, background: '#f3f4f6', color: '#374151',
                  }}>{tab}</span>
                ))}
              </div>
              {f.notes && <div style={styles.guideNote}>{f.notes}</div>}
              {f.gotchas && (
                <div style={{ ...styles.guideNote, background: '#fef3c7', borderLeftColor: '#f59e0b', color: '#92400e' }}>
                  {f.gotchas.map((g, gi) => <div key={gi}>⚠ {g}</div>)}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function MetricGuideSection() {
  const [selectedTab, setSelectedTab] = useState('competitors');
  const tabs = Object.entries(METRIC_DEFINITIONS);
  const info = METRIC_DEFINITIONS[selectedTab];

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
        {tabs.map(([key, val]) => (
          <button key={key} onClick={() => setSelectedTab(key)} style={{
            padding: '6px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
            background: selectedTab === key ? '#0365C0' : '#f3f4f6',
            color: selectedTab === key ? '#fff' : '#6b7280',
            fontSize: 12, fontWeight: selectedTab === key ? 600 : 400,
            fontFamily: "'Noto Sans SC', sans-serif",
          }}>
            {val.title}
          </button>
        ))}
      </div>
      {info && (
        <div style={{ background: '#fff', borderRadius: 8, padding: 16, border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4, color: '#1A365D', fontFamily: "'Noto Sans SC', sans-serif" }}>
            {info.title} — {info.description}
          </div>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
            数据来源: {info.sourceFiles.join(', ')}
          </div>
          <table style={{ ...styles.table, fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ ...styles.th, padding: '6px 10px' }}>指标</th>
                <th style={{ ...styles.th, padding: '6px 10px' }}>英文名</th>
                <th style={{ ...styles.th, padding: '6px 10px' }}>定义</th>
              </tr>
            </thead>
            <tbody>
              {info.metrics.map((m, i) => (
                <tr key={i}>
                  <td style={{ ...styles.td(i % 2), fontWeight: 600, fontFamily: "'Noto Sans SC', sans-serif", padding: '6px 10px' }}>{m.name}</td>
                  <td style={{ ...styles.td(i % 2), color: '#6b7280', padding: '6px 10px' }}>{m.en}</td>
                  <td style={{ ...styles.td(i % 2), padding: '6px 10px' }}>{m.definition}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DataFlowSection() {
  return (
    <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>源文件</th>
            <th style={styles.th}>来源</th>
            <th style={styles.th}>解析器</th>
            <th style={styles.th}>处理器</th>
            <th style={styles.th}>输出标签</th>
            <th style={styles.th}>说明</th>
          </tr>
        </thead>
        <tbody>
          {DATA_FLOW.map((d, i) => (
            <tr key={i}>
              <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>{d.file}</td>
              <td style={styles.td(i % 2)}>
                <span style={{
                  display: 'inline-block', padding: '1px 6px', borderRadius: 3, fontSize: 11, fontWeight: 600,
                  background: d.source === 'SellerSprite' ? '#dbeafe' : '#d1fae5',
                  color: d.source === 'SellerSprite' ? '#1e40af' : '#065f46',
                }}>{d.source === 'SellerSprite' ? '卖家精灵' : d.source === 'Seller Central' ? '卖家后台' : d.source}</span>
              </td>
              <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{d.parser}</td>
              <td style={{ ...styles.td(i % 2), fontSize: 12 }}>{d.processors.join(', ')}</td>
              <td style={styles.td(i % 2)}>
                <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                  {d.outputTabs.map((t, ti) => (
                    <span key={ti} style={{
                      display: 'inline-block', padding: '1px 5px', borderRadius: 3,
                      fontSize: 10, background: '#f3f4f6', color: '#374151',
                    }}>{t}</span>
                  ))}
                </div>
              </td>
              <td style={{ ...styles.td(i % 2), fontSize: 12, maxWidth: 250 }}>{d.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompetitorsTab({ competitors }) {
  const metrics = [
    { label: '品牌', key: 'brand' },
    { label: 'ASIN', key: 'asin' },
    { label: '价格', key: 'price', fmt: fmtUSD },
    { label: '评分', key: 'rating' },
    { label: '评论数', key: 'ratings_count', fmt: fmt },
    { label: '月销量', key: 'monthly_sales', fmt: fmt },
    { label: '月销售额', key: 'monthly_revenue', fmt: fmtUSD },
    { label: '类目BSR', key: 'category_bsr', fmt: fmt },
    { label: '子类目BSR', key: 'subcategory_bsr', fmt: fmt },
    { label: '上架日期', key: 'launch_date' },
    { label: '变体数', key: 'variation_count', fmt: fmt },
    { label: '前五核心流量词', key: 'top_keywords' },
    { label: '流量关键词数', key: 'keyword_count', fmt: fmt },
  ];

  return (
    <>
    <TabMetricHelp tabKey="competitors" />
    <div style={styles.card}>
      <h3 style={styles.cardTitle}>竞品对比矩阵</h3>
      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>指标</th>
              {competitors.map((c, i) => (
                <th key={i} style={{ ...styles.th, background: i === 0 ? '#0365C0' : '#1F4E79' }}>
                  {c.brand}{c.is_mine ? ' (我)' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map((m, ri) => (
              <tr key={m.key}>
                <td style={{ ...styles.td(ri % 2), fontWeight: 600, fontFamily: "'Noto Sans SC', sans-serif" }}>
                  {m.label}
                </td>
                {competitors.map((c, ci) => (
                  <td key={ci} style={styles.td(ri % 2)}>
                    {m.fmt ? m.fmt(c[m.key]) : (c[m.key] ?? 'N/A')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}

function ProductsTab({ pricing }) {
  const scenarios = pricing.scenarios || [];
  const variants = pricing.variants || [];

  // Editable overrides: keyed by scenario index
  const [overrides, setOverrides] = useState(() => {
    const init = {};
    scenarios.forEach((s, i) => {
      init[i] = {
        unit_cost: s.unit_cost ?? 0,
        packaging: s.packaging ?? 0,
        inbound_shipping: s.inbound_shipping ?? 0,
      };
    });
    return init;
  });

  const handleOverride = (si, key, val) => {
    setOverrides(prev => ({
      ...prev,
      [si]: { ...prev[si], [key]: val },
    }));
  };

  const getScenario = (s, si) => ({
    ...s,
    unit_cost: overrides[si]?.unit_cost ?? s.unit_cost,
    packaging: overrides[si]?.packaging ?? s.packaging,
    inbound_shipping: overrides[si]?.inbound_shipping ?? s.inbound_shipping,
  });

  const editableInputStyle = {
    border: '1px solid #d1d5db', borderRadius: 6, padding: '4px 8px', fontSize: 13,
    width: 90, color: '#0000FF', background: '#FFFDE7',
    fontFamily: "'JetBrains Mono', monospace", textAlign: 'right',
  };

  const costRows = [
    { label: '售价', key: 'price', fmt: fmtUSD },
    { label: '成品成本', key: 'unit_cost', fmt: fmtUSD, editable: true },
    { label: '包装', key: 'packaging', fmt: fmtUSD, editable: true },
    { label: '头程运费', key: 'inbound_shipping', fmt: fmtUSD, editable: true },
    { label: 'Amazon佣金(17%)', compute: (s) => s.price * s.referral_fee_rate, fmt: fmtUSD },
    { label: 'FBA配送费', key: 'fba_fee', fmt: fmtUSD },
    { label: '月仓储费', key: 'storage_fee', fmt: fmtUSD },
    { label: '广告费', compute: (s) => s.price * s.ad_rate, fmt: fmtUSD },
    { label: '退货损失', compute: (s) => s.price * s.return_rate, fmt: fmtUSD },
  ];

  const calcTotal = (s) => s.unit_cost + s.packaging + s.inbound_shipping +
    s.price * s.referral_fee_rate + s.fba_fee + s.storage_fee +
    s.price * s.ad_rate + s.price * s.return_rate;

  return (
    <>
      <TabMetricHelp tabKey="products" />
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>4价格场景成本模型</h3>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>成本项</th>
                {scenarios.map((s, i) => (
                  <th key={i} style={styles.th}>{s.scenario} ({fmtUSD(s.price)})</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {costRows.map((row, ri) => (
                <tr key={ri}>
                  <td style={{ ...styles.td(ri % 2), fontWeight: 500, fontFamily: "'Noto Sans SC', sans-serif" }}>
                    {row.label}
                  </td>
                  {scenarios.map((s, si) => {
                    const eff = getScenario(s, si);
                    if (row.editable) {
                      return (
                        <td key={si} style={{ ...styles.td(ri % 2), padding: '4px 8px' }}>
                          <input
                            type="number"
                            step="0.01"
                            value={overrides[si]?.[row.key] ?? ''}
                            onChange={(e) => handleOverride(si, row.key, parseFloat(e.target.value) || 0)}
                            style={editableInputStyle}
                          />
                        </td>
                      );
                    }
                    const val = row.compute ? row.compute(eff) : eff[row.key];
                    return (
                      <td key={si} style={{
                        ...styles.td(ri % 2),
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {row.fmt(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr>
                <td style={{ ...styles.td(false), fontWeight: 700 }}>总成本</td>
                {scenarios.map((s, i) => {
                  const eff = getScenario(s, i);
                  const total = calcTotal(eff);
                  return <td key={i} style={{ ...styles.td(false), fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>{fmtUSD(total)}</td>;
                })}
              </tr>
              <tr>
                <td style={{ ...styles.td(true), fontWeight: 700, color: '#059669' }}>毛利润</td>
                {scenarios.map((s, i) => {
                  const eff = getScenario(s, i);
                  const total = calcTotal(eff);
                  const profit = eff.price - total;
                  return <td key={i} style={{
                    ...styles.td(true), fontWeight: 700, fontFamily: "'JetBrains Mono'",
                    color: profit >= 0 ? '#059669' : '#dc2626',
                  }}>{fmtUSD(profit)}</td>;
                })}
              </tr>
              <tr>
                <td style={{ ...styles.td(false), fontWeight: 700 }}>毛利率</td>
                {scenarios.map((s, i) => {
                  const eff = getScenario(s, i);
                  const total = calcTotal(eff);
                  const margin = (eff.price - total) / eff.price;
                  return <td key={i} style={{
                    ...styles.td(false), fontWeight: 700, fontFamily: "'JetBrains Mono'",
                    color: margin >= 0 ? '#059669' : '#dc2626',
                  }}>{fmtPct(margin)}</td>;
                })}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>变体销售明细</h3>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {['ASIN', 'SKU', '销量', '销售额', 'Sessions', 'CVR', '平均售价'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {variants.map((v, i) => (
                <tr key={i}>
                  <td style={styles.td(i % 2)}><code>{v.asin}</code></td>
                  <td style={styles.td(i % 2)}>{v.sku}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(v.units_ordered)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.revenue)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(v.sessions)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(v.cvr)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.avg_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function KeywordsTab({ keywords }) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [visibleCount, setVisibleCount] = useState(200);
  const allFiltered = useMemo(() => {
    let data = keywords || [];
    if (search) {
      const q = search.toLowerCase();
      data = data.filter(k => k.keyword && k.keyword.toLowerCase().includes(q));
    }
    if (filter !== 'all') {
      data = data.filter(k => k['一级分类'] === filter);
    }
    return data;
  }, [keywords, search, filter]);
  const filtered = useMemo(() => allFiltered.slice(0, visibleCount), [allFiltered, visibleCount]);

  const classificationCounts = useMemo(() => {
    const counts = {};
    (keywords || []).forEach(k => {
      const cls = k['一级分类'] || '未分类';
      counts[cls] = (counts[cls] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [keywords]);

  return (
    <>
      <TabMetricHelp tabKey="keywords" />
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: '总关键词', val: keywords?.length || 0 },
          ...classificationCounts.slice(0, 5).map(c => ({ label: c.name, val: c.value })),
        ].map((s, i) => (
          <div key={i} style={styles.stat}>
            <div style={styles.statVal}>{fmt(s.val)}</div>
            <div style={styles.statLabel}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={styles.card}>
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            style={styles.searchInput}
            placeholder="搜索关键词..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            style={{ ...styles.searchInput, width: 200 }}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">全部分类</option>
            {classificationCounts.map(c => (
              <option key={c.name} value={c.name}>{c.name} ({c.value})</option>
            ))}
          </select>
          <span style={{ color: '#6b7280', fontSize: 13 }}>显示 {filtered.length} / {allFiltered.length} (总计 {keywords?.length || 0})</span>
        </div>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', maxHeight: 600, overflowY: 'auto' }}>
          <table style={{ ...styles.table, minWidth: 900 }}>
            <thead>
              <tr>
                <th style={{ ...styles.th, minWidth: 180 }}>关键词</th>
                <th style={{ ...styles.th, minWidth: 100 }}>一级分类</th>
                <th style={{ ...styles.th, minWidth: 100 }}>二级分类</th>
                <th style={{ ...styles.th, minWidth: 80 }}>用途</th>
                <th style={{ ...styles.th, minWidth: 90 }}>月搜索量</th>
                <th style={{ ...styles.th, minWidth: 70 }}>购买率</th>
                <th style={{ ...styles.th, minWidth: 70 }}>CPC</th>
                <th style={{ ...styles.th, minWidth: 70 }}>自然排名</th>
                <th style={{ ...styles.th, minWidth: 120 }}>数据来源</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((k, i) => (
                <tr key={i}>
                  <td style={{ ...styles.td(i % 2), minWidth: 180 }}>{k.keyword}</td>
                  <td style={{ ...styles.td(i % 2), minWidth: 100 }}>{k['一级分类']}</td>
                  <td style={{ ...styles.td(i % 2), minWidth: 100 }}>{k['二级分类']}</td>
                  <td style={{ ...styles.td(i % 2), minWidth: 80 }}>{k['用途']}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'", minWidth: 90 }}>{fmt(k.monthly_searches)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'", minWidth: 70 }}>{k.purchase_rate ? fmtPct(k.purchase_rate) : 'N/A'}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'", minWidth: 70 }}>{k.ppc_bid ? fmtUSD(k.ppc_bid) : 'N/A'}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'", minWidth: 70 }}>{k.organic_rank ?? 'N/A'}</td>
                  <td style={{ ...styles.td(i % 2), fontSize: 11, minWidth: 120, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {k.data_source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {visibleCount < allFiltered.length && (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <button
              onClick={() => setVisibleCount(prev => prev + 200)}
              style={{
                background: '#0365C0', color: '#fff', border: 'none', borderRadius: 8,
                padding: '10px 24px', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
              }}
            >
              加载更多 / Load More
            </button>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
              显示 {filtered.length} / {allFiltered.length}
            </div>
          </div>
        )}
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>关键词分类分布</h3>
        <div style={{ height: 300 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie data={classificationCounts} dataKey="value" nameKey="name" cx="50%" cy="50%"
                   outerRadius={100} label={({ name, value }) => `${name}: ${value}`}>
                {classificationCounts.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

function AdsTab({ ads }) {
  const stData = ads.search_term_summary || [];
  const campaigns = ads.campaign_summary || [];

  const topTerms = useMemo(() =>
    [...stData].sort((a, b) => (b.sales || 0) - (a.sales || 0)).slice(0, 15),
  [stData]);

  return (
    <>
      <TabMetricHelp tabKey="ads" />
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: '总花费', val: fmtUSD(stData.reduce((s, r) => s + (r.spend || 0), 0)) },
          { label: '总销售', val: fmtUSD(stData.reduce((s, r) => s + (r.sales || 0), 0)) },
          { label: '搜索词', val: stData.length },
          { label: '广告活动', val: campaigns.length },
        ].map((s, i) => (
          <div key={i} style={styles.stat}>
            <div style={styles.statVal}>{s.val}</div>
            <div style={styles.statLabel}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>搜索词表现 Top 15</h3>
        <div style={{ height: 400 }}>
          <ResponsiveContainer>
            <BarChart data={topTerms} layout="vertical" margin={{ left: 160 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={(v) => '$' + v} />
              <YAxis type="category" dataKey="keyword" width={150} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => fmtUSD(v)} />
              <Bar dataKey="sales" fill="#0365C0" name="销售额" />
              <Bar dataKey="spend" fill="#f59e0b" name="花费" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>搜索词详情</h3>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', maxHeight: 500, overflowY: 'auto' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {['关键词', '曝光', '点击', 'CTR', 'CPC', '花费', '销售额', 'ACoS', '订单', '转化率'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stData.map((r, i) => (
                <tr key={i}>
                  <td style={styles.td(i % 2)}>{r.keyword}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(r.impressions)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(r.clicks)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(r.ctr)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(r.cpc)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(r.spend)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(r.sales)}</td>
                  <td style={{
                    ...styles.td(i % 2), fontFamily: "'JetBrains Mono'",
                    color: r.acos > 0.3 ? '#dc2626' : r.acos > 0.2 ? '#d97706' : '#059669',
                  }}>{fmtPct(r.acos)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(r.orders)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(r.cvr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>广告活动概览</h3>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {['广告活动', '状态', '日预算', '曝光', '点击', '花费', '销售额', 'ACoS', '订单'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c, i) => (
                <tr key={i}>
                  <td style={styles.td(i % 2)}>{c.campaign}</td>
                  <td style={styles.td(i % 2)}>
                    <span style={{ color: c.status === 'ENABLED' ? '#059669' : '#dc2626' }}>{c.status}</span>
                  </td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(c.budget)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(c.impressions)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(c.clicks)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(c.spend)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(c.sales)}</td>
                  <td style={{
                    ...styles.td(i % 2), fontFamily: "'JetBrains Mono'",
                    color: c.acos > 0.3 ? '#dc2626' : c.acos > 0.2 ? '#d97706' : '#059669',
                  }}>{fmtPct(c.acos)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(c.orders)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function PricingTab({ pricing }) {
  const variants = pricing.variants || [];

  const [variantOverrides, setVariantOverrides] = useState(() => {
    const init = {};
    variants.forEach((v, i) => {
      init[i] = {
        unit_cost: v.unit_cost ?? 0,
        inbound_shipping: v.inbound_shipping ?? 0,
      };
    });
    return init;
  });

  const handleVariantOverride = (idx, key, val) => {
    setVariantOverrides(prev => ({
      ...prev,
      [idx]: { ...prev[idx], [key]: val },
    }));
  };

  const pricingInputStyle = {
    border: '1px solid #d1d5db', borderRadius: 6, padding: '4px 6px', fontSize: 12,
    width: 80, color: '#0000FF', background: '#FFFDE7',
    fontFamily: "'JetBrains Mono', monospace", textAlign: 'right',
  };

  return (
    <>
    <TabMetricHelp tabKey="pricing" />
    <div style={styles.card}>
      <h3 style={styles.cardTitle}>变体定价策略 — 每单位成本分解</h3>
      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={styles.table}>
          <thead>
            <tr>
              {['ASIN', 'SKU', '销量', '销售额', '平均售价', '单位成本', '采购占比',
                '单位头程', '头程占比', '配送费', '配送占比', '佣金', '佣金占比',
                '仓储费', '仓储占比', '广告花费', 'ACoS', 'TACoS'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variants.map((v, i) => {
              const uc = variantOverrides[i]?.unit_cost ?? v.unit_cost;
              const ibs = variantOverrides[i]?.inbound_shipping ?? v.inbound_shipping;
              const p = v.avg_price || 1;
              return (
                <tr key={i}>
                  <td style={styles.td(i % 2)}><code>{v.asin}</code></td>
                  <td style={styles.td(i % 2)}>{v.sku}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(v.units_ordered)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.revenue)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.avg_price)}</td>
                  <td style={{ ...styles.td(i % 2), padding: '4px 6px' }}>
                    <input
                      type="number"
                      step="0.01"
                      value={uc}
                      onChange={(e) => handleVariantOverride(i, 'unit_cost', parseFloat(e.target.value) || 0)}
                      style={pricingInputStyle}
                    />
                  </td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(uc / p)}</td>
                  <td style={{ ...styles.td(i % 2), padding: '4px 6px' }}>
                    <input
                      type="number"
                      step="0.01"
                      value={ibs}
                      onChange={(e) => handleVariantOverride(i, 'inbound_shipping', parseFloat(e.target.value) || 0)}
                      style={pricingInputStyle}
                    />
                  </td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(ibs / p)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.fba_fee)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(v.fba_fee / p)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.referral_fee)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(v.referral_fee / p)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.storage_fee)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtPct(v.storage_fee / p)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmtUSD(v.ad_spend)}</td>
                  <td style={{
                    ...styles.td(i % 2), fontFamily: "'JetBrains Mono'",
                    color: v.acos > 0.3 ? '#dc2626' : v.acos > 0.2 ? '#d97706' : '#059669',
                  }}>{fmtPct(v.acos)}</td>
                  <td style={{
                    ...styles.td(i % 2), fontFamily: "'JetBrains Mono'",
                    color: v.tacos > 0.15 ? '#dc2626' : '#059669',
                  }}>{fmtPct(v.tacos)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}

function TrafficTab({ traffic }) {
  return (
    <>
    <TabMetricHelp tabKey="traffic" />
    <div style={styles.card}>
      <h3 style={styles.cardTitle}>流量入口策略矩阵</h3>
      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={styles.table}>
          <thead>
            <tr>
              {['流量入口', '流量来源', '方案'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(traffic || []).map((t, i) => (
              <tr key={i}>
                <td style={{ ...styles.td(i % 2), fontWeight: 600, fontFamily: "'Noto Sans SC', sans-serif" }}>
                  {t.channel}
                </td>
                <td style={styles.td(i % 2)}>{t.source}</td>
                <td style={{ ...styles.td(i % 2), maxWidth: 600 }}>{t.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}

function GapTab({ gapAnalysis }) {
  const data = gapAnalysis || [];
  const counts = useMemo(() => ({
    MISSING: data.filter(d => d.gap_type === 'MISSING').length,
    CATCHUP: data.filter(d => d.gap_type === 'CATCHUP').length,
    DEFEND: data.filter(d => d.gap_type === 'DEFEND').length,
  }), [data]);

  // Dynamically detect competitor rank column from data keys
  const { compRankKey, compRankLabel } = useMemo(() => {
    if (data.length === 0) return { compRankKey: 'competitor_rank', compRankLabel: 'Competitor' };
    const first = data[0];
    const rankKey = Object.keys(first).find(k => k.endsWith('_rank') && k !== 'my_rank');
    if (rankKey) {
      const label = rankKey.replace('_rank', '');
      return { compRankKey: rankKey, compRankLabel: label };
    }
    return { compRankKey: 'competitor_rank', compRankLabel: 'Competitor' };
  }, [data]);

  return (
    <>
      <TabMetricHelp tabKey="gap" />
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ ...styles.stat, borderLeft: '4px solid #dc2626' }}>
          <div style={{ ...styles.statVal, color: '#dc2626' }}>{counts.MISSING}</div>
          <div style={styles.statLabel}>MISSING</div>
        </div>
        <div style={{ ...styles.stat, borderLeft: '4px solid #d97706' }}>
          <div style={{ ...styles.statVal, color: '#d97706' }}>{counts.CATCHUP}</div>
          <div style={styles.statLabel}>CATCHUP</div>
        </div>
        <div style={{ ...styles.stat, borderLeft: '4px solid #059669' }}>
          <div style={{ ...styles.statVal, color: '#059669' }}>{counts.DEFEND}</div>
          <div style={styles.statLabel}>DEFEND</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statVal}>{data.length}</div>
          <div style={styles.statLabel}>总计</div>
        </div>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>关键词Gap分析 — vs {compRankLabel}</h3>
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', maxHeight: 600, overflowY: 'auto' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {['关键词', '我方排名', `${compRankLabel}排名`, 'Gap类型', '月搜索量', '购买率', 'PPC竞价', '优先级', '建议操作'].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 200).map((r, i) => (
                <tr key={i}>
                  <td style={styles.td(i % 2)}>{r.keyword}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{r.my_rank ?? '—'}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{r[compRankKey] ?? '—'}</td>
                  <td style={styles.td(i % 2)}>
                    <span style={styles.badge(r.gap_type)}>{r.gap_type}</span>
                  </td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{fmt(r.monthly_searches)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{r.purchase_rate ? fmtPct(r.purchase_rate) : 'N/A'}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'" }}>{r.ppc_bid ? fmtUSD(r.ppc_bid) : 'N/A'}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'JetBrains Mono'", fontWeight: 600 }}>{fmt(r.priority_score, 1)}</td>
                  <td style={{ ...styles.td(i % 2), fontFamily: "'Noto Sans SC', sans-serif", fontSize: 12 }}>{r.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function ControlTab({ onRefresh }) {
  const [status, setStatus] = useState(null);
  const [collectStatus, setCollectStatus] = useState(null);
  const [collectMode, setCollectMode] = useState('full');
  const [isStarting, setIsStarting] = useState(false);
  const [chromeProfiles, setChromeProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState('');
  const [chromeRunning, setChromeRunning] = useState(false);
  const [adspowerEnabled, setAdspowerEnabled] = useState(false);
  const [discoverUrl, setDiscoverUrl] = useState('');
  const [discoverStatus, setDiscoverStatus] = useState(null); // null | {isRunning, progress}
  const [isDiscovering, setIsDiscovering] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, collectRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/collect'),
      ]);
      const statusData = await statusRes.json();
      setStatus(statusData);
      if (statusData.adspower?.enabled) setAdspowerEnabled(true);
      const collectData = await collectRes.json();
      setCollectStatus(collectData);
      if (collectData.chromeRunning !== undefined) setChromeRunning(collectData.chromeRunning);
    } catch {}
  }, []);

  // Fetch Chrome profiles on mount
  useEffect(() => {
    fetch('/api/profiles').then(r => r.json()).then(data => {
      setChromeProfiles(data.profiles || []);
      setChromeRunning(data.chromeRunning || false);
      // Auto-select a profile with SellerSprite cookies, or first profile
      const ssProfile = (data.profiles || []).find(p => p.has_sellersprite);
      if (ssProfile) setSelectedProfile(ssProfile.id);
      else if (data.profiles?.length) setSelectedProfile(data.profiles[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Polling: 2.5s when running, 15s when idle
  useEffect(() => {
    const isRunning = collectStatus?.isRunning;
    const interval = setInterval(fetchAll, isRunning ? 2500 : 15000);
    return () => clearInterval(interval);
  }, [collectStatus?.isRunning, fetchAll]);

  const startCollection = async () => {
    setIsStarting(true);
    try {
      const res = await fetch('/api/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: collectMode, chromeProfile: selectedProfile || undefined }),
      });
      const data = await res.json();
      if (res.ok) {
        setCollectStatus({ isRunning: true, pid: data.pid, progress: { status: 'starting', tasks: [], completed: 0, total: 0 } });
      }
    } catch {} finally {
      setIsStarting(false);
    }
  };

  const stopCollection = async () => {
    try {
      await fetch('/api/collect', { method: 'DELETE' });
      setTimeout(fetchAll, 500);
    } catch {}
  };

  const handleRefreshAfterUpload = () => {
    fetchAll();
    if (onRefresh) onRefresh();
  };

  // Poll discovery progress
  useEffect(() => {
    if (!isDiscovering) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/discover');
        const data = await res.json();
        setDiscoverStatus(data);
        if (!data.isRunning && data.progress?.status !== 'starting') {
          setIsDiscovering(false);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [isDiscovering]);

  const startDiscovery = async () => {
    if (!discoverUrl.trim()) return;
    setIsDiscovering(true);
    setDiscoverStatus(null);
    try {
      const res = await fetch('/api/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: discoverUrl.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setIsDiscovering(false);
        alert(data.error || 'Failed to start discovery');
      }
    } catch (e) {
      setIsDiscovering(false);
      alert('Failed to start discovery: ' + e.message);
    }
  };

  const progress = collectStatus?.progress || {};
  const isRunning = collectStatus?.isRunning || false;
  const tasks = progress.tasks || [];
  const ssTasks = tasks.filter(t => t.group === 'sellersprite');
  const scTasks = tasks.filter(t => t.group === 'seller_central');
  const completedCount = progress.completed || 0;
  const totalCount = progress.total || 0;
  const pct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  const ssFiles = status?.inputFiles?.sellersprite || [];
  const ssFileCount = ssFiles.filter(f => !f.ignored).length;
  const ssIgnoredCount = ssFiles.filter(f => f.ignored).length;
  const scFileCount = status?.inputFiles?.sellerCentral?.length || 0;
  const lastRun = status?.lastRun;

  // Data freshness
  const freshness = (() => {
    if (!lastRun) return { label: '暂无数据', color: '#ef4444', bg: '#fef2f2' };
    const diff = Date.now() - new Date(lastRun).getTime();
    const hours = diff / (1000 * 60 * 60);
    if (hours < 24) return { label: '新鲜 (<24小时)', color: '#059669', bg: '#f0fdf4' };
    const days = hours / 24;
    if (days < 7) return { label: `${Math.floor(days)}天前`, color: '#d97706', bg: '#fffbeb' };
    return { label: `${Math.floor(days)}天前`, color: '#ef4444', bg: '#fef2f2' };
  })();

  const modeButtons = [
    { value: 'full', label: '全部采集' },
    { value: 'sellersprite', label: '仅卖家精灵' },
    { value: 'seller-central', label: '仅卖家后台' },
  ];

  const statusIcon = (s) => {
    if (s === 'completed') return { icon: '\u2713', color: '#059669' };
    if (s === 'failed') return { icon: '\u2717', color: '#ef4444' };
    if (s === 'running') return { icon: '\u25CB', color: '#0365C0' };
    if (s === 'skipped') return { icon: '\u23ED', color: '#9ca3af' };
    return { icon: '\u25CB', color: '#d1d5db' };
  };

  const isTerminal = ['completed', 'completed_with_errors', 'failed', 'interrupted'].includes(progress.status);

  return (
    <>
      {/* Section 1: Status Overview */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ ...styles.card, flex: '1 1 160px', minWidth: 160, padding: 16, textAlign: 'center' }}>
          <div style={styles.statVal}>{ssFileCount}</div>
          <div style={styles.statLabel}>卖家精灵数据</div>
        </div>
        <div style={{ ...styles.card, flex: '1 1 160px', minWidth: 160, padding: 16, textAlign: 'center' }}>
          <div style={styles.statVal}>{scFileCount}</div>
          <div style={styles.statLabel}>卖家后台数据</div>
        </div>
        <div style={{ ...styles.card, flex: '1 1 160px', minWidth: 160, padding: 16, textAlign: 'center' }}>
          <div style={styles.statVal}>{lastRun ? new Date(lastRun).toLocaleDateString() : '--'}</div>
          <div style={styles.statLabel}>上次生成报告</div>
        </div>
        <div style={{ ...styles.card, flex: '1 1 160px', minWidth: 160, padding: 16, textAlign: 'center' }}>
          <div style={{
            display: 'inline-block', padding: '4px 12px', borderRadius: 12,
            fontSize: 13, fontWeight: 600, color: freshness.color, background: freshness.bg,
          }}>
            {freshness.label}
          </div>
          <div style={styles.statLabel}>数据新鲜度</div>
        </div>
      </div>

      {/* Step 1: New Product Analysis */}
      <div style={{ ...styles.card, padding: 24, marginBottom: 20, borderLeft: '4px solid #0365C0' }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1f2937', marginBottom: 6 }}>
          <span style={{ display: 'inline-block', background: '#0365C0', color: '#fff', width: 28, height: 28, borderRadius: '50%', textAlign: 'center', lineHeight: '28px', fontSize: 14, marginRight: 8 }}>1</span>
          输入产品链接
        </h3>
        <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 12, marginLeft: 36 }}>
          粘贴 Amazon 产品页面链接，系统将自动识别产品信息、发现竞品、提取关键词，然后自动采集数据并生成完整报告。
        </p>

        <div style={{ display: 'flex', gap: 8, marginBottom: 16, marginLeft: 36 }}>
          <input
            type="text"
            value={discoverUrl}
            onChange={e => setDiscoverUrl(e.target.value)}
            placeholder="https://www.amazon.com/dp/B0BTRTZNS8"
            style={{
              flex: 1,
              padding: '10px 14px',
              border: '2px solid #e5e7eb',
              borderRadius: 8,
              fontSize: 14,
              fontFamily: "'JetBrains Mono', monospace",
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = '#0365C0'}
            onBlur={e => e.target.style.borderColor = '#e5e7eb'}
            onKeyDown={e => e.key === 'Enter' && startDiscovery()}
            disabled={isDiscovering}
          />
          <button
            onClick={startDiscovery}
            disabled={isDiscovering || !discoverUrl.trim()}
            style={{
              padding: '10px 20px',
              background: isDiscovering ? '#9ca3af' : '#0365C0',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: isDiscovering ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {isDiscovering ? '分析中...' : '开始分析'}
          </button>
        </div>

        {/* Discovery Progress */}
        {discoverStatus?.progress && (
          <div style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: 16,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 8 }}>
              状态: {discoverStatus.progress.phase === 'initializing' ? '初始化中' : discoverStatus.progress.phase === 'pipeline' ? '分析中' : discoverStatus.progress.phase === 'collecting' ? '采集中' : discoverStatus.progress.phase || '初始化中'}
              {discoverStatus.progress.status === 'completed' && ' ✅'}
              {discoverStatus.progress.status === 'failed' && ' ❌'}
            </div>

            {/* Discovery Steps */}
            {discoverStatus.progress.discovery?.steps?.map((step, i) => (
              <div key={i} style={{
                fontSize: 12,
                padding: '4px 0',
                color: step.status === 'ok' ? '#065f46' : step.status === 'failed' ? '#dc2626' : '#6b7280',
                display: 'flex',
                gap: 8,
              }}>
                <span>{step.status === 'ok' ? '✓' : step.status === 'failed' ? '✗' : '●'}</span>
                <span>
                  {step.step === 'extract_asin' && `提取 ASIN: ${step.asin}`}
                  {step.step === 'scrape_product' && `产品信息: ${step.title || '...'}`}
                  {step.step === 'generate_seeds' && `种子词: ${(step.seeds || []).join(', ')}`}
                  {step.step === 'discover_competitors' && `发现竞品: ${step.count} 个`}
                  {step.step === 'update_config' && '配置已更新'}
                </span>
              </div>
            ))}

            {/* Collection Progress (after discovery) */}
            {discoverStatus.progress.tasks && (
              <div style={{ marginTop: 8, borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>
                  采集进度: {discoverStatus.progress.completed || 0} / {discoverStatus.progress.total || 0} 任务
                </div>
                <div style={{
                  height: 4,
                  background: '#e2e8f0',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${((discoverStatus.progress.completed || 0) / Math.max(discoverStatus.progress.total || 1, 1)) * 100}%`,
                    background: '#0365C0',
                    borderRadius: 2,
                    transition: 'width 0.3s',
                  }} />
                </div>
                {discoverStatus.progress.tasks?.filter(t => t.status !== 'pending').map((task, i) => (
                  <div key={i} style={{
                    fontSize: 11,
                    padding: '2px 0',
                    color: task.status === 'completed' ? '#065f46' : task.status === 'running' ? '#0365C0' : task.status === 'failed' ? '#dc2626' : '#9ca3af',
                  }}>
                    {task.status === 'completed' ? '✓' : task.status === 'running' ? '●' : task.status === 'failed' ? '✗' : '○'} {task.label}
                    {task.file && <span style={{ color: '#9ca3af', marginLeft: 4 }}>→ {task.file}</span>}
                    {task.error && <span style={{ color: '#dc2626', marginLeft: 4 }}>— {task.error}</span>}
                  </div>
                ))}
              </div>
            )}

            {/* Pipeline phase */}
            {discoverStatus.progress.phase === 'pipeline' && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#0365C0', fontWeight: 600 }}>
                ● 正在运行分析流程...
              </div>
            )}

            {/* Completion */}
            {discoverStatus.progress.status === 'completed' && (
              <div style={{
                marginTop: 12,
                padding: '8px 12px',
                background: '#ecfdf5',
                borderRadius: 6,
                fontSize: 13,
                color: '#065f46',
                fontWeight: 600,
              }}>
                ✅ 分析完成！请切换到其他标签页查看结果。
              </div>
            )}

            {/* Errors */}
            {discoverStatus.progress.errors?.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {discoverStatus.progress.errors.map((err, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#dc2626', padding: '2px 0' }}>
                    ⚠ {err.task}: {err.error}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Step 2: Automated Collection */}
      <div style={{ ...styles.card, borderLeft: '4px solid #00A5A5' }}>
        <h3 style={styles.cardTitle}>
          <span style={{ display: 'inline-block', background: '#00A5A5', color: '#fff', width: 28, height: 28, borderRadius: '50%', textAlign: 'center', lineHeight: '28px', fontSize: 14, marginRight: 8 }}>2</span>
          自动数据采集
        </h3>
        <p style={{ fontSize: 12, color: '#9ca3af', marginTop: -8, marginBottom: 12, marginLeft: 36 }}>
          {isRunning ? '正在采集数据，请勿关闭页面...' : isTerminal ? '采集已完成，报告已自动生成。' : '点击「开始采集」或在第一步输入链接后自动开始。'}
        </p>

        {/* Chrome running warning */}
        {chromeRunning && !isRunning && !adspowerEnabled && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
            background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, marginBottom: 16,
          }}>
            <span style={{ fontSize: 18, color: '#dc2626' }}>&#9888;</span>
            <span style={{ flex: 1, fontSize: 13, color: '#991b1b' }}>
              <strong>Chrome 正在运行。</strong> 请先完全退出 Chrome（Cmd+Q），Playwright 需要独占访问 Chrome 配置。
            </span>
          </div>
        )}

        {/* AdsPower badge — shown when AdsPower manages the browser */}
        {adspowerEnabled && !isRunning && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px',
            background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, marginBottom: 16,
          }}>
            <span style={{
              display: 'inline-block', padding: '2px 10px', borderRadius: 6,
              fontSize: 12, fontWeight: 700, color: '#fff', background: '#059669',
              letterSpacing: 0.5,
            }}>AdsPower 托管</span>
            <span style={{ fontSize: 13, color: '#166534' }}>
              浏览器由 AdsPower 管理，无需选择 Chrome 配置。
            </span>
          </div>
        )}

        {/* Chrome profile selector — hidden when AdsPower is enabled */}
        {!isRunning && !isTerminal && !adspowerEnabled && chromeProfiles.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 6 }}>
              Chrome Profile
            </label>
            <select
              value={selectedProfile}
              onChange={e => setSelectedProfile(e.target.value)}
              style={{
                padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db',
                fontSize: 13, color: '#374151', background: '#fff', minWidth: 280,
                fontFamily: "'Inter', sans-serif",
              }}
            >
              {chromeProfiles.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id})
                  {p.has_sellersprite ? ' — 卖家精灵' : ''}
                  {p.has_seller_central ? ' + 卖家后台' : ''}
                  {p.has_sellersprite === null ? '' : (!p.has_sellersprite && !p.has_seller_central ? ' — 未检测到登录' : '')}
                </option>
              ))}
            </select>
            {chromeProfiles.find(p => p.id === selectedProfile)?.has_sellersprite === false && (
              <div style={{ fontSize: 11, color: '#d97706', marginTop: 4 }}>
                此配置文件中未检测到卖家精灵登录信息，请确保已登录。
              </div>
            )}
          </div>
        )}

        {/* Mode selector */}
        {!isRunning && !isTerminal && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            {modeButtons.map(m => (
              <button key={m.value} onClick={() => setCollectMode(m.value)} style={{
                padding: '8px 16px', borderRadius: 8, border: '1px solid',
                borderColor: collectMode === m.value ? '#0365C0' : '#d1d5db',
                background: collectMode === m.value ? '#eff6ff' : '#fff',
                color: collectMode === m.value ? '#0365C0' : '#6b7280',
                fontWeight: collectMode === m.value ? 600 : 400,
                fontSize: 13, cursor: 'pointer',
                fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
              }}>
                {m.label}
              </button>
            ))}
          </div>
        )}

        {/* Start/Stop button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          {isRunning ? (
            <button onClick={stopCollection} style={{
              padding: '10px 24px', borderRadius: 8, border: 'none', fontSize: 14,
              fontWeight: 600, cursor: 'pointer', background: '#ef4444', color: '#fff',
              fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
            }}>
              停止采集
            </button>
          ) : (
            <button onClick={startCollection} disabled={isStarting || (chromeRunning && !adspowerEnabled)} style={{
              padding: '10px 24px', borderRadius: 8, border: 'none', fontSize: 14,
              fontWeight: 600, cursor: (isStarting || (chromeRunning && !adspowerEnabled)) ? 'not-allowed' : 'pointer',
              opacity: (isStarting || (chromeRunning && !adspowerEnabled)) ? 0.5 : 1,
              background: '#0365C0', color: '#fff',
              fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
            }}>
              {isStarting ? '启动中...' : (chromeRunning && !adspowerEnabled) ? '请先关闭 Chrome' : '开始采集'}
            </button>
          )}
          {isRunning && (
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              Phase: {progress.phase || 'initializing'} | PID: {collectStatus?.pid}
            </span>
          )}
          {isTerminal && (
            <span style={{
              fontSize: 13, fontWeight: 600,
              color: progress.status === 'completed' ? '#059669' :
                     progress.status === 'completed_with_errors' ? '#d97706' : '#ef4444',
            }}>
              {progress.status === 'completed' ? '采集完成，报告已生成 ✓' :
               progress.status === 'completed_with_errors' ? '采集完成（部分任务失败），报告已生成' :
               progress.status === 'interrupted' ? '采集已手动停止' : '采集失败'}
            </span>
          )}
        </div>

        {/* Progress bar */}
        {(isRunning || isTerminal) && totalCount > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#6b7280', marginBottom: 4 }}>
              <span>{completedCount} / {totalCount} tasks</span>
              <span>{pct}%</span>
            </div>
            <div style={{ height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 4, transition: 'width 0.5s ease',
                width: `${pct}%`,
                background: progress.errors?.length > 0 ? '#f59e0b' : '#0365C0',
              }} />
            </div>
          </div>
        )}

        {/* Task list */}
        {(isRunning || isTerminal) && tasks.length > 0 && (
          <div>
            {[{ label: '卖家精灵', tasks: ssTasks }, { label: '卖家后台', tasks: scTasks }]
              .filter(g => g.tasks.length > 0)
              .map(group => (
                <div key={group.label} style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
                    {group.label}
                  </div>
                  {group.tasks.map(t => {
                    const si = statusIcon(t.status);
                    return (
                      <div key={t.id} style={{
                        display: 'flex', alignItems: 'center', gap: 10, padding: '5px 8px',
                        borderRadius: 4, fontSize: 13,
                        background: t.status === 'running' ? '#eff6ff' : 'transparent',
                      }}>
                        <span style={{
                          color: si.color, fontWeight: 700, fontSize: 14, width: 18, textAlign: 'center',
                          animation: t.status === 'running' ? 'none' : 'none',
                        }}>
                          {t.status === 'running' ? '\u25CF' : si.icon}
                        </span>
                        <span style={{ flex: 1, color: '#374151' }}>{t.label}</span>
                        {t.file && (
                          <span style={{ fontSize: 11, color: '#059669', fontFamily: "'JetBrains Mono', monospace" }}>
                            {t.file}
                          </span>
                        )}
                        {t.error && t.status === 'failed' && (
                          <span style={{ fontSize: 11, color: '#ef4444' }}>{t.error}</span>
                        )}
                        {t.status === 'skipped' && t.error && (
                          <span style={{ fontSize: 11, color: '#9ca3af' }}>{t.error}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
          </div>
        )}

        {/* Errors summary */}
        {isTerminal && progress.errors?.length > 0 && (
          <div style={{
            marginTop: 12, padding: 12, borderRadius: 8,
            background: '#fef2f2', border: '1px solid #fecaca',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#dc2626', marginBottom: 4 }}>
              {progress.errors.length} 个错误:
            </div>
            {progress.errors.map((e, i) => (
              <div key={i} style={{ fontSize: 12, color: '#dc2626', padding: '2px 0' }}>
                {e.task}: {e.error}
              </div>
            ))}
          </div>
        )}

        {/* Output files section — shown when pipeline has completed */}
        {isTerminal && progress.output_files && (
          <div style={{
            marginTop: 12, padding: 12, borderRadius: 8,
            background: '#f0fdf4', border: '1px solid #bbf7d0',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#059669', marginBottom: 8 }}>
              📊 已生成报告:
            </div>
            {progress.output_files.excel?.length > 0 && progress.output_files.excel.map((f, i) => {
              const name = f.split('/').pop();
              return (
                <div key={`xl-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 12 }}>
                  <span style={{ color: '#059669' }}>📗</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", color: '#374151' }}>{name}</span>
                  <span style={{ color: '#9ca3af', fontSize: 11 }}>{f}</span>
                </div>
              );
            })}
            {progress.output_files.summary?.length > 0 && progress.output_files.summary.map((f, i) => {
              const name = f.split('/').pop();
              return (
                <div key={`md-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 12 }}>
                  <span style={{ color: '#059669' }}>📝</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", color: '#374151' }}>{name}</span>
                </div>
              );
            })}
            {progress.output_files.json_count > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 12 }}>
                <span style={{ color: '#059669' }}>📦</span>
                <span style={{ color: '#374151' }}>{progress.output_files.json_count} 个 JSON 数据文件</span>
                <span style={{ color: '#9ca3af', fontSize: 11 }}>{progress.output_files.json_dir}</span>
              </div>
            )}
            <div style={{ marginTop: 8, padding: '6px 10px', borderRadius: 4, background: '#dcfce7', fontSize: 11, color: '#166534' }}>
              💡 在终端打开 Excel 报告: <code style={{ fontFamily: "'JetBrains Mono', monospace" }}>open outputs/*.xlsx</code> — 或切换到上方其他标签页查看数据看板。
            </div>
          </div>
        )}
      </div>

      {/* Section 3: Manual Upload + Pipeline */}
      <div style={{ marginTop: 8 }}>
        <div style={{ ...styles.card, borderLeft: '4px solid #d1d5db', padding: 24 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#6b7280', marginBottom: 6 }}>
            手动上传数据文件
          </h3>
          <p style={{ fontSize: 12, color: '#9ca3af', marginBottom: 12 }}>
            如果您已经从卖家精灵或卖家后台手动导出了数据文件，可以在此上传。上传后系统将自动处理并生成报告。<br/>
            <strong>提示：</strong>通常不需要手动上传 — 第一步输入链接后会自动完成采集。仅在以下情况使用：
            已有历史导出文件、自动采集部分失败需要补充数据、或需要更新卖家后台报告。
          </p>
          <UploadTab onRefresh={handleRefreshAfterUpload} />
        </div>
      </div>
    </>
  );
}

function UploadTab({ onRefresh }) {
  const [dragOver, setDragOver] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [processLog, setProcessLog] = useState(null);
  const [status, setStatus] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/status');
      setStatus(await res.json());
    } catch {}
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const classifyFile = (name) => {
    const ssPatterns = ['ExpandKeywords', 'KeywordMining', 'CompareKeywords', 'AdsInsights', 'Competitor', 'KeywordResearch'];
    const scPatterns = ['BusinessReport', 'SpSearchTerm', 'SpCampaign', 'FBAFee'];
    if (name.endsWith('.xlsx') && ssPatterns.some(p => name.startsWith(p))) return 'SellerSprite';
    if (name.endsWith('.csv') && scPatterns.some(p => name.startsWith(p))) return 'Seller Central';
    return null;
  };

  const handleFiles = (fileList) => {
    const arr = Array.from(fileList).map(f => ({
      file: f,
      name: f.name,
      size: f.size,
      type: classifyFile(f.name),
    }));
    setFiles(prev => [...prev, ...arr]);
    setUploadResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const removeFile = (idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const upload = async () => {
    const valid = files.filter(f => f.type);
    if (valid.length === 0) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      valid.forEach(f => formData.append('files', f.file));
      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      const result = await res.json();
      setUploadResult(result);
      setFiles([]);
      fetchStatus();
    } catch (err) {
      setUploadResult({ error: err.message });
    } finally {
      setUploading(false);
    }
  };

  const runProcess = async () => {
    setProcessing(true);
    setProcessLog(null);
    try {
      const res = await fetch('/api/process', { method: 'POST' });
      const result = await res.json();
      setProcessLog(result);
      if (result.success) {
        fetchStatus();
        onRefresh();
      }
    } catch (err) {
      setProcessLog({ success: false, error: err.message });
    } finally {
      setProcessing(false);
    }
  };

  const dropZoneStyle = {
    border: `2px dashed ${dragOver ? '#0365C0' : '#d1d5db'}`,
    borderRadius: 12,
    padding: 40,
    textAlign: 'center',
    background: dragOver ? '#eff6ff' : '#f8f9fb',
    cursor: 'pointer',
    transition: 'all 0.2s',
    marginBottom: 20,
  };

  const btnStyle = (primary, disabled) => ({
    padding: '10px 24px',
    borderRadius: 8,
    border: 'none',
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    background: primary ? '#0365C0' : '#e5e7eb',
    color: primary ? '#fff' : '#374151',
    fontFamily: "'Noto Sans SC', 'Inter', sans-serif",
  });

  const fileTagStyle = (type) => ({
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    background: type === 'SellerSprite' ? '#dbeafe' : type === 'Seller Central' ? '#d1fae5' : '#fee2e2',
    color: type === 'SellerSprite' ? '#1e40af' : type === 'Seller Central' ? '#065f46' : '#991b1b',
  });

  return (
    <>
      {/* Upload zone */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>上传数据文件</h3>
        <div
          style={dropZoneStyle}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <div style={{ fontSize: 36, marginBottom: 8, color: '#9ca3af' }}>+</div>
          <div style={{ fontSize: 15, color: '#374151', marginBottom: 4 }}>
            拖拽文件到此处，或点击选择文件
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>
            支持卖家精灵 .xlsx 和卖家后台 .csv —{' '}
            <span style={{ color: '#0365C0', cursor: 'pointer' }}>不确定需要哪些文件？查看下方导出指南</span>
          </div>
          <input
            id="file-input"
            type="file"
            multiple
            accept=".xlsx,.csv"
            style={{ display: 'none' }}
            onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }}
          />
        </div>

        {files.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#374151' }}>
              待上传文件 ({files.length})
            </div>
            {files.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
                background: i % 2 ? '#f8f9fb' : '#fff', borderRadius: 6,
              }}>
                <span style={{ flex: 1, fontSize: 13 }}>{f.name}</span>
                <span style={fileTagStyle(f.type)}>{f.type === 'SellerSprite' ? '卖家精灵' : f.type === 'Seller Central' ? '卖家后台' : '未知'}</span>
                <span style={{ fontSize: 12, color: '#9ca3af', fontFamily: "'JetBrains Mono'" }}>
                  {fmtBytes(f.size)}
                </span>
                <button onClick={() => removeFile(i)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: 16,
                }}>x</button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
              <button style={btnStyle(true, uploading || files.filter(f => f.type).length === 0)} onClick={upload} disabled={uploading || files.filter(f => f.type).length === 0}>
                {uploading ? '上传中...' : `上传 ${files.filter(f => f.type).length} 个文件`}
              </button>
              <button style={btnStyle(false, false)} onClick={() => setFiles([])}>清空</button>
            </div>
            {files.some(f => !f.type) && (
              <div style={{ fontSize: 12, color: '#dc2626', marginTop: 8 }}>
                标记为「未知」的文件将被跳过（文件名不匹配已知模式）
              </div>
            )}
          </div>
        )}

        {uploadResult && (
          <div style={{
            padding: 16, borderRadius: 8, marginTop: 12,
            background: uploadResult.error ? '#fef2f2' : '#f0fdf4',
            border: `1px solid ${uploadResult.error ? '#fecaca' : '#bbf7d0'}`,
          }}>
            {uploadResult.error ? (
              <div style={{ color: '#dc2626', fontSize: 13 }}>错误: {uploadResult.error}</div>
            ) : (
              <>
                {uploadResult.saved?.length > 0 && (
                  <div style={{ color: '#059669', fontSize: 13, marginBottom: 4 }}>
                    已保存 {uploadResult.saved.length} 个文件: {uploadResult.saved.map(f => f.filename).join(', ')}
                  </div>
                )}
                {uploadResult.rejected?.length > 0 && (
                  <div style={{ color: '#d97706', fontSize: 13 }}>
                    已拒绝 {uploadResult.rejected.length} 个: {uploadResult.rejected.map(f => `${f.filename} (${f.reason})`).join(', ')}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Guide accordions */}
      <GuideAccordion title="获取数据文件" subtitle="文件获取指南">
        <FileGuideSection />
      </GuideAccordion>

      <GuideAccordion title="数据流向" subtitle="数据处理流程">
        <DataFlowSection />
      </GuideAccordion>

      <GuideAccordion title="指标定义" subtitle="指标说明">
        <MetricGuideSection />
      </GuideAccordion>

      {/* Process button */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>运行数据处理</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <button style={btnStyle(true, processing)} onClick={runProcess} disabled={processing}>
            {processing ? '处理中...' : '运行数据处理'}
          </button>
          {processing && (
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              正在执行 generate_report.py（最长 120 秒）...
            </span>
          )}
        </div>
        {processLog && (
          <div style={{
            padding: 16, borderRadius: 8,
            background: processLog.success ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${processLog.success ? '#bbf7d0' : '#fecaca'}`,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: processLog.success ? '#059669' : '#dc2626' }}>
              {processLog.success ? '数据处理完成' : '数据处理失败'}
              {processLog.elapsed_ms && ` (${(processLog.elapsed_ms / 1000).toFixed(1)}s)`}
            </div>
            {processLog.error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{processLog.error}</div>}
            {(processLog.stdout || processLog.stderr) && (
              <pre style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11, lineHeight: 1.5,
                background: '#1f2937', color: '#e5e7eb', padding: 16, borderRadius: 8,
                maxHeight: 400, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {processLog.stdout}{processLog.stderr ? '\n--- 错误输出 ---\n' + processLog.stderr : ''}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Current files */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>当前输入文件</h3>
        {status ? (
          <>
            {status.lastRun && (
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
                上次运行: {status.lastRun}
              </div>
            )}
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 300 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#1e40af' }}>
                  卖家精灵 ({status.inputFiles.sellersprite.length} 个文件)
                </div>
                {status.inputFiles.sellersprite.length === 0 ? (
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>暂无文件</div>
                ) : (
                  status.inputFiles.sellersprite.map((f, i) => (
                    <div key={i} style={{ fontSize: 12, padding: '4px 0', color: f.ignored ? '#d1d5db' : '#374151', display: 'flex', justifyContent: 'space-between', textDecoration: f.ignored ? 'line-through' : 'none' }}>
                      <span>{f.name}{f.ignored ? ' (已忽略)' : ''}</span>
                      <span style={{ color: '#9ca3af', fontFamily: "'JetBrains Mono'" }}>{fmtBytes(f.size)}</span>
                    </div>
                  ))
                )}
              </div>
              <div style={{ flex: 1, minWidth: 300 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#065f46' }}>
                  卖家后台 ({status.inputFiles.sellerCentral.length} 个文件)
                </div>
                {status.inputFiles.sellerCentral.length === 0 ? (
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>暂无文件</div>
                ) : (
                  status.inputFiles.sellerCentral.map((f, i) => (
                    <div key={i} style={{ fontSize: 12, padding: '4px 0', color: '#374151', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{f.name}</span>
                      <span style={{ color: '#9ca3af', fontFamily: "'JetBrains Mono'" }}>{fmtBytes(f.size)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
            {status.processedFiles.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#0365C0' }}>
                  已处理输出 ({status.processedFiles.length} 个文件)
                </div>
                {status.processedFiles.map((f, i) => (
                  <div key={i} style={{ fontSize: 12, padding: '4px 0', color: '#374151', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{f.name}</span>
                    <span style={{ color: '#9ca3af', fontFamily: "'JetBrains Mono'" }}>{fmtBytes(f.size)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: 13, color: '#9ca3af' }}>加载状态中...</div>
        )}
      </div>
    </>
  );
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('control');
  const [productInfo, setProductInfo] = useState(null);

  // Product selector state
  const [products, setProducts] = useState([]);
  const [activeProductId, setActiveProductId] = useState(null);
  const [showProductSelector, setShowProductSelector] = useState(false);
  const [newProductAsin, setNewProductAsin] = useState('');
  const [addingProduct, setAddingProduct] = useState(false);

  const { competitors, keywords, ads, pricing, traffic, gapAnalysis, loading, error, refresh } = useData(activeProductId);

  // Fetch product list
  useEffect(() => {
    fetch('/api/products')
      .then(r => r.json())
      .then(data => {
        setProducts(data.products || []);
        setActiveProductId(data.active_product_id);
      })
      .catch(() => {});
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!showProductSelector) return;
    const handleClickOutside = () => setShowProductSelector(false);
    const timer = setTimeout(() => document.addEventListener('click', handleClickOutside), 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('click', handleClickOutside);
    };
  }, [showProductSelector]);

  // Product switch handler
  const switchProduct = async (productId) => {
    setActiveProductId(productId);
    setShowProductSelector(false);
    await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'set_active', product_id: productId }),
    });
    window.location.reload();
  };

  // Add new product handler
  const addProduct = async () => {
    if (!newProductAsin.trim()) return;
    setAddingProduct(true);
    try {
      await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create', asin: newProductAsin.trim() }),
      });
      const res = await fetch('/api/products');
      const data = await res.json();
      setProducts(data.products || []);
      setActiveProductId(data.active_product_id);
      setNewProductAsin('');
    } catch (e) {
      console.error('Failed to add product:', e);
    }
    setAddingProduct(false);
  };

  // Fetch product info from config for dynamic header
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config', { cache: 'no-store' });
      const data = await res.json();
      if (data.product?.title) setProductInfo(data);
    } catch {}
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  // Auto-refresh dashboard data + config when collection finishes
  const handleRefresh = useCallback(() => {
    refresh();
    fetchConfig();
  }, [refresh, fetchConfig]);

  // Build dynamic header from product info
  const brand = productInfo?.product?.brand || '';
  const title = productInfo?.product?.title || '';
  const asin = productInfo?.product?.asin || '';
  const shortTitle = title.length > 60 ? title.substring(0, 60) + '...' : title;

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={{ ...styles.card, textAlign: 'center', padding: 60 }}>
          <div style={{ fontSize: 18, color: '#6b7280', marginBottom: 8 }}>加载数据中...</div>
          <div style={{ fontSize: 13, color: '#9ca3af' }}>正在获取报告数据</div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <div style={styles.headerTitle}>
            肯葳科技亚马逊自动运营系统
          </div>
          <div style={styles.headerSub}>
            {brand && shortTitle ? `${brand} ${shortTitle}` : shortTitle || '请在控制中心输入产品链接开始分析'}
            {asin ? ` — ${asin}` : ''}
            {' | '}{new Date().toLocaleDateString()}
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: 13, opacity: 0.9 }}>
          <div>{fmt(keywords?.length || 0)} 关键词</div>
          <div>{competitors?.length || 0} 竞品</div>
          <div>{gapAnalysis?.length || 0} 差距关键词</div>
        </div>
      </div>

      {/* Product Selector Bar */}
      <div style={{
        padding: '8px 24px',
        background: '#ffffff',
        borderRadius: 10,
        marginBottom: 16,
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}>
        <span style={{ fontSize: '13px', color: '#6b7280', fontWeight: 500, fontFamily: "'Noto Sans SC', sans-serif" }}>
          产品 Product:
        </span>

        {/* Current product chip / dropdown trigger */}
        <div
          onClick={(e) => { e.stopPropagation(); setShowProductSelector(!showProductSelector); }}
          style={{
            position: 'relative',
            padding: '6px 32px 6px 12px',
            background: '#f0f7ff',
            border: '1px solid #0365C0',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '13px',
            color: '#1f2937',
            fontWeight: 500,
          }}
        >
          {(() => {
            const active = products.find(p => p.id === activeProductId);
            return active
              ? `${active.brand || active.asin} — ${active.asin}`
              : (brand && asin ? `${brand} — ${asin}` : brand || asin || 'No product selected');
          })()}
          <span style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', fontSize: '10px', color: '#6b7280' }}>
            {showProductSelector ? '\u25B2' : '\u25BC'}
          </span>

          {/* Dropdown */}
          {showProductSelector && (
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: '4px',
                background: '#ffffff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                zIndex: 1000,
                minWidth: '320px',
                maxHeight: '300px',
                overflowY: 'auto',
              }}
            >
              {products.length === 0 && (
                <div style={{ padding: '12px 16px', fontSize: '13px', color: '#9ca3af' }}>
                  No products found
                </div>
              )}
              {products.map(p => (
                <div
                  key={p.id}
                  onClick={() => switchProduct(p.id)}
                  style={{
                    padding: '10px 16px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #f3f4f6',
                    background: p.id === activeProductId ? '#f0f7ff' : '#ffffff',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => { if (p.id !== activeProductId) e.currentTarget.style.background = '#f9fafb'; }}
                  onMouseLeave={e => { if (p.id !== activeProductId) e.currentTarget.style.background = '#ffffff'; }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '13px', color: '#1f2937' }}>
                      {p.brand || 'Unknown'} — {p.asin}
                    </div>
                    <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                      {p.title ? (p.title.length > 50 ? p.title.substring(0, 50) + '...' : p.title) : 'No title'}
                    </div>
                  </div>
                  {p.id === activeProductId && (
                    <span style={{ fontSize: '11px', color: '#0365C0', fontWeight: 600 }}>Active</span>
                  )}
                </div>
              ))}

              {/* Add new product input */}
              <div style={{ padding: '10px 16px', borderTop: '2px solid #e5e7eb' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    value={newProductAsin}
                    onChange={e => setNewProductAsin(e.target.value)}
                    onClick={e => e.stopPropagation()}
                    placeholder="Enter ASIN (e.g. B094PZTFMB)"
                    style={{
                      flex: 1,
                      padding: '6px 10px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '12px',
                      outline: 'none',
                    }}
                    onKeyDown={e => { if (e.key === 'Enter') addProduct(); }}
                  />
                  <button
                    onClick={addProduct}
                    disabled={addingProduct}
                    style={{
                      padding: '6px 12px',
                      background: '#0365C0',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      cursor: addingProduct ? 'wait' : 'pointer',
                      fontWeight: 500,
                      opacity: addingProduct ? 0.6 : 1,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {addingProduct ? '...' : '+ Add'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Product count badge */}
        <span style={{ fontSize: '11px', color: '#9ca3af' }}>
          {products.length} product{products.length !== 1 ? 's' : ''}
        </span>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 8, marginBottom: 16,
          background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', fontSize: 13,
        }}>
          数据加载失败: {error}
        </div>
      )}

      <div style={styles.tabBar}>
        {TABS.map(t => (
          <button key={t.key} style={styles.tab(activeTab === t.key)}
                  onClick={() => setActiveTab(t.key)}>
            {t.zh}
          </button>
        ))}
      </div>

      {activeTab === 'control' && <ControlTab onRefresh={handleRefresh} />}
      {activeTab === 'competitors' && <CompetitorsTab competitors={competitors} />}
      {activeTab === 'products' && <ProductsTab pricing={pricing} />}
      {activeTab === 'keywords' && <KeywordsTab keywords={keywords} />}
      {activeTab === 'ads' && <AdsTab ads={ads} />}
      {activeTab === 'pricing' && <PricingTab pricing={pricing} />}
      {activeTab === 'traffic' && <TrafficTab traffic={traffic} />}
      {activeTab === 'gap' && <GapTab gapAnalysis={gapAnalysis} />}
    </div>
  );
}
