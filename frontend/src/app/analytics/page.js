'use client';

import { useEffect, useState } from 'react';
import { BarChart3, Send, Eye, MessageSquare, AlertTriangle, TrendingUp } from 'lucide-react';
import { MetricCard } from '@/components/UI';
import api from '@/lib/api';

export default function AnalyticsPage() {
    const [overview, setOverview] = useState(null);
    const [campaigns, setCampaigns] = useState([]);
    const [selectedCampaign, setSelectedCampaign] = useState(null);
    const [daily, setDaily] = useState([]);
    const [stepStats, setStepStats] = useState([]);

    useEffect(() => {
        api.getOverview().then(setOverview).catch(() => { });
        api.getCampaigns().then(setCampaigns).catch(() => { });
    }, []);

    useEffect(() => {
        if (selectedCampaign) {
            api.getCampaignAnalytics(selectedCampaign).then(d => setDaily(d.daily || [])).catch(() => { });
            api.getStepAnalytics(selectedCampaign).then(d => setStepStats(d.steps || [])).catch(() => { });
        }
    }, [selectedCampaign]);

    const maxSent = Math.max(...(daily.map(d => d.sent) || [1]), 1);

    return (
        <div>
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
                <p className="text-sm text-gray-500 mt-1">Track your email outreach performance</p>
            </div>

            {/* Global Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
                <MetricCard label="Total Sent" value={overview?.total_sent?.toLocaleString() || '0'} icon={Send} color="blue" />
                <MetricCard label="Open Rate" value={`${overview?.open_rate || 0}%`} icon={Eye} color="green" />
                <MetricCard label="Click Rate" value={`${overview?.click_rate || 0}%`} icon={TrendingUp} color="purple" />
                <MetricCard label="Reply Rate" value={`${overview?.reply_rate || 0}%`} icon={MessageSquare} color="orange" />
                <MetricCard label="Bounce Rate" value={`${overview?.bounce_rate || 0}%`} icon={AlertTriangle} color="red" />
            </div>

            {/* Campaign Selector */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
                <div className="flex items-center gap-4 mb-4">
                    <h2 className="text-lg font-semibold text-gray-900">Campaign Analytics</h2>
                    <select value={selectedCampaign || ''} onChange={e => setSelectedCampaign(e.target.value || null)}
                        className="px-3 py-1.5 rounded-lg border border-gray-300 text-sm">
                        <option value="">Select campaign...</option>
                        {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                </div>

                {/* Simple bar chart using CSS */}
                {selectedCampaign && daily.length > 0 && (
                    <div>
                        <h3 className="text-sm font-medium text-gray-700 mb-3">Daily Sends (Last 30 Days)</h3>
                        <div className="flex items-end gap-1 h-32">
                            {daily.map((d, i) => (
                                <div key={i} className="flex-1 flex flex-col items-center group relative">
                                    <div className="w-full bg-blue-500 rounded-t transition-all hover:bg-blue-600"
                                        style={{ height: `${(d.sent / maxSent) * 100}%`, minHeight: d.sent > 0 ? '4px' : '0' }} />
                                    {/* Tooltip */}
                                    <div className="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                                        {d.date}: {d.sent} sent, {d.opened} opened, {d.replied} replied
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="flex justify-between text-xs text-gray-400 mt-1">
                            <span>{daily[0]?.date}</span>
                            <span>{daily[daily.length - 1]?.date}</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Per-Step Breakdown */}
            {selectedCampaign && stepStats.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
                    <div className="px-6 py-4 border-b border-gray-100">
                        <h2 className="text-lg font-semibold text-gray-900">Per-Step Performance</h2>
                    </div>
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-gray-100">
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Step</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subject</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Sent</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Opened</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Open Rate</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Replied</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Reply Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stepStats.map(s => (
                                <>
                                    <tr key={s.step_number} className="border-b border-gray-50">
                                        <td className="px-6 py-3 text-sm font-medium text-gray-900">Step {s.step_number}</td>
                                        <td className="px-6 py-3 text-sm text-gray-600 truncate max-w-[200px]">{s.subject || '—'}</td>
                                        <td className="px-6 py-3 text-sm text-gray-600 text-right">{s.sent}</td>
                                        <td className="px-6 py-3 text-sm text-gray-600 text-right">{s.opened}</td>
                                        <td className="px-6 py-3 text-sm text-right">
                                            <span className={`font-medium ${s.open_rate > 30 ? 'text-green-600' : 'text-gray-600'}`}>{s.open_rate}%</span>
                                        </td>
                                        <td className="px-6 py-3 text-sm text-gray-600 text-right">{s.replied}</td>
                                        <td className="px-6 py-3 text-sm text-right">
                                            <span className={`font-medium ${s.reply_rate > 5 ? 'text-green-600' : 'text-gray-600'}`}>{s.reply_rate}%</span>
                                        </td>
                                    </tr>
                                    {/* A/B Variants */}
                                    {s.variants?.length > 1 && s.variants.map(v => (
                                        <tr key={`${s.step_number}-${v.variant}`} className="bg-gray-50/50">
                                            <td className="px-10 py-2 text-xs text-gray-500">{v.label}</td>
                                            <td className="px-6 py-2 text-xs text-gray-400">—</td>
                                            <td className="px-6 py-2 text-xs text-gray-500 text-right">{v.sent}</td>
                                            <td className="px-6 py-2 text-xs text-gray-500 text-right">{v.opened}</td>
                                            <td className="px-6 py-2 text-xs text-right font-medium">{v.open_rate}%</td>
                                            <td className="px-6 py-2 text-xs text-gray-500 text-right">{v.replied}</td>
                                            <td className="px-6 py-2 text-xs text-right font-medium">{v.reply_rate}%</td>
                                        </tr>
                                    ))}
                                </>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Campaign Breakdown Table */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto mt-6">
                <div className="px-6 py-4 border-b border-gray-100">
                    <h2 className="text-lg font-semibold text-gray-900">All Campaigns</h2>
                </div>
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-gray-100">
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Sent</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Open Rate</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Reply Rate</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Leads</th>
                        </tr>
                    </thead>
                    <tbody>
                        {campaigns.map(c => (
                            <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                                onClick={() => setSelectedCampaign(c.id)}>
                                <td className="px-6 py-3 text-sm font-medium text-gray-900">{c.name}</td>
                                <td className="px-6 py-3 text-sm text-gray-600 text-right">{c.total_sent}</td>
                                <td className="px-6 py-3 text-sm text-right font-medium">{c.open_rate}%</td>
                                <td className="px-6 py-3 text-sm text-right font-medium">{c.reply_rate}%</td>
                                <td className="px-6 py-3 text-sm text-gray-600 text-right">{c.leads_count}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
