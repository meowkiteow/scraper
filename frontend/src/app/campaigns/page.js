'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus, Send, Copy, Trash2 } from 'lucide-react';
import { Button, StatusBadge, EmptyState } from '@/components/UI';
import api from '@/lib/api';

export default function CampaignsPage() {
    const router = useRouter();
    const [campaigns, setCampaigns] = useState([]);
    const [filter, setFilter] = useState('all');
    const [creating, setCreating] = useState(false);
    const [name, setName] = useState('');

    const load = () => api.getCampaigns().then(setCampaigns).catch(() => { });
    useEffect(() => { load(); }, []);

    const filtered = filter === 'all' ? campaigns : campaigns.filter(c => c.status === filter);

    const createCampaign = async () => {
        if (!name.trim()) return;
        try {
            const c = await api.createCampaign({ name });
            router.push(`/campaigns/${c.id}`);
        } catch (err) {
            alert(err.message);
        }
    };

    const duplicateCampaign = async (id) => {
        await api.duplicateCampaign(id);
        load();
    };

    const deleteCampaign = async (id) => {
        if (confirm('Delete this campaign? This cannot be undone.')) {
            await api.deleteCampaign(id);
            load();
        }
    };

    const tabs = ['all', 'active', 'paused', 'draft', 'completed'];

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
                    <p className="text-sm text-gray-500 mt-1">{campaigns.length} campaigns</p>
                </div>
                <Button onClick={() => setCreating(true)}><Plus className="w-4 h-4" /> New Campaign</Button>
            </div>

            {/* Create inline */}
            {creating && (
                <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 flex items-center gap-3">
                    <input type="text" placeholder="Campaign name..." value={name} onChange={e => setName(e.target.value)}
                        autoFocus onKeyDown={e => e.key === 'Enter' && createCampaign()}
                        className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <Button onClick={createCampaign}>Create</Button>
                    <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
                </div>
            )}

            {/* Filter tabs */}
            <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
                {tabs.map(tab => (
                    <button key={tab} onClick={() => setFilter(tab)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${filter === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>
                        {tab}
                    </button>
                ))}
            </div>

            {filtered.length === 0 ? (
                <EmptyState icon={Send} title="No campaigns found" description={filter === 'all' ? "Create your first campaign to start sending." : `No ${filter} campaigns.`}
                    action={filter === 'all' && <Button onClick={() => setCreating(true)}>Create Campaign</Button>} />
            ) : (
                <div className="space-y-3">
                    {filtered.map(c => (
                        <div key={c.id} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition-shadow">
                            <div className="flex items-center justify-between">
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-2">
                                        <Link href={`/campaigns/${c.id}`} className="text-base font-semibold text-gray-900 hover:text-blue-600">
                                            {c.name}
                                        </Link>
                                        <StatusBadge status={c.status} />
                                    </div>
                                    <div className="flex items-center gap-6 text-sm text-gray-500">
                                        <span>{c.leads_count} leads</span>
                                        <span>{c.steps_count} steps</span>
                                        <span>{c.accounts_count} accounts</span>
                                        <span>{c.total_sent} sent</span>
                                        <span>{c.open_rate}% opened</span>
                                        <span>{c.reply_rate}% replied</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Link href={`/campaigns/${c.id}`}>
                                        <Button variant="secondary" size="sm">Open</Button>
                                    </Link>
                                    <Button variant="ghost" size="sm" onClick={() => duplicateCampaign(c.id)}><Copy className="w-4 h-4" /></Button>
                                    <Button variant="ghost" size="sm" onClick={() => deleteCampaign(c.id)}><Trash2 className="w-4 h-4 text-red-500" /></Button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
