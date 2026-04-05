'use client';

import { useState, useEffect } from 'react';

const ACCENT = '#0365C0';
const NAVY = '#1A365D';

export default function SetupPage() {
  const [step, setStep] = useState(0); // 0=welcome, 1=detect, 2=credentials, 3=done
  const [detecting, setDetecting] = useState(false);
  const [adspowerDetected, setAdspowerDetected] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [profileId, setProfileId] = useState('');
  const [profiles, setProfiles] = useState([]);
  const [loadingProfiles, setLoadingProfiles] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const detectAdspower = async () => {
    setDetecting(true);
    setError('');
    try {
      const res = await fetch('/api/setup?action=detect');
      const data = await res.json();
      setAdspowerDetected(data.detected);
      if (data.detected) {
        setTimeout(() => setStep(2), 800);
      }
    } catch {
      setAdspowerDetected(false);
    }
    setDetecting(false);
  };

  const fetchProfiles = async () => {
    if (!apiKey.trim()) return;
    setLoadingProfiles(true);
    setError('');
    try {
      const res = await fetch(`/api/setup?action=profiles&api_key=${encodeURIComponent(apiKey)}`);
      const data = await res.json();
      if (data.success && data.profiles?.length > 0) {
        setProfiles(data.profiles);
        if (data.profiles.length === 1) {
          setProfileId(data.profiles[0].id);
        }
      } else {
        setError(data.error || 'API Key 无效或无可用配置');
        setProfiles([]);
      }
    } catch {
      setError('连接失败，请检查 API Key');
    }
    setLoadingProfiles(false);
  };

  const saveSetup = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, profile_id: profileId }),
      });
      const data = await res.json();
      if (data.success) {
        setStep(3);
        setTimeout(() => { window.location.href = '/'; }, 2000);
      } else {
        setError(data.error || '保存失败');
      }
    } catch (e) {
      setError('保存失败: ' + e.message);
    }
    setSaving(false);
  };

  useEffect(() => {
    if (step === 1) detectAdspower();
  }, [step]);

  const containerStyle = {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Inter', 'Noto Sans SC', -apple-system, sans-serif",
  };

  const cardStyle = {
    background: '#fff',
    borderRadius: 16,
    boxShadow: '0 4px 24px rgba(0,0,0,0.1)',
    padding: '48px 40px',
    maxWidth: 520,
    width: '100%',
    margin: 20,
  };

  const titleStyle = {
    fontSize: 24,
    fontWeight: 700,
    color: NAVY,
    marginBottom: 8,
    textAlign: 'center',
  };

  const subtitleStyle = {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 1.6,
  };

  const btnStyle = (primary = true, disabled = false) => ({
    display: 'inline-block',
    padding: '12px 32px',
    borderRadius: 8,
    border: primary ? 'none' : '1px solid #d1d5db',
    background: disabled ? '#d1d5db' : primary ? ACCENT : '#fff',
    color: disabled ? '#9ca3af' : primary ? '#fff' : '#374151',
    fontSize: 15,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s',
    textAlign: 'center',
    width: '100%',
  });

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    borderRadius: 8,
    border: '1px solid #d1d5db',
    fontSize: 14,
    outline: 'none',
    transition: 'border 0.2s',
    boxSizing: 'border-box',
    fontFamily: "'JetBrains Mono', monospace",
  };

  const stepIndicator = (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 24 }}>
      {[0, 1, 2, 3].map(i => (
        <div key={i} style={{
          width: i === step ? 24 : 8,
          height: 8,
          borderRadius: 4,
          background: i <= step ? ACCENT : '#e5e7eb',
          transition: 'all 0.3s',
        }} />
      ))}
    </div>
  );

  // Step 0: Welcome
  if (step === 0) {
    return (
      <div style={containerStyle}>
        <div style={cardStyle}>
          {stepIndicator}
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x1f680;</div>
          </div>
          <div style={titleStyle}>欢迎使用肯葳自动运营系统</div>
          <div style={subtitleStyle}>
            首次使用需要配置 AdsPower 浏览器自动化工具。<br />
            这将允许系统自动从卖家精灵采集数据。<br />
            <span style={{ color: '#9ca3af', fontSize: 12 }}>
              如果不使用自动采集，可以跳过此步骤，手动上传数据。
            </span>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button style={btnStyle(true)} onClick={() => setStep(1)}>
              开始配置
            </button>
          </div>
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button
              style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 13 }}
              onClick={() => { window.location.href = '/'; }}
            >
              跳过配置，手动上传数据 &rarr;
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 1: Detect AdsPower
  if (step === 1) {
    return (
      <div style={containerStyle}>
        <div style={cardStyle}>
          {stepIndicator}
          <div style={titleStyle}>检测 AdsPower</div>
          <div style={subtitleStyle}>
            正在检测你的电脑上是否运行了 AdsPower 浏览器管理工具。
          </div>
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            {detecting && (
              <div>
                <div style={{ fontSize: 36, marginBottom: 16, animation: 'spin 1s linear infinite' }}>&#x1f50d;</div>
                <div style={{ color: '#6b7280' }}>正在检测...</div>
              </div>
            )}
            {!detecting && adspowerDetected === true && (
              <div>
                <div style={{ fontSize: 48, marginBottom: 16 }}>&#x2705;</div>
                <div style={{ color: '#059669', fontWeight: 600, fontSize: 18 }}>AdsPower 已检测到</div>
                <div style={{ color: '#6b7280', marginTop: 8 }}>正在跳转到下一步...</div>
              </div>
            )}
            {!detecting && adspowerDetected === false && (
              <div>
                <div style={{ fontSize: 48, marginBottom: 16 }}>&#x26a0;&#xfe0f;</div>
                <div style={{ color: '#dc2626', fontWeight: 600, fontSize: 16 }}>未检测到 AdsPower</div>
                <div style={{ color: '#6b7280', marginTop: 12, lineHeight: 1.8, fontSize: 13 }}>
                  请确认：<br />
                  1. AdsPower 应用已打开并运行<br />
                  2. AdsPower 设置中已启用 API（端口 50325）<br />
                  3. 你已在 AdsPower 浏览器中登录了卖家精灵
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center' }}>
                  <button style={btnStyle(true)} onClick={detectAdspower}>重新检测</button>
                  <button style={btnStyle(false)} onClick={() => setStep(2)}>手动输入</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Step 2: API Key + Profile
  if (step === 2) {
    return (
      <div style={containerStyle}>
        <div style={cardStyle}>
          {stepIndicator}
          <div style={titleStyle}>输入 AdsPower 凭证</div>

          {/* API Key */}
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
              API Key
            </label>
            <input
              type="text"
              style={inputStyle}
              placeholder="粘贴你的 AdsPower API Key"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              onBlur={fetchProfiles}
            />
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
              获取方法：AdsPower &rarr; 右上角 &#x2699;&#xfe0f; 设置 &rarr; API &rarr; 复制 Key
            </div>
          </div>

          {/* Fetch Profiles Button */}
          {apiKey && profiles.length === 0 && (
            <button
              style={{ ...btnStyle(true, loadingProfiles), marginBottom: 24 }}
              onClick={fetchProfiles}
              disabled={loadingProfiles}
            >
              {loadingProfiles ? '正在获取配置列表...' : '获取浏览器配置列表'}
            </button>
          )}

          {/* Profile Selection */}
          {profiles.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                选择浏览器配置
                {profiles.length === 1 && <span style={{ color: '#059669', fontWeight: 400 }}> (已自动选择)</span>}
              </label>
              {profiles.map(p => (
                <div
                  key={p.id}
                  onClick={() => setProfileId(p.id)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    border: `2px solid ${profileId === p.id ? ACCENT : '#e5e7eb'}`,
                    background: profileId === p.id ? '#eff6ff' : '#fff',
                    cursor: 'pointer',
                    marginBottom: 8,
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#1f2937' }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: '#6b7280', fontFamily: "'JetBrains Mono', monospace" }}>
                    ID: {p.id} {p.ip ? `| IP: ${p.ip}` : ''}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              padding: '12px 16px',
              borderRadius: 8,
              background: '#fef2f2',
              color: '#dc2626',
              fontSize: 13,
              marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          {/* Save */}
          <button
            style={btnStyle(true, !apiKey || !profileId || saving)}
            onClick={saveSetup}
            disabled={!apiKey || !profileId || saving}
          >
            {saving ? '正在保存...' : '保存并进入系统'}
          </button>

          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button
              style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 13 }}
              onClick={() => setStep(1)}
            >
              &larr; 返回上一步
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 3: Done
  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        {stepIndicator}
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>&#x1f389;</div>
          <div style={titleStyle}>配置完成！</div>
          <div style={subtitleStyle}>
            系统已准备就绪，正在跳转到仪表盘...<br />
            你可以在控制中心输入 Amazon 产品链接开始分析。
          </div>
        </div>
      </div>
    </div>
  );
}
