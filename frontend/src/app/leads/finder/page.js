'use client';

import { useState, useEffect, useRef } from 'react';
import { MapPin, Search, Loader2, Users, Square, Trash2, Download, Clock, X, Settings2 } from 'lucide-react';
import { Button, EmptyState, MetricCard } from '@/components/UI';
import api from '@/lib/api';

export default function ProspectorPage() {
    const [query, setQuery] = useState('');
    const [location, setLocation] = useState('');
    const [limit, setLimit] = useState(20);
    const [searching, setSearching] = useState(false);
    const [results, setResults] = useState([]);
    const [message, setMessage] = useState(null);
    const [progress, setProgress] = useState('');
    const [jobId, setJobId] = useState(null);
    const pollRef = useRef(null);

    // Extraction options
    const [extractEmails, setExtractEmails] = useState(true);
    const [extractPhone, setExtractPhone] = useState(true);
    const [extractWebsite, setExtractWebsite] = useState(true);
    const [extractReviews, setExtractReviews] = useState(true);

    // History
    const [history, setHistory] = useState({ searches: [], total_searches: 0, total_leads: 0 });
    const [showHistory, setShowHistory] = useState(false);

    // Settings panel
    const [showOptions, setShowOptions] = useState(false);

    useEffect(() => { loadHistory(); }, []);

    const loadHistory = () => {
        api.get('/api/prospector/history').then(setHistory).catch(() => { });
    };

    const doSearch = async () => {
        if (!query.trim() || !location.trim()) return;
        setSearching(true);
        setMessage(null);
        setResults([]);
        setProgress('Starting scraper...');
        try {
            const res = await api.post('/api/prospector/search', {
                query, location, limit,
                extract_emails: extractEmails,
                extract_phone: extractPhone,
                extract_website: extractWebsite,
                extract_reviews: extractReviews,
            });
            setJobId(res.job_id);
            setProgress('Scraping in progress...');
            let attempts = 0;
            pollRef.current = setInterval(async () => {
                attempts++;
                try {
                    const job = await api.get(`/api/prospector/jobs/${res.job_id}/results`);
                    setResults(job.results || []);
                    setProgress(job.progress || '');
                    if (job.status === 'completed' || job.status === 'failed' || attempts > 300) {
                        clearInterval(pollRef.current);
                        pollRef.current = null;
                        setSearching(false);
                        setJobId(null);
                        loadHistory();
                        if (job.status === 'completed') {
                            setMessage({ type: 'success', text: `Found ${job.results?.length || 0} businesses!` });
                        } else if (job.status === 'failed') {
                            setMessage({ type: 'error', text: job.progress || 'Scraping failed' });
                        }
                    }
                } catch {
                    clearInterval(pollRef.current);
                    pollRef.current = null;
                    setSearching(false);
                }
            }, 2000);
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
            setSearching(false);
        }
    };

    const stopSearch = async () => {
        if (jobId) {
            try {
                await api.post(`/api/prospector/jobs/${jobId}/stop`, {});
                setProgress('Stopping...');
            } catch { }
        }
    };

    const clearResults = () => {
        setResults([]);
        setMessage(null);
        setProgress('');
    };

    const importAll = async () => {
        if (!results.length) return;
        try {
            const res = await api.post('/api/prospector/import', { results });
            setMessage({ type: 'success', text: `Imported ${res.added} leads! (${res.skipped} skipped)` });
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
    };

    const downloadCSV = () => {
        if (!results.length) return;
        const headers = ['name', 'phone', 'website', 'email', 'rating', 'reviews'];
        const csvRows = [
            headers.join(','),
            ...results.map(r => headers.map(h => `"${(r[h] || '').replace(/"/g, '""')}"`).join(','))
        ];
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `leads_${query}_${location}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const clearHistory = async () => {
        if (!confirm('Clear all search history?')) return;
        await api.delete('/api/prospector/history');
        loadHistory();
        setMessage({ type: 'success', text: 'History cleared' });
    };

    const loadFromHistory = (entry) => {
        setResults(entry.results || []);
        setShowHistory(false);
        setMessage({ type: 'success', text: `Loaded ${entry.total} results from "${entry.query} in ${entry.location}"` });
    };

    const safeHostname = (url) => {
        try { return new URL(url).hostname; } catch { return url; }
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Local Business Prospector</h1>
                    <p className="text-sm text-gray-500 mt-1">Find local businesses via Google Maps and import them as leads</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="secondary" onClick={() => setShowHistory(!showHistory)}>
                        <Clock className="w-4 h-4" /> History ({history.total_searches})
                    </Button>
                </div>
            </div>

            {/* Search Box */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
                <div className="flex gap-3 mb-4">
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Business Type</label>
                        <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                            placeholder="e.g. dentists, lawyers, plumbers, restaurants..."
                            onKeyDown={e => e.key === 'Enter' && !searching && doSearch()}
                            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Location</label>
                        <input type="text" value={location} onChange={e => setLocation(e.target.value)}
                            placeholder="e.g. Austin TX, 10001, Chicago IL..."
                            onKeyDown={e => e.key === 'Enter' && !searching && doSearch()}
                            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div className="flex items-end gap-2">
                        {!searching ? (
                            <Button onClick={doSearch}>
                                <Search className="w-4 h-4" /> Search
                            </Button>
                        ) : (
                            <Button variant="danger" onClick={stopSearch}>
                                <Square className="w-4 h-4" /> Stop
                            </Button>
                        )}
                    </div>
                </div>

                {/* Options Row */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                        <button onClick={() => setShowOptions(!showOptions)}
                            className={`flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${showOptions ? 'bg-blue-50 border-blue-200 text-blue-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                            <Settings2 className="w-3.5 h-3.5" /> Options
                        </button>
                        <span className="text-xs text-gray-400 ml-2">
                            {[extractEmails && 'Emails', extractPhone && 'Phone', extractWebsite && 'Website', extractReviews && 'Reviews'].filter(Boolean).join(' · ')}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <label className="text-xs text-gray-500">Max: <strong>{limit}</strong></label>
                        <input type="range" min="5" max="100" step="5" value={limit}
                            onChange={e => setLimit(parseInt(e.target.value))}
                            className="w-24 accent-blue-600" />
                    </div>
                </div>

                {/* Options Panel */}
                {showOptions && (
                    <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 md:grid-cols-4 gap-3">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={extractEmails} onChange={e => setExtractEmails(e.target.checked)}
                                className="rounded border-gray-300 text-blue-600" />
                            <div>
                                <span className="text-sm text-gray-700">Emails</span>
                                <p className="text-xs text-gray-400">Crawls websites (slower)</p>
                            </div>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={extractPhone} onChange={e => setExtractPhone(e.target.checked)}
                                className="rounded border-gray-300 text-blue-600" />
                            <div>
                                <span className="text-sm text-gray-700">Phone Number</span>
                                <p className="text-xs text-gray-400">From Maps listing</p>
                            </div>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={extractWebsite} onChange={e => setExtractWebsite(e.target.checked)}
                                className="rounded border-gray-300 text-blue-600" />
                            <div>
                                <span className="text-sm text-gray-700">Website URL</span>
                                <p className="text-xs text-gray-400">Business website</p>
                            </div>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={extractReviews} onChange={e => setExtractReviews(e.target.checked)}
                                className="rounded border-gray-300 text-blue-600" />
                            <div>
                                <span className="text-sm text-gray-700">Rating & Reviews</span>
                                <p className="text-xs text-gray-400">Star rating + count</p>
                            </div>
                        </label>
                    </div>
                )}
            </div>

            {/* Progress Bar */}
            {searching && (
                <div className="mb-4 px-4 py-3 rounded-lg bg-blue-50 border border-blue-100 text-blue-700 text-sm flex items-center gap-3">
                    <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
                    <span className="flex-1">{progress || 'Scraping in progress...'}</span>
                    {results.length > 0 && (
                        <span className="font-semibold bg-blue-100 px-2 py-0.5 rounded text-xs">{results.length} found</span>
                    )}
                    <button onClick={stopSearch} className="text-red-600 hover:text-red-700 text-xs font-medium flex items-center gap-1">
                        <Square className="w-3 h-3" /> Stop
                    </button>
                </div>
            )}

            {/* Messages */}
            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm flex items-center justify-between ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                    <span>{message.text}</span>
                    <button onClick={() => setMessage(null)}><X className="w-4 h-4" /></button>
                </div>
            )}

            {/* History Panel */}
            {showHistory && (
                <div className="mb-6 bg-white rounded-xl border border-gray-200 shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                        <div>
                            <h2 className="font-semibold text-gray-900">Search History</h2>
                            <p className="text-xs text-gray-500">{history.total_searches} searches · {history.total_leads} total leads scraped</p>
                        </div>
                        <div className="flex gap-2">
                            {history.total_searches > 0 && (
                                <Button variant="ghost" size="sm" onClick={clearHistory}>
                                    <Trash2 className="w-3.5 h-3.5" /> Clear All
                                </Button>
                            )}
                            <button onClick={() => setShowHistory(false)} className="text-gray-400 hover:text-gray-600">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    {history.searches.length === 0 ? (
                        <p className="px-6 py-8 text-sm text-gray-500 text-center">No search history yet</p>
                    ) : (
                        <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                            {history.searches.map((h, i) => (
                                <div key={h.id || i} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50 cursor-pointer"
                                    onClick={() => loadFromHistory(h)}>
                                    <div>
                                        <p className="text-sm font-medium text-gray-900">{h.query} in {h.location}</p>
                                        <p className="text-xs text-gray-500">{h.total} results · {h.timestamp?.split('T')[0]}</p>
                                    </div>
                                    <div className="flex gap-1">
                                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{h.total} leads</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Results Table */}
            {results.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    {/* Results Header */}
                    <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
                        <span className="text-sm font-semibold text-gray-900">{results.length} results</span>
                        <div className="flex gap-2">
                            <Button variant="secondary" size="sm" onClick={downloadCSV}>
                                <Download className="w-3.5 h-3.5" /> CSV
                            </Button>
                            <Button variant="secondary" size="sm" onClick={importAll}>
                                <Users className="w-3.5 h-3.5" /> Import to Leads
                            </Button>
                            <Button variant="ghost" size="sm" onClick={clearResults}>
                                <Trash2 className="w-3.5 h-3.5" /> Clear
                            </Button>
                        </div>
                    </div>

                    {/* Table */}
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-100 bg-gray-50/50">
                                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase w-8">#</th>
                                    <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Business</th>
                                    {extractPhone && <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>}
                                    {extractWebsite && <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Website</th>}
                                    {extractEmails && <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Email</th>}
                                    {extractReviews && <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Rating</th>}
                                    {extractReviews && <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Reviews</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {results.map((r, i) => (
                                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                                        <td className="px-4 py-2.5 text-xs text-gray-400">{i + 1}</td>
                                        <td className="px-4 py-2.5 text-sm font-medium text-gray-900">{r.name || '—'}</td>
                                        {extractPhone && (
                                            <td className="px-4 py-2.5 text-sm text-gray-600">
                                                {r.phone && r.phone !== 'N/A' ? (
                                                    <a href={`tel:${r.phone}`} className="text-blue-600 hover:underline">{r.phone}</a>
                                                ) : '—'}
                                            </td>
                                        )}
                                        {extractWebsite && (
                                            <td className="px-4 py-2.5 text-sm text-blue-600 truncate max-w-[180px]">
                                                {r.website && r.website !== 'No website on Maps' ? (
                                                    <a href={r.website} target="_blank" className="hover:underline">{safeHostname(r.website)}</a>
                                                ) : '—'}
                                            </td>
                                        )}
                                        {extractEmails && (
                                            <td className="px-4 py-2.5 text-sm text-gray-600 max-w-[200px] truncate">
                                                {r.email && r.email !== 'None found' ? (
                                                    <a href={`mailto:${r.email.split(',')[0]}`} className="text-blue-600 hover:underline">{r.email}</a>
                                                ) : <span className="text-gray-300">—</span>}
                                            </td>
                                        )}
                                        {extractReviews && (
                                            <td className="px-4 py-2.5 text-sm text-gray-600">
                                                {r.rating && r.rating !== 'N/A' ? `${r.rating} ⭐` : '—'}
                                            </td>
                                        )}
                                        {extractReviews && (
                                            <td className="px-4 py-2.5 text-sm text-gray-600">
                                                {r.reviews && r.reviews !== '0' ? r.reviews : '—'}
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Empty State */}
            {results.length === 0 && !searching && !showHistory && (
                <EmptyState icon={MapPin} title="Search for local businesses"
                    description="Enter a business type and location to find businesses, extract emails, phone numbers, and more." />
            )}
        </div>
    );
}
