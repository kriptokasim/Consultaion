"use client";

import { useId } from "react";
import { useI18n } from "@/lib/i18n/client";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";

export interface PanelPickerModel {
  id: string;
  name: string;
  provider: string;
}

export interface PanelPickerProps {
  models: PanelPickerModel[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  /** Minimum panel size for the active mode (Oracle uses 1; everything else uses 2 per DESIGN-SPEC). */
  minModels: number;
  maxModels: number;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

/**
 * Canonical New UX PanelPicker — one data model, rendered inline here and
 * inside PanelPickerSheet for the mobile/dense presentation. Must be fed
 * the real model registry (see lib/api/hooks/useModelRegistry.ts); do not
 * pass hardcoded model lists into this component.
 */
export function PanelPicker({
  models,
  selectedIds,
  onToggle,
  minModels,
  maxModels,
  isLoading = false,
  error = null,
  className = "",
}: PanelPickerProps) {
  const { t } = useI18n();
  const headingId = useId();

  return (
    <div className={`new-ux__panel ${className}`.trim()}>
      <div className="new-ux__panel-head">
        <span id={headingId} className="new-ux__meta">{t("panelPicker.title")}</span>
        <span className="new-ux__meta">{selectedIds.length} / {maxModels}</span>
      </div>

      {isLoading && (
        <p className="new-ux__model-copy" role="status" aria-live="polite">
          {t("panelPicker.loading")}
        </p>
      )}

      {!isLoading && error && (
        <p className="new-ux__model-copy" role="alert">
          {t("panelPicker.error")}
        </p>
      )}

      {!isLoading && !error && models.length === 0 && (
        <p className="new-ux__model-copy">{t("panelPicker.empty")}</p>
      )}

      {!isLoading && !error && models.length > 0 && (
        <div className="new-ux__panel-list" role="group" aria-labelledby={headingId}>
          {models.map((model) => {
            const selected = selectedIds.includes(model.id);
            return (
              <button
                key={model.id}
                type="button"
                className="new-ux__panel-row"
                data-selected={selected}
                onClick={() => onToggle(model.id)}
                aria-pressed={selected}
              >
                <span>{model.name}</span>
                <span>{selected ? model.provider : t("panelPicker.notSelected")}</span>
              </button>
            );
          })}
        </div>
      )}

      {minModels > 1 && (
        <p className="new-ux__footer-note">{t("panelPicker.minimum", { count: minModels })}</p>
      )}
    </div>
  );
}

export interface PanelPickerSheetProps extends PanelPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Sheet presentation of the same PanelPicker data model, for mobile/dense
 * layouts. Built on the existing Radix-backed Sheet (components/ui/sheet.tsx),
 * which already provides role=dialog, aria-modal, focus trap and its own
 * portal/stacking context — do not hand-roll a second drawer.
 */
export function PanelPickerSheet({ open, onOpenChange, ...pickerProps }: PanelPickerSheetProps) {
  const { t } = useI18n();
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="new-ux new-ux-panel-sheet" data-surface="ink">
        <SheetHeader>
          <SheetTitle>{t("panelPicker.title")}</SheetTitle>
          <SheetDescription>{t("panelPicker.sheetDescription")}</SheetDescription>
        </SheetHeader>
        <div className="new-ux-panel-sheet__body">
          <PanelPicker {...pickerProps} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
