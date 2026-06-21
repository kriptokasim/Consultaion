import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export interface ModelCardProps {
  laneName: string;
  modelKey: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  content?: string;
  latencyMs?: number;
  tokens?: { prompt: number; completion: number };
}

export function ModelCard({ laneName, modelKey, status, content, latencyMs, tokens }: ModelCardProps) {
  return (
    <Card className={`flex flex-col h-full overflow-hidden transition-colors ${status === 'running' ? 'border-primary/50 shadow-sm' : ''} ${status === 'skipped' ? 'opacity-50' : ''}`}>
      <CardHeader className="py-3 px-4 bg-muted/30 border-b flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm font-medium capitalize">{laneName}</CardTitle>
          <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-mono">{modelKey}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {status === 'running' && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
          {latencyMs && <span className="text-xs text-muted-foreground">{Math.round(latencyMs)}ms</span>}
        </div>
      </CardHeader>
      <CardContent className="p-4 flex-1 overflow-auto bg-card min-h-[120px] max-h-[300px] text-sm relative">
        {status === 'pending' && <div className="text-muted-foreground italic absolute inset-0 flex items-center justify-center">Waiting...</div>}
        {status === 'skipped' && <div className="text-muted-foreground italic absolute inset-0 flex items-center justify-center">Skipped</div>}
        {status === 'failed' && <div className="text-destructive font-medium">Lane execution failed</div>}
        {(status === 'running' || status === 'completed') && (
          <div className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
            {content || <span className="text-muted-foreground italic">Thinking...</span>}
          </div>
        )}
      </CardContent>
      {tokens && (
        <div className="bg-muted/10 border-t px-4 py-2 flex justify-between text-[10px] text-muted-foreground font-mono">
          <span>In: {tokens.prompt}</span>
          <span>Out: {tokens.completion}</span>
        </div>
      )}
    </Card>
  );
}

export function ModelCardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {children}
    </div>
  );
}
