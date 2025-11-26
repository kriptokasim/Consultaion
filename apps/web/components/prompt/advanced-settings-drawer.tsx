'use client'

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import PanelConfigurator from '@/components/parliament/PanelConfigurator'
import type { PanelSeatConfig } from '@/lib/panels'

interface AdvancedSettingsDrawerProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    panelConfig: PanelSeatConfig[]
    onPanelConfigChange: (config: PanelSeatConfig[]) => void
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

                <div className="mt-6">
                    <PanelConfigurator seats={panelConfig} onChange={onPanelConfigChange} />
                </div>
            </SheetContent>
        </Sheet>
    )
}
