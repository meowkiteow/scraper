'use client';

import { useEffect, useState } from 'react';
import { Users, Search, Download, Tag, Filter } from 'lucide-react';
import { Button, StatusBadge, EmptyState } from '@/components/UI';
import api from '@/lib/api';

export default function LeadsPage() {
    const [data, setData] = useState({ leads: [], total: 0, page: 1 });
    const [search, setSearch] = useState('');
    const [status, setStatus] = useState('');
    const [page, setPage] = useState(1);

    const load = () => {
        const params = { page, per_page: 50 };
        if (search) params.search = search;
        if (status) params.status = status;
        api.getLeads(params).then(setData).catch(() => { });
    };
    useEffect(() => { load(); }, [search, status, page]);

    const exportCSV = async () => {
        const res = await api.exportLeads(status || undefined);
        const rows = res.leads;
        if (!rows.length) return;
        const headers = Object.keys(rows[0]);
        const csv = [headers.join(','), ...rows.map(r => headers.map(h => `"${r[h] || ''}"`).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'leads.csv'; a.click();
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
                    <p className="text-sm text-gray-500 mt-1">{data.total} total leads</p>
                </div>
                <Button variant="secondary" onClick={exportCSV}><Download className="w-4 h-4" /> Export CSV</Button>
            </div>

            {/* Filters */}
            <div className="flex gap-3 mb-4">
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                    <input type="text" placeholder="Search by email, name, or company..." value={search}
                        onChange={e => { setSearch(e.target.value); setPage(1); }}
                        className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
                    className="px-3 py-2 rounded-lg border border-gray-300 text-sm">
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="replied">Replied</option>
                    <option value="bounced">Bounced</option>
                    <option value="unsubscribed">Unsubscribed</option>
                </select>
            </div>

            {/* Table */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-gray-100">
                            {['Email', 'Name', 'Company', 'Title', 'Status', 'Source', 'Added'].map(h =>
                                <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                            )}
                        </tr>
                    </thead>
                    <tbody>
                        {data.leads.length === 0 ? (
                            <tr><td colSpan={7} className="px-6 py-12 text-center text-sm text-gray-500">No leads found</td></tr>
                        ) : data.leads.map(l => (
                            <tr key={l.id} className="border-b border-gray-50 hover:bg-gray-50">
                                <td className="px-6 py-3 text-sm font-medium text-gray-900">{l.email}</td>
                                <td className="px-6 py-3 text-sm text-gray-600">{l.first_name} {l.last_name}</td>
                                <td className="px-6 py-3 text-sm text-gray-600">{l.company}</td>
                                <td className="px-6 py-3 text-sm text-gray-600">{l.title}</td>
                                <td className="px-6 py-3"><StatusBadge status={l.status} /></td>
                                <td className="px-6 py-3 text-sm text-gray-500 capitalize">{l.source}</td>
                                <td className="px-6 py-3 text-sm text-gray-500">{l.created_at?.split('T')[0]}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {data.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                    <span className="text-sm text-gray-500">Page {data.page} of {data.total_pages}</span>
                    <div className="flex gap-2">
                        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
                        <Button variant="secondary" size="sm" disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)}>Next</Button>
                    </div>
                </div>
            )}
        </div>
    );
}
