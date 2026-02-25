'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    LayoutDashboard, Mail, Send, Users, Inbox, BarChart3,
    CreditCard, MapPin, LogOut, Settings, Zap
} from 'lucide-react';
import api from '@/lib/api';

const navItems = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/campaigns', label: 'Campaigns', icon: Send },
    { href: '/accounts', label: 'Email Accounts', icon: Mail },
    { href: '/leads', label: 'Leads', icon: Users },
    { href: '/leads/finder', label: 'Prospector', icon: MapPin },
    { href: '/inbox', label: 'Inbox', icon: Inbox },
    { href: '/analytics', label: 'Analytics', icon: BarChart3 },
    { href: '/billing', label: 'Billing', icon: CreditCard },
];

export default function Sidebar({ user }) {
    const pathname = usePathname();

    return (
        <aside className="fixed left-0 top-0 h-screen w-[240px] bg-white border-r border-gray-200 flex flex-col z-50">
            {/* Logo */}
            <div className="px-5 py-5 border-b border-gray-100">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
                        <Zap className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-lg font-bold text-gray-900">ColdFlow</span>
                </div>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
                {navItems.map((item) => {
                    const isActive = pathname === item.href ||
                        (item.href !== '/' && pathname.startsWith(item.href));
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                                    ? 'bg-blue-50 text-blue-700'
                                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                }`}
                        >
                            <Icon className={`w-5 h-5 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* User + Logout */}
            <div className="px-3 py-4 border-t border-gray-100">
                {user && (
                    <div className="flex items-center gap-3 px-3 py-2">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-semibold text-sm">
                            {(user.full_name || user.email || '?')[0].toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                                {user.full_name || user.email}
                            </p>
                            <p className="text-xs text-gray-500 truncate capitalize">{user.plan} plan</p>
                        </div>
                    </div>
                )}
                <button
                    onClick={() => api.logout()}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 w-full transition-colors mt-1"
                >
                    <LogOut className="w-5 h-5 text-gray-400" />
                    Logout
                </button>
            </div>
        </aside>
    );
}
