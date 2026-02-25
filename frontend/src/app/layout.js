'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import api from '@/lib/api';
import './globals.css';

const publicPages = ['/login', '/signup', '/unsubscribe'];

export default function RootLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const isPublic = publicPages.some(p => pathname.startsWith(p));

  useEffect(() => {
    if (isPublic) {
      setLoading(false);
      return;
    }

    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }

    api.getMe()
      .then(u => { setUser(u); setLoading(false); })
      .catch(() => { api.clearToken(); router.push('/login'); });
  }, [pathname]);

  if (loading && !isPublic) {
    return (
      <html lang="en">
        <body>
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        </body>
      </html>
    );
  }

  if (isPublic) {
    return (
      <html lang="en">
        <head>
          <title>ColdFlow — Cold Email SaaS</title>
          <meta name="description" content="Send cold emails at scale. Instantly.io alternative." />
        </head>
        <body>{children}</body>
      </html>
    );
  }

  return (
    <html lang="en">
      <head>
        <title>ColdFlow — Cold Email SaaS</title>
        <meta name="description" content="Send cold emails at scale." />
      </head>
      <body>
        <div className="flex min-h-screen">
          <Sidebar user={user} />
          <main className="ml-[240px] flex-1 p-6 lg:p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
