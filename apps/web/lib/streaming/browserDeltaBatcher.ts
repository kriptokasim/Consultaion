'use client'

import type { ModelResponseDeltaPayload } from "@/lib/streaming/types"

export type DeltaEnvelope = {
  responseId: string
  attemptId?: string
  generation?: number
  text: string
  sequence: number
}

export type FlushHandler = (envelopes: DeltaEnvelope[]) => void

export class BrowserDeltaBatcher {
  private pending: Map<string, DeltaEnvelope> = new Map()
  private frameId: number | null = null
  private flushHandler: FlushHandler
  private cancelled = false

  constructor(flushHandler: FlushHandler) {
    this.flushHandler = flushHandler
  }

  add(delta: ModelResponseDeltaPayload): void {
    if (this.cancelled) return
    const key = delta.response_id
    const existing = this.pending.get(key)
    if (existing) {
      existing.text = delta.text
      existing.sequence = delta.delta_sequence
    } else {
      this.pending.set(key, {
        responseId: delta.response_id,
        attemptId: delta.run_attempt?.toString(),
        generation: delta.retry_generation,
        text: delta.text,
        sequence: delta.delta_sequence,
      })
    }
    if (this.frameId === null) {
      this.frameId = requestAnimationFrame(() => this.flush())
    }
  }

  flush(): void {
    if (this.cancelled || this.pending.size === 0) return
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId)
      this.frameId = null
    }
    const envelopes = Array.from(this.pending.values())
    this.pending.clear()
    this.flushHandler(envelopes)
  }

  cancel(): void {
    this.cancelled = true
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId)
      this.frameId = null
    }
    this.pending.clear()
  }
}
