'use client';

import { useEffect, useState } from 'react';
import { CreditCard, Check, ExternalLink } from 'lucide-react';
import { Button, MetricCard } from '@/components/UI';
import api from '@/lib/api';

export default function BillingPage() {
    const [plans, setPlans] = useState([]);
    const [subscription, setSubscription] = useState(null);
    const [loading, setLoading] = useState('');

    useEffect(() => {
        api.getPlans().then(d => setPlans(d.plans || [])).catch(() => { });
        api.getSubscription().then(setSubscription).catch(() => { });
    }, []);

    const checkout = async (planId) => {
        setLoading(planId);
        try {
            const res = await api.checkout(planId);
            if (res.url) window.location.href = res.url;
        } catch (err) {
            alert(err.message);
        }
        setLoading('');
    };

    const openPortal = async () => {
        try {
            const res = await api.billingPortal();
            if (res.url) window.location.href = res.url;
        } catch (err) {
            alert(err.message);
        }
    };

    const currentPlan = subscription?.plan || 'free';

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
                    <p className="text-sm text-gray-500 mt-1">Manage your subscription</p>
                </div>
                {currentPlan !== 'free' && (
                    <Button variant="secondary" onClick={openPortal}><ExternalLink className="w-4 h-4" /> Manage Billing</Button>
                )}
            </div>

            {/* Current Plan */}
            {subscription && (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 mb-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-lg font-semibold text-blue-900 capitalize">{currentPlan} Plan</h3>
                            <p className="text-sm text-blue-700 capitalize">Status: {subscription.plan_status}</p>
                        </div>
                        <div className="text-right text-sm text-blue-700">
                            <p>{subscription.limits?.campaigns || 0} campaigns</p>
                            <p>{subscription.limits?.accounts || 0} accounts</p>
                            <p>{subscription.limits?.leads?.toLocaleString() || 0} leads</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Plan Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {plans.map(plan => {
                    const isCurrent = currentPlan === plan.id;
                    const isPaid = plan.price > 0;

                    return (
                        <div key={plan.id}
                            className={`bg-white rounded-xl border-2 shadow-sm p-6 transition-shadow hover:shadow-md ${isCurrent ? 'border-blue-500' : 'border-gray-200'}`}>
                            {isCurrent && (
                                <span className="inline-block bg-blue-100 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full mb-3">Current Plan</span>
                            )}
                            <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                            <div className="mt-2 mb-4">
                                {plan.price === 0 ? (
                                    <span className="text-3xl font-bold text-gray-900">Free</span>
                                ) : (
                                    <div>
                                        <span className="text-3xl font-bold text-gray-900">${plan.price}</span>
                                        <span className="text-gray-500 text-sm">/mo</span>
                                    </div>
                                )}
                            </div>

                            <ul className="space-y-2 mb-6">
                                {plan.features?.map((f, i) => (
                                    <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                                        <Check className="w-4 h-4 text-green-500 flex-shrink-0" /> {f}
                                    </li>
                                ))}
                            </ul>

                            {isCurrent ? (
                                <Button variant="secondary" className="w-full" disabled>Current Plan</Button>
                            ) : isPaid ? (
                                <Button className="w-full" onClick={() => checkout(plan.id)} disabled={loading === plan.id}>
                                    {loading === plan.id ? 'Redirecting...' : 'Upgrade'}
                                </Button>
                            ) : (
                                <Button variant="secondary" className="w-full" disabled>Free</Button>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Usage */}
            {subscription?.limits && (
                <div className="mt-8">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <MetricCard label="Campaigns" value={`—/${subscription.limits.campaigns}`} icon={CreditCard} color="blue" />
                        <MetricCard label="Email Accounts" value={`—/${subscription.limits.accounts}`} icon={CreditCard} color="green" />
                        <MetricCard label="Daily Send Limit" value={subscription.limits.daily_sends?.toLocaleString() || '—'} icon={CreditCard} color="purple" />
                    </div>
                </div>
            )}
        </div>
    );
}
