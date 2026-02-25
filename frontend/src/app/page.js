'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Send, Mail, Users, BarChart3, Plus } from 'lucide-react';
import { MetricCard, StatusBadge, Button } from '@/components/UI';
import api from '@/lib/api';

export default function DashboardPage() {
  const [overview, setOverview] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.getOverview().then(setOverview).catch(() => { });
    api.getCampaigns().then(setCampaigns).catch(() => { });
    api.health().then(setHealth).catch(() => { });
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Overview of your email outreach</p>
        </div>
        <div className="flex gap-3">
          <Link href="/accounts">
            <Button variant="secondary"><Mail className="w-4 h-4" /> Add Account</Button>
          </Link>
          <Link href="/campaigns">
            <Button><Plus className="w-4 h-4" /> New Campaign</Button>
          </Link>
        </div>
      </div>

      {/* Worker Status */}
      {health && (
        <div className="flex gap-4 mb-6">
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${health.campaign_worker ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-gray-600">Sending {health.campaign_worker ? 'Active' : 'Stopped'}</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${health.warmup_worker ? 'bg-blue-500' : 'bg-gray-400'}`} />
            <span className="text-gray-600">Warmup {health.warmup_worker ? 'Active' : 'Stopped'}</span>
          </div>
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          label="Total Sent"
          value={overview?.total_sent?.toLocaleString() || '0'}
          icon={Send} color="blue"
        />
        <MetricCard
          label="Open Rate"
          value={`${overview?.open_rate || 0}%`}
          subValue={`${overview?.total_opened || 0} opened`}
          icon={Mail} color="green"
        />
        <MetricCard
          label="Reply Rate"
          value={`${overview?.reply_rate || 0}%`}
          subValue={`${overview?.total_replied || 0} replied`}
          icon={BarChart3} color="purple"
        />
        <MetricCard
          label="Active Campaigns"
          value={overview?.active_campaigns || 0}
          subValue={`${overview?.total_leads || 0} total leads`}
          icon={Users} color="orange"
        />
      </div>

      {/* Campaign Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Campaigns</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sent</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Opened</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Replied</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Leads</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {campaigns.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-sm text-gray-500">
                    No campaigns yet. Create your first one!
                  </td>
                </tr>
              ) : (
                campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <Link href={`/campaigns/${c.id}`} className="text-sm font-medium text-gray-900 hover:text-blue-600">
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4"><StatusBadge status={c.status} /></td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.total_sent}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {c.total_opened} <span className="text-gray-400">({c.open_rate}%)</span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {c.total_replied} <span className="text-gray-400">({c.reply_rate}%)</span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.leads_count}</td>
                    <td className="px-6 py-4">
                      <Link href={`/campaigns/${c.id}`}>
                        <Button variant="ghost" size="sm">Open</Button>
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
