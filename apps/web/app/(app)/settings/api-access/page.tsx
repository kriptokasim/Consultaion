import { Suspense } from 'react';
import APIKeyManager from '@/components/settings/APIKeyManager';

export default function APIAccessPage() {
    return (
        <main className="container mx-auto max-w-4xl p-6">
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-amber-900 dark:text-amber-50">
                    API Access
                </h1>
                <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
                    Manage API keys for programmatic access to your account.
                </p>
            </div>

            <Suspense fallback={<div>Loading...</div>}>
                <APIKeyManager />
            </Suspense>
        </main>
    );
}
