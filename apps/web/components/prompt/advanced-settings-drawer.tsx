'use client'

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import PanelConfigurator from '@/components/parliament/PanelConfigurator'
import type { PanelSeatConfig } from '@/lib/panels'

interface AdvancedSettingsDrawerProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    panelConfig: PanelSeatConfig[]
    onPanelConfigChange: (config: PanelSeatConfig[]) => void
    gatewayPolicy?: string
    onGatewayPolicyChange?: (policy: string) => void
}

/**
 * AdvancedSettingsDrawer - Side drawer for model/debate configuration
 * 
 * Moves model selection, delegate configuration, and other advanced settings
 * out of the main prompt area into a clean side panel.
 */
export function AdvancedSettingsDrawer({
    open,
    onOpenChange,
    panelConfig,
    onPanelConfigChange,
    gatewayPolicy = 'auto',
    onGatewayPolicyChange,
}: AdvancedSettingsDrawerProps) {
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
                <SheetHeader>
                    <SheetTitle>Advanced settings</SheetTitle>
                    <SheetDescription>
                        Configure models, delegates, and debate parameters
                    </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-6">
                    <div className="rounded-3xl border border-amber-200/70 bg-white/80 p-4 shadow-sm dark:border-amber-900/40 dark:bg-stone-950/40">
                        <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-600">Model Gateway Mode</label>
                            <select
                                className="w-full rounded-2xl border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900 dark:border-amber-800 dark:bg-stone-900 dark:text-stone-50"
                                value={gatewayPolicy}
                                onChange={(e) => onGatewayPolicyChange?.(e.target.value)}
                            >
                                <option value="auto">Auto (Smart Router)</option>
                                <option value="direct">Direct Providers (No Gateway)</option>
                                <option value="fallback">High Availability (Fallback Chain)</option>
                            </select>
                            <p className="text-xs text-muted-foreground">
                                Controls the backend model routing policy for handling request limits and provider health.
                            </p>
                        </div>
                    </div>

                    <PanelConfigurator seats={panelConfig} onChange={onPanelConfigChange} />
                </div>
            </SheetContent>
        </Sheet>
    )
}
