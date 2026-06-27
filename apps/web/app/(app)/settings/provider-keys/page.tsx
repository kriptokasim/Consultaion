"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";
import { API_ORIGIN } from "@/lib/config/runtime";
import { ShieldCheck, Plus, Trash2, Key, AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";

interface ProviderKey {
  id: string;
  provider: string;
  masked_key: string;
  created_at: string;
  updated_at: string;
}

const PROVIDERS = [
  { id: "openai", name: "OpenAI", placeholder: "sk-proj-...", docUrl: "https://platform.openai.com/api-keys" },
  { id: "anthropic", name: "Anthropic", placeholder: "sk-ant-...", docUrl: "https://console.anthropic.com/settings/keys" },
  { id: "gemini", name: "Google Gemini", placeholder: "AIzaSy...", docUrl: "https://aistudio.google.com/app/apikey" },
  { id: "openrouter", name: "OpenRouter", placeholder: "sk-or-...", docUrl: "https://openrouter.ai/keys" }
];

export default function ProviderKeysPage() {
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [newKey, setNewKey] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState<string | null>(null);

  const apiBase = API_ORIGIN;

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/provider-keys`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setKeys(data);
      }
    } catch (err) {
      console.error("Failed to fetch provider keys:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleAddOrUpdate = async (provider: string) => {
    if (!newKey.trim()) return;

    setIsValidating(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    trackEvent("byok_validation_started", { provider });

    try {
      const res = await fetch(`${apiBase}/provider-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, key: newKey.trim() }),
        credentials: "include"
      });

      const data = await res.json();

      if (!res.ok) {
        trackEvent("byok_validation_failed", { provider, error: data.message });
        setErrorMsg(data.message || "Key validation failed. Make sure the API key is valid and has proper permissions.");
        return;
      }

      trackEvent("byok_validation_succeeded", { provider });
      trackEvent("byok_key_saved", { provider });

      setSuccessMsg(`Successfully validated and saved key for ${provider.toUpperCase()}`);
      setNewKey("");
      setEditingProvider(null);
      fetchKeys();
    } catch (err) {
      trackEvent("byok_validation_failed", { provider, error: "Network/HTTP error" });
      setErrorMsg("Network error trying to contact key validation services. Please try again.");
    } finally {
      setIsValidating(false);
    }
  };

  const handleDelete = async (provider: string) => {
    if (!confirm(`Are you sure you want to delete your key for ${provider.toUpperCase()}? This will revert back to platform hosted credits.`)) {
      return;
    }

    try {
      const res = await fetch(`${apiBase}/provider-keys/${provider}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (res.ok) {
        setSuccessMsg(`Successfully deleted key for ${provider.toUpperCase()}`);
        fetchKeys();
      } else {
        setErrorMsg("Failed to delete provider key.");
      }
    } catch (err) {
      setErrorMsg("Network error. Could not delete provider key.");
    }
  };

  const handleTest = async (provider: string) => {
    setIsTesting(provider);
    setErrorMsg(null);
    setSuccessMsg(null);
    
    try {
      const res = await fetch(`${apiBase}/ops/probe/${provider}`, {
        method: "POST",
        credentials: "include"
      });
      
      const data = await res.json();
      
      if (res.ok && data.success) {
        setSuccessMsg(`Test successful: ${provider.toUpperCase()} key is active and responding.`);
        trackEvent("byok_test_succeeded", { provider });
      } else {
        setErrorMsg(`Test failed for ${provider.toUpperCase()}: ${data.message || 'Unknown error'}`);
        trackEvent("byok_test_failed", { provider, error: data.message });
      }
    } catch (err) {
      setErrorMsg(`Network error while testing ${provider.toUpperCase()} key.`);
      trackEvent("byok_test_failed", { provider, error: "Network error" });
    } finally {
      setIsTesting(null);
    }
  };

  return (
    <main className="container mx-auto max-w-4xl p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-amber-900 dark:text-amber-50">
          Bring Your Own Key (BYOK)
        </h1>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400 max-w-xl leading-relaxed">
          Provide your own LLM API keys to run custom debates. When a provider key is set, Consultaion will route queries through your own billing account. Otherwise, runs use shared platform credits.
        </p>
      </div>

      {successMsg && (
        <div className="mb-6 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-900/30 p-4 text-emerald-800 dark:text-emerald-300 flex items-center gap-2 text-sm font-semibold">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="mb-6 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200/50 dark:border-rose-900/30 p-4 text-rose-800 dark:text-rose-300 flex items-start gap-2.5 text-sm leading-relaxed">
          <AlertCircle className="h-5 w-5 text-rose-500 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold block mb-0.5">Validation Error</span>
            {errorMsg}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 text-amber-600 animate-spin" />
        </div>
      ) : (
        <div className="space-y-6">
          {PROVIDERS.map((prov) => {
            const keyRecord = keys.find((k) => k.provider === prov.id);
            const isEditing = editingProvider === prov.id;

            return (
              <div
                key={prov.id}
                className="card-elevated border border-slate-200 dark:border-slate-800/80 p-6 flex flex-col justify-between md:flex-row md:items-center gap-6"
              >
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                      {prov.name}
                    </h3>
                    {keyRecord ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/40 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:text-amber-300 border border-amber-200/50 dark:border-amber-900/30">
                        <ShieldCheck className="h-3 w-3 text-amber-600 dark:text-amber-400" />
                        Configured
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-semibold text-slate-500">
                        Not Set
                      </span>
                    )}
                  </div>
                  
                  {keyRecord ? (
                    <div className="flex items-center gap-1.5 text-sm font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/40 px-2.5 py-1.5 rounded-lg border border-slate-200/50 dark:border-slate-800/40 w-fit">
                      <Key className="h-3.5 w-3.5 text-slate-400" />
                      {keyRecord.masked_key}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Shared platform credits will be used for this provider.
                    </p>
                  )}
                  
                  <a
                    href={prov.docUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-amber-700 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300 block underline"
                  >
                    Get {prov.name} API Key &rarr;
                  </a>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {isEditing ? (
                    <div className="flex flex-col gap-2 w-full sm:w-auto">
                      <div className="flex items-center gap-2">
                        <input
                          type="password"
                          value={newKey}
                          onChange={(e) => setNewKey(e.target.value)}
                          placeholder={prov.placeholder}
                          className="rounded-lg border border-slate-200 bg-white py-1.5 px-3 text-sm text-slate-900 outline-none transition focus:border-amber-500 dark:border-slate-800 dark:bg-slate-950 dark:text-white w-48 sm:w-60"
                        />
                        <Button
                          disabled={isValidating}
                          onClick={() => handleAddOrUpdate(prov.id)}
                          className="bg-amber-600 hover:bg-amber-700 text-white py-1.5 px-4 rounded-lg font-semibold text-sm shadow-sm"
                        >
                          {isValidating ? "Validating..." : "Save"}
                        </Button>
                      </div>
                      <button
                        onClick={() => {
                          setEditingProvider(null);
                          setNewKey("");
                        }}
                        className="text-xs text-left font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditingProvider(prov.id);
                          setNewKey("");
                        }}
                        className="text-sm font-semibold flex items-center gap-1.5"
                      >
                        <Plus className="h-4 w-4" />
                        {keyRecord ? "Update Key" : "Add Key"}
                      </Button>
                      {keyRecord && (
                        <div className="flex items-center gap-2">
                          <Button
                            variant="secondary"
                            onClick={() => handleTest(prov.id)}
                            disabled={isTesting === prov.id}
                            className="text-sm font-semibold h-10 px-3 flex items-center gap-2"
                          >
                            <RefreshCw className={`h-4 w-4 ${isTesting === prov.id ? 'animate-spin' : ''}`} />
                            {isTesting === prov.id ? "Testing..." : "Test Key"}
                          </Button>
                          <button
                            onClick={() => handleDelete(prov.id)}
                            className="p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-rose-600 transition dark:border-slate-800 dark:hover:bg-slate-850"
                            title="Remove Key"
                          >
                            <Trash2 className="h-4.5 w-4.5" />
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
