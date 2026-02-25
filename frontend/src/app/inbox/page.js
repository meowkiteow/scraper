'use client';

import { useEffect, useState } from 'react';
import { Inbox, RefreshCw, Tag, Eye, Filter } from 'lucide-react';
import { Button, EmptyState } from '@/components/UI';
import api from '@/lib/api';

const LABELS = [
    { value: 'all', label: 'All', color: 'gray' },
    { value: 'interested', label: 'Interested', color: 'green' },
    { value: 'not_interested', label: 'Not Interested', color: 'red' },
    { value: 'meeting_booked', label: 'Meeting Booked', color: 'blue' },
    { value: 'follow_up', label: 'Follow Up', color: 'yellow' },
    { value: 'none', label: 'Untagged', color: 'gray' },
];

const LABEL_COLORS = {
    interested: 'bg-green-100 text-green-700',
    not_interested: 'bg-red-100 text-red-700',
    meeting_booked: 'bg-blue-100 text-blue-700',
    follow_up: 'bg-yellow-100 text-yellow-700',
    unsubscribe: 'bg-gray-100 text-gray-600',
    none: 'bg-gray-50 text-gray-500',
};

export default function InboxPage() {
    const [data, setData] = useState({ messages: [], total: 0, unread_count: 0 });
    const [selected, setSelected] = useState(null);
    const [message, setMessage] = useState(null);
    const [filter, setFilter] = useState('all');
    const [syncing, setSyncing] = useState(false);

    const load = () => {
        const params = { per_page: 50 };
        if (filter !== 'all') params.label = filter;
        api.getInbox(params).then(setData).catch(() => { });
    };
    useEffect(() => { load(); }, [filter]);

    const openMessage = async (msg) => {
        setSelected(msg);
        if (!msg.is_read) {
            await api.markRead(msg.id);
            load();
        }
    };

    const setLabel = async (msgId, label) => {
        await api.setLabel(msgId, label);
        load();
        if (selected?.id === msgId) {
            setSelected(s => ({ ...s, label }));
        }
    };

    const syncNow = async () => {
        setSyncing(true);
        try {
            const res = await api.syncInbox();
            setMessage({ type: 'success', text: `Synced! ${res.new_messages} new messages.` });
            load();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
        setSyncing(false);
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Inbox</h1>
                    <p className="text-sm text-gray-500 mt-1">{data.unread_count} unread · {data.total} total</p>
                </div>
                <Button variant="secondary" onClick={syncNow} disabled={syncing}>
                    <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} /> Sync Now
                </Button>
            </div>

            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="float-right">&times;</button>
                </div>
            )}

            {/* Filter tabs */}
            <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
                {LABELS.map(l => (
                    <button key={l.value} onClick={() => setFilter(l.value)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filter === l.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>
                        {l.label}
                    </button>
                ))}
            </div>

            <div className="flex gap-4 h-[calc(100vh-220px)]">
                {/* Thread List */}
                <div className="w-96 bg-white rounded-xl border border-gray-200 shadow-sm overflow-y-auto flex-shrink-0">
                    {data.messages.length === 0 ? (
                        <div className="p-6">
                            <EmptyState icon={Inbox} title="No messages" description="Sync your inbox to see replies." />
                        </div>
                    ) : data.messages.map(msg => (
                        <div key={msg.id} onClick={() => openMessage(msg)}
                            className={`px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${selected?.id === msg.id ? 'bg-blue-50' : 'hover:bg-gray-50'} ${!msg.is_read ? 'bg-blue-50/50' : ''}`}>
                            <div className="flex items-center justify-between mb-1">
                                <span className={`text-sm ${!msg.is_read ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>
                                    {msg.lead?.first_name || msg.from_email?.split('@')[0] || 'Unknown'}
                                </span>
                                <span className="text-xs text-gray-400">{msg.received_at?.split('T')[0]}</span>
                            </div>
                            <p className="text-sm text-gray-500 truncate">{msg.subject}</p>
                            <div className="flex items-center gap-2 mt-1">
                                {msg.label && msg.label !== 'none' && (
                                    <span className={`text-xs px-1.5 py-0.5 rounded ${LABEL_COLORS[msg.label]}`}>{msg.label.replace('_', ' ')}</span>
                                )}
                                {!msg.is_read && <span className="w-2 h-2 rounded-full bg-blue-500" />}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Message View */}
                <div className="flex-1 bg-white rounded-xl border border-gray-200 shadow-sm overflow-y-auto">
                    {selected ? (
                        <div className="p-6">
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <h2 className="text-lg font-semibold text-gray-900">{selected.subject}</h2>
                                    <p className="text-sm text-gray-500">From: {selected.from_email}</p>
                                    <p className="text-xs text-gray-400">{selected.received_at}</p>
                                    {selected.lead && (
                                        <p className="text-sm text-blue-600 mt-1">{selected.lead.first_name} at {selected.lead.company}</p>
                                    )}
                                </div>
                            </div>

                            {/* Label buttons */}
                            <div className="flex gap-2 mb-4 flex-wrap">
                                {['interested', 'not_interested', 'meeting_booked', 'follow_up'].map(l => (
                                    <button key={l} onClick={() => setLabel(selected.id, l)}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${selected.label === l
                                            ? LABEL_COLORS[l] + ' border-transparent'
                                            : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                                        {l.replace('_', ' ')}
                                    </button>
                                ))}
                            </div>

                            <div className="border-t border-gray-100 pt-4">
                                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap"
                                    dangerouslySetInnerHTML={{ __html: selected.body || 'No content' }} />
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-gray-400">Select a message to view</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
