'use client';

import { useEffect, useState } from 'react';
import { Mail, Plus, Wifi, Shield, Flame, Trash2, Send, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Button, StatusBadge, Modal, Input, EmptyState } from '@/components/UI';
import api from '@/lib/api';

const PROVIDERS = {
    gmail: { label: 'Gmail', smtp: 'smtp.gmail.com', port: 587, imap: 'imap.gmail.com' },
    outlook: { label: 'Outlook / Office 365', smtp: 'smtp.office365.com', port: 587, imap: 'outlook.office365.com' },
    custom: { label: 'Custom SMTP', smtp: '', port: 587, imap: '' },
};

export default function AccountsPage() {
    const [accounts, setAccounts] = useState([]);
    const [showAdd, setShowAdd] = useState(false);
    const [form, setForm] = useState({ email: '', from_name: '', provider: 'gmail', smtp_host: 'smtp.gmail.com', smtp_port: 587, smtp_username: '', smtp_password: '', daily_limit: 40, signature_html: '' });
    const [loading, setLoading] = useState({});
    const [message, setMessage] = useState(null);

    const load = () => api.getAccounts().then(setAccounts).catch(() => { });
    useEffect(() => { load(); }, []);

    const setProvider = (p) => {
        const config = PROVIDERS[p];
        setForm(f => ({ ...f, provider: p, smtp_host: config.smtp, smtp_port: config.port }));
    };

    const addAccount = async () => {
        try {
            await api.createAccount({ ...form, smtp_username: form.smtp_username || form.email });
            setShowAdd(false);
            setForm({ email: '', from_name: '', provider: 'gmail', smtp_host: 'smtp.gmail.com', smtp_port: 587, smtp_username: '', smtp_password: '', daily_limit: 40, signature_html: '' });
            load();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
    };

    const action = async (id, fn, label) => {
        setLoading(l => ({ ...l, [id + label]: true }));
        try {
            const res = await fn(id);
            setMessage({ type: 'success', text: res.message || `${label} successful` });
            load();
        } catch (err) {
            setMessage({ type: 'error', text: err.message });
        }
        setLoading(l => ({ ...l, [id + label]: false }));
    };

    const DnsIcon = ({ ok }) => ok === true ? <CheckCircle className="w-4 h-4 text-green-500" /> : ok === false ? <XCircle className="w-4 h-4 text-red-500" /> : <AlertCircle className="w-4 h-4 text-gray-300" />;

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Email Accounts</h1>
                    <p className="text-sm text-gray-500 mt-1">Connect your email accounts for sending campaigns</p>
                </div>
                <Button onClick={() => setShowAdd(true)}><Plus className="w-4 h-4" /> Add Account</Button>
            </div>

            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="float-right">&times;</button>
                </div>
            )}

            {accounts.length === 0 ? (
                <EmptyState icon={Mail} title="No email accounts connected" description="Add your Gmail, Outlook, or custom SMTP account to start sending."
                    action={<Button onClick={() => setShowAdd(true)}>Add Account</Button>} />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {accounts.map((acc) => (
                        <div key={acc.id} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                            <div className="flex items-start justify-between mb-3">
                                <div>
                                    <h3 className="font-semibold text-gray-900">{acc.email}</h3>
                                    <p className="text-sm text-gray-500">{acc.from_name || 'No name set'}</p>
                                </div>
                                <StatusBadge status={acc.status} />
                            </div>

                            {/* DNS Health */}
                            <div className="flex items-center gap-4 mb-3 text-xs">
                                <div className="flex items-center gap-1"><DnsIcon ok={acc.dns_spf_ok} /> SPF</div>
                                <div className="flex items-center gap-1"><DnsIcon ok={acc.dns_dkim_ok} /> DKIM</div>
                                <div className="flex items-center gap-1"><DnsIcon ok={acc.dns_dmarc_ok} /> DMARC</div>
                            </div>

                            {/* Warmup + Sends */}
                            <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
                                <span>{acc.sends_today}/{acc.daily_limit} sent today</span>
                                {acc.warmup_enabled && (
                                    <span className="flex items-center gap-1 text-orange-600">
                                        <Flame className="w-3.5 h-3.5" /> Warmup {Math.round(acc.warmup_score)}%
                                    </span>
                                )}
                            </div>

                            {acc.last_error && (
                                <div className="bg-red-50 text-red-600 text-xs px-3 py-2 rounded-lg mb-3 truncate">{acc.last_error}</div>
                            )}

                            {/* Actions */}
                            <div className="flex flex-wrap gap-2">
                                <Button size="sm" variant="secondary" onClick={() => action(acc.id, api.testSmtp.bind(api), 'test')}
                                    disabled={loading[acc.id + 'test']}>
                                    <Wifi className="w-3.5 h-3.5" /> Test
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => action(acc.id, api.sendTestEmail.bind(api), 'send')}
                                    disabled={loading[acc.id + 'send']}>
                                    <Send className="w-3.5 h-3.5" /> Send Test
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => action(acc.id, api.checkDns.bind(api), 'dns')}
                                    disabled={loading[acc.id + 'dns']}>
                                    <Shield className="w-3.5 h-3.5" /> DNS Check
                                </Button>
                                <Button size="sm" variant={acc.warmup_enabled ? 'success' : 'secondary'}
                                    onClick={() => action(acc.id, api.toggleWarmup.bind(api), 'warmup')}>
                                    <Flame className="w-3.5 h-3.5" /> {acc.warmup_enabled ? 'Warmup On' : 'Warmup Off'}
                                </Button>
                                <Button size="sm" variant="danger" onClick={() => { api.deleteAccount(acc.id); load(); }}>
                                    <Trash2 className="w-3.5 h-3.5" />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Add Account Modal */}
            <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add Email Account">
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Provider</label>
                        <div className="flex gap-2">
                            {Object.entries(PROVIDERS).map(([key, { label }]) => (
                                <button key={key} onClick={() => setProvider(key)}
                                    className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${form.provider === key ? 'bg-blue-50 border-blue-300 text-blue-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
                                    {label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {form.provider === 'gmail' && (
                        <div className="bg-blue-50 text-blue-700 text-xs px-3 py-2 rounded-lg">
                            💡 For Gmail, use an <a href="https://myaccount.google.com/apppasswords" target="_blank" className="underline">App Password</a>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                        <Input label="Email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="you@company.com" />
                        <Input label="From Name" value={form.from_name} onChange={e => setForm(f => ({ ...f, from_name: e.target.value }))} placeholder="John Smith" />
                    </div>

                    <Input label="Password / App Password" type="password" value={form.smtp_password}
                        onChange={e => setForm(f => ({ ...f, smtp_password: e.target.value }))} />

                    {form.provider === 'custom' && (
                        <div className="grid grid-cols-2 gap-3">
                            <Input label="SMTP Host" value={form.smtp_host} onChange={e => setForm(f => ({ ...f, smtp_host: e.target.value }))} />
                            <Input label="SMTP Port" type="number" value={form.smtp_port} onChange={e => setForm(f => ({ ...f, smtp_port: parseInt(e.target.value) }))} />
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Daily Limit: {form.daily_limit}</label>
                        <input type="range" min="5" max="100" step="5" value={form.daily_limit}
                            onChange={e => setForm(f => ({ ...f, daily_limit: parseInt(e.target.value) }))}
                            className="w-full accent-blue-600" />
                    </div>

                    <Button className="w-full" onClick={addAccount}>Add Account</Button>
                </div>
            </Modal>
        </div>
    );
}
