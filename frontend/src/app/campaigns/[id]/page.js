'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Play, Pause, Plus, Trash2, ArrowLeft, GripVertical, Copy, ChevronDown, Upload, Users } from 'lucide-react';
import { Button, StatusBadge, Input, Modal } from '@/components/UI';
import api from '@/lib/api';

export default function CampaignEditorPage() {
    const { id } = useParams();
    const router = useRouter();
    const [campaign, setCampaign] = useState(null);
    const [tab, setTab] = useState('sequence');
    const [accounts, setAccounts] = useState([]);
    const [allAccounts, setAllAccounts] = useState([]);
    const [leads, setLeads] = useState({ leads: [], total: 0 });
    const [stats, setStats] = useState(null);
    const [showImport, setShowImport] = useState(false);
    const [importText, setImportText] = useState('');
    const [message, setMessage] = useState(null);

    const load = () => {
        api.getCampaign(id).then(setCampaign).catch(() => router.push('/campaigns'));
        api.getAccounts().then(setAllAccounts).catch(() => { });
        api.getCampaignLeads(id).then(setLeads).catch(() => { });
        api.getCampaignStats(id).then(setStats).catch(() => { });
    };
    useEffect(() => { load(); }, [id]);

    // ── Step Management ──
    const addStep = async () => {
        const stepNum = (campaign?.steps?.length || 0) + 1;
        await api.addStep(id, {
            step_number: stepNum,
            delay_days: stepNum === 1 ? 0 : 2,
            subject: '',
            body: '',
        });
        load();
    };

    const updateStep = async (stepId, field, value) => {
        await api.updateStep(stepId, { [field]: value });
    };

    const deleteStep = async (stepId) => {
        await api.deleteStep(stepId);
        load();
    };

    // ── Campaign Actions ──
    const startCampaign = async () => {
        try {
            await api.startCampaign(id);
            setMessage({ type: 'success', text: 'Campaign started!' });
            load();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
    };

    const pauseCampaign = async () => {
        await api.pauseCampaign(id);
        load();
    };

    const updateSettings = async (field, value) => {
        await api.updateCampaign(id, { [field]: value });
        load();
    };

    // ── Lead Import ──
    const importLeads = async () => {
        const lines = importText.split('\n').filter(l => l.trim());
        const leadsData = lines.map(line => {
            const parts = line.split(',').map(s => s.trim());
            return { email: parts[0], first_name: parts[1] || '', last_name: parts[2] || '', company: parts[3] || '' };
        });
        try {
            const result = await api.importLeads(id, leadsData);
            setMessage({ type: 'success', text: `Added ${result.added} leads (${result.skipped} skipped)` });
            setShowImport(false);
            setImportText('');
            load();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
    };

    if (!campaign) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;

    return (
        <div>
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <button onClick={() => router.push('/campaigns')} className="text-gray-400 hover:text-gray-600">
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div className="flex-1">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
                        <StatusBadge status={campaign.status} />
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                        {campaign.steps?.length || 0} steps · {leads.total} leads · {campaign.accounts?.length || 0} accounts
                    </p>
                </div>
                <div className="flex gap-2">
                    {campaign.status === 'active' ? (
                        <Button variant="secondary" onClick={pauseCampaign}><Pause className="w-4 h-4" /> Pause</Button>
                    ) : (
                        <Button onClick={startCampaign}><Play className="w-4 h-4" /> Start</Button>
                    )}
                </div>
            </div>

            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="float-right">&times;</button>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
                {['sequence', 'leads', 'settings'].map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>
                        {t}
                    </button>
                ))}
            </div>

            {/* ── Sequence Tab ── */}
            {tab === 'sequence' && (
                <div className="space-y-4">
                    {campaign.steps?.map((step, i) => (
                        <div key={step.id} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold">
                                        {step.step_number}
                                    </div>
                                    <span className="text-sm font-medium text-gray-600">
                                        {step.delay_days === 0 ? 'Send immediately' : `Wait ${step.delay_days} day${step.delay_days > 1 ? 's' : ''}`}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {step.step_number > 1 && (
                                        <select value={step.delay_days} onChange={(e) => updateStep(step.id, 'delay_days', parseInt(e.target.value))}
                                            className="text-sm border border-gray-200 rounded-lg px-2 py-1">
                                            {[0, 1, 2, 3, 5, 7, 10, 14].map(d => <option key={d} value={d}>{d} days</option>)}
                                        </select>
                                    )}
                                    <Button variant="ghost" size="sm" onClick={() => deleteStep(step.id)}><Trash2 className="w-4 h-4 text-red-400" /></Button>
                                </div>
                            </div>

                            <input
                                type="text" placeholder="Subject line..."
                                defaultValue={step.subject}
                                onBlur={(e) => updateStep(step.id, 'subject', e.target.value)}
                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-medium mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />

                            <textarea
                                placeholder="Email body... Use {{first_name}}, {{company}} for variables. Use {Hi|Hey|Hello} for spintax."
                                defaultValue={step.body}
                                onBlur={(e) => updateStep(step.id, 'body', e.target.value)}
                                rows={6}
                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />

                            <p className="text-xs text-gray-400 mt-2">
                                Variables: {'{{first_name}}'}, {'{{last_name}}'}, {'{{company}}'}, {'{{title}}'}, {'{{website}}'} · Spintax: {'{Hi|Hey|Hello}'}
                            </p>
                        </div>
                    ))}

                    <button onClick={addStep}
                        className="w-full py-4 rounded-xl border-2 border-dashed border-gray-200 text-gray-400 hover:border-blue-300 hover:text-blue-500 transition-colors text-sm font-medium flex items-center justify-center gap-2">
                        <Plus className="w-4 h-4" /> Add Step
                    </button>
                </div>
            )}

            {/* ── Leads Tab ── */}
            {tab === 'leads' && (
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <span className="text-sm text-gray-500">{leads.total} leads in this campaign</span>
                        <Button onClick={() => setShowImport(true)}><Upload className="w-4 h-4" /> Import Leads</Button>
                    </div>

                    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-100">
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Step</th>
                                </tr>
                            </thead>
                            <tbody>
                                {leads.leads?.length === 0 ? (
                                    <tr><td colSpan={5} className="px-6 py-12 text-center text-sm text-gray-500">No leads imported yet</td></tr>
                                ) : leads.leads?.map(l => (
                                    <tr key={l.id} className="border-b border-gray-50">
                                        <td className="px-6 py-3 text-sm text-gray-900">{l.email}</td>
                                        <td className="px-6 py-3 text-sm text-gray-600">{l.first_name} {l.last_name}</td>
                                        <td className="px-6 py-3 text-sm text-gray-600">{l.company}</td>
                                        <td className="px-6 py-3"><StatusBadge status={l.status} /></td>
                                        <td className="px-6 py-3 text-sm text-gray-600">{l.current_step || 0}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <Modal isOpen={showImport} onClose={() => setShowImport(false)} title="Import Leads">
                        <div className="space-y-4">
                            <p className="text-sm text-gray-500">Paste leads, one per line: <code className="text-xs bg-gray-100 px-1 rounded">email, first_name, last_name, company</code></p>
                            <textarea value={importText} onChange={e => setImportText(e.target.value)} rows={10}
                                placeholder="john@company.com, John, Doe, Acme Inc&#10;jane@startup.io, Jane, Smith, StartupCo"
                                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            <div className="flex justify-end gap-2">
                                <Button variant="secondary" onClick={() => setShowImport(false)}>Cancel</Button>
                                <Button onClick={importLeads}>Import {importText.split('\n').filter(l => l.trim()).length} Leads</Button>
                            </div>
                        </div>
                    </Modal>
                </div>
            )}

            {/* ── Settings Tab ── */}
            {tab === 'settings' && (
                <div className="space-y-6 max-w-2xl">
                    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                        <h3 className="font-semibold text-gray-900 mb-4">Campaign Settings</h3>
                        <div className="space-y-4">
                            <Input label="Campaign Name" defaultValue={campaign.name}
                                onBlur={e => updateSettings('name', e.target.value)} />

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Send Window Start</label>
                                    <select defaultValue={campaign.send_window_start} onChange={e => updateSettings('send_window_start', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
                                        {Array.from({ length: 24 }, (_, i) => <option key={i} value={i}>{i}:00</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Send Window End</label>
                                    <select defaultValue={campaign.send_window_end} onChange={e => updateSettings('send_window_end', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
                                        {Array.from({ length: 24 }, (_, i) => <option key={i} value={i}>{i}:00</option>)}
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">Daily Limit: {campaign.daily_limit}</label>
                                <input type="range" min="10" max="500" step="10" defaultValue={campaign.daily_limit}
                                    onChange={e => updateSettings('daily_limit', parseInt(e.target.value))}
                                    className="w-full accent-blue-600" />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">Rotation Strategy</label>
                                <select defaultValue={campaign.rotation_strategy} onChange={e => updateSettings('rotation_strategy', e.target.value)}
                                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
                                    <option value="round_robin">Round Robin</option>
                                    <option value="weighted">Weighted</option>
                                    <option value="random">Random</option>
                                </select>
                            </div>

                            <div className="space-y-2">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" defaultChecked={campaign.stop_on_reply}
                                        onChange={e => updateSettings('stop_on_reply', e.target.checked)}
                                        className="rounded border-gray-300 text-blue-600" />
                                    <span className="text-sm text-gray-700">Stop sequence on reply</span>
                                </label>
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" defaultChecked={campaign.track_opens}
                                        onChange={e => updateSettings('track_opens', e.target.checked)}
                                        className="rounded border-gray-300 text-blue-600" />
                                    <span className="text-sm text-gray-700">Track opens</span>
                                </label>
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" defaultChecked={campaign.track_clicks}
                                        onChange={e => updateSettings('track_clicks', e.target.checked)}
                                        className="rounded border-gray-300 text-blue-600" />
                                    <span className="text-sm text-gray-700">Track clicks</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Account Assignment */}
                    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                        <h3 className="font-semibold text-gray-900 mb-4">Sending Accounts</h3>
                        <div className="space-y-2">
                            {allAccounts.map(acc => {
                                const assigned = campaign.accounts?.some(a => a.id === acc.id);
                                return (
                                    <label key={acc.id} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${assigned ? 'border-blue-200 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}>
                                        <input type="checkbox" checked={assigned}
                                            onChange={() => {
                                                const ids = assigned
                                                    ? campaign.accounts.filter(a => a.id !== acc.id).map(a => a.id)
                                                    : [...(campaign.accounts?.map(a => a.id) || []), acc.id];
                                                updateSettings('account_ids', ids);
                                            }}
                                            className="rounded border-gray-300 text-blue-600" />
                                        <div>
                                            <p className="text-sm font-medium text-gray-900">{acc.email}</p>
                                            <p className="text-xs text-gray-500">{acc.sends_today}/{acc.daily_limit} sent · <StatusBadge status={acc.status} /></p>
                                        </div>
                                    </label>
                                );
                            })}
                            {allAccounts.length === 0 && (
                                <p className="text-sm text-gray-500">No accounts available. <a href="/accounts" className="text-blue-600 hover:underline">Add one</a></p>
                            )}
                        </div>
                    </div>

                    {/* Stats */}
                    {stats && stats.total_sent > 0 && (
                        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                            <h3 className="font-semibold text-gray-900 mb-4">Performance</h3>
                            <div className="grid grid-cols-4 gap-4">
                                <div className="text-center">
                                    <p className="text-2xl font-bold text-gray-900">{stats.total_sent}</p>
                                    <p className="text-xs text-gray-500">Sent</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-2xl font-bold text-green-600">{stats.open_rate}%</p>
                                    <p className="text-xs text-gray-500">Open Rate</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-2xl font-bold text-blue-600">{stats.click_rate}%</p>
                                    <p className="text-xs text-gray-500">Click Rate</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-2xl font-bold text-purple-600">{stats.reply_rate}%</p>
                                    <p className="text-xs text-gray-500">Reply Rate</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Danger Zone */}
                    <div className="bg-white rounded-xl border border-red-200 shadow-sm p-5">
                        <h3 className="font-semibold text-red-700 mb-2">Danger Zone</h3>
                        <p className="text-sm text-gray-500 mb-4">Permanently delete this campaign and all its data.</p>
                        <Button variant="danger" onClick={() => { if (confirm('Delete permanently?')) { api.deleteCampaign(id); router.push('/campaigns'); } }}>
                            <Trash2 className="w-4 h-4" /> Delete Campaign
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
