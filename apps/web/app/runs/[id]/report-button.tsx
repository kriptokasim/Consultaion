'use client'

import { useState } from 'react'

export function ReportButton({ debateId, apiBase }: { debateId: string; apiBase: string }) {
  const [status, setStatus] = useState<string | null>(null)
  const [downloadUri, setDownloadUri] = useState<string | null>(null)

  const runExport = async () => {
    setStatus('Generating report…')
    setDownloadUri(null)
    try {
      const res = await fetch(`${apiBase}/debates/${debateId}/export`, { method: 'POST' })
      if (!res.ok) {
        throw new Error('Export failed')
      }
      const data = await res.json()
      setDownloadUri(`${apiBase}${data.uri}`)
      setStatus('Report ready')
    } catch (err) {
      console.error(err)
      setStatus('Failed to generate report')
    }
  }

  return (
    <div className="space-y-2">
      <button onClick={runExport} className="px-4 py-2 bg-blue-600 text-white rounded">
        Download report
      </button>
      {status ? <p className="text-sm text-slate-600">{status}</p> : null}
      {downloadUri ? (
        <a href={downloadUri} target="_blank" rel="noreferrer" className="text-sm text-blue-600 underline">
          Open report file
        </a>
      ) : null}
    </div>
  )
}
