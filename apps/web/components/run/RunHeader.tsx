import React from 'react';
import { Badge } from '@/components/ui/badge';

export interface RunHeaderProps {
  title: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  mode: string;
  badges?: React.ReactNode[];
  actions?: React.ReactNode;
}

export function RunHeader({ title, status, mode, badges, actions }: RunHeaderProps) {
  const statusColors = {
    running: 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20',
    completed: 'bg-green-500/10 text-green-500 hover:bg-green-500/20',
    failed: 'bg-red-500/10 text-red-500 hover:bg-red-500/20',
    pending: 'bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20',
  };

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        <Badge variant="secondary" className="font-mono text-xs capitalize">
          {mode}
        </Badge>
        <Badge variant="outline" className={`capitalize ${statusColors[status]}`}>
          {status}
        </Badge>
        {badges && (
          <div className="flex items-center gap-2 border-l pl-3 ml-1">
            {badges.map((badge, idx) => (
              <React.Fragment key={idx}>{badge}</React.Fragment>
            ))}
          </div>
        )}
      </div>
      
      {actions && (
        <div className="flex items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}
