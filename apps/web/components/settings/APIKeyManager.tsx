'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Plus, Trash2, Copy, Check, AlertCircle, Key } from 'lucide-react';
import { apiRequest } from '@/lib/apiClient';

type APIKey = {
    id: string;
    name: string;
    prefix: string;
    created_at: string;
    last_used_at: string | null;
    revoked: boolean;
    team_id: string | null;
};

type APIKeyCreateResponse = {
    id: string;
    name: string;
    prefix: string;
    created_at: string;
    secret: string;
};

export default function APIKeyManager() {
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newKeyName, setNewKeyName] = useState('');
    const [createdKey, setCreatedKey] = useState<APIKeyCreateResponse | null>(null);
    const [copiedSecret, setCopiedSecret] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const queryClient = useQueryClient();

    // Fetch API keys
    const { data: keys, isLoading } = useQuery<APIKey[]>({
        queryKey: ['api-keys'],
        queryFn: async () => {
            const response = await apiRequest<APIKey[]>({ path: '/keys', method: 'GET' });
            return response;
        },
    });

    // Create API key mutation
    const createKeyMutation = useMutation({
        mutationFn: async (name: string) => {
            return apiRequest<APIKeyCreateResponse>({
                path: '/keys',
                method: 'POST',
                body: { name },
            });
        },
        onSuccess: (data) => {
            setCreatedKey(data);
            setShowCreateModal(false);
            setNewKeyName('');
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
        },
        onError: (err: any) => {
            setError(err.message || 'Failed to create API key');
        },
    });

    // Revoke API key mutation
    const revokeKeyMutation = useMutation({
        mutationFn: async (keyId: string) => {
            return apiRequest({ path: `/keys/${keyId}`, method: 'DELETE' });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
        },
    });

    const handleCreate = () => {
        if (!newKeyName.trim()) {
            setError('Please enter a key name');
            return;
        }
        setError(null);
        createKeyMutation.mutate(newKeyName.trim());
    };

    const handleCopySecret = async () => {
        if (createdKey) {
            await navigator.clipboard.writeText(createdKey.secret);
            setCopiedSecret(true);
            setTimeout(() => setCopiedSecret(false), 2000);
        }
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return 'Never';
        return new Date(dateString).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    if (isLoading) {
        return <div className="text-center py-8">Loading API keys...</div>;
    }

    return (
        <div className="space-y-6">
            {/* Header with Create Button */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Key className="h-5 w-5 text-amber-600" />
                    <h2 className="text-xl font-semibold text-amber-900 dark:text-amber-50">
                        Your API Keys
                    </h2>
                </div>
                <Button
                    onClick={() => setShowCreateModal(true)}
                    className="inline-flex items-center gap-2"
                >
                    <Plus className="h-4 w-4" />
                    Create New Key
                </Button>
            </div>

            {/* Documentation Link */}
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950">
                <p className="text-sm text-blue-900 dark:text-blue-100">
                    📚 Learn how to use API keys in your applications:{' '}
                    <a
                        href="/docs/api-access"
                        className="font-semibold underline hover:text-blue-700"
                    >
                        API Access Documentation
                    </a>
                </p>
            </div>

            {/* API Keys List */}
            <div className="rounded-lg border border-stone-200 dark:border-stone-800">
                {!keys || keys.length === 0 ? (
                    <div className="p-8 text-center text-stone-500">
                        <Key className="mx-auto h-12 w-12 text-stone-300 mb-3" />
                        <p>No API keys yet. Create one to get started.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-stone-200 dark:divide-stone-800">
                        {keys.map((key) => (
                            <div key={key.id} className="p-4 hover:bg-stone-50 dark:hover:bg-stone-900">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <h3 className="font-semibold text-amber-900 dark:text-amber-50">
                                                {key.name}
                                            </h3>
                                            {key.revoked && (
                                                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800 dark:bg-red-900 dark:text-red-100">
                                                    Revoked
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1 font-mono text-sm text-stone-600 dark:text-stone-400">
                                            {key.prefix}•••••••
                                        </p>
                                        <div className="mt-2 flex gap-4 text-xs text-stone-500">
                                            <span>Created: {formatDate(key.created_at)}</span>
                                            <span>Last used: {formatDate(key.last_used_at)}</span>
                                        </div>
                                    </div>
                                    {!key.revoked && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => {
                                                if (confirm(`Revoke "${key.name}"? This cannot be undone.`)) {
                                                    revokeKeyMutation.mutate(key.id);
                                                }
                                            }}
                                            className="text-red-600 hover:text-red-700"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-stone-900">
                        <h3 className="text-lg font-semibold text-amber-900 dark:text-amber-50">
                            Create New API Key
                        </h3>
                        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
                            Give your API key a descriptive name to help you remember its purpose.
                        </p>

                        {error && (
                            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                                <AlertCircle className="inline h-4 w-4 mr-2" />
                                {error}
                            </div>
                        )}

                        <div className="mt-4">
                            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                                Key Name
                            </label>
                            <input
                                type="text"
                                value={newKeyName}
                                onChange={(e) => setNewKeyName(e.target.value)}
                                placeholder="e.g., CI Pipeline, Local Development"
                                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-stone-700 dark:bg-stone-800"
                                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                            />
                        </div>

                        <div className="mt-6 flex gap-3">
                            <Button
                                onClick={handleCreate}
                                disabled={createKeyMutation.isPending}
                                className="flex-1"
                            >
                                {createKeyMutation.isPending ? 'Creating...' : 'Create Key'}
                            </Button>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setShowCreateModal(false);
                                    setNewKeyName('');
                                    setError(null);
                                }}
                            >
                                Cancel
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {/* Secret Display Modal */}
            {createdKey && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-stone-900">
                        <h3 className="text-lg font-semibold text-amber-900 dark:text-amber-50">
                            API Key Created Successfully
                        </h3>

                        <div className="mt-4 rounded-lg border-2 border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950">
                            <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                                ⚠️ Copy this secret now - it won't be shown again!
                            </p>
                        </div>

                        <div className="mt-4">
                            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                                API Key Secret
                            </label>
                            <div className="mt-1 flex gap-2">
                                <input
                                    type="text"
                                    value={createdKey.secret}
                                    readOnly
                                    className="flex-1 rounded-lg border border-stone-300 bg-stone-50 px-3 py-2 font-mono text-sm dark:border-stone-700 dark:bg-stone-800"
                                />
                                <Button onClick={handleCopySecret} variant="outline">
                                    {copiedSecret ? (
                                        <>
                                            <Check className="h-4 w-4 mr-2" />
                                            Copied!
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="h-4 w-4 mr-2" />
                                            Copy
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>

                        <div className="mt-6">
                            <Button
                                onClick={() => {
                                    setCreatedKey(null);
                                    setCopiedSecret(false);
                                }}
                                className="w-full"
                            >
                                Done
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
